"""The daily optimisation pipeline.

Steps: fetch carbon forecast -> validate -> optimise -> record monitoring, with a
keep-last-good-schedule fallback so a bad forecast pull never leaves users with
nothing. All I/O (the carbon fetch, the stores) is injected, so the whole thing
runs in tests with no network and no scheduler.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from community_energy_flex.data_sources.tariffs import Tariff
from community_energy_flex.domain.models import (
    SLOTS_PER_DAY,
    Objective,
    ObjectiveWeights,
    Schedule,
    ScheduledTask,
    Task,
)
from community_energy_flex.monitoring.store import (
    DataFreshness,
    OptimisationQuality,
    PipelineRun,
)
from community_energy_flex.optimisation.metrics import average_robustness, constraint_violations
from community_energy_flex.optimisation.planning import build_planning_slots
from community_energy_flex.optimisation.rule_based import optimise

# --- keep-last-good-schedule stores -----------------------------------------
InputProvenanceState = Literal["live_forecast", "sample_input"]
ReportingStatus = Literal["reportable", "not_reportable"]


@dataclass(frozen=True)
class LastGoodSchedule:
    """A schedule together with the immutable lineage needed when it is reused."""

    schedule: Schedule
    schedule_run_id: str
    input_provenance_state: InputProvenanceState | None
    source_observed_at: str | None = None
    source_valid_from: str | None = None
    source_valid_to: str | None = None


class LastGoodStore(Protocol):
    def save(self, record: LastGoodSchedule) -> None: ...
    def load(self) -> LastGoodSchedule | None: ...


class InMemoryLastGoodStore:
    def __init__(self) -> None:
        self._record: LastGoodSchedule | None = None

    def save(self, record: LastGoodSchedule) -> None:
        self._record = record

    def load(self) -> LastGoodSchedule | None:
        return self._record


class JsonLastGoodStore:
    """Persists the last good schedule to disk so a fallback survives restarts.

    Uses JSON rather than pickle: the artifact stays inert, so loading it can
    never execute code even if the file on disk is tampered with. The schedule
    is a flat tree of dataclasses over primitives, so it round-trips cleanly.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, record: LastGoodSchedule) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "objective": str(record.schedule.objective),
            "tasks": [asdict(t) for t in record.schedule.tasks],
            "schedule_run_id": record.schedule_run_id,
            "input_provenance_state": record.input_provenance_state,
            "source_observed_at": record.source_observed_at,
            "source_valid_from": record.source_valid_from,
            "source_valid_to": record.source_valid_to,
        }
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def load(self) -> LastGoodSchedule | None:
        if not self.path.exists():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        schedule = Schedule(
            objective=Objective(payload["objective"]),
            tasks=[ScheduledTask(**task) for task in payload["tasks"]],
        )
        # Legacy schedule-only files cannot truthfully identify their origin.
        # They remain inspectable but are ineligible for serving as fallback.
        return LastGoodSchedule(
            schedule=schedule,
            schedule_run_id=payload.get("schedule_run_id", "legacy-unknown"),
            input_provenance_state=payload.get("input_provenance_state"),
            source_observed_at=payload.get("source_observed_at"),
            source_valid_from=payload.get("source_valid_from"),
            source_valid_to=payload.get("source_valid_to"),
        )


# --- steps ------------------------------------------------------------------
class DataValidationError(ValueError):
    """Raised when a fetched carbon curve is unusable."""


def fetch_carbon_forecast(fetcher: Callable[[], list[float]]) -> list[float]:
    """Run the injected fetcher. Any failure propagates as an exception for the
    pipeline's fallback to catch."""
    return fetcher()


def validate_carbon_curve(curve: list[float], expected_slots: int = SLOTS_PER_DAY) -> None:
    if len(curve) < expected_slots:
        raise DataValidationError(
            f"carbon curve has {len(curve)} slots, need {expected_slots} "
            "(forecast missing for tomorrow)"
        )
    if any(v is None or v < 0 for v in curve[:expected_slots]):
        raise DataValidationError("carbon curve contains missing or negative values")


