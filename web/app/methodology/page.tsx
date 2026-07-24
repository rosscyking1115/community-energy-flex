import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Method — Community Energy Flex",
  description: "How the recommended window and the saving are worked out.",
};

const ROWS = [
  {
    h: "The comparison start is yours",
    p: "Every reportable planning difference is measured against the preferred start you explicitly provide. It is not a best case, a national average, or an inferred usual time. If you do not provide one, the planner can still recommend a feasible window but does not report a cost or carbon difference.",
  },
  {
    h: "Two channels: price and carbon",
    p: "Price comes from your tariff — half-hourly Octopus Agile rates, or the Economy 7 / flat rate you enter. Carbon comes from the regional forecast, drawn as the band's bars. We score each possible start on both and let you weight which matters more.",
  },
  {
    h: "Carbon is regional, not per-postcode",
    p: 'Grid carbon intensity is published by region (a GSP group), so we say "South West England region", never your street. Northern Ireland has no live GB feed, so we use a typical-day EirGrid profile and label it as such.',
  },
  {
    h: "A robustness indicator, not a probability",
    p: "The Strong, Mixed, or Fragile indicator combines how decisive the preferred window is with forecast horizon, carbon-data type, and tariff provenance. It is deterministic and uncalibrated: it helps expose sensitivity, but it is not a probability and does not guarantee an outcome.",
  },
];

export default function Methodology() {
  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "54px var(--pad-x) 88px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--slate)", margin: "0 0 16px" }}>
        Method
      </p>
      <h1 style={{ fontWeight: 700, fontSize: "clamp(28px,4.4vw,42px)", lineHeight: 1.08, letterSpacing: "-0.025em", margin: "0 0 28px", maxWidth: "18ch" }}>
        How the window and the saving are worked out.
      </h1>
      <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
        {ROWS.map((m) => (
          <div key={m.h}>
            <h2 style={{ fontWeight: 600, fontSize: 20, margin: "0 0 8px", letterSpacing: "-0.01em" }}>{m.h}</h2>
            <p style={{ margin: 0, fontSize: 16, color: "var(--ink-soft)", lineHeight: 1.62 }}>{m.p}</p>
          </div>
        ))}
        <div style={{ borderTop: "1px solid var(--line)", paddingTop: 20 }}>
          <p style={{ margin: 0, fontSize: 13.5, color: "var(--slate)", lineHeight: 1.6 }}>
            Open source. Price: Octopus Agile API. Carbon: NESO / National Grid
            Carbon Intensity regional forecast (GB); EirGrid typical-day profile
            (Northern Ireland). Appliance energy figures are typical published
            values — adjust them to your own if you know them.
          </p>
        </div>
      </div>
    </main>
  );
}
