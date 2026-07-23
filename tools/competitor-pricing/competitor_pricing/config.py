from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .zones import UNKNOWN_ZONE, home_zone, normalize_region, resolve_zone

logger = logging.getLogger(__name__)


@dataclass
class UsConfig:
    name: str
    price_per_night: float
    currency: str = "EUR"
    rooms: Optional[int] = None
    has_pool: Optional[bool] = None
    booking_url: Optional[str] = None  # our own listing, scraped for parity
    # Which Madeira zone we sit in. Drives the "home zone" highlight and the
    # like-for-like comparison against competitors in the same area.
    zone: str = "southwest"


@dataclass
class CompetitorConfig:
    name: str
    booking_url: Optional[str] = None
    airbnb_listing_id: Optional[str] = None
    rooms: Optional[int] = None
    has_pool: Optional[bool] = None
    region: Optional[str] = None


@dataclass
class WindowConfig:
    """One date window to check prices for.

    Either a fixed offset from today (checkin_offset_days) or the next
    upcoming weekend (next_weekend: true -> check-in next Friday).
    """

    label: str
    checkin_offset_days: int = 14
    nights: int = 2
    next_weekend: bool = False


@dataclass
class SearchConfig:
    windows: list[WindowConfig] = field(default_factory=list)
    adults: int = 2


@dataclass
class AirbnbProviderConfig:
    enabled: bool = False
    base_url: str = ""
    listing_endpoint: str = ""
    api_key_env: str = ""
    auth_header_template: str = ""
    field_map: dict[str, str] = field(default_factory=dict)


@dataclass
class EmailConfig:
    from_addr: str = ""
    to: list[str] = field(default_factory=list)
    subject_prefix: str = "[Competitor Pricing]"
    # "always" sends the weekly digest every run; "changes_only" sends
    # only when the run produced at least one alert.
    mode: str = "always"


@dataclass
class Config:
    us: UsConfig
    competitors: list[CompetitorConfig]
    search: SearchConfig
    airbnb_provider: AirbnbProviderConfig
    email: EmailConfig


def _require(d: dict[str, Any], key: str, context: str) -> Any:
    if key not in d:
        raise ValueError(f"Missing required field '{key}' in {context}")
    return d[key]


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Copy config.example.yaml to {path.name} and fill in your data."
        )
    raw = yaml.safe_load(path.read_text()) or {}

    us_raw = _require(raw, "us", "config")
    us = UsConfig(
        name=_require(us_raw, "name", "us"),
        price_per_night=float(_require(us_raw, "price_per_night", "us")),
        currency=us_raw.get("currency", "EUR"),
        rooms=us_raw.get("rooms"),
        has_pool=us_raw.get("has_pool"),
        booking_url=us_raw.get("booking_url"),
        zone=home_zone(us_raw.get("zone")).label,
    )

    competitors_raw = raw.get("competitors", [])
    competitors = []
    for c in competitors_raw:
        name = _require(c, "name", "competitor")
        if not c.get("booking_url") and not c.get("airbnb_listing_id"):
            raise ValueError(
                f"Competitor '{name}' needs a booking_url and/or airbnb_listing_id"
            )
        raw_region = c.get("region")
        zone = resolve_zone(raw_region)
        if zone is UNKNOWN_ZONE:
            logger.warning(
                "Competitor '%s' has region %r that doesn't match any Madeira "
                "zone; grouping it under '%s'. See zones.py for accepted values.",
                name,
                raw_region,
                UNKNOWN_ZONE.label,
            )
        competitors.append(
            CompetitorConfig(
                name=name,
                booking_url=c.get("booking_url"),
                airbnb_listing_id=c.get("airbnb_listing_id"),
                rooms=c.get("rooms"),
                has_pool=c.get("has_pool"),
                region=normalize_region(raw_region),
            )
        )

    search_raw = raw.get("search", {})
    windows_raw = search_raw.get("windows")
    if windows_raw:
        windows = [
            WindowConfig(
                label=_require(w, "label", "search.windows entry"),
                checkin_offset_days=w.get("checkin_offset_days", 14),
                nights=w.get("nights", 2),
                next_weekend=w.get("next_weekend", False),
            )
            for w in windows_raw
        ]
    else:
        # Backward compatibility: old configs described a single window
        # with top-level checkin_offset_days/nights.
        offset = search_raw.get("checkin_offset_days", 14)
        windows = [
            WindowConfig(
                label=f"+{offset}d",
                checkin_offset_days=offset,
                nights=search_raw.get("nights", 2),
            )
        ]
    search = SearchConfig(windows=windows, adults=search_raw.get("adults", 2))

    ab_raw = raw.get("airbnb_provider", {})
    airbnb_provider = AirbnbProviderConfig(
        enabled=ab_raw.get("enabled", False),
        base_url=ab_raw.get("base_url", ""),
        listing_endpoint=ab_raw.get("listing_endpoint", ""),
        api_key_env=ab_raw.get("api_key_env", ""),
        auth_header_template=ab_raw.get("auth_header_template", ""),
        field_map=ab_raw.get("field_map", {}),
    )

    email_raw = raw.get("email", {})
    email = EmailConfig(
        from_addr=email_raw.get("from", ""),
        to=email_raw.get("to", []),
        subject_prefix=email_raw.get("subject_prefix", "[Competitor Pricing]"),
        mode=email_raw.get("mode", "always"),
    )
    if email.mode not in ("always", "changes_only"):
        raise ValueError(f"email.mode must be 'always' or 'changes_only', got '{email.mode}'")

    return Config(
        us=us,
        competitors=competitors,
        search=search,
        airbnb_provider=airbnb_provider,
        email=email,
    )
