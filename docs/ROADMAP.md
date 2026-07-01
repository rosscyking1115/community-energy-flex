# Roadmap — 3-month build

Governing rule: each heavy tool earns its place with a real job, and there is a
usable tool early so quality compounds. Build on **DuckDB first**; Snowflake is a
second dbt target, not a rewrite.

## Milestone A — usable vertical slice ✅ (in progress)

Carbon Intensity client · tariff models (flat / Economy 7 / time-of-use) ·
rule-based optimiser (cheapest / lowest-carbon / balanced / avoid-peak) with
baseline, confidence, caveats · Streamlit app · text/Excel/PDF reports ·
dbt-on-DuckDB scaffold (staging → half-hourly options mart) · test suite · CI.
**The three definitions are pinned** in [METHODOLOGY.md](METHODOLOGY.md).

## Milestone B — warehouse, orchestration, quality

Snowflake as a second dbt target · domain-constraint dbt tests + freshness ·
Dagster daily pipeline (fetch → load → dbt → optimise → report) + schedules +
keep-last-good-schedule on failure · **forecast-vs-actual retro loop** ·
`MONITORING.*` run tracking (not MLflow yet).

## Milestone C — forecasting, real optimisation, BI

Weather (Open-Meteo) → demand forecast (baseline → XGBoost) → **MLflow now earns
its place** · **LP/MILP optimiser** (pulp/ortools): battery, EV-by-deadline,
peak-load, no-overlap · Octopus Agile tariff · Power BI: **star-schema review
gate** on the `RPT_*` marts, then 5 pages, then DAX optimisation.

## Milestone D — community, auth, pilot-readiness

Community aggregation + comparison marts · real OIDC auth + Snowflake row-access
policies + audit logging · **design + accessibility pass** on Streamlit and the
PDF · runbook, methodology/caveat docs · real case study evaluated through the
retro loop · full code-review (context-isolation) gating release.

## Skill touchpoints

| Phase | Skills applied |
|---|---|
| A (scaffold) | `create-readme`; `tdd` (independent expected values) on the optimiser |
| B | `improve-codebase-architecture` on `optimisation/` + `reporting/`; `github-actions-docs` for CI |
| C | `power-bi-model-design-review` → `power-bi-dax-optimization` |
| D | `frontend-design` + `web-design-guidelines`; `/code-review` with context-isolation |

**Out of scope (all milestones):** direct appliance control, live grid ops,
trading, guaranteed savings, Tableau.
