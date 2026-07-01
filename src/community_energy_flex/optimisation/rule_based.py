"""The MVP rule-based optimiser.

Each task is scheduled independently at its best-scoring feasible start (no
cross-task load constraint yet - that arrives with the LP/MILP optimiser in a
later milestone). Every recommendation carries a baseline comparison, a
confidence score, and a caveat.
"""

from __future__ import annotations

from dataclasses import dataclass

from community_energy_flex.domain.models import (
    Objective,
    ObjectiveWeights,
    PlanningSlot,
    ScheduledTask,
    Task,
)
from community_energy_flex.optimisation.baseline import baseline_placement
from community_energy_flex.optimisation.confidence import compute_confidence
from community_energy_flex.optimisation.energy_model import all_placements
from community_energy_flex.optimisation.feasible_windows import feasible_start_indices
from community_energy_flex.optimisation.objective import score_placements

_SLOT_HOURS = 0.5


@dataclass(frozen=True)
class Schedule:
    """A full optimisation result across all tasks."""

    objective: Objective
    tasks: list[ScheduledTask]

    @property
    def total_cost_p(self) -> float:
        return sum(t.cost_p for t in self.tasks)

    @property
    def total_carbon_g(self) -> float:
        return sum(t.carbon_g for t in self.tasks)

    @property
    def total_baseline_cost_p(self) -> float:
        return sum(t.baseline_cost_p for t in self.tasks)

    @property
    def total_baseline_carbon_g(self) -> float:
        return sum(t.baseline_carbon_g for t in self.tasks)

    @property
    def total_cost_saving_p(self) -> float:
        return self.total_baseline_cost_p - self.total_cost_p

    @property
    def total_carbon_saving_g(self) -> float:
        return self.total_baseline_carbon_g - self.total_carbon_g


def optimise(
    tasks: list[Task],
    slots: list[PlanningSlot],
    objective: Objective,
    weights: ObjectiveWeights | None = None,
    *,
    using_actual_carbon: bool = False,
    tariff_is_manual: bool = True,
) -> Schedule:
    weights = weights or ObjectiveWeights()
    scheduled: list[ScheduledTask] = []

    for task in tasks:
        starts = feasible_start_indices(task, len(slots))
        if not starts:  # optional task with no room
            continue
        placements = all_placements(task, slots, starts)
        scored = score_placements(task, placements, slots, objective, weights)
        best = scored[0].placement
        base = baseline_placement(task, slots)

        conf = compute_confidence(
            [sp.score for sp in scored],
            horizon_hours=best.start_index * _SLOT_HOURS,
            using_actual_carbon=using_actual_carbon,
            tariff_is_manual=tariff_is_manual,
            single_option=len(scored) == 1,
        )

        scheduled.append(
            ScheduledTask(
                task_id=task.task_id,
                device_type=task.device_type,
                start_index=best.start_index,
                end_index=best.end_index,
                cost_p=best.cost_p,
                carbon_g=best.carbon_g,
                baseline_start_index=base.start_index,
                baseline_cost_p=base.cost_p,
                baseline_carbon_g=base.carbon_g,
                confidence=conf.value,
                confidence_band=conf.band,
                caveat=conf.caveat,
            )
        )

    return Schedule(objective=objective, tasks=scheduled)
