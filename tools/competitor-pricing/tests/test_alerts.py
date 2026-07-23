"""Tests for zone-aware alerting in report.compute_alerts.

Runs under pytest, or standalone: `python tests/test_alerts.py`.
Requires pandas (same dependency the report module already needs).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from competitor_pricing.models import PropertyReport  # noqa: E402
from competitor_pricing.report import build_dataframe, compute_alerts  # noqa: E402


def _prev(rows: list[dict]) -> dict:
    """Shape a previous-snapshot lookup keyed by (name, window)."""
    return {(r["Name"], r.get("Window", "")): r for r in rows}


def _kinds(alerts: list[dict]) -> list[str]:
    return [a["kind"] for a in alerts]


def test_first_run_has_no_alerts():
    df = build_dataframe(
        [PropertyReport(name="Us", source="us", price_per_night=95, region="South-West")]
    )
    assert compute_alerts(df, {}, 95, home_zone="southwest") == []


def test_same_zone_undercut_is_flagged_as_home_undercut():
    reports = [
        PropertyReport(name="Us", source="us", price_per_night=95, region="South-West"),
        PropertyReport(
            name="Rival", source="booking", window="weekend",
            price_per_night=90, region="South-West",
        ),
    ]
    df = build_dataframe(reports)
    prev = _prev([{"Name": "Rival", "Window": "weekend", "Price/night": 100}])
    alerts = compute_alerts(df, prev, 95, home_zone="southwest")
    assert "home_undercut" in _kinds(alerts)
    assert not any(k == "undercut" for k in _kinds(alerts))
    assert "in your zone" in next(a["text"] for a in alerts if a["kind"] == "home_undercut")


def test_other_zone_undercut_stays_generic():
    reports = [
        PropertyReport(name="Us", source="us", price_per_night=95, region="South-West"),
        PropertyReport(
            name="Rival", source="booking", window="weekend",
            price_per_night=90, region="North",
        ),
    ]
    df = build_dataframe(reports)
    prev = _prev([{"Name": "Rival", "Window": "weekend", "Price/night": 100}])
    alerts = compute_alerts(df, prev, 95, home_zone="southwest")
    assert "undercut" in _kinds(alerts)
    assert "home_undercut" not in _kinds(alerts)


def test_newly_most_expensive_in_home_zone_fires_once():
    # This run: both same-zone rivals sit below us; last run one was above.
    reports = [
        PropertyReport(name="Us", source="us", price_per_night=120, region="South-West"),
        PropertyReport(name="A", source="booking", window="weekend", price_per_night=100, region="South-West"),
        PropertyReport(name="B", source="booking", window="weekend", price_per_night=110, region="South-West"),
    ]
    df = build_dataframe(reports)
    prev = _prev([
        {"Name": "A", "Window": "weekend", "Price/night": 100},
        {"Name": "B", "Window": "weekend", "Price/night": 130},  # was above us
    ])
    alerts = compute_alerts(df, prev, 120, home_zone="southwest")
    assert "home_most_expensive" in _kinds(alerts)


def test_persistent_most_expensive_does_not_realert():
    # We were already the most expensive last run, so no new alert this run.
    reports = [
        PropertyReport(name="Us", source="us", price_per_night=120, region="South-West"),
        PropertyReport(name="A", source="booking", window="weekend", price_per_night=100, region="South-West"),
    ]
    df = build_dataframe(reports)
    prev = _prev([{"Name": "A", "Window": "weekend", "Price/night": 90}])
    alerts = compute_alerts(df, prev, 120, home_zone="southwest")
    assert "home_most_expensive" not in _kinds(alerts)


def test_home_zone_alerts_sort_first():
    reports = [
        PropertyReport(name="Us", source="us", price_per_night=95, region="South-West"),
        PropertyReport(name="Far", source="booking", window="weekend", price_per_night=50, region="North"),
        PropertyReport(name="Near", source="booking", window="weekend", price_per_night=90, region="South-West"),
    ]
    df = build_dataframe(reports)
    prev = _prev([
        {"Name": "Far", "Window": "weekend", "Price/night": 100},
        {"Name": "Near", "Window": "weekend", "Price/night": 100},
    ])
    alerts = compute_alerts(df, prev, 95, home_zone="southwest")
    # The home-zone undercut must be the first alert shown.
    assert alerts[0]["kind"] == "home_undercut"


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
