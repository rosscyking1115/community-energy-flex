"""Score candidate placements under a chosen objective.

Cost and carbon are min-max normalised to 0..1 *across a task's own feasible
placements*, so the four objectives are comparable and the BALANCED weights
behave predictably. Lower score is always better.
"""

from __future__ import annotations

from dataclasses import dataclass

from community_energy_flex.domain.models import (
    Objective,
    ObjectiveWeights,
    Placement,
    PlanningSlot,
    Task,
)


@dataclass(frozen=True)
class ScoredPlacement:
    placement: Placement
    score: float


def _normalise(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def _peak_fraction(placement: Placement, slots: list[PlanningSlot]) -> float:
    occupied = range(placement.start_index, placement.end_index)
    peak = sum(1 for i in occupied if slots[i].is_peak)
    return peak / len(occupied)


def _comfort_penalties(task: Task, placements: list[Placement]) -> list[float]:
    if task.preferred_start is None:
        return [0.0 for _ in placements]
    starts = [p.start_index for p in placements]
    span = max(starts) - min(starts)
    if span == 0:
        return [0.0 for _ in placements]
    return [abs(p.start_index - task.preferred_start) / span for p in placements]


def score_placements(
    task: Task,
    placements: list[Placement],
    slots: list[PlanningSlot],
    objective: Objective,
    weights: ObjectiveWeights,
) -> list[ScoredPlacement]:
    """Return placements scored and sorted best (lowest) first. Ties break by
    earliest start for determinism."""
    norm_cost = _normalise([p.cost_p for p in placements])
    norm_carbon = _normalise([p.carbon_g for p in placements])
    comfort = _comfort_penalties(task, placements)
    peak = [_peak_fraction(p, slots) for p in placements]

    scored: list[ScoredPlacement] = []
    for i, p in enumerate(placements):
        if objective is Objective.CHEAPEST:
            score = norm_cost[i]
        elif objective is Objective.LOWEST_CARBON:
            score = norm_carbon[i]
        elif objective is Objective.AVOID_PEAK:
            score = 0.5 * peak[i] + 0.5 * norm_cost[i]
        elif objective is Objective.BALANCED:
            total_w = weights.cost + weights.carbon + weights.comfort
            score = (
                weights.cost * norm_cost[i]
                + weights.carbon * norm_carbon[i]
                + weights.comfort * comfort[i]
            ) / total_w
        else:  # pragma: no cover - exhaustive enum
            raise ValueError(f"unknown objective {objective}")
        scored.append(ScoredPlacement(placement=p, score=score))

    scored.sort(key=lambda sp: (sp.score, sp.placement.start_index))
    return scored
