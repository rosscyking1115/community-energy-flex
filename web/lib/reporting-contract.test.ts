import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

describe("reporting-contract fixture input", () => {
  it("keeps the explicit preferred baseline and conditional figures stable", () => {
    const fixturePath = fileURLToPath(
      new URL("../../data/fixtures/reporting_contract_v1.json", import.meta.url),
    );
    const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
    const task = fixture.api_request.tasks[0];

    expect(task.preferred).toBe("17:00");
    expect(task.duration_hours).toBe(1);
    expect(fixture.baseline_cost_p - fixture.scheduled_cost_p).toBe(fixture.expected.cost_saving_p);
    expect(fixture.baseline_carbon_g - fixture.scheduled_carbon_g).toBe(
      fixture.expected.carbon_saving_g,
    );
    expect(fixture.baseline_peak_slot_count - fixture.scheduled_peak_slot_count).toBe(
      fixture.expected.peak_slots_avoided,
    );
  });
});
