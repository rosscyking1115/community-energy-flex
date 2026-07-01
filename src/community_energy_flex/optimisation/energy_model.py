"""Turn a task placement into cost and carbon.

Energy is spread evenly across the task's occupied slots. For a placement over
slots ``[start, end)`` with ``e`` kWh per slot:

    cost_p   = sum over slots of  e * unit_rate_p_per_kwh(slot)
    carbon_g = sum over slots of  e * carbon_gco2_per_kwh(slot)

The standing charge is intentionally excluded (it is fixed per day and does not
depend on *when* a task runs). See docs/METHODOLOGY.md.
"""

from __future__ import annotations

from community_energy_flex.domain.models import Placement, PlanningSlot, Task


def evaluate_placement(task: Task, slots: list[PlanningSlot], start_index: int) -> Placement:
    end_index = start_index + task.duration_slots
    if start_index < 0 or end_index > len(slots):
        raise IndexError(
            f"placement [{start_index}, {end_index}) is outside the "
            f"{len(slots)}-slot horizon"
        )
    energy = task.energy_per_slot_kwh
    cost_p = 0.0
    carbon_g = 0.0
    for i in range(start_index, end_index):
        cost_p += energy * slots[i].price_p_per_kwh
        carbon_g += energy * slots[i].carbon_gco2_per_kwh
    return Placement(
        task_id=task.task_id,
        start_index=start_index,
        end_index=end_index,
        cost_p=cost_p,
        carbon_g=carbon_g,
    )


def all_placements(task: Task, slots: list[PlanningSlot], starts: list[int]) -> list[Placement]:
    return [evaluate_placement(task, slots, s) for s in starts]
