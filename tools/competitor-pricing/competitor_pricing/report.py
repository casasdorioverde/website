from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from .models import PropertyReport
from .zones import normalize_region, zone_order

# Price move (either direction) vs the previous run that counts as an alert.
ALERT_MOVE_PCT = 10.0

# Alert kinds, ordered by how loudly they should shout. Home-zone signals rank
# above island-wide ones because same-zone competitors share our actual market.
_ALERT_PRIORITY = {
    "home_undercut": 0,
    "home_most_expensive": 1,
    "undercut": 2,
    "sold_out": 3,
    "price_drop": 4,
    "price_rise": 5,
}


def _prev_price(prev: dict, name: str, window: str) -> Optional[float]:
    row = prev.get((name, window or ""))
    if not row:
        return None
    return row.get("Price/night")


def build_dataframe(
    reports: list[PropertyReport], prev: Optional[dict] = None
) -> pd.DataFrame:
    prev = prev or {}
    rows = []
    us_price = next((r.price_per_night for r in reports if r.source == "us"), None)

    for r in reports:
        vs_us_pct = None
        if us_price and r.price_per_night is not None and us_price > 0:
            vs_us_pct = round((r.price_per_night - us_price) / us_price * 100, 1)

        prev_price = _prev_price(prev, r.name, r.window)
        delta_pct = None
        if prev_price and r.price_per_night is not None and prev_price > 0:
            delta_pct = round((r.price_per_night - prev_price) / prev_price * 100, 1)

        rows.append(
            {
                "Name": r.name,
                "Source": r.source,
                "Region": r.region or "",
                "Window": r.window or "",
                "Price/night": r.price_per_night,
                "Currency": r.currency,
                "vs. us (%)": vs_us_pct,
                "Δ prev (%)": delta_pct,
                "Rooms": r.rooms,
                "Pool": r.has_pool,
                "Rating": r.rating,
                "Occupancy signal": r.occupancy_signal,
                "Occupancy %": r.occupancy_pct,
                "URL": r.url or "",
                "Notes": "; ".join(r.warnings) if r.warnings else r.notes,
            }
        )

    df = pd.DataFrame(rows)
    # "us" rows first, then group by window and region, cheapest first
    # within each group (unknown price last).
    df["_sort_key"] = df["Price/night"].fillna(float("inf"))
    df["_us_first"] = (df["Source"] != "us").astype(int)
    df = df.sort_values(["_us_first", "Window", "Region", "_sort_key"]).drop(
        columns=["_sort_key", "_us_first"]
    )
    return df.reset_index(drop=True)


def compute_alerts(
    df: pd.DataFrame,
    prev: dict,
    us_price: Optional[float],
    home_zone: Optional[str] = None,
) -> list[dict[str, str]]:
    """Noteworthy changes vs the previous run. Empty on the first run.

    `home_zone` is our own zone (any spelling); when given, undercuts by
    same-zone competitors are flagged more prominently and a separate alert
    fires when we newly become the most expensive property in our zone.
    """
    alerts: list[dict[str, str]] = []
    if not prev:
        return alerts

    home_label = normalize_region(home_zone) if home_zone else None

    for _, row in df.iterrows():
        if row["Source"] == "us":
            continue
        name, window = row["Name"], row["Window"] or ""
        label = f"{name}" + (f" [{window}]" if window else "")
        prev_row = prev.get((name, window))
        if not prev_row:
            continue

        price = row["Price/night"]
        prev_price = prev_row.get("Price/night")
        in_home_zone = home_label is not None and row["Region"] == home_label

        if price is not None and prev_price:
            move = (price - prev_price) / prev_price * 100
            if abs(move) >= ALERT_MOVE_PCT:
                direction = "dropped" if move < 0 else "rose"
                alerts.append(
                    {
                        "kind": "price_drop" if move < 0 else "price_rise",
                        "text": (
                            f"{label}: price {direction} {abs(move):.0f}% "
                            f"({prev_price:.0f} → {price:.0f} {row['Currency']})"
                        ),
                    }
                )
            if (
                us_price
                and price < us_price <= prev_price
            ):
                zone_note = f" in your zone ({home_label})" if in_home_zone else ""
                alerts.append(
                    {
                        "kind": "home_undercut" if in_home_zone else "undercut",
                        "text": (
                            f"{label}: now cheaper than us{zone_note} "
                            f"({price:.0f} vs our {us_price:.0f} {row['Currency']})"
                        ),
                    }
                )

        prev_signal = prev_row.get("Occupancy signal")
        if row["Occupancy signal"] == "sold_out" and prev_signal != "sold_out":
            alerts.append({"kind": "sold_out", "text": f"{label}: now sold out"})

    if home_label and us_price:
        alerts.extend(
            _home_zone_position_alerts(df, prev, us_price, home_label)
        )

    alerts.sort(key=lambda a: _ALERT_PRIORITY.get(a["kind"], 99))
    return alerts


