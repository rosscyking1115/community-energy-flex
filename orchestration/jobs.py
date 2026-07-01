"""Dagster jobs. Requires the ``orchestration`` extra."""

from __future__ import annotations

from dagster import AssetSelection, define_asset_job

daily_energy_optimisation_job = define_asset_job(
    name="daily_energy_optimisation_job",
    selection=AssetSelection.all(),
    description="Fetch carbon forecast, optimise the schedule, and write reports.",
)
