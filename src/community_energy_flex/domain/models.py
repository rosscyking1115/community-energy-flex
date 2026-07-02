"""Core domain models.

A planning day is divided into 48 half-hour *slots*, indexed 0..47. Slot ``i``
covers the period ``[i * 30min, (i + 1) * 30min)``. Slot indices are the common
currency across the whole optimiser: tasks, tariffs, and carbon forecasts are
all expressed in slots so the optimiser never has to reason about wall-clock
time directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import StrEnum

SLOTS_PER_DAY = 48
SLOT_MINUTES = 30


def slot_to_time(index: int) -> str:
    """Render a slot boundary as ``HH:MM`` (24:00 for the end of the day)."""
    total_minutes = index * SLOT_MINUTES
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def slot_to_clock(index: int) -> time:
    """Clock time at the start of a slot, for the UI's time pickers. Slot 48
    (the end-of-day boundary) wraps to 00:00 - callers that mean "finish by end
    of day" treat 00:00 as slot 48."""
    minutes = (index % SLOTS_PER_DAY) * SLOT_MINUTES
    return time(hour=minutes // 60, minute=minutes % 60)


def clock_to_slot(value: time) -> int:
    """Slot index containing a clock time (rounded down to the half hour)."""
    return value.hour * 2 + (1 if value.minute >= 30 else 0)


class Objective(StrEnum):
    """What the user is optimising for."""

    CHEAPEST = "cheapest"
    LOWEST_CARBON = "lowest_carbon"
    BALANCED = "balanced"
    AVOID_PEAK = "avoid_peak"


@dataclass(frozen=True)
class ObjectiveWeights:
    """Weights for the BALANCED objective. Need not sum to 1; they are applied
    to already-normalised (0..1) cost, carbon, and comfort terms."""

    cost: float = 0.5
    carbon: float = 0.5
    comfort: float = 0.0

    def __post_init__(self) -> None:
        for name in ("cost", "carbon", "comfort"):
            if getattr(self, name) < 0:
                raise ValueError(f"weight '{name}' must be non-negative")
        if self.cost + self.carbon + self.comfort == 0:
            raise ValueError("at least one weight must be positive")


@dataclass(frozen=True)
class Task:
    """A flexible electricity-consuming activity to be scheduled.

    ``earliest_start`` and ``latest_finish`` bound the feasible window as slot
    indices. ``latest_finish`` is *exclusive*: a task with ``latest_finish=14``
    must have completed by the start of slot 14 (07:00). ``preferred_start`` is
    the slot the user would naturally run it at; it defines the baseline and can
    feed a comfort penalty.
    """

    task_id: str
    device_type: str
    energy_kwh: float
    duration_slots: int
    earliest_start: int = 0
    latest_finish: int = SLOTS_PER_DAY
    must_run: bool = True
    preferred_start: int | None = None
    noise_sensitive: bool = False
    comfort_priority: float = 1.0

    def __post_init__(self) -> None:
        if self.energy_kwh <= 0:
            raise ValueError(f"task {self.task_id}: energy_kwh must be > 0")
        if self.duration_slots < 1:
            raise ValueError(f"task {self.task_id}: duration_slots must be >= 1")
        if not (0 <= self.earliest_start < SLOTS_PER_DAY):
            raise ValueError(f"task {self.task_id}: earliest_start out of range")
        if not (0 < self.latest_finish <= SLOTS_PER_DAY):
            raise ValueError(f"task {self.task_id}: latest_finish out of range")
        if self.latest_finish - self.earliest_start < self.duration_slots:
            raise ValueError(
                f"task {self.task_id}: window "
                f"[{self.earliest_start}, {self.latest_finish}) is too small for "
                f"duration {self.duration_slots}"
            )
        if self.preferred_start is not None and not (
            self.earliest_start <= self.preferred_start
            <= self.latest_finish - self.duration_slots
        ):
            raise ValueError(
                f"task {self.task_id}: preferred_start {self.preferred_start} "
                "is outside the feasible window"
            )

    @property
    def energy_per_slot_kwh(self) -> float:
        """Energy is assumed evenly spread across the task's occupied slots."""
        return self.energy_kwh / self.duration_slots


@dataclass(frozen=True)
class CarbonSlot:
    """A half-hourly carbon-intensity reading from the source API."""

    index: int
    start: datetime
    end: datetime
    forecast_gco2_per_kwh: float | None
    actual_gco2_per_kwh: float | None = None

    @property
    def best_estimate(self) -> float:
        """Prefer measured actuals; fall back to forecast."""
        if self.actual_gco2_per_kwh is not None:
            return self.actual_gco2_per_kwh
        if self.forecast_gco2_per_kwh is not None:
            return self.forecast_gco2_per_kwh
        raise ValueError(f"carbon slot {self.index} has no value")


@dataclass(frozen=True)
class PlanningSlot:
    """A slot on the planning horizon with price and carbon attached."""

    index: int
    carbon_gco2_per_kwh: float
    price_p_per_kwh: float
    is_peak: bool = False
    start: datetime | None = None


@dataclass(frozen=True)
class Placement:
    """The cost and carbon of running a task at a given start slot."""

    task_id: str
    start_index: int
    end_index: int  # exclusive
    cost_p: float
    carbon_g: float


@dataclass(frozen=True)
class ScheduledTask:
    """The optimiser's recommendation for a single task, with baseline
    comparison, confidence, and a plain-language caveat."""

    task_id: str
    device_type: str
    start_index: int
    end_index: int
    cost_p: float
    carbon_g: float
    baseline_start_index: int
    baseline_cost_p: float
    baseline_carbon_g: float
    confidence: float
    confidence_band: str
    caveat: str

    @property
    def cost_saving_p(self) -> float:
        return self.baseline_cost_p - self.cost_p

    @property
    def carbon_saving_g(self) -> float:
        return self.baseline_carbon_g - self.carbon_g


@dataclass(frozen=True)
class Schedule:
    """A full optimisation result across all tasks.

    Lives in the domain layer (not the optimiser module) because it is the
    shared result type that reporting, the pipeline, and the retro loop all
    depend on - they should depend on the domain, not on the optimiser's
    implementation.
    """

    objective: Objective
    tasks: list[ScheduledTask]

    @property
    def total_cost_p(self) -> float:
        return sum(t.cost_p for t in self.tasks)

    @property
    def total_carbon_g(self) -> float:
        return sum(t.carbon_g for t in self.tasks)

    @property
    def total_baseline_cost_p(self) -> float:
        return sum(t.baseline_cost_p for t in self.tasks)

    @property
    def total_baseline_carbon_g(self) -> float:
        return sum(t.baseline_carbon_g for t in self.tasks)

    @property
    def total_cost_saving_p(self) -> float:
        return self.total_baseline_cost_p - self.total_cost_p

    @property
    def total_carbon_saving_g(self) -> float:
        return self.total_baseline_carbon_g - self.total_carbon_g
