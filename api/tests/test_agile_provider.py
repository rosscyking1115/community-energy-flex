from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("fastapi")

from community_energy_api import agile  # noqa: E402
from community_energy_flex.data_sources.octopus_agile import OctopusAgileClient  # noqa: E402


def _rates(day: str = "2026-07-04", n: int = 48) -> dict:
    results = []
    for i in range(n):
        hh, mm = i // 2, "30" if i % 2 else "00"
        stamp = f"{day}T{hh:02d}:{mm}:00Z"
        results.append({"valid_from": stamp, "valid_to": stamp, "value_inc_vat": 10.0 + i * 0.1})
    return {"results": results}


def test_agile_curve_builds_48_slots_for_a_region():
    region = {"id": "london", "name": "London", "agile_gsp": "C"}
    client = OctopusAgileClient(fetch=lambda url: _rates())
    curve, day = agile.agile_curve(region, client=client, day=date(2026, 7, 4))
    assert len(curve) == 48
    assert curve[0] == 10.0
    assert day == "2026-07-04"


def test_agile_unavailable_without_gsp():
    region = {"id": "northern-ireland", "name": "Northern Ireland", "agile_gsp": None}
    with pytest.raises(agile.AgileUnavailable):
        agile.agile_curve(region)
