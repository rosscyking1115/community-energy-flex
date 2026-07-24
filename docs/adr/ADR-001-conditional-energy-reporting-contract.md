# ADR-001: Conditional energy reporting contract

**Status:** Accepted — E-CONTRACT contract. The bounded consumer repair is locally implemented and requires independent Reviewer/QA re-check; this record does not authorise PBIX replacement, commit, deployment, publication, or a public claim change.<br>
**Date:** 2026-07-23<br>
**Scope:** dbt reporting, API/web/report consumers, Power BI, and Dagster hand-off. The optimiser's feasibility and schedule-selection logic is out of scope.

## Context

The product produces a one-day, half-hourly recommendation from task constraints, a tariff, and a carbon curve. It also has a synthetic Power BI path. Those paths share cost, carbon, peak, and saving terms without one reporting contract.

The decision supported is: *which feasible schedule should a planner inspect, given declared input provenance and an explicit preferred-start comparison?* This is not evidence of appliance operation, household behaviour, or realised customer savings.

## Decision

### Grains and keys

| Asset | Grain and key | Contract |
|---|---|---|
| Planning options | One 48-slot planning day; `(planning_date, slot_index)`, `slot_index` `0..47` | A slot is a nominal 30-minute interval in `[00:00, 24:00)` of the declared planning day. Retain source timezone and valid-for interval. Do not silently pad or relabel a DST/source-period mismatch as a complete 48-slot forecast. |
| Reporting fact | One row per `(reporting_date, community_id, household_id, device_type)` | `fct_daily_savings` is a daily device roll-up, not a task event log. Same-device tasks must be aggregated upstream before writing the fact. `schedule_run_id` is an attribute, not a second grain. |
| Reporting aggregates | `rpt_daily_savings`: date; `rpt_monthly_community_savings`: community × calendar month | Aggregate the fact only. Do not recalculate a baseline or select a schedule. |

`planning_date` is the intended schedule date, not retrieval or report-generation date. The metrics compare baseline and selected task slots in that planning day; they are not observed consumption windows.

### Ownership and metrics

The optimiser owns task validity, feasible placements, objective scoring, schedule selection, and raw baseline/selected placement values. dbt owns the reporting transformation: validate attributable optimiser output, aggregate it to the reporting grain, calculate reported differences, and expose the facts. API, web, Power BI, and Dagster must not independently recalculate a schedule or baseline.

| Metric | Formula, unit, sign, and time window | Null policy | Reporting owner |
|---|---|---|---|
| `cost_saving_p` | `baseline_cost_p - scheduled_cost_p`, pence. Positive means selected estimated task unit-rate cost is lower than the explicit preferred-start baseline; negative remains negative. Standing charges excluded. | `NULL` if explicit preferred start, selected schedule, tariff curve, or named price provenance is absent/invalid. Zero is a valid calculated zero. | dbt; optimiser supplies placement costs. |
| `carbon_saving_g` | `baseline_carbon_g - scheduled_carbon_g`, grams CO2e. Positive means selected estimated grid carbon is lower; negative remains negative. | `NULL` if explicit preferred start, selected schedule, carbon curve, or named carbon provenance is absent/invalid. Zero is a valid calculated zero. | dbt; optimiser supplies placement carbon. |
| `peak_slots_avoided` | `baseline_peak_slot_count - scheduled_peak_slot_count`, half-hour slots. Positive means fewer selected-plan slots overlap the declared peak set; negative means added overlap. The current declared set is slots `34..37` (`17:00–19:00`). It is a positional count, not measured kW, demand, or system-peak reduction. | `NULL` if either window, the peak-set version, or provenance is absent/invalid. Zero is equal valid overlap. Never clamp. | dbt from optimiser windows and the declared peak set. |

The baseline is the task's **explicit preferred start**. It is neither a population counterfactual nor an inferred "usual" time. If that start is absent or cannot be evaluated as a feasible baseline, emit `reporting_status = 'not_reportable'` with all three metrics `NULL`, or reject the input and record the reason. Never substitute `earliest_start`, a default evening anchor, or a clamped substitute while retaining the preferred-start label.

Aggregates include only `reporting_status = 'reportable'`, surface excluded-row counts, and never display a missing metric as zero.

### Provenance and minimum lineage

Every reportable fact must retain, directly or through an immutable schedule-run reference:

- `planning_date`, `schedule_run_id`, task/device keys, selected and baseline windows, objective, and peak-set version;
- `baseline_cost_p`, `scheduled_cost_p`, `baseline_carbon_g`, and `scheduled_carbon_g`, to reconcile reported differences;
- carbon and price identifiers/labels, retrieval and valid-for timestamps where supplied, and fallback reason; and
- `input_provenance_state`: `live_forecast`, `last_good_fallback`, or `sample_input`, plus `schedule_adherence_observed`.

Existing detailed `carbon_source` values remain useful. A labelled typical or built-in profile is `sample_input` for reporting: it is a non-live planning input, not a forecast. `live_forecast` requires response-level `is_live_forecast = true`. A last-good fallback is a previously generated schedule, not a fresh forecast; preserve its original run ID, original input provenance and valid-for interval, and attach the new failure reason. It must never be relabelled live. The deterministic Power BI fixture is `sample_input` and must identify its fixture/generator version.

### Permitted language

| Situation | Permitted | Prohibited |
|---|---|---|
| Live source planning result | “forecast”, “estimated planning difference”, or “forecast cost/carbon difference relative to the preferred start” | “realised”, “actual household saving”, “guaranteed saving” |
| Typical, sample, or synthetic input | “illustrative”, “synthetic-household demonstration”, or “sample-input planning result” | A customer outcome or a live measured result |
| Later-curve analysis with no adherence evidence | “conditional ex-post” and “conditional on the assumed schedule and load shape” | “realised customer savings”, “customer outcome”, or a measured-adherence claim |
| Peak metric | “peak-slot overlap avoided relative to the declared 17:00–19:00 planning peak” | “peak-demand reduction”, “grid peak reduced”, or a kW/energy reduction claim |

`schedule_adherence_observed` is false unless a future authorised source contains adherence evidence. Its false state is an adjacent caveat for conditional ex-post output.

### Dimensions and history

SCD2 is rejected for current `dim_community` and `dim_device`. Community names are curated fixtures and devices are derived from synthetic seeds; neither is a real, change-bearing source with an effective-date reporting decision. Source/run/fixture version and observation timestamps are sufficient. Reconsider SCD2 only with a real source whose changes must be reproduced historically.

## Consequences

- The optimiser remains the sole owner of feasibility and schedule selection; dbt becomes the sole reporting transformation.
- The current daily synthetic fact needs raw baseline/selected carbon and cost, windows, provenance, run/fixture identifiers, and status before certification.
- Consumers need qualified labels and an unavailable state. The authorised bounded repair applies these to Next.js and portable report consumers; it does not authorise PBIX replacement, a commit, deployment, publication, or any source refresh.
- The fact does not become SCD2, a task event log, or a flat Power BI table.

## Formula and consumer inventory

| Area | Current calculation or label | Consumer | Contract disposition |
|---|---|---|---|
| Optimiser placement | `evaluate_placement`: per-slot energy × price/carbon; standing charge excluded | Rule-based and LP/MILP | Retain as optimiser-owned raw placement calculation. |
| Optimiser baseline | `preferred_start`, otherwise `earliest_start`, clamped feasible | Rule-based and LP/MILP schedules; API; reports | Conflict: reporting baseline must be explicit preferred start only. |
| Optimiser totals | Baseline total minus selected total, cost/carbon | API totals; reports; monitoring; experiments | Retain as optimiser diagnostics; dbt owns daily reporting derivation/reconciliation. |
| Retro evaluation | Re-scores fixed selected/baseline windows against later or synthetic carbon curve | `retro_demo.py`; case study; methodology | Conditional ex-post only; adherence false. |
| Power BI seed | Runs optimiser; writes rounded values; peak is `max(0, baseline overlap - selected overlap)` | `seed_daily_savings.csv`; dbt | Synthetic; conflict: clamp hides a negative peak increase. |
| Half-hour dbt mart | Joins price/carbon by `slot_index`; hard-codes peak `34..37` | dbt tests and option reporting | Add date, valid interval, provenance, peak-set version before treating it as planning-day contract. |
| dbt daily fact | Casts seed columns and joins dimensions | Power BI star | Declares the target grain but does not enforce it: the synthetic seed is per task and dbt does not aggregate same-device rows. It also lacks schedule, baseline-carbon, provenance, and status lineage. |
| dbt aggregates | `SUM` cost/carbon/peak; `AVG` robustness; task/household counts | Timeline/community reports | Fact-only aggregates after reportable-status/provenance rules exist. |
| API | Cost/carbon totals and carbon/price provenance | Next.js and external API users | Useful provenance; lacks date, schedule run ID, raw values, and reporting status. |
| Text/Excel/PDF/Streamlit | “Estimated cost saving”, “Estimated carbon saving”, per-task “saves” | Portable reports and Streamlit | Need provenance-qualified labels when implementation is authorised. |
| Next.js planner | Totals, baseline windows, source-state display | Public planning UI | Consume API only; do not recompute metrics. |
| Power BI DAX | `Total Cost Saving (GBP)`, `Total Carbon Saving (kg)`, `Peak Slots Avoided`, ratios, robustness-gated saving | PBIX dashboard | Arithmetic consumer only; labels currently omit illustrative/forecast/conditional qualification. |
| Dagster | `carbon_forecast_curve → daily_schedule → action_report`; asset metadata has cost/carbon totals | Dagster UI and action report | Coordinate runs only; retain source/run provenance and do not describe sample/last-good as fresh live data. |

