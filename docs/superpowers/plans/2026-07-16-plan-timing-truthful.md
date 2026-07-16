# Truthful Load Timing (Plan page, sub-project A) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Plan page stop lying — replace the misleading "That window runs past midnight." error with per-cause messages, prevent impossible windows before submit, and drop the retired 00:00–08:00 default.

**Architecture:** Extract all timing arithmetic out of the React component into a pure, dependency-free `web/lib/planning.ts`, test it with Vitest, then rewire `web/app/plan/page.tsx` to consume it. `web/lib/api.ts` gains an `ApiError` carrying the HTTP status and raw detail, which today are both discarded.

**Tech Stack:** Next.js 15 (App Router), React 19, TypeScript 5.7, Vitest (new), FastAPI backend (unchanged).

Spec: `docs/superpowers/specs/2026-07-16-plan-timing-ux-design.md`

## Global Constraints

- **Web-only.** No change to any API request/response shape, engine, or Python code. Sub-projects B (baseline semantics) and C (overnight/wrap) are out of scope.
- **Slot convention:** 48 half-hour slots per day. `earliest` is inclusive, `0..47`. `finishBy` is **exclusive**, `1..48` (48 = 24:00). `durationSlots = Math.max(1, Math.round(duration_hours * 2))`.
- **Baseline anchor is slot 38 (19:00)** — must match `BASELINE_SLOT` in `web/app/page.tsx:16` so the product makes one consistent claim.
- **Never render "past midnight" unless `earliest >= finishBy`.** This is the defect being fixed; do not reintroduce it as a catch-all.
- **State the baseline actually used**, never the one we wish we used. The engine clamps it until B lands.
- CI runs Node 20 (`.github/workflows/ci.yml`), working-directory `web`.
- Existing commands must stay green: `npm run typecheck`, `npm run build`, `uv run python -m pytest`.

## File Structure

| File | Responsibility |
|---|---|
| `web/lib/planning.ts` (create) | **Pure** timing logic. No React, no fetch, no DOM. The unit under test and the unit C will edit. |
| `web/lib/planning.test.ts` (create) | Vitest suite for the above. |
| `web/vitest.config.ts` (create) | Vitest config + `@/` alias (Next resolves it via tsconfig; Vitest needs it explicitly). |
| `web/package.json` (modify) | `vitest` devDependency + `test` script. |
| `.github/workflows/ci.yml` (modify) | Run the suite in the existing `web` job. |
| `web/lib/api.ts` (modify) | Throw `ApiError` (status + raw detail) instead of `Error(detail)`. |
| `web/app/plan/page.tsx` (modify) | React state + rendering only. All arithmetic delegated to `planning.ts`. |

---

### Task 1: Vitest harness + window geometry (`fits`, `widen`)

**Files:**
- Create: `web/vitest.config.ts`
- Create: `web/lib/planning.ts`
- Create: `web/lib/planning.test.ts`
- Modify: `web/package.json`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `SLOTS` from `web/lib/scoring.ts` (exported, `= 48`).
- Produces: `export interface Win { earliest: number; finishBy: number }`, `export function fits(win: Win, durationSlots: number): boolean`, `export function widen(win: Win, durationSlots: number): Win | null`.

- [ ] **Step 1: Install Vitest**

```bash
cd web && npm install -D vitest
```

- [ ] **Step 2: Add the test script**

In `web/package.json`, add to `"scripts"` (after `"typecheck"`):

```json
    "test": "vitest run"
```

- [ ] **Step 3: Create `web/vitest.config.ts`**

The `@/` alias comes from `web/tsconfig.json` (`"paths": { "@/*": ["./*"] }`). Next applies it automatically; Vitest does not, so it is declared here.

```ts
import path from "node:path";

import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
});
```

- [ ] **Step 4: Write the failing test**

Create `web/lib/planning.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { fits, widen } from "@/lib/planning";

describe("fits", () => {
  it("accepts an exact fit", () => {
    expect(fits({ earliest: 24, finishBy: 28 }, 4)).toBe(true);
  });

  it("rejects a window one slot short", () => {
    expect(fits({ earliest: 24, finishBy: 27 }, 4)).toBe(false);
  });

  it("rejects the reported bug: 12:00-13:00 for a 2-hour wash", () => {
    expect(fits({ earliest: 24, finishBy: 26 }, 4)).toBe(false);
  });

  it("accepts the full day", () => {
    expect(fits({ earliest: 0, finishBy: 48 }, 4)).toBe(true);
  });

  it("rejects a zero-length window", () => {
    expect(fits({ earliest: 24, finishBy: 24 }, 1)).toBe(false);
  });

  it("rejects an inverted (wrapping) window", () => {
    expect(fits({ earliest: 44, finishBy: 14 }, 4)).toBe(false);
  });
});

describe("widen", () => {
  it("pulls earliest back, preserving the finish-by deadline", () => {
    // The reported bug: 12:00-13:00, 2-hour wash -> 11:00-13:00, not 12:00-14:00.
    expect(widen({ earliest: 24, finishBy: 26 }, 4)).toEqual({ earliest: 22, finishBy: 26 });
  });

  it("extends finish-by only when earliest is already at 00:00", () => {
    expect(widen({ earliest: 0, finishBy: 2 }, 4)).toEqual({ earliest: 0, finishBy: 4 });
  });

  it("splits across both edges when neither alone suffices", () => {
    // Pull earliest 1 -> 0 (gains 1 slot), still 2 short, so extend finishBy 2 -> 4.
    // The result is exactly durationSlots wide: widening is minimal, never generous.
    expect(widen({ earliest: 1, finishBy: 2 }, 4)).toEqual({ earliest: 0, finishBy: 4 });
  });

  it("returns the window unchanged when it already fits", () => {
    expect(widen({ earliest: 0, finishBy: 48 }, 4)).toEqual({ earliest: 0, finishBy: 48 });
  });

  it("returns null when the whole day cannot hold the load", () => {
    expect(widen({ earliest: 0, finishBy: 4 }, 49)).toBeNull();
  });
});
```

