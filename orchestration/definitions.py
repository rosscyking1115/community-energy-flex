"""Dagster entry point. Load with:  dagster dev -m orchestration.definitions
(requires ``pip install '.[orchestration]'``)."""

from __future__ import annotations

from dagster import Definitions, load_assets_from_modules

from orchestration import assets
from orchestration.jobs import daily_energy_optimisation_job
from orchestration.schedules import daily_optimisation_schedule

defs = Definitions(
    assets=load_assets_from_modules([assets]),
    jobs=[daily_energy_optimisation_job],
    schedules=[daily_optimisation_schedule],
)
