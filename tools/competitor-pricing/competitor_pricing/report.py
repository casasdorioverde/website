from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from .models import PropertyReport

# Price move (either direction) vs the previous run that counts as an alert.
ALERT_MOVE_PCT = 10.0


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
    df: pd.DataFrame, prev: dict, us_price: Optional[float]
) -> list[dict[str, str]]:
    """Noteworthy changes vs the previous run. Empty on the first run."""
    alerts: list[dict[str, str]] = []
    if not prev:
        return alerts

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
                alerts.append(
                    {
                        "kind": "undercut",
                        "text": (
                            f"{label}: now cheaper than us "
                            f"({price:.0f} vs our {us_price:.0f} {row['Currency']})"
                        ),
                    }
                )

        prev_signal = prev_row.get("Occupancy signal")
        if row["Occupancy signal"] == "sold_out" and prev_signal != "sold_out":
            alerts.append({"kind": "sold_out", "text": f"{label}: now sold out"})

    return alerts


def to_html(df: pd.DataFrame) -> str:
    return df.to_html(index=False, na_rep="?", border=0)


def to_csv(df: pd.DataFrame) -> str:
    return df.to_csv(index=False)


def to_json(
    df: pd.DataFrame,
    alerts: Optional[list[dict[str, str]]] = None,
    history_map: Optional[dict] = None,
    windows: Optional[list[str]] = None,
) -> str:
    rows: list[dict[str, Any]] = json.loads(df.to_json(orient="records"))
    if history_map:
        for row in rows:
            key = (row.get("Name", ""), row.get("Window", "") or "")
            if key in history_map:
                row["History"] = history_map[key]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "windows": windows or [],  # config order, drives dashboard tab order
        "alerts": alerts or [],
        "rows": rows,
    }
    return json.dumps(payload, indent=2)