- [ ] **Step 5: Run the test to verify it fails**

```bash
cd web && npx vitest run
```

Expected: FAIL — `Failed to resolve import "@/lib/planning"` (the module does not exist yet).

- [ ] **Step 6: Write the minimal implementation**

Create `web/lib/planning.ts`:

```ts
// Pure timing logic for the Plan page. No React, no fetch, no DOM — this is the
// arithmetic that decides whether a load can run in a window, and it is the part
// that types cannot check. Slot convention: 48 half-hours; `earliest` inclusive
// (0..47), `finishBy` exclusive (1..48, where 48 = 24:00).

import { SLOTS } from "@/lib/scoring";

export interface Win {
  earliest: number;
  finishBy: number;
}

/** Can `durationSlots` fit between `earliest` and `finishBy`? */
export function fits(win: Win, durationSlots: number): boolean {
  return win.finishBy - win.earliest >= durationSlots;
}

/**
 * Smallest widening of `win` that fits the load, or null if the day cannot.
 *
 * Pulls `earliest` back first and only extends `finishBy` once earliest hits
 * 00:00: "finish by" is usually a real deadline (the wash must be done before
 * you leave), whereas "earliest" is a convenience. Extending the deadline would
 * silently break the constraint the user actually cared about.
 */
export function widen(win: Win, durationSlots: number): Win | null {
  const need = durationSlots - (win.finishBy - win.earliest);
  if (need <= 0) return win;

  const earliest = Math.max(0, win.earliest - need);
  const stillNeeded = need - (win.earliest - earliest);
  const finishBy = win.finishBy + stillNeeded;
  if (finishBy > SLOTS) return null;

  return { earliest, finishBy };
}
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
cd web && npx vitest run
```

Expected: PASS — 11 tests passed.

- [ ] **Step 8: Add the CI step**

In `.github/workflows/ci.yml`, in the `web` job, after the `Typecheck` step:

```yaml
      - name: Test
        run: npm test
```

- [ ] **Step 9: Verify typecheck still passes**

```bash
cd web && npm run typecheck
```

Expected: no output (success).

- [ ] **Step 10: Commit**

```bash
git add web/package.json web/package-lock.json web/vitest.config.ts web/lib/planning.ts web/lib/planning.test.ts .github/workflows/ci.yml
git commit -m "test(web): add vitest and cover window geometry"
```

---

### Task 2: Chip windows and baseline derivation

**Files:**
- Modify: `web/lib/planning.ts`
- Modify: `web/lib/planning.test.ts`

**Interfaces:**
- Consumes: `Win`, `fits` from Task 1.
- Produces: `export type Chip = "anytime" | "early" | "daytime" | "custom"`, `export const CHIPS: { id: Chip; label: string }[]`, `export function windowForChip(chip: Chip, noiseSensitive: boolean): Win`, `export function defaultBaseline(win: Win, durationSlots: number): number`.

- [ ] **Step 1: Write the failing tests**

Append to `web/lib/planning.test.ts`:

```ts
import { defaultBaseline, windowForChip } from "@/lib/planning";

describe("windowForChip", () => {
  it("anytime is the whole day for a non-noise-sensitive load", () => {
    expect(windowForChip("anytime", false)).toEqual({ earliest: 0, finishBy: 48 });
  });

  it("anytime avoids sleeping hours for a noise-sensitive load", () => {
    // 07:00 = slot 14, 23:00 = slot 46. No 3am washing machine.
    expect(windowForChip("anytime", true)).toEqual({ earliest: 14, finishBy: 46 });
  });

  it("early hours is 00:00-07:00", () => {
    expect(windowForChip("early", false)).toEqual({ earliest: 0, finishBy: 14 });
  });

  it("early hours ignores noise sensitivity (the user asked for it explicitly)", () => {
    expect(windowForChip("early", true)).toEqual({ earliest: 0, finishBy: 14 });
  });

  it("daytime is 09:00-17:00", () => {
    expect(windowForChip("daytime", false)).toEqual({ earliest: 18, finishBy: 34 });
  });

  it("custom falls back to the whole day", () => {
    expect(windowForChip("custom", false)).toEqual({ earliest: 0, finishBy: 48 });
  });
});

describe("defaultBaseline", () => {
  it("is 19:00 when the window allows it", () => {
    expect(defaultBaseline({ earliest: 0, finishBy: 48 }, 4)).toBe(38);
  });

  it("clamps down to the latest legal start in an early-hours window", () => {
    // 00:00-07:00 with a 2-hour wash: latest legal start is 05:00 (slot 10).
    expect(defaultBaseline({ earliest: 0, finishBy: 14 }, 4)).toBe(10);
  });

  it("clamps up to earliest when the window starts after 19:00", () => {
    expect(defaultBaseline({ earliest: 42, finishBy: 48 }, 4)).toBe(42);
  });

  it("accounts for duration at the end of the day", () => {
    expect(defaultBaseline({ earliest: 0, finishBy: 48 }, 24)).toBe(24);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd web && npx vitest run
```

