from __future__ import annotations

import pandas as pd

from .models import PropertyReport


def build_dataframe(reports: list[PropertyReport]) -> pd.DataFrame:
    rows = []
    us_price = next((r.price_per_night for r in reports if r.source == "us"), None)

    for r in reports:
        vs_us_pct = None
        if us_price and r.price_per_night is not None and us_price > 0:
            vs_us_pct = round((r.price_per_night - us_price) / us_price * 100, 1)

        rows.append(
            {
                "Name": r.name,
                "Source": r.source,
                "Price/night": r.price_per_night,
                "Currency": r.currency,
                "vs. us (%)": vs_us_pct,
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
    # Keep "us" first, then sort the rest by price ascending (unknown last).
    df["_sort_key"] = df["Price/night"].fillna(float("inf"))
    df["_us_first"] = (df["Source"] != "us").astype(int)
    df = df.sort_values(["_us_first", "_sort_key"]).drop(columns=["_sort_key", "_us_first"])
    return df.reset_index(drop=True)


def to_html(df: pd.DataFrame) -> str:
    return df.to_html(index=False, na_rep="?", border=0)


def to_csv(df: pd.DataFrame) -> str:
    return df.to_csv(index=False)


def to_json(df: pd.DataFrame) -> str:
    import json
    from datetime import datetime, timezone

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": json.loads(df.to_json(orient="records")),
    }
    return json.dumps(payload, indent=2)
