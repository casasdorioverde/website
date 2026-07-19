"""Generic REST+JSON Airbnb data provider, driven entirely by config.yaml.

Most vendors selling Airbnb price/occupancy data (AirDNA, Rabbu, AirROI,
Mashvisor, PriceLabs, ...) expose a simple "GET a listing, get back JSON"
endpoint. Rather than hardcoding one vendor's response shape (which would be
wrong for anyone using a different provider, or if that vendor changes their
API), this provider is fully described by config.yaml's `airbnb_provider`
section: base_url + listing_endpoint build the request, auth_header_template
builds the header, and field_map picks values out of the response with
dot-notation paths (e.g. "data.price.amount").

If your vendor needs something this can't express (pagination, a non-JSON
body, OAuth instead of a static key), subclass AirbnbDataProvider directly
instead of trying to force it through this generic one.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import requests

from ..config import AirbnbProviderConfig
from ..models import PropertyReport
from .base import AirbnbDataProvider

logger = logging.getLogger(__name__)


def _get_path(data: Any, dotted_path: str) -> Optional[Any]:
    current = data
    for key in dotted_path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


class HttpJsonAirbnbProvider(AirbnbDataProvider):
    def __init__(self, config: AirbnbProviderConfig):
        self.config = config

    def _auth_header(self) -> dict[str, str]:
        api_key = os.environ.get(self.config.api_key_env, "")
        if not api_key:
            raise RuntimeError(
                f"Environment variable '{self.config.api_key_env}' is not set; "
                "cannot authenticate with the Airbnb data provider."
            )
        rendered = self.config.auth_header_template.format(api_key=api_key)
        name, _, value = rendered.partition(":")
        return {name.strip(): value.strip()}

    def fetch(self, listing_id: str) -> PropertyReport:
        report = PropertyReport(name=listing_id, source="airbnb")

        if not self.config.enabled:
            report.notes = "airbnb_provider disabled in config.yaml"
            return report

        url = self.config.base_url.rstrip("/") + self.config.listing_endpoint.format(
            listing_id=listing_id
        )

        try:
            response = requests.get(
                url, headers=self._auth_header(), timeout=15
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("Airbnb provider request failed for %s: %s", listing_id, exc)
            report.notes = f"Provider request failed: {exc}"
            report.warnings.append(str(exc))
            return report

        fm = self.config.field_map
        if "price_per_night" in fm:
            price = _get_path(payload, fm["price_per_night"])
            report.price_per_night = float(price) if price is not None else None
        if "currency" in fm:
            currency = _get_path(payload, fm["currency"])
            if currency:
                report.currency = currency
        if "occupancy_pct" in fm:
            occ = _get_path(payload, fm["occupancy_pct"])
            report.occupancy_pct = float(occ) if occ is not None else None
            report.occupancy_signal = "available" if occ is not None else "unknown"
        if "rating" in fm:
            rating = _get_path(payload, fm["rating"])
            report.rating = float(rating) if rating is not None else None
        if "rooms" in fm:
            rooms = _get_path(payload, fm["rooms"])
            report.rooms = int(rooms) if rooms is not None else None

        for field_name in fm:
            if field_name not in {
                "price_per_night",
                "currency",
                "occupancy_pct",
                "rating",
                "rooms",
            }:
                report.warnings.append(f"Unknown field_map key: {field_name}")

        return report
