# Project status

**Release:** v0.2.1 (continues the v0.2.0 credibility closeout)  
**State:** feature frozen  
**Product and repository name:** Community Energy Flex

Community Energy Flex is a portfolio decision-support demonstrator for scheduling flexible electricity demand. It is not connected to customer meters or appliances and does not claim measured operational savings.

## Capability status matrix

| Capability | Status | Evidence / boundary |
|---|---|---|
| Rule-based scheduling | running | Core optimiser and invariant tests |
| LP/MILP scheduling | built-local | Optional PuLP path and parity/invariant tests |
| Next.js web client | running | Public Vercel deployment; dated reachability recorded in the release evidence |
| FastAPI service | running | Public Fly.io deployment; health, OpenAPI, forecast, and optimise smoke recorded at release |
| GB Carbon Intensity forecast | running with fallback | Response provenance distinguishes live forecast from labelled GB sample fallback |
| Northern Ireland carbon | synthetic-demo | Labelled EirGrid-derived typical profile; not a live same-day forecast |
| Octopus Agile prices | running for configured GB regions | Live only when retrieval succeeds; unsupported/unpublished states are explicit |
| Flat and Economy 7 tariffs | running | User-entered, never labelled live |
| Robustness indicator | evidence-only | Transparent heuristic with parity tests; not calibrated |
| Conditional ex-post retro | synthetic-demo | Constructed curves; no observed adherence or customer outcome |
| Text, Excel, and PDF reports | built-local | Serialisation tests; optional report dependencies |
| dbt/Snowflake/Dagster/Power BI | built-local / synthetic-demo | Reproducible synthetic reporting path, not a connected production warehouse |
| Smart-meter ingestion and appliance control | designed-not-connected | Explicitly out of scope |
| Forecast-vintage archive | capturing since 2026-07-27 | Capture job only; no evaluation and no result yet |
| Forecast-vintage benchmark | planned | Needs enough captured vintages to cover horizons and seasons |

Python tests cover optimisation, API validation/provenance, fallback behaviour, retro semantics, and report exports. CI also compiles the web client.

## Evidence boundary

All case-study, dashboard, and retro figures are synthetic-household demonstrations. Conditional ex-post analysis asks what the scheduled and baseline windows would have consumed under an altered curve. It does not observe schedule adherence and must not be described as realised customer savings.

See [CLAIM_LEDGER.md](CLAIM_LEDGER.md) and the [closeout evidence pack](evidence/credibility-closeout/).

## Product decision, 2026-07-27: stop developing the product

**The product side of this repository is stopped, not paused.** An evidence scan on
2026-07-27 concluded that the function this tool performs has already been absorbed by the
market and, in part, by statute. The evidence below was re-checked against primary sources on
the same date before being recorded here.

| Finding | What was verified, and how |
|---|---|
| The largest flexible household load already ships pre-configured to avoid peak | The Electric Vehicles (Smart Charge Points) Regulations 2021 (SI 2021/1467), reg. 10, require a relevant charge point to have "pre-set default charging hours which are outside of peak hours". Reg. 2 defines peak hours as 8am–11am **and** 4pm–10pm on weekdays. The first tranche came into force 30 June 2022. **Qualification:** this mandates a *default*, not behaviour — the owner may accept, remove or modify the hours on first use and may override the default mode at any time, and charge points sold under a demand-side-response agreement are exempt. |
| Supplier tariffs remove the scheduling problem rather than solving it | Intelligent Octopus Go gives a fixed off-peak window (typically 23:30–05:30) and Octopus itself dispatches the charge against a user-stated target. From 2026 a six-hour cap and a "Charge Cap" toggle apply. The household states an outcome; the supplier does the scheduling. |
| The recommendation artefact already exists, free | AgileAlert (agilealert.co.uk) publishes regional half-hourly Agile prices with carbon intensity, names dishwasher, washing machine, tumble dryer and EV windows, and offers daily email alerts at no cost. It is built on the Octopus public API and the Carbon Intensity API — **the same two sources this repository uses**. |
| Open-source tooling does the same thing *and* actuates | The Home Assistant Octopus Energy integration's target-rate / target-timeframe binary sensors compute the cheapest continuous or intermittent window in a 24-hour period and switch on while it is active, so an automation can drive the appliance directly. |
| The market rewards actuation over recommendation | Western Power Distribution and Regen (2017) measured a 13% turn-up response under automated control against an ongoing time-of-use tariff, versus 5% under manual control. **Correction to how this is often quoted:** those are response magnitudes, not participation rates. |

The last row is the decisive one. This repository is a recommender, and appliance control is
out of scope by design — see the capability matrix above. The gap between 13% and 5% is the
gap between what the market wants and what this tool is.

**In scope from 2026-07-27:** the forecast-vintage archive in
[`research/forecast_vintages/`](../research/forecast_vintages/), which is a capture job
answering a research question, not a product. It is in scope only because the data it collects
is non-reproducible after the fact.

**Out of scope from 2026-07-27:** new product features, user acquisition, growth surfaces,
and any work whose justification is adoption.

Stopping for a stated and evidenced reason is the decision being recorded here. Nothing in the
capability matrix above is withdrawn, and no existing claim changes.

## Freeze policy

After v0.2.0, in-scope maintenance is limited to:

- correctness and regression fixes;
- security and dependency maintenance;
- deployment reliability;
- documentation corrections that preserve the evidence boundary.

New product features, calibrated performance claims, and customer-outcome language remain out of scope until supported by observed data and a new project decision.