Expected: FAIL — `"defaultBaseline" is not exported by "lib/planning.ts"`.

- [ ] **Step 3: Write the minimal implementation**

Append to `web/lib/planning.ts`:

```ts
/** 19:00 — the "typical evening start". Must match BASELINE_SLOT in app/page.tsx. */
export const BASELINE_ANCHOR = 38;

const QUIET_START = 14; // 07:00
const QUIET_END = 46; // 23:00

export type Chip = "anytime" | "early" | "daytime" | "custom";

export const CHIPS: { id: Chip; label: string }[] = [
  { id: "anytime", label: "Anytime" },
  { id: "early", label: "Early hours" },
  { id: "daytime", label: "Daytime" },
  { id: "custom", label: "Custom" },
];

/**
 * The window a chip means.
 *
 * "Early hours" is 00:00-07:00, not 22:00-07:00: the engine plans a single
 * midnight-to-midnight day and cannot express a window that crosses midnight.
 * Naming it for what it actually does is deliberate — see sub-project C.
 */
export function windowForChip(chip: Chip, noiseSensitive: boolean): Win {
  switch (chip) {
    case "early":
      return { earliest: 0, finishBy: 14 };
    case "daytime":
      return { earliest: 18, finishBy: 34 };
    case "anytime":
      return noiseSensitive
        ? { earliest: QUIET_START, finishBy: QUIET_END }
        : { earliest: 0, finishBy: SLOTS };
    case "custom":
      return { earliest: 0, finishBy: SLOTS };
  }
}

/**
 * The baseline start we compare savings against, clamped into the window.
 *
 * The clamp is not a choice: domain/models.py rejects a preferred_start outside
 * the feasible window, so 19:00 with an early-hours window would 422. The UI
 * must therefore state the baseline this returns, not claim 19:00.
 * Sub-project B removes the clamp.
 */
export function defaultBaseline(win: Win, durationSlots: number): number {
  const latestStart = win.finishBy - durationSlots;
  return Math.max(win.earliest, Math.min(BASELINE_ANCHOR, latestStart));
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd web && npx vitest run
```

Expected: PASS — 21 tests passed.

- [ ] **Step 5: Commit**

```bash
git add web/lib/planning.ts web/lib/planning.test.ts
git commit -m "feat(web): add chip windows and baseline derivation"
```

---

### Task 3: `ApiError` and honest error classification

**Files:**
- Modify: `web/lib/api.ts:12-21`
- Modify: `web/lib/planning.ts`
- Modify: `web/lib/planning.test.ts`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `export class ApiError extends Error { status: number; detail: unknown }` from `@/lib/api`; `export type ErrorKind = "window_too_small" | "baseline_outside" | "infeasible" | "forecast_unavailable" | "generic"` and `export function classifyApiError(detail: unknown, status: number): ErrorKind` from `@/lib/planning`.

**Context the implementer needs:** `api/community_energy_api/main.py:155` maps engine `ValueError` → HTTP 422 with a **string** detail (e.g. `task Washing machine: window [24, 26) is too small for duration 4`). FastAPI request-validation failures return 422 with an **array** detail (`[{ msg, loc, ... }]`). `web/lib/proxy.ts` forwards the upstream status and turns a network failure into 503. Today `asJson` throws `new Error(detail ?? res.statusText)`, which discards the status and stringifies an array detail to `[object Object]`.

- [ ] **Step 1: Write the failing tests**

Append to `web/lib/planning.test.ts`:

