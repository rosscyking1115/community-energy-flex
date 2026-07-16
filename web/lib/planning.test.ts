import { describe, expect, it } from "vitest";

import { defaultBaseline, fits, windowForChip } from "@/lib/planning";

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
