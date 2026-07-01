from __future__ import annotations

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
    run_daily_pipeline,
)


def _config(fetcher):
    return DailyPipelineConfig(
        tasks=sample_tasks(),
        tariff=FlatTariff(unit_rate_p=28.0),
        objective=Objective.BALANCED,
        carbon_fetcher=fetcher,
    )


def test_success_path_records_all_three_monitoring_tables(tmp_path):
    store = CsvMonitoringStore(tmp_path)
    result = run_daily_pipeline(_config(sample_carbon_curve), store=store)

    assert result.status == "success"
    assert result.schedule is not None
    assert store.read(PipelineRun)[0]["status"] == "success"
    assert store.read(OptimisationQuality)[0]["constraint_violations"] == "0"
    assert store.read(DataFreshness)[0]["is_fresh"] == "True"


def test_falls_back_to_last_good_schedule_on_fetch_failure(tmp_path):
    store = CsvMonitoringStore(tmp_path)
    last_good = InMemoryLastGoodStore()

    # First run succeeds and seeds the last-good store.
    ok = run_daily_pipeline(_config(sample_carbon_curve), store=store, last_good=last_good)
    assert ok.status == "success"

    # Second run: the fetch blows up -> pipeline serves the last good schedule.
    def boom():
        raise ConnectionError("carbon API down")

    result = run_daily_pipeline(_config(boom), store=store, last_good=last_good)
    assert result.status == "fallback"
    assert result.schedule is ok.schedule
    assert store.read(PipelineRun)[-1]["status"] == "fallback"


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
