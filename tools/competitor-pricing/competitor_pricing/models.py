from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PropertyReport:
    name: str
    source: str  # "us" | "booking" | "airbnb"
    url: Optional[str] = None
    price_per_night: Optional[float] = None
    currency: str = "EUR"
    rooms: Optional[int] = None
    has_pool: Optional[bool] = None
    rating: Optional[float] = None
    occupancy_signal: str = "unknown"  # "sold_out" | "limited" | "available" | "unknown"
    occupancy_pct: Optional[float] = None
    notes: str = ""
    warnings: list[str] = field(default_factory=list)
