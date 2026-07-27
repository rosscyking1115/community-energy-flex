"""Dagster schedules. Requires the ``orchestration`` extra."""

from __future__ import annotations

from dagster import ScheduleDefinition

from orchestration.jobs import daily_energy_optimisation_job

# Run once a day, early morning, to plan the coming day. A finer hourly forecast
# refresh can be added as demand-forecasting comes online in Milestone C.
#
# Posture on default_status: left unset deliberately. Nothing hosts this code -
# there is no Dagster deployment, so no daemon ever evaluates this cron and the
# schedule cannot be running. Pinning it to STOPPED would imply a live instance
# that had been switched off. The honest disclosure is that orchestration here is
# local-only, and it is stated in docs/DAGSTER_PIPELINE.md and the claim ledger
# rather than encoded as a flag on an object nothing loads. If this is ever
# deployed, set default_status=DefaultScheduleStatus.STOPPED and turn it on
# explicitly.
daily_optimisation_schedule = ScheduleDefinition(
    job=daily_energy_optimisation_job,
    cron_schedule="30 5 * * *",
    execution_timezone="Europe/London",
    name="daily_optimisation_run",
)
