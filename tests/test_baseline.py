from __future__ import annotations

from community_energy_flex.domain.models import Task
from community_energy_flex.optimisation.baseline import baseline_start_index


def test_baseline_uses_preferred_start_when_feasible():
    task = Task("t", "d", energy_kwh=1.0, duration_slots=2, earliest_start=0,
                latest_finish=8, preferred_start=5)
    assert baseline_start_index(task, num_slots=8) == 5


def test_baseline_falls_back_to_earliest_when_no_preference():
    task = Task("t", "d", energy_kwh=1.0, duration_slots=2, earliest_start=3, latest_finish=8)
    assert baseline_start_index(task, num_slots=8) == 3


def test_baseline_clamps_when_horizon_shrinks():
    task = Task("t", "d", energy_kwh=1.0, duration_slots=2, earliest_start=0,
                latest_finish=8, preferred_start=5)
    # horizon only 6 slots -> latest legal start is 4, so clamp 5 -> 4
    assert baseline_start_index(task, num_slots=6) == 4
