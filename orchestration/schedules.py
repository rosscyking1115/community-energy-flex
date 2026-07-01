"""Dagster schedules. Requires the ``orchestration`` extra."""

from __future__ import annotations

from dagster import ScheduleDefinition

from orchestration.jobs import daily_energy_optimisation_job

# Run once a day, early morning, to plan the coming day. A finer hourly forecast
# refresh can be added as demand-forecasting comes online in Milestone C.
daily_optimisation_schedule = ScheduleDefinition(
    job=daily_energy_optimisation_job,
    cron_schedule="30 5 * * *",
    execution_timezone="Europe/London",
    name="daily_optimisation_run",
)