```ts
import { classifyApiError } from "@/lib/planning";

describe("classifyApiError", () => {
  it("classifies the reported bug as a too-small window, not a midnight wrap", () => {
    expect(
      classifyApiError("task Washing machine: window [24, 26) is too small for duration 4", 422),
    ).toBe("window_too_small");
  });

  it("classifies a baseline outside the window", () => {
    expect(
      classifyApiError("task Washing machine: preferred_start 38 is outside the feasible window", 422),
    ).toBe("baseline_outside");
  });

  it("classifies an infeasible task", () => {
    expect(
      classifyApiError("task Kiln cannot be scheduled within [0, 14) on a 48-slot horizon", 422),
    ).toBe("infeasible");
  });

  it("classifies any 503 as forecast unavailable, whatever the detail says", () => {
    expect(classifyApiError("Carbon data is unavailable for this region", 503)).toBe(
      "forecast_unavailable",
    );
  });

  it("handles FastAPI's array-shaped validation detail without crashing", () => {
    expect(
      classifyApiError([{ msg: "Field required", loc: ["body", "tasks", 0, "device_type"] }], 422),
    ).toBe("generic");
  });

  it("falls back to generic for an unrecognised string", () => {
    expect(classifyApiError("something we have never seen", 422)).toBe("generic");
  });

  it("falls back to generic for a null detail", () => {
    expect(classifyApiError(null, 500)).toBe("generic");
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd web && npx vitest run
```

Expected: FAIL — `"classifyApiError" is not exported by "lib/planning.ts"`.

- [ ] **Step 3: Implement the classifier**

Append to `web/lib/planning.ts`:

```ts
export type ErrorKind =
  | "window_too_small"
  | "baseline_outside"
  | "infeasible"
  | "forecast_unavailable"
  | "generic";

/** FastAPI details are a string (our HTTPException) or an array (request validation). */
function detailToText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : "")).join(" ");
  }
  return "";
}

/**
 * Map an API failure to the reason we show.
 *
 * This parses the engine's message text, which is coupling to a format the API
 * does not promise. It is accepted because sub-project A cannot change the API
 * contract; C should add a machine-readable code, and this is the one function
 * that changes when it does.
 *
 * Note there is no "midnight wrap" kind: the engine reports a wrap as "too
 * small" (window [44, 6)), and the form now blocks it before submit. The
 * midnight message belongs to the client-side guard, not here.
 */
export function classifyApiError(detail: unknown, status: number): ErrorKind {
  if (status === 503) return "forecast_unavailable";
  const text = detailToText(detail);
  if (/is too small for duration/.test(text)) return "window_too_small";
  if (/preferred_start .* outside the feasible window/.test(text)) return "baseline_outside";
  if (/cannot be scheduled within/.test(text)) return "infeasible";
  return "generic";
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd web && npx vitest run
```

Expected: PASS — 28 tests passed.

- [ ] **Step 5: Make `api.ts` carry the status and raw detail**

Replace `web/lib/api.ts:12-21` with:

```ts
/** An API failure that keeps the HTTP status and the raw detail body. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: unknown,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => b?.detail)
      .catch(() => null);
    throw new ApiError(
      res.status,
      detail ?? null,
      typeof detail === "string" ? detail : res.statusText,
    );
  }
  return res.json() as Promise<T>;
}
```

- [ ] **Step 6: Verify typecheck passes**

```bash
cd web && npm run typecheck
```

Expected: no output (success).

- [ ] **Step 7: Commit**

```bash
git add web/lib/api.ts web/lib/planning.ts web/lib/planning.test.ts
git commit -m "feat(web): classify API errors by cause, not by regex guess"
```

---

### Task 4: Chips and the feasibility guard in the form

**Files:**
- Modify: `web/app/plan/page.tsx` (imports, `Added`, `togglePreset`, `setTime`, `canOpt`, the load card render)

**Interfaces:**
- Consumes: `Chip`, `CHIPS`, `Win`, `fits`, `widen`, `windowForChip`, `defaultBaseline` from `@/lib/planning`.
- Produces: an `Added` record carrying `chip: Chip`; `blockingLoad`, used by Task 5's submit hint.

- [ ] **Step 1: Extend the imports and the `Added` shape**

In `web/app/plan/page.tsx`, add to the imports:

```ts
import {
  CHIPS,
  defaultBaseline,
  fits,
  widen,
  windowForChip,
  type Chip,
} from "@/lib/planning";
```

Add `chip` to `Added` (line 23-33):

```ts
interface Added {
  key: string;
  id: string;
  name: string;
  energy_kwh: number;
  duration_hours: number;
  durSlots: number;
  chip: Chip;
  noiseSensitive: boolean;
  earliest: number; // slot
  finishBy: number; // end slot (1–48)
  preferred: number; // slot
}
```

- [ ] **Step 2: Default new loads to "Anytime" instead of 00:00–08:00**

Replace `togglePreset` (lines 82-104) with:

```ts
  function togglePreset(a: Appliance) {
    const durSlots = Math.max(1, Math.round(a.duration_hours * 2));
    const noiseSensitive = a.noise_sensitive;
    const win = windowForChip("anytime", noiseSensitive);
    setAdded((prev) =>
      prev.some((x) => x.id === a.id)
        ? prev.filter((x) => x.id !== a.id)
        : [
            ...prev,
            {
              key: `${a.id}-${Date.now()}`,
              id: a.id,
              name: a.name,
              energy_kwh: a.energy_kwh,
              duration_hours: a.duration_hours,
              durSlots,
              chip: "anytime",
              noiseSensitive,
              earliest: win.earliest,
              finishBy: win.finishBy,
              preferred: defaultBaseline(win, durSlots),
            },
          ],
    );
  }
```

