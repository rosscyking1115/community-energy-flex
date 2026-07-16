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
