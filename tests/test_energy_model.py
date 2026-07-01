from __future__ import annotations

import pytest

from community_energy_flex.domain.models import Task
from community_energy_flex.optimisation.energy_model import evaluate_placement


def test_cost_and_carbon_are_summed_per_slot(varied_slots):
    # 2 kWh over 2 slots -> 1 kWh per slot. Start at slot 1:
    #   cost   = 1*15 + 1*5  = 20p
    #   carbon = 1*250 + 1*260 = 510 g
    task = Task("t", "test", energy_kwh=2.0, duration_slots=2)
    placement = evaluate_placement(task, varied_slots, start_index=1)
    assert placement.cost_p == pytest.approx(20.0)
    assert placement.carbon_g == pytest.approx(510.0)
    assert placement.end_index == 3


def test_placement_off_the_end_raises(varied_slots):
    task = Task("t", "test", energy_kwh=1.0, duration_slots=2)
    with pytest.raises(IndexError):
        evaluate_placement(task, varied_slots, start_index=7)
