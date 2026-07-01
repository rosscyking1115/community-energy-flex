"""Enumerate the start slots at which a task may legally run."""

from __future__ import annotations

from community_energy_flex.domain.models import Task


class InfeasibleTaskError(ValueError):
    """Raised when a must-run task has no feasible start on the horizon."""


def feasible_start_indices(task: Task, num_slots: int) -> list[int]:
    """Every start slot ``s`` such that the whole task fits inside both its own
    window and the planning horizon."""
    latest_start = min(task.latest_finish, num_slots) - task.duration_slots
    starts = [s for s in range(task.earliest_start, latest_start + 1)]
    if not starts and task.must_run:
        raise InfeasibleTaskError(
            f"task {task.task_id} cannot be scheduled within "
            f"[{task.earliest_start}, {task.latest_finish}) on a "
            f"{num_slots}-slot horizon"
        )
    return starts
