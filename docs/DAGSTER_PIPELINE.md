# Dagster pipeline

Dagster owns the daily workflow. **The logic lives in plain functions**
(`src/community_energy_flex/pipeline/daily.py`) that are unit-tested without a
scheduler; the Dagster layer in `orchestration/` is a thin wrapper. This keeps
the pipeline testable and the orchestration swappable.

## Run it

```bash
pip install -e ".[orchestration,warehouse]"
dagster dev -m orchestration.definitions      # opens the Dagster UI
```

## Asset graph

```
carbon_forecast_curve  ──►  daily_schedule  ──►  action_report
   (live API or sample)     (run_daily_pipeline)   (text report + metadata)
```

- **carbon_forecast_curve** — pulls the regional forecast; falls back to the
  sample curve if the API is unreachable.
- **daily_schedule** — runs `run_daily_pipeline`: validate → optimise → record
  monitoring, saving the result as the *last good schedule*.
- **action_report** — renders the portable report and surfaces savings as asset
  metadata in the UI.

## Schedule

`daily_optimisation_run` — `30 5 * * *` Europe/London, to plan the coming day.

## Failure handling

Built into the pipeline core, so it holds whether run by Dagster or directly:

- **Fetch/validation fails** → serve the **last good schedule** (`status="fallback"`)
  rather than leaving users with nothing; the failure is recorded.
- **Forecast missing for tomorrow** (curve shorter than 48 slots) → `DataValidationError`.
- **No last good available** → `status="failed"`, schedule is `None`, run recorded.
- Every run writes to the monitoring store (`pipeline_runs`, `optimisation_quality`,
  `data_freshness`) — the MVP stand-in for the plan's `MONITORING.*` tables.

## Why not MLflow yet

A deterministic rule-based optimiser has no model to track experiments for. Run
evidence goes to the monitoring store instead. MLflow joins in Milestone C, when
the demand-forecast model gives it a real job.