The old fallback to slot 16 (`a.typical_latest ? clockToSlot(a.typical_latest) : 16`) is deliberately gone: it defaulted every non-EV load to a 00:00–08:00 window, a leftover of the retired After Midnight premise.

- [ ] **Step 3: Add chip selection and keep the baseline legal**

Add after `togglePreset`:

```ts
  function chooseChip(key: string, chip: Chip) {
    setAdded((prev) =>
      prev.map((a) => {
        if (a.key !== key) return a;
        if (chip === "custom") return { ...a, chip };
        const win = windowForChip(chip, a.noiseSensitive);
        return { ...a, chip, ...win, preferred: defaultBaseline(win, a.durSlots) };
      }),
    );
  }

  function applyWiden(key: string) {
    setAdded((prev) =>
      prev.map((a) => {
        if (a.key !== key) return a;
        const w = widen({ earliest: a.earliest, finishBy: a.finishBy }, a.durSlots);
        if (!w) return a;
        return { ...a, ...w, preferred: defaultBaseline(w, a.durSlots) };
      }),
    );
  }
```

Replace `setTime` (lines 106-108) so an edited window keeps the baseline inside it — otherwise the API 422s with `preferred_start ... outside the feasible window`:

```ts
  function setTime(key: string, field: "earliest" | "finishBy" | "preferred", v: number) {
    setAdded((prev) =>
      prev.map((a) => {
        if (a.key !== key) return a;
        const next = { ...a, [field]: v };
        if (field === "preferred") return next;
        const win = { earliest: next.earliest, finishBy: next.finishBy };
        return fits(win, a.durSlots) ? { ...next, preferred: defaultBaseline(win, a.durSlots) } : next;
      }),
    );
  }
```

- [ ] **Step 4: Block submit on an infeasible load**

Replace `canOpt` / `optHint` (lines 110-118) with:

```ts
  const blockingLoad = added.find((a) => !fits({ earliest: a.earliest, finishBy: a.finishBy }, a.durSlots));
  const canOpt = !!regionId && !!tariff && added.length > 0 && !blockingLoad;
  const optHint = !regionId
    ? "Pick a region to begin."
    : !tariff
      ? "Choose your tariff."
      : added.length === 0
        ? "Add at least one load."
        : blockingLoad
          ? `${blockingLoad.name}: the window is too short.`
          : "We'll fetch the forecast and bracket your windows.";
```

- [ ] **Step 5: Render the chips, the duration, and the guard**

Replace the three `TimeField`s (lines 264-266) with:

```tsx
                      <div style={{ gridColumn: "1 / -1", display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 4 }}>
                        {CHIPS.map((c) => {
                          const w = windowForChip(c.id, a.noiseSensitive);
                          const disabled = c.id !== "custom" && !fits(w, a.durSlots);
                          return (
                            <button
                              key={c.id}
                              type="button"
                              disabled={disabled}
                              aria-pressed={a.chip === c.id}
                              title={disabled ? `${a.name} needs ${a.duration_hours}h; ${c.label} is shorter.` : undefined}
                              onClick={() => chooseChip(a.key, c.id)}
                              style={{
                                padding: "6px 12px",
                                borderRadius: 999,
                                fontSize: 13,
                                cursor: disabled ? "not-allowed" : "pointer",
                                border: "1px solid var(--line)",
                                background: a.chip === c.id ? "var(--ink)" : "var(--panel)",
                                color: disabled ? "var(--slate-mute)" : a.chip === c.id ? "var(--paper)" : "var(--ink)",
                              }}
                            >
                              {c.label}
                            </button>
                          );
                        })}
                      </div>
                      {a.chip === "custom" && (
                        <>
                          <TimeField label="Earliest start" value={a.earliest} opts={START_OPTS} onChange={(v) => setTime(a.key, "earliest", v)} />
                          <TimeField label="Finish by" value={a.finishBy} opts={FINISH_OPTS} onChange={(v) => setTime(a.key, "finishBy", v)} />
                          <TimeField
                            label="Usual start (baseline)"
                            value={a.preferred}
                            opts={START_OPTS.filter((o) => o.v >= a.earliest && o.v <= a.finishBy - a.durSlots)}
                            onChange={(v) => setTime(a.key, "preferred", v)}
                          />
                        </>
                      )}
                      {!fits({ earliest: a.earliest, finishBy: a.finishBy }, a.durSlots) && (
                        <p role="status" style={{ gridColumn: "1 / -1", margin: "6px 0 0", fontSize: 13, color: "var(--ink)" }}>
                          {a.earliest >= a.finishBy
                            ? "Finish-by must be after earliest start. We plan a single midnight-to-midnight day, so a window that crosses midnight isn't supported yet."
                            : `A ${a.duration_hours}-hour ${a.name.toLowerCase()} needs at least a ${a.duration_hours}-hour window — you've allowed ${((a.finishBy - a.earliest) / 2).toFixed(1)} hours.`}
                          {(() => {
                            const w = widen({ earliest: a.earliest, finishBy: a.finishBy }, a.durSlots);
                            return w ? (
                              <button type="button" onClick={() => applyWiden(a.key)} style={{ marginLeft: 10, textDecoration: "underline", background: "none", border: "none", cursor: "pointer", color: "var(--ink)", font: "inherit" }}>
                                Widen to {slotToClock(w.earliest)}–{slotToClock(w.finishBy)}
                              </button>
                            ) : null;
                          })()}
                        </p>
                      )}
