"""Tests for the canonical Madeira zone normalisation.

Runs under pytest, or standalone: `python tests/test_zones.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from competitor_pricing.zones import (  # noqa: E402
    UNKNOWN_ZONE,
    home_zone,
    normalize_region,
    resolve_zone,
    zone_order,
)


def test_compass_points_map_to_zones():
    assert normalize_region("north") == "North"
    assert normalize_region("SW") == "South-West"
    assert normalize_region("west") == "South-West"
    assert normalize_region("east") == "South-East"


def test_town_names_map_to_their_zone():
    assert normalize_region("Calheta") == "South-West"
    assert normalize_region("Ponta do Sol") == "South-West"
    assert normalize_region("Funchal") == "South / Funchal"
    assert normalize_region("Machico") == "South-East"
    assert normalize_region("Porto Santo") == "Porto Santo"


def test_accents_and_case_are_ignored():
    assert normalize_region("CÂMARA DE LOBOS") == "South / Funchal"
    assert normalize_region("são vicente") == "North"
    assert normalize_region("Caniço") == "South-East"


def test_embedded_town_name_resolves_via_partial_match():
    assert normalize_region("A lovely quinta in Calheta") == "South-West"
    assert normalize_region("Guest house near Machico") == "South-East"


def test_short_words_do_not_trigger_false_partial_matches():
    # "atlantis" ends in "s"; the compass code "s" must NOT match it.
    assert resolve_zone("atlantis") is UNKNOWN_ZONE
    assert resolve_zone("nowhere special") is UNKNOWN_ZONE


def test_blank_input_is_untagged_not_unknown():
    assert resolve_zone(None) is None
    assert resolve_zone("") is None
    assert resolve_zone("   ") is None
    assert normalize_region(None) is None


def test_unrecognised_region_falls_to_unknown_sentinel():
    zone = resolve_zone("Lisbon")
    assert zone is UNKNOWN_ZONE
    assert zone.label == "Other / unmapped"


def test_home_zone_default_and_override():
    assert home_zone().key == "southwest"
    assert home_zone(None).key == "southwest"
    assert home_zone("Funchal").key == "south"
    # An unrecognised override falls back to the default home zone.
    assert home_zone("nowhere").key == "southwest"


def test_zone_order_is_west_to_east_then_unknown_last():
    labels = ["North", "Other / unmapped", "South-West", "South-East", "South / Funchal"]
    assert zone_order(labels) == [
        "South-West",
        "South / Funchal",
        "South-East",
        "North",
        "Other / unmapped",
    ]


def test_zone_order_dedupes_and_ignores_blanks():
    assert zone_order(["North", "North", "", "South-West"]) == ["South-West", "North"]


def _run_standalone() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_standalone())
