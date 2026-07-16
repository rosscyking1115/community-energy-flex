# Plan page: truthful load timing (sub-project A)

Date: 2026-07-16
Status: approved for planning
Scope: `web/` only — no engine, API or contract changes

## Why

A user picked a washing machine (0.8 kWh, 120 min), set the window to 12:00–13:00, and was told:

> That window runs past midnight.

Midnight was not involved. The real API response was:

```
task Washing machine: window [24, 26) is too small for duration 4
```

A one-hour window cannot hold a two-hour wash. The app diagnosed the problem correctly and then displayed
something unrelated, because `web/app/plan/page.tsx:152` classifies errors with a regex:

```ts
const kind: ErrorKind = /window|midnight|feasible|too small|preferred/i.test(msg) ? "422" : ...
```

Any match renders the single message at `page.tsx:318`. Three distinct failures — window too small, baseline
outside the window, and a genuine midnight wrap — all render as the wrap message. Only the third is ever true.

Three things combined to manufacture the confusion:

1. **Duration was invisible as a constraint.** The card shows `0.8 kWh · 120 min`, but nothing connects that to
   the window you are choosing, so a 1-hour window looks reasonable.
2. **The default window is 00:00–08:00.** `page.tsx:84` falls back to slot 16 when a preset has no
   `typical_latest` — which is every preset except the two EV ones. This is a leftover of the retired
   "After Midnight" premise, the same one fixed in the home hero in `c507323`.
3. **Nothing prevents an impossible window.** `setTime` does no validation and `canOpt` ignores feasibility, so
   the submit button stays enabled and the only feedback is a server round-trip that reports the wrong reason.

## Non-goals

Deliberately excluded, each with its own follow-up sub-project:

- **Sub-project B — baseline semantics.** `preferred_start` is validated against the constraint window
  (`domain/models.py:102`), so a baseline of 19:00 with an early-hours window is rejected. A therefore keeps
  clamping and *states the baseline actually used*. B decouples the two.
- **Sub-project C — overnight/wrap support.** The engine plans one midnight-to-midnight day; `22:00→07:00` is
  not expressible. A labels the capability honestly rather than pretending. C extends the horizon.

A must not make B or C harder. It does not change any API request shape.

## Design

### 1. Separate the three concepts

The form presents three identical dropdowns for three unlike things. Give each its own weight:

| Concept | Owner | Today | After A |
|---|---|---|---|
| **Constraint** — when it *may* run | user | 2 dropdowns, default 00:00–08:00 | chips, default "Anytime" |
| **Duration** — how long it takes | preset | shown but inert | shown, and enforced against the window |
| **Baseline** — what we compare against | system | "Usual start" dropdown | derived; stated in the result |

### 2. Window chips

Per load, replacing the two dropdowns as the primary control:

| Chip | Window | Notes |
|---|---|---|
| **Anytime** (default) | 00:00–24:00 | 07:00–23:00 when the preset is `noise_sensitive` |
| **Early hours** | 00:00–07:00 | Named for what it is. Not "Overnight" — see C. |
| **Daytime** | 09:00–17:00 | |
| **Custom** | user-chosen | reveals the existing earliest / finish-by dropdowns |

`noise_sensitive` is already on the appliance payload (`true` for washer and dishwasher) and currently unused.
Using it for the Anytime default stops us proposing a 3am wash.

A chip whose window cannot hold the load is **disabled**, with the reason on hover/focus (e.g. an 8 kWh kiln at
8 h cannot fit Early hours). Disabled chips are never silently substituted.

### 3. Feasibility guard

Pure predicate: `finishBy - earliest >= durationSlots`.

When violated:
- inline text under the load: *"A 2-hour wash needs at least a 2-hour window — you've allowed 1 hour."*
- submit disabled, with `optHint` naming the offending load
- a **"Widen to 11:00–13:00"** button applying the minimal widening that fits

Widening pulls **earliest-start back first**, and only extends finish-by if the window hits 00:00. "Finish by"
is usually the real-world deadline — the wash must be done before you leave — whereas "earliest" is a
convenience. Extending finish-by to 14:00 would silently break the constraint the user actually cared about, so
12:00–13:00 for a 2-hour wash widens to 11:00–13:00, not 12:00–14:00. `widen` returns `null` when the whole day
cannot hold the load.

