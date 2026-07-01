"""Dagster assets - thin wrappers over the tested pipeline core in
``community_energy_flex.pipeline``. Requires the ``orchestration`` extra
(``pip install '.[orchestration]'``). No business logic lives here; that all
sits in plain functions that are unit-tested without a scheduler.
"""

from __future__ import annotations

from dagster import AssetExecutionContext, MetadataValue, asset

from community_energy_flex.data_sources.carbon_intensity import (
    CarbonIntensityClient,
    carbon_curve,
)
from community_energy_flex.demo import sample_carbon_curve, sample_tariffs, sample_tasks
from community_energy_flex.domain.models import SLOTS_PER_DAY, Objective
from community_energy_flex.monitoring.store import CsvMonitoringStore
from community_energy_flex.pipeline.daily import (
    DailyPipelineConfig,
    PickleLastGoodStore,
    run_daily_pipeline,
)
from community_energy_flex.reporting.summary import build_action_summary, format_text_report

# In a later milestone these become Dagster resources/config (region, tariff,
# per-user tasks). For now the sample data keeps the graph runnable end to end.
_STORE = CsvMonitoringStore("monitoring_data")
_LAST_GOOD = PickleLastGoodStore("monitoring_data/last_good_schedule.pkl")


@asset(description="Half-hourly carbon-intensity forecast for the planning day.")
def carbon_forecast_curve(context: AssetExecutionContext) -> list[float]:
    try:
        slots = CarbonIntensityClient().regional_forecast_by_postcode("BS1")
        curve = carbon_curve(slots, num_slots=SLOTS_PER_DAY)
        context.add_output_metadata({"source": "live", "slots": len(curve)})
    except Exception as exc:  # noqa: BLE001 - sample fallback keeps the demo alive
        context.log.warning(f"Live carbon fetch failed ({exc}); using sample curve.")
        curve = sample_carbon_curve()
        context.add_output_metadata({"source": "sample", "slots": len(curve)})
    return curve


@asset(description="Optimised schedule with baseline, confidence and monitoring.")
def daily_schedule(context: AssetExecutionContext, carbon_forecast_curve: list[float]):
    config = DailyPipelineConfig(
        tasks=sample_tasks(),
        tariff=sample_tariffs()["Agile-style"],
        objective=Objective.BALANCED,
        carbon_fetcher=lambda: carbon_forecast_curve,
    )
    result = run_daily_pipeline(config, store=_STORE, last_good=_LAST_GOOD)
    context.add_output_metadata(
        {"status": result.status, "run_id": result.run_id}
    )
    return result


@asset(description="Portable action report (text) for households/managers.")
def action_report(context: AssetExecutionContext, daily_schedule) -> str:
    if daily_schedule.schedule is None:
        context.log.error("No schedule available; skipping report.")
        return ""
    summary = build_action_summary(daily_schedule.schedule)
    report = format_text_report(summary)
    context.add_output_metadata(
        {
            "cost_saving_gbp": round(summary.total_cost_saving_pounds, 2),
            "carbon_saving_kg": round(summary.total_carbon_saving_kg, 2),
            "preview": MetadataValue.md(f"```\n{report}\n```"),
        }
    )
    return report