# --- orchestrated run -------------------------------------------------------
@dataclass
class DailyPipelineConfig:
    tasks: list[Task]
    tariff: Tariff
    objective: Objective = Objective.BALANCED
    weights: ObjectiveWeights = field(default_factory=ObjectiveWeights)
    carbon_fetcher: Callable[[], list[float]] | None = None
    using_actual_carbon: bool = False
    job: str = "daily_energy_optimisation"
    input_provenance_state: InputProvenanceState = "sample_input"
    source_observed_at: str | None = None
    source_valid_from: str | None = None
    source_valid_to: str | None = None


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    status: str  # "success" | "fallback" | "failed"
    schedule: Schedule | None
    message: str = ""
    # `run_id` identifies this pipeline attempt. `schedule_run_id` identifies
    # the schedule actually served, which differs during last-good fallback.
    schedule_run_id: str | None = None
    input_provenance_state: str | None = None
    original_input_provenance_state: InputProvenanceState | None = None
    source_observed_at: str | None = None
    source_valid_from: str | None = None
    source_valid_to: str | None = None
    failure_reason: str | None = None
    reporting_status: ReportingStatus = "not_reportable"


def run_daily_pipeline(
    config: DailyPipelineConfig,
    *,
    store=None,
    last_good: LastGoodStore | None = None,
) -> PipelineResult:
    run_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    fetcher = config.carbon_fetcher
    if fetcher is None:
        raise ValueError("config.carbon_fetcher must be provided")

    def _record_run(status: str, rows: int, message: str) -> None:
        if store is not None:
            store.record(
                PipelineRun(
                    run_id=run_id, job=config.job, status=status,
                    duration_s=round(time.perf_counter() - started, 4),
                    rows_ingested=rows, message=message,
                )
            )

    try:
        curve = fetch_carbon_forecast(fetcher)
        validate_carbon_curve(curve)
        if store is not None:
            store.record(
                DataFreshness(
                    run_id=run_id, source="carbon_intensity",
                    fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
                    expected_slots=SLOTS_PER_DAY, actual_slots=len(curve),
                    is_fresh=len(curve) >= SLOTS_PER_DAY,
                )
            )
        slots = build_planning_slots(curve, config.tariff)
        schedule = optimise(
            config.tasks, slots, config.objective, config.weights,
            using_actual_carbon=config.using_actual_carbon,
            tariff_is_manual=getattr(config.tariff, "is_manual", True),
        )
    except Exception as exc:  # noqa: BLE001 - degrade gracefully, never crash the job
        fallback = last_good.load() if last_good is not None else None
        failure_reason = f"{type(exc).__name__}: {exc}"
        if fallback is not None and fallback.input_provenance_state is not None:
            _record_run("fallback", 0, f"{failure_reason}; used last good schedule")
            return PipelineResult(
                run_id,
                "fallback",
                fallback.schedule,
                str(exc),
                schedule_run_id=fallback.schedule_run_id,
                input_provenance_state="last_good_fallback",
                original_input_provenance_state=fallback.input_provenance_state,
                source_observed_at=fallback.source_observed_at,
                source_valid_from=fallback.source_valid_from,
                source_valid_to=fallback.source_valid_to,
                failure_reason=failure_reason,
                reporting_status="not_reportable",
            )
        if fallback is not None:
            failure_reason = f"{failure_reason}; last-good lineage is incomplete"
        _record_run("failed", 0, failure_reason)
        return PipelineResult(
            run_id, "failed", None, str(exc), failure_reason=failure_reason
        )

    if last_good is not None:
        last_good.save(
            LastGoodSchedule(
                schedule=schedule,
                schedule_run_id=run_id,
                input_provenance_state=config.input_provenance_state,
                source_observed_at=config.source_observed_at,
                source_valid_from=config.source_valid_from,
                source_valid_to=config.source_valid_to,
            )
        )
    if store is not None:
        store.record(
            OptimisationQuality(
                run_id=run_id, objective=str(config.objective),
                task_count=len(schedule.tasks),
                total_cost_saving_p=round(schedule.total_cost_saving_p, 3),
                total_carbon_saving_g=round(schedule.total_carbon_saving_g, 3),
                avg_robustness=round(average_robustness(schedule), 3),
                constraint_violations=constraint_violations(config.tasks, schedule),
            )
        )
    _record_run("success", len(curve), "")
    return PipelineResult(
        run_id,
        "success",
        schedule,
        "",
        schedule_run_id=run_id,
        input_provenance_state=config.input_provenance_state,
        original_input_provenance_state=config.input_provenance_state,
        source_observed_at=config.source_observed_at,
        source_valid_from=config.source_valid_from,
        source_valid_to=config.source_valid_to,
        reporting_status=(
            "reportable"
            if all(task.preferred_start is not None for task in config.tasks)
            else "not_reportable"
        ),
    )
