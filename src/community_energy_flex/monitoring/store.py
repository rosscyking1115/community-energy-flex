"""Monitoring records and a CSV-backed store.

Deliberately dependency-light: it appends rows to CSV files so run evidence
survives locally with zero infrastructure. On Snowflake these become the
MONITORING.PIPELINE_RUNS / OPTIMISATION_QUALITY / DATA_FRESHNESS tables; the
record shapes here match those columns.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class PipelineRun:
    run_id: str
    job: str
    status: str  # "success" | "failed" | "fallback"
    duration_s: float
    rows_ingested: int = 0
    message: str = ""
    recorded_at: str = ""


@dataclass(frozen=True)
class OptimisationQuality:
    run_id: str
    objective: str
    task_count: int
    total_cost_saving_p: float
    total_carbon_saving_g: float
    avg_confidence: float
    constraint_violations: int
    recorded_at: str = ""


@dataclass(frozen=True)
class DataFreshness:
    run_id: str
    source: str
    fetched_at: str
    expected_slots: int
    actual_slots: int
    is_fresh: bool
    recorded_at: str = ""


_FILES = {
    PipelineRun: "pipeline_runs.csv",
    OptimisationQuality: "optimisation_quality.csv",
    DataFreshness: "data_freshness.csv",
}


class CsvMonitoringStore:
    """Appends monitoring records to per-type CSV files under ``base_dir``."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, record) -> Path:
        return self.base_dir / _FILES[type(record)]

    def record(self, record) -> None:
        if type(record) not in _FILES:
            raise TypeError(f"unknown monitoring record type {type(record)!r}")
        # Stamp recorded_at at write time if the caller left it blank.
        data = asdict(record)
        if not data.get("recorded_at"):
            data["recorded_at"] = _utc_now()

        path = self._path(record)
        write_header = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=[f.name for f in fields(record)])
            if write_header:
                writer.writeheader()
            writer.writerow(data)

    def read(self, record_type) -> list[dict]:
        path = self.base_dir / _FILES[record_type]
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
