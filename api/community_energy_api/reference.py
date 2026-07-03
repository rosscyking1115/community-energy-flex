"""Load the static reference datasets (regions, appliances) once into memory.

Per the MoveIn playbook: ship a tiny read-only extract, not a database. These
files are versioned in the repo; a refresh is a new file + redeploy.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

_REF_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"


@functools.lru_cache(maxsize=1)
def regions() -> list[dict]:
    return json.loads((_REF_DIR / "regions.json").read_text(encoding="utf-8"))["regions"]


@functools.lru_cache(maxsize=1)
def appliances() -> list[dict]:
    return json.loads((_REF_DIR / "appliances.json").read_text(encoding="utf-8"))["appliances"]


def region_by_id(region_id: str) -> dict | None:
    return next((r for r in regions() if r["id"] == region_id), None)


def region_for_outcode(outcode: str) -> dict | None:
    """Resolve a postcode outcode (e.g. 'BS1', 'BT9') to a region by its letter
    prefix - longest prefix wins so 'BT' beats 'B'."""
    letters = "".join(c for c in outcode.strip().upper() if c.isalpha())
    best: dict | None = None
    best_len = 0
    for region in regions():
        for prefix in region["postcode_prefixes"]:
            if letters.startswith(prefix) and len(prefix) > best_len:
                best, best_len = region, len(prefix)
    return best