## Unresolved conflicts

1. `docs/CLAIM_LEDGER.md` and the Next.js planner describe a default, clamped 19:00 baseline; optimiser code also falls back to `earliest_start`. This conflicts with the explicit-preferred-start reporting baseline.
2. The 48-slot dbt mart lacks planning date, timezone, valid interval, and provenance. Its completeness test is unconditional. `carbon_curve` can repeat its final value to reach 48 slots, conflicting with the no-false-completeness rule.
3. The synthetic daily fact has no baseline carbon, selected carbon, selected/baseline windows, task/run ID, source timestamps, price provenance, or reporting status. dbt cannot yet reconcile its precomputed differences.
4. The seed clamps negative peak changes and the peak set is not versioned.
5. The core pipeline stores only a last-good schedule. Dagster can catch a fetch failure and return a sample curve before the core sees it, losing fallback provenance and allowing a normal-success presentation.
6. DAX, action reports, Streamlit, scripts, and dashboard labels use unqualified “saving” language, despite the claim ledger requiring synthetic figures to be called demonstrations.
7. Optimiser output is task-grain while the reporting fact is device-grain. Same-device daily roll-up is not yet defined.
8. The ADR's `NULL`/`not_reportable` policy conflicts with the current dbt `not_null` test on `fct_daily_savings.cost_saving_p`; the test must be redesigned with the reportable-status rule rather than silently preserving the old non-null requirement.

## Verification evidence

Inspected: `docs/CLAIM_LEDGER.md`, `docs/METHODOLOGY.md`, `docs/RETRO.md`, `docs/CASE_STUDY.md`, `docs/DATA_SOURCES.md`; optimiser, domain, pipeline, monitoring and reporting modules; all dbt reporting models, seeds, and tests; API models/service/carbon provider; web and Streamlit consumers; `powerbi/measures.dax`; the seed generator; and Dagster assets/docs.

The contract was independently reviewed before the bounded consumer repair. The repair is still subject to a fresh independent Reviewer/QA re-check before any closeout or Ross-controlled Git action. Existing untracked `.agents/` and `skills-lock.json` files remain untouched.

## Reviewer/QA handoff

Return **PASS / PASS-WITH-NITS / BLOCK** against this checklist:

1. Verify every locked requirement: grains, explicit baseline, units/sign/window/null policy/owner, provenance, permitted language, and SCD2 rejection.
2. Independently reproduce the seven conflicts from the cited source areas, especially default/clamped baseline, 48-slot padding, peak clamp, and Dagster provenance loss.
3. Confirm the ADR keeps feasibility and schedule selection with the optimiser and reporting transformation with dbt.
4. Confirm the local consumer repair preserves the explicit-preferred comparison: live, sample-input, fallback, and not-reportable rendered paths must use the allowed wording and must not show unavailable metrics.
5. Before any public wording change, require a claim-ledger copy audit showing permitted language for every consumer state.

**Handoff:** this re-check is limited to the authorised consumer repair. A PASS does not authorise a PBIX replacement, commit, deployment, publication, or public claim change.
