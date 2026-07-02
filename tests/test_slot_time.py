from __future__ import annotations

from datetime import time

import pytest

from community_energy_flex.domain.models import (
    SLOTS_PER_DAY,
    clock_to_slot,
    slot_to_clock,
    slot_to_time,
)


def test_slot_to_time_string():
    assert slot_to_time(0) == "00:00"
    assert slot_to_time(14) == "07:00"
    assert slot_to_time(48) == "24:00"


def test_slot_to_clock():
    assert slot_to_clock(0) == time(0, 0)
    assert slot_to_clock(14) == time(7, 0)
    assert slot_to_clock(47) == time(23, 30)
    assert slot_to_clock(48) == time(0, 0)  # end-of-day wraps to midnight


def test_clock_to_slot_rounds_down_to_the_half_hour():
    assert clock_to_slot(time(0, 0)) == 0
    assert clock_to_slot(time(7, 0)) == 14
    assert clock_to_slot(time(23, 30)) == 47
    assert clock_to_slot(time(8, 15)) == 16  # 08:00 slot
    assert clock_to_slot(time(8, 45)) == 17  # 08:30 slot


@pytest.mark.parametrize("slot", range(SLOTS_PER_DAY))
def test_clock_slot_round_trip(slot):
    assert clock_to_slot(slot_to_clock(slot)) == slot
