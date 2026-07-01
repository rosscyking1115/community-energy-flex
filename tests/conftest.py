"""Shared fixtures. A tiny hand-worked planning horizon lets tests assert
against independently computed expected values rather than re-running the
optimiser's own arithmetic (guarding against tautological tests)."""

from __future__ import annotations

import pytest

from community_energy_flex.domain.models import PlanningSlot


@pytest.fixture
def flat_slots() -> list[PlanningSlot]:
    """8 slots, flat 10p, flat 100 gCO2 - a neutral horizon."""
    return [
        PlanningSlot(index=i, carbon_gco2_per_kwh=100.0, price_p_per_kwh=10.0)
        for i in range(8)
    ]


@pytest.fixture
def varied_slots() -> list[PlanningSlot]:
    """8 slots with a clear cheapest slot (index 2) and greenest slot (index 5),
    all values chosen by hand so tests can assert exact placements."""
    prices = [20.0, 15.0, 5.0, 12.0, 18.0, 25.0, 30.0, 22.0]
    carbon = [300.0, 250.0, 260.0, 200.0, 150.0, 90.0, 120.0, 280.0]
    peaks = {6}
    return [
        PlanningSlot(
            index=i,
            carbon_gco2_per_kwh=carbon[i],
            price_p_per_kwh=prices[i],
            is_peak=i in peaks,
        )
        for i in range(8)
    ]
