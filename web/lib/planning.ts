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
