"""Dagster assets - thin wrappers over the tested pipeline core in
``community_energy_flex.pipeline``. Requires the ``orchestration`` extra
(``pip install '.[orchestration]'``). No business logic lives here; that all
sits in plain functions that are unit-tested without a scheduler.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from dagster import MetadataValue, asset

from community_energy_flex.data_sources.carbon_intensity import (
    CarbonIntensityClient,
    carbon_curve,
)
from community_energy_flex.demo import sample_carbon_curve, sample_tariffs, sample_tasks
from community_energy_flex.domain.models import SLOTS_PER_DAY, Objective
from community_energy_flex.monitoring.store import CsvMonitoringStore
from community_energy_flex.pipeline.daily import (
    DailyPipelineConfig,
    DataValidationError,
    JsonLastGoodStore,
    run_daily_pipeline,
)
from community_energy_flex.reporting.summary import (
    ReportingContext,
    build_action_summary,
    format_text_report,
    report_basis_for_input_provenance,
)

# In a later milestone these become Dagster resources/config (region, tariff,
# per-user tasks). For now the sample data keeps the graph runnable end to end.
_STORE = CsvMonitoringStore("monitoring_data")
_LAST_GOOD = JsonLastGoodStore("monitoring_data/last_good_schedule.json")

AcceptedProvenance = Literal["live_forecast", "last_good_fallback", "sample_input"]


@dataclass(frozen=True)
class ForecastAssetValue:
    """Acquisition result passed to Dagster only; optimisation stays in the core."""

    curve: list[float] | None
    provenance_state: AcceptedProvenance | Literal["unavailable"]
    failure_reason: str | None = None
    source_observed_at: str | None = None
    source_valid_from: str | None = None
    source_valid_to: str | None = None


def render_publishable_action_report(result, forecast: ForecastAssetValue) -> str | None:
    """Render only a fresh, provenance-qualified successful run.

    A failed run or a served last-good schedule remains observable in Dagster,
    but cannot overwrite a fresh action report.
    """
    if result.status != "success" or result.schedule is None:
        return None
    if forecast.provenance_state not in {"live_forecast", "sample_input"}:
        return None
    return format_text_report(
        build_action_summary(result.schedule),
        reporting_context=ReportingContext(
            basis=report_basis_for_input_provenance(forecast.provenance_state),
            status=result.reporting_status,
            reason=(
                "No explicit preferred start was supplied; cost and carbon differences "
                "are unavailable."
            ),
        ),
    )


@asset(description="Half-hourly carbon input with explicit live/sample/unavailable provenance.")
def carbon_forecast_curve(context):
    if os.getenv("CEF_FIXTURE_MODE") == "1":
        curve = sample_carbon_curve()
        context.add_output_metadata({"source": "sample_input", "slots": len(curve)})
        return ForecastAssetValue(curve, "sample_input")
    try:
        slots = CarbonIntensityClient().regional_forecast_by_postcode("BS1")
        curve = carbon_curve(slots, num_slots=SLOTS_PER_DAY)
        source_observed_at = datetime.now(UTC).isoformat()
        context.add_output_metadata({"source": "live_forecast", "slots": len(curve)})
        return ForecastAssetValue(
            curve,
            "live_forecast",
            source_observed_at=source_observed_at,
            source_valid_from=slots[0].start.isoformat() if slots else None,
            source_valid_to=slots[-1].end.isoformat() if slots else None,
        )
    except Exception as exc:  # noqa: BLE001 - sample fallback keeps the demo alive
        context.log.error(f"Live carbon fetch failed ({exc}); no fresh forecast is available.")
        context.add_output_metadata({"source": "unavailable", "failure": type(exc).__name__})
        return ForecastAssetValue(None, "unavailable", type(exc).__name__)


@asset(description="Optimised schedule with baseline, robustness and monitoring.")
def daily_schedule(context, carbon_forecast_curve: ForecastAssetValue):
    def unavailable_curve() -> list[float]:
        raise DataValidationError(
            carbon_forecast_curve.failure_reason or "forecast provenance missing"
        )

    config = DailyPipelineConfig(
        tasks=sample_tasks(),
        tariff=sample_tariffs()["Agile-style"],
        objective=Objective.BALANCED,
        carbon_fetcher=(lambda: carbon_forecast_curve.curve)
        if carbon_forecast_curve.curve is not None
        else unavailable_curve,
        input_provenance_state=(
            carbon_forecast_curve.provenance_state
            if carbon_forecast_curve.provenance_state in {"live_forecast", "sample_input"}
            else "sample_input"
        ),
        source_observed_at=carbon_forecast_curve.source_observed_at,
        source_valid_from=carbon_forecast_curve.source_valid_from,
        source_valid_to=carbon_forecast_curve.source_valid_to,
    )
    result = run_daily_pipeline(config, store=_STORE, last_good=_LAST_GOOD)
    context.add_output_metadata(
        {
            "status": result.status,
            "run_id": result.run_id,
            "schedule_run_id": result.schedule_run_id or "",
            "provenance_state": result.input_provenance_state or "unavailable",
            "original_input_provenance_state": result.original_input_provenance_state or "",
            "source_observed_at": result.source_observed_at or "",
            "source_valid_from": result.source_valid_from or "",
            "source_valid_to": result.source_valid_to or "",
            "failure_reason": result.failure_reason or "",
        }
    )
    return result


@asset(description="Portable action report (text) for households/managers.")
def action_report(context, daily_schedule, carbon_forecast_curve: ForecastAssetValue) -> str:
    report = render_publishable_action_report(daily_schedule, carbon_forecast_curve)
    if report is None:
        context.log.warning(
            "Fresh action report blocked: run failed/fell back or provenance is missing."
        )
        context.add_output_metadata(
            {
                "publication_status": "blocked",
                "schedule_run_id": daily_schedule.schedule_run_id or "",
                "provenance_state": daily_schedule.input_provenance_state or "unavailable",
                "original_input_provenance_state": (
                    daily_schedule.original_input_provenance_state or ""
                ),
                "failure_reason": daily_schedule.failure_reason or "",
            }
        )
        return ""
    summary = build_action_summary(daily_schedule.schedule)
    context.add_output_metadata(
        {
            "publication_status": "published",
            "provenance_state": carbon_forecast_curve.provenance_state,
            "conditional_cost_difference_gbp": round(summary.total_cost_saving_pounds, 2),
            "conditional_carbon_difference_kg": round(summary.total_carbon_saving_kg, 2),
            "preview": MetadataValue.md(f"```\n{report}\n```"),
        }
    )
    return report
