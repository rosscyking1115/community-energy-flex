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
 (live/sample/unavailable)  (Python core)       (guarded fresh publication)
```

- **carbon_forecast_curve** — pulls the regional forecast and labels its
  provenance. `CEF_FIXTURE_MODE=1` selects deterministic `sample_input` for
  CI/demo runs; a live failure is `unavailable`, never silently relabelled.
- **daily_schedule** — runs `run_daily_pipeline`: validate → optimise → record
  monitoring, saving the result as the *last good schedule*.
- **action_report** — renders only a successful, provenance-qualified fresh
  report. Failed, unavailable, and last-good fallback runs remain visible in
  Dagster but cannot publish a fresh report.

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
