# Claim ledger

This ledger defines which public statements the repository can support at the v0.2.0 credibility closeout.

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

## Review rule

Any new headline number, “live” label, outcome claim, or reliability statement must be added here with a reproducible evidence path before it is published.
