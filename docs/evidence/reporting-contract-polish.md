# Reporting-contract polish evidence

## Scope

This note records the post-review polish of the conditional reporting contract.
It retains the Python optimiser as the business-logic owner and uses Dagster
only as a thin orchestration layer.

## Publication boundary

- `CEF_FIXTURE_MODE=1` is deterministic CI/demo mode and uses the labelled
  `sample_input` curve; it needs no live or paid service.
- A live acquisition failure is recorded as unavailable. The core may return a
  last-good schedule, retaining its original schedule run ID, input provenance,
  source observation timestamp, validity interval, and the current failure
  reason. Dagster blocks a fresh action report for fallback, failure, or
  missing provenance.
- A new report is rendered only for a successful run with `live_forecast` or
  `sample_input` provenance. It is labelled forecast/estimated for live input,
  sample-input/illustrative for synthetic input, and never a savings guarantee.
  `conditional ex-post` is reserved for later-curve analysis.

## Consumer boundary

The fixed synthetic fixture reconciles raw baseline/scheduled values through
dbt, API input/output, web input, Power BI seed/export and DAX. dbt remains the
sole owner of reported cost, carbon and peak differences.

## Verified contract guards

- Rows with a missing explicit preferred start, or a non-matching/clamped
  baseline start, become `not_reportable` and retain `NULL` reported metrics.
- dbt rejects a mixed schedule run, provenance state, observation timestamp, or
  validity interval at the reporting grain; it never builds a comma-concatenated
  lineage field.
- The CI fixture job regenerates the synthetic seed, builds/tests DuckDB dbt,
  generates dbt docs, and reconciles the fixture without a live or premium
  service.
- Power BI PBIX refresh remains a separate manual evidence gate; the automated
  checks cover only the seed and DAX source, not the PBIX binary.
