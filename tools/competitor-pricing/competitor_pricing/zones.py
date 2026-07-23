"""Canonical Madeira geographic zones ("ARU zones").

The competitor config lets you tag each property with a free-text `region`.
Left unchecked that drifts into a mess of spellings ("south west", "SW",
"Calheta", "ponta do sol", "poente"...) that don't group or sort cleanly.

This module is the single source of truth: it maps any of those spellings to
one canonical zone, gives each zone a stable display label, a compass bearing
and a deterministic sort order, and knows which zone Casas do Rio Verde sits
in (its home zone) so the report can compare like-for-like.

Nothing here scrapes or fetches; it's pure normalization so it's trivially
testable and safe to import anywhere.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Zone:
    """One canonical Madeira zone."""

    key: str  # stable machine id, e.g. "southwest"
    label: str  # display name, e.g. "South-West"
    compass: str  # short compass bearing, e.g. "SW"
    order: int  # deterministic sort order across the island
    municipalities: tuple[str, ...] = ()  # towns that belong to this zone
    aliases: tuple[str, ...] = ()  # extra spellings that map here


# Casas do Rio Verde is in Ponta do Sol, on the sunny south-west coast, so
# `southwest` is the home zone by default. Ordering runs roughly west -> east
# along the populated south coast, then the north coast, then Porto Santo, so
# the compass reads naturally left-to-right.
_ZONES: tuple[Zone, ...] = (
    Zone(
        key="southwest",
        label="South-West",
        compass="SW",
        order=10,
        municipalities=("Ponta do Sol", "Calheta", "Ribeira Brava"),
        aliases=("west", "poente", "oeste", "calheta", "ponta do sol", "ribeira brava"),
    ),
    Zone(
        key="south",
        label="South / Funchal",
        compass="S",
        order=20,
        municipalities=("Funchal", "Câmara de Lobos"),
        aliases=("funchal", "camara de lobos", "centro", "central", "sul"),
    ),
    Zone(
        key="southeast",
        label="South-East",
        compass="SE",
        order=30,
        municipalities=("Santa Cruz", "Machico", "Caniço", "Caniçal"),
        aliases=(
            "east",
            "este",
            "nascente",
            "leste",
            "santa cruz",
            "machico",
            "canico",
            "canical",
            "airport",
            "aeroporto",
        ),
    ),
    Zone(
        key="north",
        label="North",
        compass="N",
        order=40,
        municipalities=("São Vicente", "Santana", "Porto Moniz", "Porto da Cruz"),
        aliases=(
            "norte",
            "sao vicente",
            "santana",
            "porto moniz",
            "porto da cruz",
            "seixal",
        ),
    ),
    Zone(
        key="porto-santo",
        label="Porto Santo",
        compass="PS",
        order=50,
        municipalities=("Porto Santo", "Vila Baleira"),
        aliases=("porto santo", "vila baleira", "golden island", "ilha dourada"),
    ),
)

ZONES_BY_KEY: dict[str, Zone] = {z.key: z for z in _ZONES}

# Default home zone for Casas do Rio Verde. Overridable via `us.zone` in config.
HOME_ZONE_KEY = "southwest"

# Minimum alias length eligible for substring ("contains") matching. Exact
# matches ignore this; it only guards the fuzzy fallback below.
_PARTIAL_MATCH_MIN_LEN = 5

# Sentinel for competitors tagged with a region we don't recognise. It still
# groups them together (better than scattering) and flags the typo to the user.
UNKNOWN_ZONE = Zone(
    key="other",
    label="Other / unmapped",
    compass="·",
    order=90,
    aliases=(),
)


def _slug(value: str) -> str:
    """Lower-case, strip accents, collapse separators to single spaces."""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().strip()
    text = re.sub(r"[\-_/]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


# Precomputed lookup: every accepted spelling -> canonical key.
_ALIAS_TO_KEY: dict[str, str] = {}
for _z in _ZONES:
    for _spelling in (_z.key, _z.label, _z.compass, *_z.municipalities, *_z.aliases):
        _ALIAS_TO_KEY[_slug(_spelling)] = _z.key


def resolve_zone(region: str | None) -> Zone | None:
    """Map a free-text region to its canonical Zone.

    Returns None for empty/blank input (the property simply has no zone), and
    the UNKNOWN_ZONE sentinel for a non-empty value we can't place — so callers
    can distinguish "not tagged" from "tagged with something unrecognised".
    """
    if region is None:
        return None
    slug = _slug(region)
    if not slug:
        return None
    key = _ALIAS_TO_KEY.get(slug)
    if key:
        return ZONES_BY_KEY[key]
    # Fall back to a partial match so "quinta in calheta" still resolves. Only
    # match on aliases long enough to be unambiguous — short directional tokens
    # and compass codes ("s", "n") would spuriously hit words like "atlantis".
    for alias, alias_key in _ALIAS_TO_KEY.items():
        if len(alias) >= _PARTIAL_MATCH_MIN_LEN and alias in slug:
            return ZONES_BY_KEY[alias_key]
    return UNKNOWN_ZONE


def normalize_region(region: str | None) -> str | None:
    """Canonical display label for a free-text region, or None if untagged."""
    zone = resolve_zone(region)
    return zone.label if zone else None


def home_zone(key: str | None = None) -> Zone:
    """Resolve the home zone from a config key, defaulting to Casas do Rio Verde's."""
    if key:
        resolved = resolve_zone(key)
        if resolved and resolved is not UNKNOWN_ZONE:
            return resolved
    return ZONES_BY_KEY[HOME_ZONE_KEY]


def zone_order(labels: list[str]) -> list[str]:
    """Sort a list of display labels by canonical island order (west -> east)."""
    seen: dict[str, None] = {}
    for label in labels:
        if label and label not in seen:
            seen[label] = None

    def sort_key(label: str) -> tuple[int, str]:
        zone = resolve_zone(label)
        return (zone.order if zone else 99, label)

    return sorted(seen, key=sort_key)
