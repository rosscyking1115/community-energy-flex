# Metric catalogue

All metrics below are planning comparisons. They use synthetic-household inputs
unless a future source is explicitly recorded otherwise. They are illustrative,
conditional ex-post where a later curve is used, and not a savings guarantee.

| Metric | Unit and sign | Definition | Owner | Publish condition |
|---|---|---|---|---|
| Scheduled cost | pence; lower is better | Cost of the selected feasible schedule | optimiser raw output | Accepted source/run provenance |
| Baseline cost | pence | Cost at the task's explicit preferred start | optimiser raw output | Accepted source/run provenance |
| Conditional cost difference | pence; baseline minus scheduled | dbt reporting difference, not realised customer savings | dbt | `reporting_status = reportable` |
| Scheduled carbon | grams CO2e; lower is better | Carbon for the selected feasible schedule | optimiser raw output | Accepted source/run provenance |
| Conditional carbon difference | grams CO2e; baseline minus scheduled | dbt reporting difference; conditional ex-post only for later-curve analysis | dbt | `reporting_status = reportable` |
| Peak slots avoided | half-hour slots; baseline overlap minus scheduled overlap | Reported peak difference | dbt | `reporting_status = reportable` |
| Robustness indicator | unitless 0–1 | Heuristic input-sensitivity indicator; not a probability | Python core | Always caveated |

An absent preferred start, or a baseline start that does not equal the explicit
preferred start, makes the row `not_reportable`; all reported cost, carbon and
peak differences remain `NULL`. Reporting never substitutes or clamps a
preferred start. Missing inputs are never converted to zero.

`last_good_fallback` identifies a reused schedule, not a fresh forecast. It
retains the original schedule run ID, original input provenance, source
observation timestamp and validity interval, plus the new failure reason.
Fresh action-report publication remains blocked for this state.
Legacy schedule-only records have unknown lineage and are refused rather than
being relabelled as a provenance state.
