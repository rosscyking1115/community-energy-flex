from __future__ import annotations

import pytest

from community_energy_flex.data_sources.tariffs import FlatTariff
from community_energy_flex.demo import sample_carbon_curve, sample_tasks
from community_energy_flex.domain.models import Objective
from community_energy_flex.monitoring.retro import carbon_forecast_error, evaluate_retrospective
from community_energy_flex.optimisation.planning import build_planning_slots
from community_energy_flex.optimisation.rule_based import optimise

TARIFF = FlatTariff(unit_rate_p=28.0)


def _schedule_and_slots(curve):
    slots = build_planning_slots(curve, TARIFF)
    schedule = optimise(sample_tasks(), slots, Objective.LOWEST_CARBON)
    return schedule, slots


def test_perfect_forecast_realises_exactly():
    curve = sample_carbon_curve()
    schedule, _ = _schedule_and_slots(curve)
    # actuals == forecast -> the plan realises exactly what was promised
    actual_slots = build_planning_slots(curve, TARIFF)
    report = evaluate_retrospective(
        sample_tasks(), schedule, actual_slots,
        forecast_curve=curve, actual_curve=curve,
    )
    assert report.carbon_forecast_mae == 0.0
    assert report.realised_carbon_fraction == pytest.approx(1.0)
    assert report.total_actual_carbon_saving_g == pytest.approx(
        report.total_forecast_carbon_saving_g
    )


def test_forecast_error_metrics():
    forecast = [100.0, 100.0, 100.0]
    actual = [120.0, 80.0, 100.0]
    mae, bias = carbon_forecast_error(forecast, actual)
    # |−20|,|20|,|0| -> 40/3 ; bias (−20+20+0)/3 = 0
    assert mae == pytest.approx(40 / 3)
    assert bias == pytest.approx(0.0)


def test_worse_actuals_reduce_realised_saving():
    curve = sample_carbon_curve()
    schedule, _ = _schedule_and_slots(curve)
    # Overnight actuals turned out dirtier than forecast: flatten the curve so
    # the chosen (greenest-forecast) slots no longer look as good.
    flat_actual = [200.0] * len(curve)
    actual_slots = build_planning_slots(flat_actual, TARIFF)
    report = evaluate_retrospective(
        sample_tasks(), schedule, actual_slots,
        forecast_curve=curve, actual_curve=flat_actual,
    )
    # A flat actual curve means shifting saved no carbon in reality.
    assert report.total_actual_carbon_saving_g == pytest.approx(0.0, abs=1e-6)
    assert report.realised_carbon_fraction < 1.0
    assert report.carbon_forecast_mae > 0.0
