// Pure timing logic for the Plan page. No React, no fetch, no DOM — this is the
// arithmetic that decides whether a load can run in a window, and it is the part
// that types cannot check. Slot convention: 48 half-hours; `earliest` inclusive
// (0..47), `finishBy` exclusive (1..48, where 48 = 24:00).

import { SLOTS } from "@/lib/scoring";

export interface Win {
  earliest: number;
  finishBy: number;
}

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

export type ErrorKind =
  | "window_too_small"
  | "baseline_outside"
  | "infeasible"
  | "forecast_unavailable"
  | "generic";

/** The four strings each failure shows, in one place so they cannot drift apart. */
export const ERROR_COPY: Record<ErrorKind, { eyebrow: string; heading: string; body: string; cta: string }> = {
  window_too_small: {
    eyebrow: "Window too short",
    heading: "One of your loads needs a longer window.",
    body: "The run window is shorter than the load takes. Go back and choose a longer window.",
    cta: "Fix the times",
  },
  baseline_outside: {
    eyebrow: "Baseline outside window",
    heading: "That usual start isn't inside the window.",
    body: "The usual start has to be a time the load could actually run within the window you set. Go back and move it inside, or choose a longer window.",
    cta: "Fix the times",
  },
  infeasible: {
    eyebrow: "No feasible start",
    heading: "We couldn't fit that load into its window.",
    body: "There's no start time inside that window where the load finishes in time. Try a wider window.",
    cta: "Fix the times",
  },
  forecast_unavailable: {
    eyebrow: "Forecast unavailable",
    heading: "We can't reach the forecast right now.",
    body: "The carbon or price feed didn't respond. Nothing is wrong with your plan — try again shortly.",
    cta: "Back to my plan",
  },
  generic: {
    eyebrow: "Something went wrong",
    heading: "We couldn't build the plan.",
    body: "Something went wrong building the plan. Try again, or change the loads.",
    cta: "Back to my plan",
  },
};

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
