from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class UsConfig:
    name: str
    price_per_night: float
    currency: str = "EUR"
    rooms: Optional[int] = None
    has_pool: Optional[bool] = None


@dataclass
class CompetitorConfig:
    name: str
    booking_url: Optional[str] = None
    airbnb_listing_id: Optional[str] = None
    rooms: Optional[int] = None
    has_pool: Optional[bool] = None


@dataclass
class SearchConfig:
    checkin_offset_days: int = 14
    nights: int = 2
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
    )

    competitors_raw = raw.get("competitors", [])
    competitors = []
    for c in competitors_raw:
        name = _require(c, "name", "competitor")
        if not c.get("booking_url") and not c.get("airbnb_listing_id"):
            raise ValueError(
                f"Competitor '{name}' needs a booking_url and/or airbnb_listing_id"
            )
        competitors.append(
            CompetitorConfig(
                name=name,
                booking_url=c.get("booking_url"),
                airbnb_listing_id=c.get("airbnb_listing_id"),
                rooms=c.get("rooms"),
                has_pool=c.get("has_pool"),
            )
        )

    search_raw = raw.get("search", {})
    search = SearchConfig(
        checkin_offset_days=search_raw.get("checkin_offset_days", 14),
        nights=search_raw.get("nights", 2),
        adults=search_raw.get("adults", 2),
    )

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
    )

    return Config(
        us=us,
        competitors=competitors,
        search=search,
        airbnb_provider=airbnb_provider,
        email=email,
    )
