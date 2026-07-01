"""Run the optimiser end-to-end on the sample data and print an action report.

    python -m community_energy_flex               # balanced
    python -m community_energy_flex cheapest      # or lowest_carbon / avoid_peak
"""

from __future__ import annotations

import sys

from community_energy_flex.demo import sample_carbon_curve, sample_tariffs, sample_tasks
from community_energy_flex.domain.models import Objective
from community_energy_flex.optimisation.planning import build_planning_slots
from community_energy_flex.optimisation.rule_based import optimise
from community_energy_flex.reporting.summary import build_action_summary, format_text_report


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    name = argv[0] if argv else "balanced"
    try:
        objective = Objective(name)
    except ValueError:
        print(f"Unknown objective '{name}'. Choose from: {[o.value for o in Objective]}")
        return 2

    # A time-of-use tariff so cost savings are visible (a flat tariff correctly
    # yields zero cost saving - shifting time can't change a flat unit rate).
    tariff = sample_tariffs()["Agile-style"]
    slots = build_planning_slots(sample_carbon_curve(), tariff)
    schedule = optimise(
        sample_tasks(), slots, objective, tariff_is_manual=tariff.is_manual
    )
    print(format_text_report(build_action_summary(schedule)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
