from __future__ import annotations

from dataclasses import replace

import pytest

pytest.importorskip("dagster")

from dagster import materialize  # noqa: E402
from orchestration.assets import (  # noqa: E402
    ForecastAssetValue,
    carbon_forecast_curve,
    render_publishable_action_report,
)

from community_energy_flex.data_sources.tariffs import FlatTariff
from community_energy_flex.demo import sample_carbon_curve, sample_tasks
from community_energy_flex.domain.models import Objective
from community_energy_flex.pipeline.daily import DailyPipelineConfig, run_daily_pipeline


def _successful_result():
    return run_daily_pipeline(
        DailyPipelineConfig(
            tasks=sample_tasks(),
            tariff=FlatTariff(unit_rate_p=28.0),
            objective=Objective.BALANCED,
            carbon_fetcher=sample_carbon_curve,
        )
    )


def test_action_report_publishes_only_success_with_accepted_provenance():
    result = _successful_result()
    report = render_publishable_action_report(
        result, ForecastAssetValue(sample_carbon_curve(), "sample_input")
    )

    assert report is not None
    assert "illustrative" in report.lower()
    assert "sample-input" in report.lower()
    assert "conditional ex-post" not in report.lower()
    assert "not a savings guarantee" in report.lower()


def test_live_forecast_report_uses_forecast_not_ex_post_language():
    report = render_publishable_action_report(
        _successful_result(), ForecastAssetValue(sample_carbon_curve(), "live_forecast")
    )

    assert report is not None
    assert "forecast planning result" in report.lower()
    assert "conditional ex-post" not in report.lower()


def test_dagster_report_fails_closed_without_explicit_preferred_start():
    result = run_daily_pipeline(
        DailyPipelineConfig(
            tasks=[replace(task, preferred_start=None) for task in sample_tasks()],
            tariff=FlatTariff(unit_rate_p=28.0),
            objective=Objective.BALANCED,
            carbon_fetcher=sample_carbon_curve,
        )
    )
    report = render_publishable_action_report(
        result, ForecastAssetValue(sample_carbon_curve(), "sample_input")
    )

    assert report is not None
    assert "not reportable" in report.lower()
    assert "cost difference:" not in report.lower()


@pytest.mark.parametrize("status", ["failed", "fallback"])
def test_failed_or_last_good_run_cannot_publish_a_fresh_report(status):
    result = _successful_result()
    blocked = result.__class__(result.run_id, status, result.schedule, "source failed")

    assert render_publishable_action_report(
        blocked, ForecastAssetValue(None, "unavailable", "upstream_timeout")
    ) is None


def test_missing_required_provenance_cannot_publish_a_fresh_report():
    assert render_publishable_action_report(
        _successful_result(), ForecastAssetValue(sample_carbon_curve(), "unavailable")
    ) is None


def test_ci_fixture_mode_materializes_without_a_live_api_call(monkeypatch):
    monkeypatch.setenv("CEF_FIXTURE_MODE", "1")

    result = materialize([carbon_forecast_curve])

    assert result.success
    output = result.output_for_node("carbon_forecast_curve")
    assert output.provenance_state == "sample_input"
    assert len(output.curve or []) == 48
