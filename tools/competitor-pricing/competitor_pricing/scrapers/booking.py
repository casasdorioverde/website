"""Best-effort Booking.com property page scraper.

Booking.com renders prices client-side and changes its markup often, so this
module deliberately never raises on a missing field: every extraction is
wrapped so a broken selector degrades to "unknown" (and, for rooms/pool,
falls back to the manual value from config.yaml) instead of crashing the
whole report run. Expect to have to touch the selectors below occasionally.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Optional
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from playwright.sync_api import sync_playwright

from ..config import CompetitorConfig, WindowConfig
from ..models import PropertyReport

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_PRICE_RE = re.compile(r"[€$£]\s?([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)")
_ROOMS_RE = re.compile(r"\b(\d{1,3})\s+rooms?\b", re.IGNORECASE)
_LIMITED_RE = re.compile(
    r"only\s+\d+\s+(?:room|left|rooms)|in high demand|almost fully booked",
    re.IGNORECASE,
)
_SOLD_OUT_RE = re.compile(r"sold out|no availability|no rooms left", re.IGNORECASE)


def _window_checkin(window: WindowConfig) -> date:
    if window.next_weekend:
        # Next Friday, at least 2 days out so "next weekend" on a Thursday
        # doesn't mean tomorrow.
        d = date.today() + timedelta(days=2)
        while d.weekday() != 4:  # Friday
            d += timedelta(days=1)
        return d
    return date.today() + timedelta(days=window.checkin_offset_days)


def _build_search_url(booking_url: str, window: WindowConfig, adults: int) -> str:
    checkin = _window_checkin(window)
    checkout = checkin + timedelta(days=window.nights)

    parsed = urlparse(booking_url)
    query = dict(parse_qsl(parsed.query))
    query.update(
        {
            "checkin": checkin.isoformat(),
            "checkout": checkout.isoformat(),
            "group_adults": str(adults),
            "no_rooms": "1",
        }
    )
    return urlunparse(parsed._replace(query=urlencode(query)))


def _parse_price(text: str) -> Optional[float]:
    candidates = []
    for match in _PRICE_RE.finditer(text):
        raw = match.group(1).replace(".", "").replace(",", ".") if "," in match.group(1) and match.group(1).rfind(",") > match.group(1).rfind(".") else match.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        if 15 <= value <= 5000:  # filter out taxes/fees/noise
            candidates.append(value)
    return min(candidates) if candidates else None


def _parse_rating(text: str) -> Optional[float]:
    match = re.search(r"\b(\d(?:\.\d)?)\s*(?:/\s*10)?\b", text)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return value if 0 <= value <= 10 else None


def _detect_occupancy_signal(text: str, price_found: bool) -> str:
    if _SOLD_OUT_RE.search(text):
        return "sold_out"
    if _LIMITED_RE.search(text):
        return "limited"
    if price_found:
        return "available"
    return "unknown"


def scrape_booking_listing(
    competitor: CompetitorConfig, window: WindowConfig, adults: int = 2
) -> PropertyReport:
    report = PropertyReport(
        name=competitor.name,
        source="booking",
        window=window.label,
        region=competitor.region,
        url=competitor.booking_url,
        rooms=competitor.rooms,
        has_pool=competitor.has_pool,
    )

    url = _build_search_url(competitor.booking_url, window, adults)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # Dismiss the GDPR cookie banner if present, best-effort.
            try:
                page.click("#onetrust-accept-btn-handler", timeout=3_000)
            except Exception:
                pass

            price_texts: list[str] = []
            try:
                page.wait_for_selector(
                    '[data-testid="price-and-discounted-price"]', timeout=10_000
                )
                price_texts = page.locator(
                    '[data-testid="price-and-discounted-price"]'
                ).all_inner_texts()
            except Exception:
                report.warnings.append("Price element not found within timeout")

            rating_text = ""
            try:
                rating_text = page.inner_text(
                    '[data-testid="review-score"]', timeout=3_000
                )
            except Exception:
                report.warnings.append("Review score element not found")

            body_text = page.inner_text("body")
            browser.close()
    except Exception as exc:
        logger.warning("Failed to load %s: %s", url, exc)
        report.occupancy_signal = "unknown"
        report.notes = f"Scrape failed: {exc}"
        return report

    # Prefer the dedicated price elements (one per room type) over scanning
    # the whole page, which also contains taxes/fees that can be mistaken
    # for the room price.
    price_candidates = [p for p in (_parse_price(t) for t in price_texts) if p is not None]
    price = min(price_candidates) if price_candidates else _parse_price(body_text)
    if price is not None:
        report.price_per_night = price
    else:
        report.warnings.append("Could not parse a price from the page")

    rating = _parse_rating(rating_text)
    if rating is not None:
        report.rating = rating

    if "pool" in body_text.lower() or "swimming pool" in body_text.lower():
        report.has_pool = True
    elif competitor.has_pool is not None:
        report.has_pool = competitor.has_pool
    else:
        report.warnings.append("Pool amenity not detected; not in config either")

    rooms_match = _ROOMS_RE.search(body_text)
    if rooms_match:
        report.rooms = int(rooms_match.group(1))
    elif competitor.rooms is not None:
        report.rooms = competitor.rooms
    else:
        report.warnings.append("Room count not detected; not in config either")

    report.occupancy_signal = _detect_occupancy_signal(body_text, price is not None)

    return report
