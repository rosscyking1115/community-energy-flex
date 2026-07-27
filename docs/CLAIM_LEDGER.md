# Claim ledger

This ledger defines which public statements the repository can support at the v0.2.1 release (the v0.2.0 credibility-closeout line).

| Claim | Status | Evidence | Required wording / boundary |
|---|---|---|---|
| The engine recommends feasible windows for flexible tasks. | Supported | Optimiser invariant tests and domain constraints | Recommendation, not appliance control. |
| Recommendations are compared with a baseline. | Supported | `preferred_start` baseline implementation and tests | The baseline defaults to a typical 19:00 start, clamped into the chosen window when 19:00 doesn't fit, and is user-settable only under Custom. |
| GB responses can use a live carbon forecast. | Supported, conditional | Carbon provider and API provenance tests | Say “live” only when `is_live_forecast` is true for that response. |
| Northern Ireland has live forecast coverage. | Not supported | Region capability and fallback contract | It uses a labelled EirGrid-derived typical profile. |
| The service is always backed by live data. | Not supported | Explicit fallback paths | Show the source label and fallback reason. |
| The robustness indicator is a calibrated confidence probability. | Not supported | Indicator implementation | Call it robustness; state that it is heuristic and uncalibrated. |
| The synthetic retro workflow measures realised household savings. | Not supported | `schedule_adherence_observed = false` | Call outputs conditional ex-post savings or synthetic stress-test results. |
| Illustrative case-study and dashboard savings are customer outcomes. | Not supported | Synthetic fixtures and generated seeds | Label them synthetic-household demo figures. |
| Excel and PDF action reports are exportable. | Supported | Report serialisation tests | Optional report dependencies must be installed. |
| The deployed web and API surfaces are publicly reachable. | Deployment-time claim | Deployment smoke evidence | Recheck at release time; availability is not guaranteed. |
| The MILP applies a peak-load constraint across tasks that the rule-based optimiser cannot express. | Supported | `optimisation/linear_programming.py` peak-load constraint and `tests/test_linear_programming.py` | A structural claim about the model, never a claim about measured savings. |
| The dbt reporting fact is a type-enforced contract with declared exposures. | Supported | `contract: enforced: true` and the exposure block in `dbt_energy/models/marts/reporting/_schema.yml` | Quote column and exposure counts only after re-counting from the schema file. |
| The Snowflake models have been built against a live account. | Not supported | `warehouse/snowflake_setup.sql` and a second dbt profile target are the only Snowflake artefacts | Say bootstrap DDL and profile target; never “running on Snowflake”. |
| Dagster orchestration is deployed and running on a schedule. | Not supported | `orchestration/` is loadable but has no host; nothing executes `daily_optimisation_run` | Describe orchestration as thin and local; the cron literal is a declaration of intent. |

| The scheduling function this tool performs is unserved by the market. | Not supported | Primary sources checked 2026-07-27 and recorded in [STATUS](STATUS.md): SI 2021/1467 reg. 10, Intelligent Octopus Go, AgileAlert, the Home Assistant Octopus Energy target-timeframe sensors | Do not describe this as an unmet need. Say the function is already served, including free of charge. |
| GB chargepoints are legally required to charge off-peak. | Not supported | SI 2021/1467 reg. 10 mandates a pre-set *default* outside peak hours; the owner may modify or override it, and DSR-agreement units are exempt | Say the default configuration is mandated, never that the behaviour is. |
| Automated demand response achieves ~13% participation versus ~5% manual. | Not supported as worded | Western Power Distribution and Regen (2017) | Those are turn-up response magnitudes against an ongoing time-of-use tariff, not participation rates. Quote them as response magnitudes or not at all. |
| GB carbon-intensity forecast vintages can be reconstructed from the API after the fact. | Not supported | Checked 2026-07-27: all 27 documented intensity endpoints are keyed by target time; a past-dated `fw48h` window replays the settled series rather than the vintage issued then | State that vintages exist only from 2026-07-27 forward, and only for observation times the capture job actually recorded. |
| The forecast-vintage archive shows how wrong the GB forecast is. | Not supported | `research/forecast_vintages/` is a capture job with no evaluation | It accumulates evidence for a future benchmark. Report no forecast-quality result until one has been computed and added here. |
| `observed_at` in the vintage archive is the forecast's issue time. | Not supported | The Carbon Intensity API publishes no issue timestamp | It is capture time, an upper bound on issue time. Horizons derived from it are horizons-from-observation. |

## Review rule

Any new headline number, “live” label, outcome claim, or reliability statement must be added here with a reproducible evidence path before it is published.
