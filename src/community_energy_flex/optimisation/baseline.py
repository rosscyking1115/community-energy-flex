"""The baseline: what the user would do *without* the tool.

Defined as running each task at its natural slot - its ``preferred_start`` if
given, otherwise its ``earliest_start``. The optimiser's savings are always
measured against this, so the headline numbers mean "versus business as usual".
See docs/METHODOLOGY.md.
"""

from __future__ import annotations

from community_energy_flex.domain.models import Placement, PlanningSlot, Task
from community_energy_flex.optimisation.energy_model import evaluate_placement


def baseline_start_index(task: Task, num_slots: int) -> int:
    natural = task.preferred_start if task.preferred_start is not None else task.earliest_start
    latest_start = min(task.latest_finish, num_slots) - task.duration_slots
    # Clamp into the feasible range so the baseline is always a legal placement.
    return max(task.earliest_start, min(natural, latest_start))


def baseline_placement(task: Task, slots: list[PlanningSlot]) -> Placement:
    return evaluate_placement(task, slots, baseline_start_index(task, len(slots)))
