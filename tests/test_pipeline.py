from __future__ import annotations

import json
from dataclasses import asdict, replace

from community_energy_flex.data_sources.tariffs import FlatTariff
from community_energy_flex.demo import sample_carbon_curve, sample_tasks
from community_energy_flex.domain.models import Objective
from community_energy_flex.monitoring.store import (
    CsvMonitoringStore,
    DataFreshness,
    OptimisationQuality,
    PipelineRun,
)
from community_energy_flex.pipeline.daily import (
    DailyPipelineConfig,
    InMemoryLastGoodStore,
    JsonLastGoodStore,
    run_daily_pipeline,
)


def _config(fetcher):
    return DailyPipelineConfig(
        tasks=sample_tasks(),
        tariff=FlatTariff(unit_rate_p=28.0),
        objective=Objective.BALANCED,
        carbon_fetcher=fetcher,
        input_provenance_state="live_forecast",
        source_observed_at="2026-07-03T12:00:00+00:00",
        source_valid_from="2026-07-04T00:00:00+00:00",
        source_valid_to="2026-07-05T00:00:00+00:00",
    )


def test_success_path_records_all_three_monitoring_tables(tmp_path):
    store = CsvMonitoringStore(tmp_path)
    result = run_daily_pipeline(_config(sample_carbon_curve), store=store)

    assert result.status == "success"
    assert result.schedule is not None
    assert store.read(PipelineRun)[0]["status"] == "success"
    assert store.read(OptimisationQuality)[0]["constraint_violations"] == "0"
    assert store.read(DataFreshness)[0]["is_fresh"] == "True"


def test_success_without_explicit_preferred_starts_is_not_reportable(tmp_path):
    config = _config(sample_carbon_curve)
    config.tasks = [replace(task, preferred_start=None) for task in config.tasks]

    result = run_daily_pipeline(config, store=CsvMonitoringStore(tmp_path))

    assert result.status == "success"
    assert result.reporting_status == "not_reportable"


def test_falls_back_to_last_good_schedule_on_fetch_failure(tmp_path):
    store = CsvMonitoringStore(tmp_path)
    last_good = InMemoryLastGoodStore()

    # First run succeeds and seeds the last-good store.
    ok = run_daily_pipeline(_config(sample_carbon_curve), store=store, last_good=last_good)
    assert ok.status == "success"
    assert ok.schedule_run_id == ok.run_id

    # Second run: the fetch blows up -> pipeline serves the last good schedule.
    def boom():
        raise ConnectionError("carbon API down")

    result = run_daily_pipeline(_config(boom), store=store, last_good=last_good)
    assert result.status == "fallback"
    assert result.schedule is ok.schedule
    assert result.schedule_run_id == ok.run_id
    assert result.input_provenance_state == "last_good_fallback"
    assert result.original_input_provenance_state == "live_forecast"
    assert result.source_observed_at == "2026-07-03T12:00:00+00:00"
    assert result.source_valid_from == "2026-07-04T00:00:00+00:00"
    assert result.source_valid_to == "2026-07-05T00:00:00+00:00"
    assert result.failure_reason == "ConnectionError: carbon API down"
    assert store.read(PipelineRun)[-1]["status"] == "fallback"


def test_json_last_good_store_round_trips_across_restarts(tmp_path):
    """The on-disk store must reload an identical schedule (and survive a fresh
    process) so a fallback works after a restart - without pickle."""
    store = JsonLastGoodStore(tmp_path / "last_good.json")
    assert store.load() is None  # nothing saved yet

    saved = run_daily_pipeline(_config(sample_carbon_curve), last_good=store).schedule
    assert saved is not None

    # A brand-new store pointed at the same file simulates a restart.
    reloaded = JsonLastGoodStore(tmp_path / "last_good.json").load()
    assert reloaded is not None
    assert reloaded.schedule_run_id
    assert reloaded.input_provenance_state == "live_forecast"
    assert reloaded.source_observed_at == "2026-07-03T12:00:00+00:00"
    assert reloaded.schedule.objective == saved.objective
    assert [t.task_id for t in reloaded.schedule.tasks] == [t.task_id for t in saved.tasks]
    assert reloaded.schedule.total_cost_saving_p == saved.total_cost_saving_p
    assert reloaded.schedule.total_carbon_saving_g == saved.total_carbon_saving_g


def test_hard_failure_when_no_last_good_available(tmp_path):
    store = CsvMonitoringStore(tmp_path)

    def short_curve():
        return [100.0] * 10  # fails validation (needs 48)

    result = run_daily_pipeline(
        _config(short_curve), store=store, last_good=InMemoryLastGoodStore()
    )
    assert result.status == "failed"
    assert result.schedule is None
    assert store.read(PipelineRun)[-1]["status"] == "failed"


def test_legacy_schedule_only_last_good_is_not_relabelled_or_served(tmp_path):
    path = tmp_path / "legacy_last_good.json"
    saved = run_daily_pipeline(_config(sample_carbon_curve)).schedule
    assert saved is not None
    legacy_payload = {
        "objective": str(saved.objective),
        "tasks": [asdict(task) for task in saved.tasks],
    }
    path.write_text(
        json.dumps(legacy_payload),
        encoding="utf-8",
    )

    result = run_daily_pipeline(
        _config(lambda: (_ for _ in ()).throw(ConnectionError("carbon API down"))),
        last_good=JsonLastGoodStore(path),
    )

    assert result.status == "failed"
    assert result.schedule is None
    assert result.failure_reason is not None
    assert "lineage is incomplete" in result.failure_reason
