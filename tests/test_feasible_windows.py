from __future__ import annotations

import pytest

from community_energy_flex.domain.models import Task
from community_energy_flex.optimisation.feasible_windows import (
    InfeasibleTaskError,
    feasible_start_indices,
)


def test_window_respects_bounds_and_duration():
    task = Task("t", "d", energy_kwh=1.0, duration_slots=2, earliest_start=2, latest_finish=6)
    # starts where [s, s+2) fits inside [2, 6): 2, 3, 4
    assert feasible_start_indices(task, num_slots=8) == [2, 3, 4]


def test_horizon_can_further_restrict_starts():
    task = Task("t", "d", energy_kwh=1.0, duration_slots=2, earliest_start=0, latest_finish=8)
    assert feasible_start_indices(task, num_slots=4) == [0, 1, 2]


def test_infeasible_must_run_task_raises():
    task = Task(
        "t", "d", energy_kwh=1.0, duration_slots=2, earliest_start=0, latest_finish=8,
        must_run=True,
    )
    with pytest.raises(InfeasibleTaskError):
        feasible_start_indices(task, num_slots=1)


def test_infeasible_optional_task_returns_empty():
    task = Task(
        "t", "d", energy_kwh=1.0, duration_slots=2, earliest_start=0, latest_finish=8,
        must_run=False,
    )
    assert feasible_start_indices(task, num_slots=1) == []
