# Methodology

This document pins down the three things a decision-support tool must not leave
vague: the **baseline**, the **cost/carbon maths**, and the **confidence** score.

## Slots

A planning day is 48 half-hour slots, indexed `0..47`. Slot `i` covers
`[i·30min, (i+1)·30min)`. `08:00` is slot 16; `latest_finish` is *exclusive*
(a task that must finish by 07:00 has `latest_finish = 14`).

## Cost and carbon of a placement

Energy is spread evenly across a task's occupied slots: a task using `E` kWh over
`d` slots draws `E/d` kWh per slot. For a placement over slots `[start, end)`:

```
cost_p   = Σ  (E/d) · unit_rate_p_per_kwh(slot)
carbon_g = Σ  (E/d) · carbon_gco2_per_kwh(slot)
```

**The standing charge is excluded from savings.** It is a fixed daily cost that
does not depend on *when* a task runs, so folding it in would dilute and distort
the shift-driven saving. It may still be shown for total-bill context.

## Baseline (business as usual)

Savings only mean something against a defined baseline. The baseline is each task
run at its **natural slot**: its `preferred_start` if given, else its
`earliest_start`, clamped into the feasible window. Savings are then:

```
cost_saving   = baseline_cost   − optimised_cost
carbon_saving = baseline_carbon − optimised_carbon
```

Under a **flat** tariff the cost saving is correctly ~£0 — shifting time cannot
change a flat unit rate. Cost savings come from time-of-use tariffs; carbon
savings come from the carbon curve.

## Objectives

Cost and carbon are min-max normalised to `0..1` across a task's own feasible
placements, so objectives are comparable. Lower score is better.

| Objective | Score |
|---|---|
| `cheapest` | normalised cost |
| `lowest_carbon` | normalised carbon |
| `avoid_peak` | ½·peak-overlap + ½·normalised cost |
| `balanced` | `(w_cost·cost + w_carbon·carbon + w_comfort·comfort) / Σw` |

Ties break to the earliest start for determinism.

## Confidence

Confidence is a product of four factors, each in `(0, 1]`, so any weak input
drags the whole score down (the principle: *make uncertainty visible*).

| Factor | Meaning | Value |
|---|---|---|
| **decisiveness** | how far the best option beats the *mean* feasible option (materiality `m` vs threshold 0.25) | `0.3 + 0.7·min(1, m/0.25)` |
| **horizon** | forecasts far ahead are less reliable | `max(0.5, 1 − 0.02·(hours−12))` |
| **data** | measured actual carbon beats a forecast | `1.0` actual / `0.85` forecast |
| **tariff** | a hand-typed tariff is less certain | `1.0` known / `0.8` manual |

`confidence = decisiveness · horizon · data · tariff`, banded **High ≥ 0.75**,
**Medium ≥ 0.5**, else **Low**. Decisiveness is measured against the *typical*
option, not the adjacent runner-up: on a 48-slot day the next slot is always a
near-tie, which would make every recommendation look falsely fragile. A genuinely
flat landscape (every time equally good) is honestly low-decisiveness — the
choice barely matters. The weakest factor becomes the plain-language caveat.