```

This is the only place the "midnight" wording survives, and only when `earliest >= finishBy` — the one case where it is true.

The baseline control appears **only under Custom**: the chips always derive a legal baseline via
`defaultBaseline`, so it is only needed when the user is setting exact times. Its options are filtered to
starts that are legal in the current window, which is what `domain/models.py:102` requires — an unfiltered
list is how a user reaches the `preferred_start ... outside the feasible window` 422.

- [ ] **Step 6: Update the section helper text**

Replace line 239's text with:

```tsx
            <p style={{ margin: "0 0 14px", fontSize: 13.5, color: "var(--slate)" }}>Add a preset, then choose when it can run. We&apos;ll find the cleanest window inside it.</p>
```

- [ ] **Step 7: Verify typecheck, tests and build**

```bash
cd web && npm run typecheck && npx vitest run && npm run build
```

Expected: typecheck silent; 28 tests pass; build succeeds.

If `clockToSlot` is now unused in `page.tsx`, remove it from the `@/lib/scoring` import — an unused import fails no check here, but leaving it is dead code.

- [ ] **Step 8: Commit**

```bash
git add web/app/plan/page.tsx
git commit -m "feat(web): choose load windows with chips and block impossible ones"
```

---

### Task 5: Honest error screen and a stated baseline

**Files:**
- Modify: `web/app/plan/page.tsx` (`ErrorKind` type, `onSubmit` catch, error render, results render)

**Interfaces:**
- Consumes: `ApiError` from `@/lib/api`; `classifyApiError`, `ErrorKind` from `@/lib/planning`.
- Produces: nothing consumed later.

- [ ] **Step 1: Replace the local `ErrorKind`**

Delete line 21 (`type ErrorKind = "422" | "503" | "generic";`) and import the real one:

```ts
import { ApiError } from "@/lib/api";
import { classifyApiError, type ErrorKind } from "@/lib/planning";
```

Merge these with the existing `@/lib/api` and `@/lib/planning` import statements rather than adding duplicates.

- [ ] **Step 2: Classify on status and detail, not on a regex over the message**

Replace the `catch` block (lines 150-158) with:

```ts
    } catch (err) {
      const kind: ErrorKind =
        err instanceof ApiError ? classifyApiError(err.detail, err.status) : "generic";
      setErrorKind(kind);
      setPhase("error");
      setLiveStatus("Error: could not build the plan.");
    }
```

- [ ] **Step 3: Say what actually went wrong**

Replace the error `<h2>` (line 318) and its body paragraph (lines 319-322) with:

```tsx
          <h2 style={{ fontWeight: 700, fontSize: 22, margin: "0 0 10px", letterSpacing: "-0.01em" }}>
            {errorKind === "window_too_small"
              ? "One of your loads needs a longer window."
              : errorKind === "baseline_outside"
                ? "That usual start isn't inside the window."
                : errorKind === "infeasible"
                  ? "We couldn't fit that load into its window."
                  : errorKind === "forecast_unavailable"
                    ? "We can't reach the forecast right now."
                    : "We couldn't build the plan."}
          </h2>
          <p style={{ margin: "0 0 18px", fontSize: 15, lineHeight: 1.55, color: "var(--ink-soft-2)", maxWidth: "58ch" }}>
            {errorKind === "window_too_small"
              ? "The run window is shorter than the load takes. Go back and widen it — the form will suggest the smallest change that works."
              : errorKind === "baseline_outside"
                ? "The usual start has to be a time the load could actually run within the window you set. Go back and move it inside, or widen the window."
                : errorKind === "infeasible"
                  ? "There's no start time inside that window where the load finishes in time. Try a wider window."
                  : errorKind === "forecast_unavailable"
                    ? "The carbon or price feed didn't respond. Nothing is wrong with your plan — try again shortly."
                    : "Something went wrong building the plan. Try again, or change the loads."}
          </p>
```

The old "That window runs past midnight." text is gone from this screen. The only surviving midnight wording is Task 4's inline guard, shown only when `earliest >= finishBy`.

- [ ] **Step 4: Confirm the results already state the real baseline — change nothing**

No code change. The spec requires the page to state the baseline actually used rather than claim 19:00, and
`web/app/plan/page.tsx:431-434` already does:

```tsx
                Run <span ...>{t.run_window}</span>
                <span ...> instead of </span>
                <span className="mono">{t.baseline_window}</span>.