This makes the "too small" 422 unreachable from the UI.

### 4. Baseline

Not a primary input. Derived as `clamp(19:00, earliest, finishBy - durationSlots)`:

- 19:00 matches the home hero's existing "typical evening start", so the product makes one consistent claim.
- Clamping is required by `domain/models.py:102` until B lands.
- The result states **the baseline actually used** — "vs a 05:00 start", not "vs a typical 19:00 start" — so a
  clamped baseline is never misreported. This is the honest interim; B removes the clamp.
- Advanced discloses a baseline dropdown limited to feasible starts.

### 5. Honest error mapping

Replace the regex with a mapping over the API's `detail` string:

| API detail | Kind | Message |
|---|---|---|
| `... is too small for duration ...` | `window_too_small` | names the load, its duration, the window given |
| `preferred_start ... outside the feasible window` | `baseline_outside` | baseline isn't reachable in this window |
| `cannot be scheduled within ...` | `infeasible` | no legal start on the horizon |
| 503 / unavailable | `forecast_unavailable` | unchanged |
| anything else | `generic` | unchanged |

The midnight message is **kept but narrowed** to the only case where it is true: Custom with
`earliest >= finishBy`. Wording states the real limitation — we plan one midnight-to-midnight day, so windows
crossing midnight are not supported yet — which is honest until C.

Parsing an error string is coupling to a message format. It is accepted here because A cannot change the API
contract; C should introduce a machine-readable error code, and this mapping is the place that changes.

### 6. Module boundary

New `web/lib/planning.ts` — pure, no React, no fetch:

```ts
export type Chip = "anytime" | "early" | "daytime" | "custom";
export interface Win { earliest: number; finishBy: number }

export function windowForChip(chip: Chip, noiseSensitive: boolean): Win;
export function fits(win: Win, durationSlots: number): boolean;
export function widen(win: Win, durationSlots: number): Win | null;
export function defaultBaseline(win: Win, durationSlots: number): number;
export function classifyApiError(detail: string, status: number): ErrorKind;
```

`plan/page.tsx` keeps React state and rendering only. This is the unit worth testing and the unit C will edit.

### 7. Testing

Add **Vitest** to `web/` plus a CI step alongside the existing typecheck job.

Chosen over typecheck-only because A's value is entirely in arithmetic that types cannot check: clamping,
widening, slot boundaries, and error classification. This repository's stated discipline is evidence over
assertion; the bug it fixes shipped precisely because nothing exercised this logic.

Cases:
- `fits`: exact fit, one slot short, zero-length, full day
- `widen`: pulls earliest back; falls back to extending finish-by only at 00:00; returns `null` when the day
  cannot hold the load
- `windowForChip`: noise-sensitive vs not; every chip
- `defaultBaseline`: 19:00 inside window; clamped low by an early window; clamped by duration at day end
- `classifyApiError`: one case per row above, including the wrap case and an unrecognised string → `generic`

No component or E2E tests: the render is thin once the logic is extracted.

## Verification

- `npm run typecheck`, `npm run build`, `npx vitest run`, `uv run python -m pytest` (unchanged, must stay green)
- Reproduce the original report against the live API: washing machine, 12:00–13:00 → submit blocked, inline
  message names duration, "Widen to 11:00–13:00" produces a plan
- Every chip on a noise-sensitive and a non-noise-sensitive load
- Confirm the "past midnight" text appears only for Custom with `earliest >= finishBy`

## Risks

- **Chip rework when C lands.** "Early hours" becomes a real "Overnight (22:00–07:00)". Accepted: A is
  self-contained and stops the app lying now.
- **Error-string parsing is brittle.** Mitigated by isolating it in one function; C replaces it with a code.
- **Regional edge case.** North Scotland's live carbon is 0 gCO₂/kWh across all 48 slots (verified upstream at
  NESO, not a defect), so carbon ties everywhere and ranking falls to the price tie-break. Out of scope for A;
  noted so it is not mistaken for a bug introduced here.
