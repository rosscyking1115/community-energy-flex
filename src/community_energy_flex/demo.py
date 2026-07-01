"""Self-contained sample data so the optimiser and app run with zero setup.

The sample carbon curve is greenest overnight and dirtiest in the evening
peak, which is roughly how GB carbon intensity behaves. Nothing here touches
the network; the live client lives in :mod:`data_sources.carbon_intensity`.
"""

from __future__ import annotations

import math

from community_energy_flex.data_sources.tariffs import (
    Band,
    Economy7Tariff,
    FlatTariff,
    MultiBandTariff,
)
from community_energy_flex.domain.models import SLOTS_PER_DAY, Task


def sample_carbon_curve() -> list[float]:
    """A plausible half-hourly gCO2/kWh curve: low at night, evening peak."""
    curve = []
    for i in range(SLOTS_PER_DAY):
        # base sinusoid low ~03:00, high ~18:00, plus an evening peak bump
        hour = i * 0.5
        base = 200 + 90 * math.sin((hour - 9) / 24 * 2 * math.pi)
        peak_bump = 70 if 34 <= i <= 37 else 0
        curve.append(round(base + peak_bump, 1))
    return curve


def sample_tariffs() -> dict[str, object]:
    """A few ready-made tariffs to pick from."""
    agile_prices = [max(5.0, c / 12.0) for c in sample_carbon_curve()]
    return {
        "Flat 28p": FlatTariff(unit_rate_p=28.0, standing_charge_p=45.0, name="Flat 28p"),
        "Economy 7": Economy7Tariff(
            day_rate_p=32.0, night_rate_p=14.0, standing_charge_p=45.0
        ),
        "Agile-style": MultiBandTariff(
            bands=tuple(Band(i, i + 1, round(p, 2)) for i, p in enumerate(agile_prices)),
            default_rate_p=round(sum(agile_prices) / len(agile_prices), 2),
            standing_charge_p=45.0,
            name="Agile-style",
            is_manual=False,
        ),
    }


def sample_tasks() -> list[Task]:
    """A typical evening's flexible loads for a household."""
    return [
        Task(
            task_id="dishwasher",
            device_type="Dishwasher",
            energy_kwh=1.2,
            duration_slots=4,  # 2 hours
            earliest_start=38,  # after 19:00
            latest_finish=SLOTS_PER_DAY,
            preferred_start=40,  # 20:00
            noise_sensitive=True,
        ),
        Task(
            task_id="washing_machine",
            device_type="Washing machine",
            energy_kwh=0.9,
            duration_slots=3,
            earliest_start=0,
            latest_finish=14,  # must finish by 07:00
            preferred_start=11,  # naturally set for the 05:30 morning ramp
        ),
        Task(
            task_id="ev_charge",
            device_type="EV charge",
            energy_kwh=7.0,
            duration_slots=6,  # 3 hours
            earliest_start=0,
            latest_finish=15,  # by 07:30
            preferred_start=0,
        ),
    ]
