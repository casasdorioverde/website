"""Read/write the dated history files that power deltas and sparklines.

Each run writes <history_dir>/YYYY-MM-DD.json with the same payload shape
as latest.json. Re-running on the same day overwrites that day's file.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_SPARKLINE_POINTS = 12

Key = tuple[str, str]  # (name, window)


def _row_key(row: dict[str, Any]) -> Key:
    return (row.get("Name", ""), row.get("Window", "") or "")


def load_history_files(history_dir: Path) -> list[tuple[str, list[dict[str, Any]]]]:
    """All prior runs as (date_str, rows), oldest first. Today's file excluded
    so a re-run on the same day doesn't compare against itself."""
    if not history_dir.is_dir():
        return []
    today = date.today().isoformat()
    out = []
    for f in sorted(history_dir.glob("*.json")):
        if f.stem == today:
            continue
        try:
            payload = json.loads(f.read_text())
            out.append((f.stem, payload.get("rows", [])))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping unreadable history file %s: %s", f, exc)
    return out


def previous_snapshot(
    files: list[tuple[str, list[dict[str, Any]]]],
) -> dict[Key, dict[str, Any]]:
    """Most recent prior run, keyed by (name, window)."""
    if not files:
        return {}
    _, rows = files[-1]
    return {_row_key(r): r for r in rows}


def build_history_map(
    files: list[tuple[str, list[dict[str, Any]]]],
) -> dict[Key, list[dict[str, Any]]]:
    """Per-property price series across past runs, for sparklines."""
    out: dict[Key, list[dict[str, Any]]] = {}
    for date_str, rows in files[-MAX_SPARKLINE_POINTS:]:
        for r in rows:
            price = r.get("Price/night")
            out.setdefault(_row_key(r), []).append({"date": date_str, "price": price})
    return out


def write_history_file(history_dir: Path, payload_json: str) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    path = history_dir / f"{date.today().isoformat()}.json"
    path.write_text(payload_json)
    return path
