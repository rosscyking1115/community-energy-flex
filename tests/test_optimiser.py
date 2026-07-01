"""Optimiser behaviour and, crucially, its invariants.

Expected placements are worked out by hand from the ``varied_slots`` fixture,
never by re-running the solver, so these tests can actually catch a broken
optimiser.
"""

from __future__ import annotations

import pytest

from community_energy_flex.data_sources.tariffs import FlatTariff
from community_energy_flex.demo import sample_carbon_curve, sample_tasks
from community_energy_flex.domain.models import Objective, Task
from community_energy_flex.optimisation.planning import build_planning_slots
from community_energy_flex.optimisation.rule_based import optimise

ALL_OBJECTIVES = list(Objective)


def _one_slot_task() -> list[Task]:
    return [Task("t", "d", energy_kwh=1.0, duration_slots=1, earliest_start=0, latest_finish=8)]


def test_cheapest_picks_the_cheapest_slot(varied_slots):
    # prices = [20,15,5,12,18,25,30,22] -> cheapest is slot 2
    sched = optimise(_one_slot_task(), varied_slots, Objective.CHEAPEST)
    assert sched.tasks[0].start_index == 2


def test_lowest_carbon_picks_the_greenest_slot(varied_slots):
    # carbon = [300,250,260,200,150,90,120,280] -> greenest is slot 5
    sched = optimise(_one_slot_task(), varied_slots, Objective.LOWEST_CARBON)
    assert sched.tasks[0].start_index == 5


def test_avoid_peak_does_not_pick_the_peak_slot(varied_slots):
    sched = optimise(_one_slot_task(), varied_slots, Objective.AVOID_PEAK)
    assert varied_slots[sched.tasks[0].start_index].is_peak is False


def test_ties_break_to_earliest_start(flat_slots):
    # Every slot identical -> earliest feasible start wins, deterministically.
    sched = optimise(_one_slot_task(), flat_slots, Objective.CHEAPEST)
    assert sched.tasks[0].start_index == 0


# --- Invariants: must hold for every objective on the realistic sample day ---

@pytest.fixture
def sample_slots():
    return build_planning_slots(sample_carbon_curve(), FlatTariff(unit_rate_p=28.0))


@pytest.mark.parametrize("objective", ALL_OBJECTIVES)
def test_all_must_run_tasks_are_scheduled(objective, sample_slots):
    tasks = sample_tasks()
    sched = optimise(tasks, sample_slots, objective)
    assert {t.task_id for t in sched.tasks} == {t.task_id for t in tasks}


@pytest.mark.parametrize("objective", ALL_OBJECTIVES)
def test_no_task_is_scheduled_outside_its_window(objective, sample_slots):
    tasks = {t.task_id: t for t in sample_tasks()}
    sched = optimise(list(tasks.values()), sample_slots, objective)
    for st in sched.tasks:
        task = tasks[st.task_id]
        assert st.start_index >= task.earliest_start
        assert st.end_index <= task.latest_finish
        assert st.end_index <= len(sample_slots)


def test_cheapest_never_costs_more_than_baseline(sample_slots):
    sched = optimise(sample_tasks(), sample_slots, Objective.CHEAPEST)
    assert sched.total_cost_p <= sched.total_baseline_cost_p + 1e-9


def test_lowest_carbon_never_emits_more_than_baseline(sample_slots):
    sched = optimise(sample_tasks(), sample_slots, Objective.LOWEST_CARBON)
    assert sched.total_carbon_g <= sched.total_baseline_carbon_g + 1e-9
