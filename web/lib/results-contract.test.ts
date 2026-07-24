import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Results } from "../app/plan/page.client";
import type { OptimiseResponse } from "@/lib/types";

const result: OptimiseResponse = {
  price_is_live: true,
  carbon_source: "gb_live_forecast",
  carbon_source_label: "GB regional forecast",
  is_live_forecast: true,
  is_fallback: false,
  objective: "balanced",
  region: "South West England",
  total_cost_saving_p: 120,
  total_carbon_saving_g: 340,
  safety_statement: "Planning only; not a savings guarantee.",
  tasks: [{
    name: "Dishwasher",
    device_type: "Dishwasher",
    run_window: "01:00-02:00",
    baseline_window: "19:00-20:00",
    cost_saving_p: 120,
    carbon_saving_g: 340,
    baseline_cost_p: 200,
    scheduled_cost_p: 80,
    baseline_carbon_g: 500,
    scheduled_carbon_g: 160,
    baseline_peak_slot_count: 1,
    scheduled_peak_slot_count: 0,
    robustness_score: 0.9,
    robustness_band: "Strong",
    caveat: "Use the declared window.",
  }],
};

function renderResult(
  reportingStatus: "reportable" | "not_reportable",
  basis: "forecast" | "sample_input" | "fallback",
) {
  return renderToStaticMarkup(React.createElement(Results, {
    result: { ...result, is_fallback: basis === "fallback" },
    region: { id: "sw", name: "South West England", nation: "England", carbon_source: "live", supports_live_forecast: true, supports_agile: true },
    forecast: null,
    windows: [],
    baselines: [],
    tariffLabel: "Flat rate",
    reportingStatus,
    reportBasis: basis,
    showTable: false,
    onToggleTable: () => undefined,
    onBack: () => undefined,
  }));
}

describe("planner results reporting contract", () => {
  it("renders a forecast result as an estimated difference relative to the explicit preferred start", () => {
    const html = renderResult("reportable", "forecast");

    expect(html).toContain("Estimated planning difference relative to your preferred start");
    expect(html).toContain("forecast planning result; not a savings guarantee");
    expect(html).not.toContain("Move every load and you save, tomorrow");
  });

  it.each([
    ["sample_input", "Illustrative sample-input planning result; not a savings guarantee"],
    ["fallback", "Illustrative fallback planning result; not a savings guarantee"],
  ] as const)("renders %s provenance without an unqualified savings claim", (basis, expected) => {
    expect(renderResult("reportable", basis)).toContain(expected);
  });

  it("suppresses inherited baseline and metric copy when no explicit preferred start was supplied", () => {
    const html = renderResult("not_reportable", "sample_input");

    expect(html).toContain("Not reportable: add an explicit preferred start to compare cost and carbon.");
    expect(html).not.toContain("£1.20");
    expect(html).not.toContain("instead of");
    expect(html).not.toContain("saved ·");
  });
});
