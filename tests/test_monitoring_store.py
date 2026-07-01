from __future__ import annotations

from community_energy_flex.monitoring.store import (
    CsvMonitoringStore,
    DataFreshness,
    OptimisationQuality,
    PipelineRun,
)


def test_records_write_and_read_back(tmp_path):
    store = CsvMonitoringStore(tmp_path)
    store.record(PipelineRun(run_id="r1", job="daily", status="success", duration_s=1.2))
    store.record(PipelineRun(run_id="r2", job="daily", status="failed", duration_s=0.3))

    rows = store.read(PipelineRun)
    assert [r["run_id"] for r in rows] == ["r1", "r2"]
    assert rows[0]["recorded_at"]  # stamped automatically


def test_each_record_type_gets_its_own_file(tmp_path):
    store = CsvMonitoringStore(tmp_path)
    store.record(
        OptimisationQuality(
            run_id="r1", objective="balanced", task_count=3,
            total_cost_saving_p=12.0, total_carbon_saving_g=140.0,
            avg_confidence=0.8, constraint_violations=0,
        )
    )
    store.record(
        DataFreshness(
            run_id="r1", source="carbon_intensity", fetched_at="2026-07-01T00:00:00+00:00",
            expected_slots=48, actual_slots=48, is_fresh=True,
        )
    )
    assert (tmp_path / "optimisation_quality.csv").exists()
    assert (tmp_path / "data_freshness.csv").exists()
    assert store.read(OptimisationQuality)[0]["constraint_violations"] == "0"
