"""The forecast-vs-actual retro loop: did yesterday's plan actually help?

The Carbon Intensity API returns a *forecast* and, once a period has passed, the
measured *actual*. This module re-scores a schedule that was built on the
forecast against what actually happened, so the tool can say honestly how much it
really saved - and how good its forecast was. This is what turns "we think this
saves money" into evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from community_energy_flex.domain.models import PlanningSlot, Task
from community_energy_flex.optimisation.energy_model import evaluate_placement
from community_energy_flex.optimisation.rule_based import Schedule


@dataclass(frozen=True)
class RetroTaskResult:
    task_id: str
    forecast_cost_saving_p: float
    actual_cost_saving_p: float
    forecast_carbon_saving_g: float
    actual_carbon_saving_g: float

    @property
    def still_saved_cost(self) -> bool:
        return self.actual_cost_saving_p >= -1e-9

    @property
    def still_saved_carbon(self) -> bool:
        return self.actual_carbon_saving_g >= -1e-9


@dataclass(frozen=True)
class RetroReport:
    results: list[RetroTaskResult]
    carbon_forecast_mae: float
    carbon_forecast_bias: float

    @property
    def total_forecast_cost_saving_p(self) -> float:
        return sum(r.forecast_cost_saving_p for r in self.results)

    @property
    def total_actual_cost_saving_p(self) -> float:
        return sum(r.actual_cost_saving_p for r in self.results)

    @property
    def total_forecast_carbon_saving_g(self) -> float:
        return sum(r.forecast_carbon_saving_g for r in self.results)

    @property
    def total_actual_carbon_saving_g(self) -> float:
        return sum(r.actual_carbon_saving_g for r in self.results)

    def _realised(self, actual: float, forecast: float) -> float:
        if abs(forecast) < 1e-9:
            return 1.0 if abs(actual) < 1e-9 else 0.0
        return actual / forecast

    @property
    def realised_cost_fraction(self) -> float:
        """Actual cost saving as a fraction of what was forecast (1.0 = spot on)."""
        return self._realised(self.total_actual_cost_saving_p, self.total_forecast_cost_saving_p)

    @property
    def realised_carbon_fraction(self) -> float:
        return self._realised(
            self.total_actual_carbon_saving_g, self.total_forecast_carbon_saving_g
        )


def carbon_forecast_error(
    forecast_curve: list[float], actual_curve: list[float]
) -> tuple[float, float]:
    """Return (MAE, bias) of the carbon forecast. Positive bias = forecast ran
    high (over-predicted intensity)."""
    n = min(len(forecast_curve), len(actual_curve))
    if n == 0:
        return 0.0, 0.0
    diffs = [forecast_curve[i] - actual_curve[i] for i in range(n)]
    mae = sum(abs(d) for d in diffs) / n
    bias = sum(diffs) / n
    return mae, bias


def evaluate_retrospective(
    tasks: list[Task],
    schedule: Schedule,
    actual_slots: list[PlanningSlot],
    *,
    forecast_curve: list[float] | None = None,
    actual_curve: list[float] | None = None,
) -> RetroReport:
    """Re-score ``schedule`` (built on the forecast) against ``actual_slots``.

    ``actual_slots`` must use the same tariff as the original run, so only the
    carbon differs. Optionally pass the raw forecast/actual carbon curves to also
    get the forecast error.
    """
    tasks_by_id = {t.task_id: t for t in tasks}
    results: list[RetroTaskResult] = []
    for st in schedule.tasks:
        task = tasks_by_id[st.task_id]
        actual_opt = evaluate_placement(task, actual_slots, st.start_index)
        actual_base = evaluate_placement(task, actual_slots, st.baseline_start_index)
        results.append(
            RetroTaskResult(
                task_id=st.task_id,
                forecast_cost_saving_p=st.cost_saving_p,
                actual_cost_saving_p=actual_base.cost_p - actual_opt.cost_p,
                forecast_carbon_saving_g=st.carbon_saving_g,
                actual_carbon_saving_g=actual_base.carbon_g - actual_opt.carbon_g,
            )
        )

    mae, bias = (
        carbon_forecast_error(forecast_curve, actual_curve)
        if forecast_curve is not None and actual_curve is not None
        else (0.0, 0.0)
    )
    return RetroReport(results=results, carbon_forecast_mae=mae, carbon_forecast_bias=bias)