```

`t.baseline_window` is the server's own baseline placement, so a clamped baseline is already reported
truthfully, per load. The band reinforces it with the `usual` tick, and the totals say "vs your usual timings".

Read those lines and confirm they are intact. **Do not add a second baseline caption** — the hard-coded
`vs a 19:00 start` string lives in `web/app/page.tsx` (the home hero) and must not be copied here. This step
exists to stop a well-meaning implementer duplicating what the API already reports.

- [ ] **Step 5: Verify typecheck, tests and build**

```bash
cd web && npm run typecheck && npx vitest run && npm run build
```

Expected: typecheck silent; 28 tests pass; build succeeds.

- [ ] **Step 6: Commit**

```bash
git add web/app/plan/page.tsx
git commit -m "fix(web): report the real reason a plan failed"
```

---

### Task 6: End-to-end verification against the live API

**Files:** none modified (verification only; fix and re-commit if anything fails).

- [ ] **Step 1: Start the dev server**

Use the existing `web` config in `.claude/launch.json` (do not start a server via a shell command).

- [ ] **Step 2: Reproduce the original bug report**

On `/plan`: pick **South West England** → **Agile** → **Washing machine** → chip **Custom** → Earliest `12:00`, Finish by `13:00`.

Expected:
- Submit is disabled; the hint reads `Washing machine: the window is too short.`
- Inline: `A 2-hour washing machine needs at least a 2-hour window — you've allowed 1.0 hours.`
- A `Widen to 11:00–13:00` button is offered
- **No "past midnight" text anywhere**

- [ ] **Step 3: Confirm the one-click fix produces a plan**

Click `Widen to 11:00–13:00`, then submit. Expected: a plan renders, and the recommendation card reads
`Run HH:MM-HH:MM instead of 11:00-13:00` — the baseline clamped into the widened window (19:00 is not
reachable there), reported honestly rather than as 19:00.

- [ ] **Step 4: Confirm the genuine midnight case still says midnight**

Custom → Earliest `22:00`, Finish by `03:00`. Expected the inline guard: `Finish-by must be after earliest start. We plan a single midnight-to-midnight day, so a window that crosses midnight isn't supported yet.`

- [ ] **Step 5: Confirm the default is no longer 00:00–08:00**

Remove and re-add **Washing machine**. Expected: chip **Anytime** selected; no time dropdowns shown; submitting produces a plan whose window falls inside 07:00–23:00 (noise-sensitive), and the recommendation card reads `instead of 19:00-21:00` — 19:00 is reachable in an Anytime window, so the baseline is the real anchor.

Then add **EV charge - overnight (~40 kWh)** (6 h, not noise-sensitive) and confirm **Early hours** is enabled (00:00–07:00 holds 6 h) while **Daytime** (09:00–17:00, 8 h) is also enabled; confirm **Kiln (pottery / craft)** (8 h) has **Early hours** disabled with a title explaining why.

- [ ] **Step 6: Check the console and the full suites**

```bash
cd web && npm run typecheck && npx vitest run && npm run build
cd .. && uv run python -m pytest -q
```

Expected: all green; Python unchanged at 157 passed. Read the browser console: expect no errors.

- [ ] **Step 7: Commit any fixes**

```bash
git add -A web
git commit -m "fix(web): address verification findings on the plan form"
```

(Skip if nothing needed fixing.)

---

---

### Task 7: Replace Widen with chip suggestions (added after Task 6 verification)

**Why this exists:** Task 6 drove the real app and found two flaws in this plan's own design.

1. **Minimal widen guarantees a worthless plan.** "Widen to 11:00–13:00" produces a window exactly
   `durationSlots` wide, so there is exactly ONE feasible placement: the run window equals the baseline and
   the saving is always zero. The live result read `Run 11:00-13:00 instead of 11:00-13:00.` — `0p & 0 g`.
2. **Widen returns nonsense on an inverted window.** For 22:00→03:00 it offered "Widen to 01:00–03:00",
   discarding the user's 22:00 start, directly beneath a message saying midnight-crossing isn't supported.

Ross's decision: **drop the Widen button and point at the chips instead**, and make the inverted-window
rejection explicit. Dropping the button leaves `widen` with no caller, so it goes too — dead code, not
speculative inventory for sub-project C, which needs different (ring-based) logic anyway.

**Files:**
- Modify: `web/lib/planning.ts`
- Modify: `web/lib/planning.test.ts`
- Modify: `web/app/plan/page.tsx`

**Interfaces:**
- Consumes: `Win`, `fits`, `Chip`, `CHIPS`, `windowForChip` (Tasks 1-2).
- Produces: `export function fittingChips(noiseSensitive: boolean, durationSlots: number): Chip[]`.
- **Removes:** `export function widen(...)` — delete the function, its doc comment, and its 5 tests.

- [ ] **Step 1: Write the failing tests**

In `web/lib/planning.test.ts`, DELETE the entire `describe("widen", ...)` block (5 tests), and remove `widen`
from the `@/lib/planning` import. Then append:

