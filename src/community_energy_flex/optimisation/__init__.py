"""The scheduling optimiser: feasible windows, energy model, objectives,
confidence, and the rule-based solver."""

from community_energy_flex.optimisation.planning import (
    DEFAULT_PEAK_SLOTS,
    build_planning_slots,
)
from community_energy_flex.optimisation.rule_based import optimise

__all__ = ["optimise", "build_planning_slots", "DEFAULT_PEAK_SLOTS"]
