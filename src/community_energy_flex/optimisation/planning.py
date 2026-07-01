"""Assemble the planning horizon: one :class:`PlanningSlot` per half hour with
carbon and price attached."""

from __future__ import annotations

from community_energy_flex.data_sources.tariffs import Tariff, price_curve
from community_energy_flex.domain.models import SLOTS_PER_DAY, PlanningSlot

# 17:00-19:00 is the classic GB demand peak: slots 34..37 inclusive.
DEFAULT_PEAK_SLOTS: frozenset[int] = frozenset({34, 35, 36, 37})


def build_planning_slots(
    carbon_curve: list[float],
    tariff: Tariff,
    peak_slots: frozenset[int] = DEFAULT_PEAK_SLOTS,
    num_slots: int = SLOTS_PER_DAY,
) -> list[PlanningSlot]:
    """Combine a per-slot carbon curve and a tariff into planning slots.

    ``carbon_curve`` must be at least ``num_slots`` long.
    """
    if len(carbon_curve) < num_slots:
        raise ValueError(
            f"carbon_curve has {len(carbon_curve)} slots, need {num_slots}"
        )
    prices = price_curve(tariff, num_slots)
    return [
        PlanningSlot(
            index=i,
            carbon_gco2_per_kwh=carbon_curve[i],
            price_p_per_kwh=prices[i],
            is_peak=i in peak_slots,
        )
        for i in range(num_slots)
    ]
