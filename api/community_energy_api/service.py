"""Translate an API request into an engine call and back. All domain logic lives
in ``community_energy_flex``; this only marshals types."""

from __future__ import annotations

from datetime import time

from community_energy_api.carbon import CarbonCurveResult
from community_energy_api.models import (
    OptimiseRequest,
    OptimiseResponse,
    ScheduledTaskOut,
    TariffSpec,
    TaskSpec,
)
from community_energy_flex.data_sources.tariffs import (
    Economy7Tariff,
    FlatTariff,
    Tariff,
    multiband_from_half_hour_prices,
)
from community_energy_flex.domain.models import (
    SLOTS_PER_DAY,
    Objective,
    ObjectiveWeights,
    Task,
    clock_to_slot,
)
from community_energy_flex.optimisation.planning import build_planning_slots
from community_energy_flex.optimisation.rule_based import optimise
from community_energy_flex.reporting.summary import build_action_summary


def _to_slot(hhmm: str | None, *, end: bool = False) -> int | None:
    if hhmm is None:
        return None
    if hhmm == "":
        return SLOTS_PER_DAY if end else 0
    hours, minutes = (int(p) for p in hhmm.split(":"))
    slot = clock_to_slot(time(hours, minutes))
    if end and slot == 0:  # 00:00 as a deadline means end of day
        return SLOTS_PER_DAY
    return slot


def build_tariff(spec: TariffSpec) -> tuple[Tariff, bool]:
    """Return (tariff, is_manual). is_manual feeds the robustness heuristic."""
    if spec.kind == "flat":
        if spec.unit_rate_p is None:
            raise ValueError("flat tariff needs unit_rate_p")
        flat = FlatTariff(unit_rate_p=spec.unit_rate_p, standing_charge_p=spec.standing_charge_p)
        return flat, True
    if spec.kind == "economy7":
        if spec.day_rate_p is None or spec.night_rate_p is None:
            raise ValueError("economy7 tariff needs day_rate_p and night_rate_p")
        return (
            Economy7Tariff(
                day_rate_p=spec.day_rate_p,
                night_rate_p=spec.night_rate_p,
                standing_charge_p=spec.standing_charge_p,
            ),
            True,
        )
    # agile / manual_half_hourly: 48 half-hourly prices
    if not spec.prices_p or len(spec.prices_p) < SLOTS_PER_DAY:
        raise ValueError(f"{spec.kind} tariff needs {SLOTS_PER_DAY} half-hourly prices")
    is_manual = spec.kind == "manual_half_hourly"
    tariff = multiband_from_half_hour_prices(
        spec.prices_p, standing_charge_p=spec.standing_charge_p, is_manual=is_manual
    )
    return tariff, is_manual


def build_tasks(specs: list[TaskSpec]) -> list[Task]:
    tasks = []
    for i, s in enumerate(specs):
        tasks.append(
            Task(
                task_id=s.name or f"task_{i}",
                device_type=s.device_type,
                energy_kwh=s.energy_kwh,
                duration_slots=max(1, round(s.duration_hours * 2)),
                earliest_start=_to_slot(s.earliest),
                latest_finish=_to_slot(s.latest, end=True),
                preferred_start=_to_slot(s.preferred),
            )
        )
    return tasks


def peak_slot_count(start_index: int, end_index: int, slots) -> int:
    """Return optimiser-window peak overlap for API diagnostics, not reporting."""
    duration_slots = end_index - start_index
    if duration_slots < 1:
        return 0
    return sum(slot.is_peak for slot in slots[start_index:end_index])


def baseline_peak_slot_count(baseline_start_index: int, duration_slots: int, slots) -> int:
    """Return the explicit-baseline overlap as raw optimiser diagnostic input."""
    return sum(
        slot.is_peak
        for slot in slots[baseline_start_index : baseline_start_index + duration_slots]
    )


def run_optimise(
    req: OptimiseRequest, carbon: CarbonCurveResult, region_name: str
) -> OptimiseResponse:
    tariff, is_manual = build_tariff(req.tariff)
    tasks = build_tasks(req.tasks)  # raises ValueError on invalid constraints
    slots = build_planning_slots(carbon.values, tariff)
    objective = Objective(req.objective)
    weights = (
        ObjectiveWeights(cost=req.cost_weight, carbon=1.0 - req.cost_weight)
        if objective is Objective.BALANCED
        else ObjectiveWeights()
    )
    schedule = optimise(tasks, slots, objective, weights, tariff_is_manual=is_manual)
    summary = build_action_summary(schedule)
    price_is_live = req.tariff.kind == "agile"
    price_source = "octopus_agile_live" if price_is_live else "user_entered_tariff"
    tariff_labels = {
        "flat": "flat",
        "economy7": "Economy 7",
        "manual_half_hourly": "half-hourly",
    }
    price_source_label = (
        "Octopus Agile published rates"
        if price_is_live
        else f"User-entered {tariff_labels[req.tariff.kind]} tariff"
    )

    return OptimiseResponse(
        objective=objective.value,
        region=region_name,
        carbon_source=carbon.source,
        carbon_source_label=carbon.source_label,
        retrieved_at_utc=carbon.retrieved_at_utc,
        valid_from_utc=carbon.valid_from_utc,
        valid_to_utc=carbon.valid_to_utc,
        is_live_forecast=carbon.is_live_forecast,
        is_fallback=carbon.is_fallback,
        fallback_reason=carbon.fallback_reason,
        price_source=price_source,
        price_source_label=price_source_label,
        price_is_live=price_is_live,
        price_unavailable_reason=None,
        total_cost_saving_p=summary.total_cost_saving_p,
        total_carbon_saving_g=summary.total_carbon_saving_g,
        tasks=[
            ScheduledTaskOut(
                name=ln.task_id,
                device_type=ln.device_type,
                run_window=ln.recommended_window,
                baseline_window=ln.baseline_window,
                cost_saving_p=ln.cost_saving_p,
                carbon_saving_g=ln.carbon_saving_g,
                baseline_cost_p=scheduled.baseline_cost_p,
                scheduled_cost_p=scheduled.cost_p,
                baseline_carbon_g=scheduled.baseline_carbon_g,
                scheduled_carbon_g=scheduled.carbon_g,
                baseline_peak_slot_count=baseline_peak_slot_count(
                    scheduled.baseline_start_index,
                    scheduled.end_index - scheduled.start_index,
                    slots,
                ),
                scheduled_peak_slot_count=peak_slot_count(
                    scheduled.start_index,
                    scheduled.end_index,
                    slots,
                ),
                robustness_score=next(
                    t.robustness_score for t in schedule.tasks if t.task_id == ln.task_id
                ),
                robustness_band=ln.robustness_band,
                caveat=ln.caveat,
            )
            for ln in summary.lines
            for scheduled in [next(t for t in schedule.tasks if t.task_id == ln.task_id)]
        ],
        safety_statement=summary.safety_statement,
    )