def _home_zone_position_alerts(
    df: pd.DataFrame, prev: dict, us_price: float, home_label: str
) -> list[dict[str, str]]:
    """Fire when we newly become the most expensive property in our own zone.

    Compared per date window against the previous run, so a persistent "most
    expensive" state doesn't re-alert every week (keeps email changes_only
    meaningful) — it only speaks up on the run where the ranking flips.
    """
    out: list[dict[str, str]] = []
    zone_rows = df[(df["Source"] != "us") & (df["Region"] == home_label)]
    if zone_rows.empty:
        return out

    for window, group in zone_rows.groupby(zone_rows["Window"].fillna("")):
        now = [
            (r["Name"], r["Price/night"])
            for _, r in group.iterrows()
            if r["Price/night"] is not None
        ]
        if not now:
            continue

        us_is_top_now = all(p < us_price for _, p in now)
        # Was us already the most expensive last run? Only compare against
        # competitors we have a previous price for; if we have none, we can't
        # tell it "newly" flipped, so stay quiet.
        prev_prices = [
            pp
            for comp_name, _ in now
            if (pp := (prev.get((comp_name, window)) or {}).get("Price/night")) is not None
        ]
        us_was_top_prev = bool(prev_prices) and all(p < us_price for p in prev_prices)

        if us_is_top_now and prev_prices and not us_was_top_prev:
            cheapest = min(p for _, p in now)
            win_note = f" [{window}]" if window else ""
            out.append(
                {
                    "kind": "home_most_expensive",
                    "text": (
                        f"You are now the most expensive in {home_label}{win_note}: "
                        f"{len(now)} competitor(s) below you, cheapest {cheapest:.0f} "
                        f"vs your {us_price:.0f}"
                    ),
                }
            )
    return out


def to_html(df: pd.DataFrame) -> str:
    return df.to_html(index=False, na_rep="?", border=0)


def to_csv(df: pd.DataFrame) -> str:
    return df.to_csv(index=False)


def to_json(
    df: pd.DataFrame,
    alerts: Optional[list[dict[str, str]]] = None,
    history_map: Optional[dict] = None,
    windows: Optional[list[str]] = None,
    home_zone: Optional[str] = None,
) -> str:
    rows: list[dict[str, Any]] = json.loads(df.to_json(orient="records"))
    if history_map:
        for row in rows:
            key = (row.get("Name", ""), row.get("Window", "") or "")
            if key in history_map:
                row["History"] = history_map[key]

    # Canonical west->east ordering of the zones actually present, so the
    # dashboard compass lays out consistently instead of by insertion order.
    present = [r.get("Region", "") for r in rows if r.get("Region")]
    ordered_zones = zone_order(present)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "windows": windows or [],  # config order, drives dashboard tab order
        "zone_order": ordered_zones,  # canonical order for the zone compass
        "home_zone": home_zone or "",  # our own zone, highlighted in the UI
        "alerts": alerts or [],
        "rows": rows,
    }
    return json.dumps(payload, indent=2)
