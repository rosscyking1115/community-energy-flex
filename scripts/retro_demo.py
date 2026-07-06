"""The forecast-vs-actual retro loop, made visible: "did yesterday's plan
actually save?"

A schedule is committed on the *forecast*. Then the day happens. This runs the
same four community-centre loads once, then re-scores that fixed plan against
several ways the day could actually turn out, and prints what was *realised*
versus what was forecast — the check that turns "we think this saves" into
evidence.

The actuals here are **simulated** to exercise the loop (we don't store the
forecast we made on a past day, so a true historical replay isn't possible); the
retro maths is the real engine (`monitoring/retro.py`). Cost is left certain on
purpose: Agile prices are published day-ahead, so the forecast *risk* is carbon,
not price — which is exactly what the table below stresses.

    PYTHONPATH=src python scripts/retro_demo.py
"""

from __future__ import annotations

import random

from community_energy_flex.demo import sample_carbon_curve, sample_tariffs
from community_energy_flex.domain.models import Objective, Task
from community_energy_flex.monitoring.retro import evaluate_retrospective
from community_energy_flex.optimisation.planning import build_planning_slots
from community_energy_flex.optimisation.rule_based import optimise

TASKS = [
    Task("dishwasher", "Commercial dishwasher", energy_kwh=3.0, duration_slots=3,
         earliest_start=26, latest_finish=44, preferred_start=27),
    Task("water_heater", "Water heater", energy_kwh=4.0, duration_slots=4,
         earliest_start=0, latest_finish=16, preferred_start=12),
    Task("minibus", "Minibus EV charge", energy_kwh=20.0, duration_slots=10,
         earliest_start=0, latest_finish=15, preferred_start=0),
    Task("scrubber", "Floor scrubber charge", energy_kwh=1.5, duration_slots=2,
         earliest_start=0, latest_finish=16, preferred_start=12),
]


def _roll(curve: list[float], k: int) -> list[float]:
    """Shift a curve right by k slots (the shape arrives k half-hours late)."""
    return curve[-k:] + curve[:-k]


def _noisy(curve: list[float], pct: float, seed: int) -> list[float]:
    rng = random.Random(seed)
    return [c * (1 + rng.uniform(-pct, pct)) for c in curve]


# How the day could actually turn out, given the forecast `f`.
SCENARIOS: list[tuple[str, object]] = [
    ("Forecast was spot on", lambda f: list(f)),
    ("Grid ran 8% dirtier", lambda f: [c * 1.08 for c in f]),
    ("Grid ran 6% cleaner", lambda f: [c * 0.94 for c in f]),
    ("Noisy day (+/-15%)", lambda f: _noisy(f, 0.15, seed=7)),
    ("Evening peak came 1h late", lambda f: _roll(f, 2)),
]


def main() -> int:
    forecast = sample_carbon_curve()
    tariff = sample_tariffs()["Agile-style"]
    slots = build_planning_slots(forecast, tariff)

    # One plan, committed on the forecast.
    schedule = optimise(TASKS, slots, Objective.BALANCED, tariff_is_manual=False)
    forecast_g = schedule.total_carbon_saving_g

    print('Forecast-vs-actual retro - "did yesterday\'s plan actually save?"\n')
    print(f"  Plan committed on the forecast: {forecast_g:.0f} g CO2 saving expected"
          f" across {len(schedule.tasks)} loads.\n")

    header = f"  {'How the day turned out':30} {'forecast':>9} {'actual':>9} {'realised':>9} {'fc MAE':>8}  {'still saved?':>12}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    realised_pcts = []
    still_saved = 0
    for name, actual_fn in SCENARIOS:
        actual = actual_fn(forecast)  # type: ignore[operator]
        actual_slots = build_planning_slots(actual, tariff)
        retro = evaluate_retrospective(
            TASKS, schedule, actual_slots, forecast_curve=forecast, actual_curve=actual
        )
        pct = retro.realised_carbon_fraction * 100
        realised_pcts.append(pct)
        saved = retro.total_actual_carbon_saving_g >= 0
        still_saved += int(saved)
        print(
            f"  {name:30} {retro.total_forecast_carbon_saving_g:>7.0f} g"
            f" {retro.total_actual_carbon_saving_g:>7.0f} g"
            f" {pct:>8.0f}%"
            f" {retro.carbon_forecast_mae:>6.0f} g"
            f"  {'yes' if saved else 'no':>12}"
        )

    avg = sum(realised_pcts) / len(realised_pcts)
    print(
        f"\n  Across {len(SCENARIOS)} scenarios: realised {avg:.0f}% of the forecast"
        f" carbon saving on average; the plan still saved carbon in"
        f" {still_saved}/{len(SCENARIOS)}."
    )
    print("  Cost is unchanged in every row - Agile prices are known day-ahead, so"
          " carbon is the only thing the forecast can get wrong.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