```ts
import { fittingChips } from "@/lib/planning";

describe("fittingChips", () => {
  it("offers every preset window to a short load", () => {
    expect(fittingChips(false, 4)).toEqual(["anytime", "early", "daytime"]);
  });

  it("drops early hours for an 8-hour slow cooker", () => {
    // Early hours is 00:00-07:00 = 14 slots; the load needs 16.
    expect(fittingChips(false, 16)).toEqual(["anytime", "daytime"]);
  });

  it("offers every preset window to a short noise-sensitive load", () => {
    expect(fittingChips(true, 4)).toEqual(["anytime", "early", "daytime"]);
  });

  it("offers only anytime to a 17-hour load", () => {
    expect(fittingChips(false, 34)).toEqual(["anytime"]);
  });

  it("offers nothing when a noise-sensitive load outlasts every window", () => {
    // Anytime for a noise-sensitive load is 07:00-23:00 = 32 slots.
    expect(fittingChips(true, 34)).toEqual([]);
  });

  it("never offers custom", () => {
    expect(fittingChips(false, 4)).not.toContain("custom");
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd web && npx vitest run
```

Expected: FAIL — `"fittingChips" is not exported by "lib/planning.ts"`.

- [ ] **Step 3: Make the wrap rejection explicit and add `fittingChips`**

In `web/lib/planning.ts`, replace `fits` with:

```ts
/**
 * Can `durationSlots` fit between `earliest` and `finishBy`?
 *
 * A window whose finish is not after its start crosses midnight, which the engine
 * cannot express — rejected explicitly rather than relying on the subtraction
 * going negative.
 */
export function fits(win: Win, durationSlots: number): boolean {
  if (win.finishBy <= win.earliest) return false;
  return win.finishBy - win.earliest >= durationSlots;
}
```

DELETE the entire `widen` function and its doc comment.

Append:

```ts
/**
 * The preset chips whose window can actually hold this load, in CHIPS order.
 *
 * Used to suggest a way out when a custom window is too short. We point at
 * windows we already know are good rather than inventing a minimal one: the
 * smallest window that fits a load has exactly one placement, so it would
 * always produce a plan that recommends the baseline and saves nothing.
 */
export function fittingChips(noiseSensitive: boolean, durationSlots: number): Chip[] {
  return CHIPS.map((c) => c.id)
    .filter((id) => id !== "custom")
    .filter((id) => fits(windowForChip(id, noiseSensitive), durationSlots));
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd web && npx vitest run
```

Expected: PASS — 29 tests passed (28 − 5 widen + 6 fittingChips).

- [ ] **Step 5: Remove the Widen button and suggest chips**

In `web/app/plan/page.tsx`:

Remove `widen` from the `@/lib/planning` import and add `fittingChips`. Delete the whole `applyWiden`
function.

Replace the guard paragraph's contents (the `!fits(...) && (...)` block from Task 4) with:

```tsx
                      {!fits({ earliest: a.earliest, finishBy: a.finishBy }, a.durSlots) && (
                        <p role="status" style={{ gridColumn: "1 / -1", margin: "6px 0 0", fontSize: 13, color: "var(--ink)" }}>
                          {a.earliest >= a.finishBy
                            ? "Finish-by must be after earliest start. We plan a single midnight-to-midnight day, so a window that crosses midnight isn't supported yet."
                            : `A ${a.duration_hours}-hour ${a.name.toLowerCase()} needs at least a ${a.duration_hours}-hour window — you've allowed ${((a.finishBy - a.earliest) / 2).toFixed(1)} hours.`}
                          {(() => {
                            const ok = fittingChips(a.noiseSensitive, a.durSlots);
                            if (!ok.length) return " No preset window is long enough for this load.";
                            const labels = ok.map((id) => CHIPS.find((c) => c.id === id)!.label);
                            const list = labels.length > 1
                              ? `${labels.slice(0, -1).join(", ")} or ${labels[labels.length - 1]}`
                              : labels[0];
                            return ` Try ${list}.`;
                          })()}
                        </p>
                      )}
```

No "Widen to …" button anywhere. The midnight wording still appears only when `earliest >= finishBy`.

- [ ] **Step 6: Verify typecheck, tests and build**

```bash
cd web && npm run typecheck && npx vitest run && npm run build
```

Expected: typecheck silent; 29 tests pass; build succeeds. Confirm no reference to `widen` or `applyWiden`
remains: `grep -rn "widen\|applyWiden" web/lib web/app` should return nothing.

- [ ] **Step 7: Commit**

```bash
git add web/lib/planning.ts web/lib/planning.test.ts web/app/plan/page.tsx
git commit -m "fix(web): suggest a workable window instead of a minimal one"
```

---

## Definition of done

- The reported bug (12:00–13:00, 2-hour wash) is caught in the form, explained accurately, and fixable in one click.
- "That window runs past midnight." can only appear when `earliest >= finishBy`.
- New loads default to Anytime, never 00:00–08:00.
- The displayed baseline is always the one sent to the API.
- `npm run typecheck`, `npm test`, `npm run build`, and `python -m pytest` are green; CI runs the Vitest suite.
- Sub-projects B (baseline semantics) and C (overnight/wrap) remain untouched and unblocked.
