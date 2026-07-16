"use client";

import { useEffect, useMemo, useState } from "react";

import BandLegend from "@/components/BandLegend";
import DayBand from "@/components/DayBand";
import { ApiError, getAppliances, getForecast, getRegions, optimise } from "@/lib/api";
import { money, grams } from "@/lib/format";
import { parseWindow, slotToClock, type Window } from "@/lib/scoring";
import {
  CHIPS,
  classifyApiError,
  defaultBaseline,
  ERROR_COPY,
  fits,
  fittingChips,
  windowForChip,
  type Chip,
  type ErrorKind,
} from "@/lib/planning";
import type {
  Appliance,
  Forecast,
  Objective,
  OptimiseResponse,
  Region,
  TariffKind,
  TariffSpec,
} from "@/lib/types";

type Phase = "form" | "loading" | "error" | "results";

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

const TARIFFS: { id: TariffKind; label: string; sub: string; agile?: boolean }[] = [
  { id: "agile", label: "Agile", sub: "auto", agile: true },
  { id: "economy7", label: "Economy 7", sub: "day/night" },
  { id: "flat", label: "Flat rate", sub: "" },
];

const OBJECTIVES: { id: Objective; label: string }[] = [
  { id: "cheapest", label: "Cheapest" },
  { id: "lowest_carbon", label: "Lowest carbon" },
  { id: "balanced", label: "Balanced" },
  { id: "avoid_peak", label: "Avoid peak" },
];

const START_OPTS = Array.from({ length: 48 }, (_, i) => ({ v: i, label: slotToClock(i) }));
const FINISH_OPTS = Array.from({ length: 48 }, (_, i) => ({ v: i + 1, label: i + 1 >= 48 ? "24:00" : slotToClock(i + 1) }));

export default function PlanPage() {
  const [regions, setRegions] = useState<Region[]>([]);
  const [appliances, setAppliances] = useState<Appliance[]>([]);
  const [regionId, setRegionId] = useState("");
  const [tariff, setTariff] = useState<TariffKind | null>(null);
  const [added, setAdded] = useState<Added[]>([]);
  const [objective, setObjective] = useState<Objective>("balanced");
  const [weight, setWeight] = useState(0.5);
  const [forecast, setForecast] = useState<Forecast | null>(null);

  const [phase, setPhase] = useState<Phase>("form");
  const [result, setResult] = useState<OptimiseResponse | null>(null);
  const [errorKind, setErrorKind] = useState<ErrorKind>("generic");
  const [showTable, setShowTable] = useState(false);
  const [liveStatus, setLiveStatus] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    getRegions().then(setRegions).catch((e: Error) => setLoadError(e.message));
    getAppliances().then(setAppliances).catch(() => undefined);
  }, []);

  const region = useMemo(() => regions.find((r) => r.id === regionId), [regions, regionId]);

  function chooseRegion(id: string) {
    setRegionId(id);
    setTariff(null);
    setForecast(null);
    getForecast(id).then(setForecast).catch(() => setForecast(null));
  }

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

  const blockingLoad = added.find(
    (a) =>
      !fits({ earliest: a.earliest, finishBy: a.finishBy }, a.durSlots) ||
      a.preferred < a.earliest ||
      a.preferred > a.finishBy - a.durSlots,
  );
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

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canOpt) return;
    setPhase("loading");
    setLiveStatus("Working… reading the forecast.");
    const tariffSpec: TariffSpec =
      tariff === "agile"
        ? { kind: "agile" }
        : tariff === "economy7"
          ? { kind: "economy7", day_rate_p: 32, night_rate_p: 14, standing_charge_p: 45 }
          : { kind: "flat", unit_rate_p: 28 };
    const tasks = added.map((a) => ({
      name: a.name,
      device_type: a.name,
      energy_kwh: a.energy_kwh,
      duration_hours: a.duration_hours,
      earliest: slotToClock(a.earliest),
      latest: a.finishBy >= 48 ? "" : slotToClock(a.finishBy),
      preferred: slotToClock(a.preferred),
    }));
    const cost_weight = objective === "cheapest" ? 1 : objective === "lowest_carbon" ? 0 : weight;
    try {
      const [res, fc] = await Promise.all([
        optimise({ region_id: regionId, tariff: tariffSpec, tasks, objective, cost_weight }),
        forecast ? Promise.resolve(forecast) : getForecast(regionId),
      ]);
      setResult(res);
      setForecast(fc);
      setPhase("results");
      setLiveStatus(`Plan ready. ${res.tasks.length} window(s) found.`);
      window.scrollTo(0, 0);
    } catch (err) {
      const kind: ErrorKind =
        err instanceof ApiError ? classifyApiError(err.detail, err.status) : "generic";
      setErrorKind(kind);
      setPhase("error");
      setLiveStatus("Error: could not build the plan.");
    }
  }

  function backToForm() {
    setPhase("form");
    setLiveStatus("");
  }

  // ---- derived results ----
  const windows: Window[] = useMemo(
    () => (result ? result.tasks.map((t) => ({ ...parseWindow(t.run_window), label: `run ${t.run_window}` })) : []),
    [result],
  );
  const baselines = useMemo(
    () => (result ? result.tasks.map((t) => parseWindow(t.baseline_window).s) : []),
    [result],
  );

  return (
    <main style={{ maxWidth: "var(--col)", margin: "0 auto", padding: "42px var(--pad-x) 88px" }}>
      <div style={{ margin: "0 0 34px" }}>
        <p className="mono" style={eyebrow}>Plan a day</p>
        <h1 style={{ fontWeight: 700, fontSize: "clamp(26px,4vw,38px)", lineHeight: 1.08, letterSpacing: "-0.02em", margin: 0, maxWidth: "20ch" }}>
          Your region, your tariff, the loads you can move.
        </h1>
      </div>

      <p aria-live="polite" className="visually-hidden">{liveStatus}</p>
      {loadError && (
        <p role="alert" style={{ ...panel, borderLeft: "4px solid var(--filament)", margin: "0 0 24px" }}>{loadError}</p>
      )}

      {phase === "form" && (
        <form onSubmit={submit} style={{ display: "grid", gridTemplateColumns: "1fr", gap: 36 }}>
          {/* 01 region */}
          <fieldset style={fieldset}>
            <legend style={legend}><span className="mono" style={stepNo}>01</span><span style={stepTitle}>Your region</span></legend>
            <div role="radiogroup" aria-label="Region" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(210px,1fr))", gap: 8 }}>
              {regions.map((r) => {
                const sel = r.id === regionId;
                return (
                  <button key={r.id} type="button" role="radio" aria-checked={sel} onClick={() => chooseRegion(r.id)} style={{ ...regionBtn, ...(sel ? selected : unselected) }}>
                    <span style={{ display: "block", fontSize: 15, fontWeight: 600 }}>{r.name}</span>
                    <span className="mono" style={{ display: "block", fontSize: 11.5, letterSpacing: "0.04em", marginTop: 4, color: sel ? "#b9c2cc" : "var(--slate)" }}>
                      {r.supports_live_forecast ? "live forecast supported" : "typical-day profile"}
                    </span>
                  </button>
                );
              })}
            </div>
            {region && !region.supports_live_forecast && (
              <p style={{ margin: "12px 0 0", fontSize: 13.5, color: "var(--ink-soft-2)", background: "var(--panel)", border: "1px solid var(--line)", borderLeft: "3px solid var(--filament)", borderRadius: 6, padding: "11px 13px", lineHeight: 1.5 }}>
                Northern Ireland has no live GB regional feed, so this uses an <strong style={{ fontWeight: 600 }}>EirGrid typical-day profile</strong>. Treat the timings as guidance, not a same-day forecast.
              </p>
            )}
          </fieldset>

          {/* 02 tariff */}
          <fieldset style={{ ...fieldset, ...(regionId ? {} : dim) }}>
            <legend style={legend}><span className="mono" style={stepNo}>02</span><span style={stepTitle}>Your tariff</span></legend>
            <div role="radiogroup" aria-label="Tariff" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {TARIFFS.map((t) => {
                const disabled = !!t.agile && !!region && !region.supports_agile;
                const sel = tariff === t.id;
                return (
                  <button key={t.id} type="button" role="radio" aria-checked={sel} aria-disabled={disabled} onClick={() => !disabled && setTariff(t.id)} style={{ ...tariffBtn, ...(disabled ? disabledChip : sel ? selected : unselected) }}>
                    <span style={{ fontWeight: 600, fontSize: 14.5 }}>{t.label}</span>
                    <span className="mono" style={{ fontSize: 11.5, marginLeft: 9, color: disabled ? "var(--slate-mute)" : sel ? "#b9c2cc" : "var(--slate)" }}>
                      {disabled ? "needs Agile region" : t.sub}
                    </span>
                  </button>
                );
              })}
            </div>
          </fieldset>

          {/* 03 loads */}
          <fieldset style={{ ...fieldset, ...(regionId ? {} : dim) }}>
            <legend style={{ ...legend, margin: "0 0 6px" }}><span className="mono" style={stepNo}>03</span><span style={stepTitle}>Loads to move</span></legend>
            <p style={{ margin: "0 0 14px", fontSize: 13.5, color: "var(--slate)" }}>Add a preset, then choose when it can run. We&apos;ll find the cleanest window inside it.</p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "0 0 18px" }}>
              {appliances.map((a) => {
                const on = added.some((x) => x.id === a.id);
                return (
                  <button key={a.id} type="button" aria-pressed={on} onClick={() => togglePreset(a)} style={{ ...chip, ...(on ? { background: "var(--ink)", border: "1px solid var(--ink)", color: "var(--paper)" } : { background: "var(--panel)", border: "1px solid var(--ink)", color: "var(--ink)" }) }}>
                    <span style={{ fontWeight: 600 }}>{on ? "✓ " : "+ "}{a.name}</span>
                    <span className="mono" style={{ fontSize: 11.5, color: on ? "#b9c2cc" : "var(--slate)", marginLeft: 8 }}>{a.energy_kwh} kWh</span>
                  </button>
                );
              })}
            </div>

            {added.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {added.map((a) => (
                  <div key={a.key} style={{ ...panel, padding: 16 }}>
                    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, margin: "0 0 13px" }}>
                      <div>
                        <span style={{ fontWeight: 600, fontSize: 16 }}>{a.name}</span>
                        <span className="mono" style={{ fontSize: 12, color: "var(--slate)", marginLeft: 10 }}>{a.energy_kwh} kWh · {Math.round(a.duration_hours * 60)} min</span>
                      </div>
                      <button type="button" onClick={() => setAdded((p) => p.filter((x) => x.key !== a.key))} style={removeBtn}>Remove {a.name}</button>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 12 }}>
                      <div style={{ gridColumn: "1 / -1", display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 4 }}>
                        {CHIPS.map((c) => {
                          const w = windowForChip(c.id, a.noiseSensitive);
                          const disabled = c.id !== "custom" && !fits(w, a.durSlots);
                          return (
                            <button
                              key={c.id}
                              type="button"
                              aria-disabled={disabled}
                              aria-pressed={a.chip === c.id}
                              onClick={() => { if (disabled) return; chooseChip(a.key, c.id); }}
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
                              <span style={{ display: "block" }}>{c.label}</span>
                              {c.id !== "custom" && (
                                <span style={{ display: "block", fontSize: 11, opacity: 0.7 }}>
                                  {slotToClock(w.earliest)}–{slotToClock(w.finishBy)}
                                </span>
                              )}
                              {disabled && <span className="visually-hidden"> — unavailable: {a.name} needs {a.duration_hours}h, {c.label} is shorter.</span>}
                            </button>
                          );
                        })}
                      </div>
                      {a.chip === "custom" && (
                        <>
                          <TimeField label="Earliest start" value={a.earliest} opts={START_OPTS} onChange={(v) => setTime(a.key, "earliest", v)} />
                          <TimeField label="Finish by" value={a.finishBy} opts={FINISH_OPTS} onChange={(v) => setTime(a.key, "finishBy", v)} />
                          {fits({ earliest: a.earliest, finishBy: a.finishBy }, a.durSlots) && (
                            <TimeField
                              label="Usual start (baseline)"
                              value={a.preferred}
                              opts={START_OPTS.filter((o) => o.v >= a.earliest && o.v <= a.finishBy - a.durSlots)}
                              onChange={(v) => setTime(a.key, "preferred", v)}
                            />
                          )}
                        </>
                      )}
                      {!fits({ earliest: a.earliest, finishBy: a.finishBy }, a.durSlots) && (
                        <p role="status" style={{ gridColumn: "1 / -1", margin: "6px 0 0", fontSize: 13, color: "var(--ink)" }}>
                          {a.earliest >= a.finishBy
                            ? "Finish-by must be after earliest start. We plan a single midnight-to-midnight day, so a window that crosses midnight isn't supported yet."
                            : `${a.name} needs at least a ${a.duration_hours}-hour window — you've allowed ${((a.finishBy - a.earliest) / 2).toFixed(1)} hours.`}
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
                    </div>
                  </div>
                ))}
              </div>
            )}
          </fieldset>

          {/* 04 objective */}
          <fieldset style={{ ...fieldset, ...(regionId ? {} : dim) }}>
            <legend style={legend}><span className="mono" style={stepNo}>04</span><span style={stepTitle}>What matters most</span></legend>
            <div role="radiogroup" aria-label="Objective" style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "0 0 18px" }}>
              {OBJECTIVES.map((o) => {
                const sel = objective === o.id;
                return (
                  <button key={o.id} type="button" role="radio" aria-checked={sel} onClick={() => { setObjective(o.id); setWeight(o.id === "cheapest" ? 1 : o.id === "lowest_carbon" ? 0 : 0.5); }} style={{ ...objBtn, ...(sel ? selected : unselected) }}>{o.label}</button>
                );
              })}
            </div>
            <div style={{ ...panel, padding: "16px 18px", maxWidth: 540 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, color: "var(--ink-soft-2)", margin: "0 0 8px", fontWeight: 500 }}>
                <span>Lowest carbon</span><span>Cheapest cost</span>
              </div>
              <label>
                <span className="visually-hidden">Balance cost against carbon</span>
                <input type="range" min={0} max={1} step={0.05} value={weight} onChange={(e) => { setObjective("balanced"); setWeight(Number(e.target.value)); }} style={{ width: "100%", accentColor: "var(--filament)", cursor: "pointer", height: 24 }} />
              </label>
              <p className="mono" style={{ margin: "8px 0 0", fontSize: 12.5, color: "var(--ink)" }}>
                {objective === "cheapest" ? "100% cost · 0% carbon (Cheapest)" : objective === "lowest_carbon" ? "0% cost · 100% carbon (Lowest carbon)" : objective === "avoid_peak" ? "Balanced, 16:00–19:00 peak avoided" : `${Math.round(weight * 100)}% cost · ${100 - Math.round(weight * 100)}% carbon`}
              </p>
            </div>
          </fieldset>

          <div style={{ borderTop: "1px solid var(--line)", paddingTop: 22, display: "flex", flexWrap: "wrap", gap: 14, alignItems: "center" }}>
            <button type="submit" aria-disabled={!canOpt} style={{ ...ctaPrimary, ...(canOpt ? {} : { color: "var(--slate-mute)", background: "var(--panel-alt)", border: "1px solid var(--line)", cursor: "not-allowed" }) }}>Show the plan →</button>
            <span style={{ fontSize: 13, color: "var(--slate)" }}>{optHint}</span>
          </div>
        </form>
      )}

      {phase === "loading" && (
        <div aria-busy="true" style={{ animation: "cef-fade .3s ease both" }}>
          <p className="mono" style={{ fontSize: 12, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--slate)", margin: "0 0 16px" }}>Reading the forecast for {region?.name ?? "your region"}…</p>
          <div style={{ ...shimmer, width: "100%", height: 180, border: "1px solid var(--line)", borderRadius: "var(--radius-lg)", marginBottom: 14 }} />
          <div style={{ ...shimmer, height: 60, borderRadius: 8, marginBottom: 12 }} />
          <div style={{ ...shimmer, height: 60, borderRadius: 8 }} />
        </div>
      )}

      {phase === "error" && (
        <div role="alert" style={{ animation: "cef-fade .3s ease both", ...panel, borderLeft: "4px solid var(--filament)", padding: 26, maxWidth: 660 }}>
          <p className="mono" style={{ fontSize: 12, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--slate)", margin: "0 0 10px" }}>
            {ERROR_COPY[errorKind].eyebrow}
          </p>
          <h2 style={{ fontWeight: 700, fontSize: 22, margin: "0 0 10px", letterSpacing: "-0.01em" }}>
            {ERROR_COPY[errorKind].heading}
          </h2>
          <p style={{ margin: "0 0 18px", fontSize: 15, lineHeight: 1.55, color: "var(--ink-soft-2)", maxWidth: "58ch" }}>
            {ERROR_COPY[errorKind].body}
          </p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button type="button" onClick={backToForm} style={ctaPrimary}>
              {ERROR_COPY[errorKind].cta}
            </button>
          </div>
        </div>
      )}

      {phase === "results" && result && (
        <Results
          result={result}
          region={region}
          forecast={forecast}
          windows={windows}
          baselines={baselines}
          tariffLabel={tariffLabel(tariff)}
          showTable={showTable}
          onToggleTable={() => setShowTable((s) => !s)}
          onBack={backToForm}
        />
      )}
    </main>
  );
}

function tariffLabel(t: TariffKind | null): string {
  return t === "agile" ? "Octopus Agile" : t === "economy7" ? "Economy 7" : t === "flat" ? "Flat rate" : "your tariff";
}

function TimeField({ label, value, opts, onChange }: { label: string; value: number; opts: { v: number; label: string }[]; onChange: (v: number) => void }) {
  return (
    <label style={{ display: "block" }}>
      <span style={{ display: "block", fontSize: 12, color: "var(--ink-soft-2)", marginBottom: 5, fontWeight: 500 }}>{label}</span>
      <select value={value} onChange={(e) => onChange(Number(e.target.value))} style={selectStyle}>
        {opts.map((o) => (<option key={o.v} value={o.v}>{o.label}</option>))}
      </select>
    </label>
  );
}

function Results({ result, region, forecast, windows, baselines, tariffLabel, showTable, onToggleTable, onBack }: {
  result: OptimiseResponse;
  region: Region | undefined;
  forecast: Forecast | null;
  windows: Window[];
  baselines: number[];
  tariffLabel: string;
  showTable: boolean;
  onToggleTable: () => void;
  onBack: () => void;
}) {
  const source = result.carbon_source_label;
  const basis = `${tariffLabel} · ${source}`;
  const inWin = (i: number) => windows.some((w) => i >= w.s && i < w.e);
  const caveats = [
    "Savings are versus a typical 19:00 start, moved inside your chosen window when 19:00 doesn't fit — not a best case.",
    region && !region.supports_live_forecast
      ? "Northern Ireland uses a typical-day profile, so treat window timings as guidance rather than a same-day forecast."
      : result.is_fallback
        ? "The live carbon feed was unavailable, so this plan uses a labelled GB sample profile and its timings are illustrative."
      : `Regional carbon is zonal — it reflects the ${region?.name ?? "selected"} region, not your exact postcode.`,
    "A run that finishes right on your finish-by time leaves no slack. Give yourself a margin if the load must be done.",
  ];

  return (
    <div style={{ animation: "cef-fade .35s ease both" }}>
      {/* safety statement — always */}
      <div role="note" style={{ ...panel, padding: "14px 16px", margin: "0 0 26px", display: "flex", gap: 12, alignItems: "flex-start" }}>
        <span aria-hidden="true" className="mono" style={{ fontSize: 13, color: "var(--slate)", fontWeight: 600, border: "1.5px solid var(--slate)", borderRadius: "50%", width: 20, height: 20, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>i</span>
        <p style={{ margin: 0, fontSize: 13.5, color: "var(--ink-soft-2)", lineHeight: 1.5 }}>{result.safety_statement}</p>
      </div>

      {result.is_fallback && (
        <div role="status" style={{ ...panel, borderLeft: "4px solid var(--filament)", padding: "14px 16px", margin: "-12px 0 26px" }}>
          <p style={{ margin: 0, fontSize: 13.5, color: "var(--ink-soft-2)", lineHeight: 1.5 }}>
            Live carbon data was unavailable. This plan uses {result.carbon_source_label}; treat the recommended times and savings as illustrative.
          </p>
        </div>
      )}

      {/* totals */}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 20, borderBottom: "2px solid var(--ink)", paddingBottom: 22, margin: "0 0 26px" }}>
        <div>
          <p className="mono" style={{ fontSize: 11.5, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--slate)", margin: "0 0 8px" }}>Move every load and you save, tomorrow</p>
          <p className="mono" style={{ margin: 0, fontWeight: 600, fontSize: "clamp(30px,5.4vw,48px)", lineHeight: 1, letterSpacing: "-0.02em" }}>{money(result.total_cost_saving_p)} <span style={{ color: "var(--slate)", fontWeight: 500 }}>&amp;</span> {grams(result.total_carbon_saving_g)}</p>
          <p style={{ margin: "9px 0 0", fontSize: 13, color: "var(--slate)" }}>vs a typical start · {basis}</p>
        </div>
        <button type="button" onClick={onBack} style={ctaGhost}>Adjust</button>
      </div>

      {/* recommendation cards */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12, margin: "0 0 34px" }}>
        {result.tasks.map((t, i) => {
          const level = t.robustness_band === "Strong" ? 3 : t.robustness_band === "Mixed" ? 2 : 1;
          return (
            <article key={i} style={{ ...panel, padding: "18px 20px" }}>
              <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap", margin: "0 0 12px" }}>
                <h3 style={{ fontWeight: 600, fontSize: 18, margin: 0, letterSpacing: "-0.01em" }}>{t.device_type}</h3>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span aria-hidden="true" style={{ display: "flex", gap: 3 }}>
                    {[1, 2, 3].map((n) => (<span key={n} style={{ display: "inline-block", width: 13, height: 8, borderRadius: 1, border: "1px solid var(--ink)", background: n <= level ? "var(--ink)" : "transparent" }} />))}
                  </span>
                  <span className="mono" style={{ fontSize: 11, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--ink-soft-2)" }}>{t.robustness_band} robustness</span>
                </div>
              </div>
              <p style={{ margin: "0 0 14px", fontSize: 16, lineHeight: 1.5 }}>
                Run <span className="mono" style={{ fontWeight: 600, background: "var(--amber-chip)", padding: "1px 6px", borderRadius: 4 }}>{t.run_window}</span>
                <span style={{ color: "var(--slate)" }}> instead of </span>
                <span className="mono">{t.baseline_window}</span>.
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 20px", alignItems: "baseline" }}>
                <span className="mono" style={{ fontSize: 21, fontWeight: 600 }}>{money(t.cost_saving_p)}</span>
                <span className="mono" style={{ fontSize: 21, fontWeight: 600 }}>{grams(t.carbon_saving_g)}</span>
                <span style={{ fontSize: 12, color: "var(--slate)", lineHeight: 1.4 }}>saved · {basis}</span>
              </div>
              <p style={{ margin: "10px 0 0", fontSize: 12.5, color: "var(--slate)", lineHeight: 1.45 }}>{t.caveat}</p>
            </article>
          );
        })}
      </div>

      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 16, flexWrap: "wrap", margin: "0 0 6px" }}>
        <h2 style={{ fontWeight: 700, fontSize: 21, margin: 0, letterSpacing: "-0.01em" }}>Tomorrow, midnight to midnight</h2>
        <button type="button" onClick={onToggleTable} aria-expanded={showTable} style={ctaGhostSm}>{showTable ? "Hide data table" : "Show data table"}</button>
      </div>
      <p style={{ margin: "0 0 14px", fontSize: 13.5, color: "var(--ink-soft-2)", maxWidth: "66ch" }}>
        Dark bars are grid carbon each half-hour — taller and denser means heavier. The thin line is price. Amber brackets mark your recommended windows; the tick marked <em>usual</em> is the baseline start. Intensity is never shown in colour.
      </p>

      {forecast && (
        <>
          <BandLegend hasPrice={!!forecast.price_p} hasBaseline={baselines.length > 0} />
          <DayBand carbon={forecast.carbon_g} price={forecast.price_p} windows={windows} baselines={baselines} regionName={forecast.region} hasTable />
          <p style={{ margin: "8px 0 0", fontSize: 12, color: "var(--slate)", lineHeight: 1.5 }}>
            Source: {source} and {tariffLabel}. 48 half-hourly points for {forecast.region}, local time. Intensity is encoded by bar height and ink density, never by colour; amber marks only where to act.
          </p>

          {showTable && (
            <div style={{ margin: "16px 0 0", border: "1px solid var(--line)", borderRadius: 8, maxHeight: 340, overflow: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <caption style={{ textAlign: "left", padding: "12px 14px", fontSize: 12.5, color: "var(--ink-soft-2)" }}>Half-hourly price and carbon for {forecast.region} — the same figures as the band. Rows inside a recommended window are marked.</caption>
                <thead>
                  <tr style={{ position: "sticky", top: 0, background: "var(--paper-band)" }}>
                    <th scope="col" style={th}>Time</th>
                    <th scope="col" style={{ ...th, textAlign: "right" }}>Price p/kWh</th>
                    <th scope="col" style={{ ...th, textAlign: "right" }}>Carbon g/kWh</th>
                    <th scope="col" style={th}>Window</th>
                  </tr>
                </thead>
                <tbody>
                  {forecast.carbon_g.map((c, i) => (
                    <tr key={i} style={inWin(i) ? { background: "var(--amber-row)" } : undefined}>
                      <td className="mono" style={td}>{slotToClock(i)}</td>
                      <td className="mono" style={{ ...td, textAlign: "right" }}>{forecast.price_p ? forecast.price_p[i].toFixed(1) : "—"}</td>
                      <td className="mono" style={{ ...td, textAlign: "right" }}>{Math.round(c)}</td>
                      <td style={{ ...td, fontSize: 12 }}>{inWin(i) ? "● recommended" : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* caveats */}
      <section style={{ margin: "30px 0 0" }}>
        <h2 style={{ fontWeight: 700, fontSize: 19, margin: "0 0 12px", letterSpacing: "-0.01em" }}>What to keep in mind</h2>
        <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 10 }}>
          {caveats.map((c, i) => (
            <li key={i} style={{ display: "flex", gap: 10, fontSize: 14.5, color: "var(--ink-soft-2)", lineHeight: 1.5 }}>
              <span aria-hidden="true" className="mono" style={{ color: "var(--filament)", fontWeight: 600 }}>—</span><span>{c}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* sources */}
      <footer style={{ borderTop: "1px solid var(--line)", paddingTop: 18, marginTop: 30 }}>
        <p className="mono" style={{ fontSize: 11, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--slate-mute)", margin: "0 0 10px" }}>Sources</p>
        <ol style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
          <li style={srcLi}>Price — Octopus Agile half-hourly rates (or the Economy 7 / flat rates you entered).</li>
          <li style={srcLi}>Carbon — {result.carbon_source_label}{result.is_fallback ? ` (fallback: ${result.fallback_reason ?? "upstream unavailable"})` : ""}.</li>
          <li style={srcLi}>Appliance energy and duration — typical published figures; adjust to your own model if known.</li>
          <li style={srcLi}>All timings are local clock time for the selected region.</li>
        </ol>
      </footer>
    </div>
  );
}

// ---- shared style objects (token-driven) ----
const eyebrow: React.CSSProperties = { fontSize: 12, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--slate)", margin: "0 0 10px" };
const fieldset: React.CSSProperties = { border: "none", margin: 0, padding: 0, minInlineSize: 0 };
const dim: React.CSSProperties = { opacity: 0.45, pointerEvents: "none" };
const legend: React.CSSProperties = { padding: 0, display: "flex", alignItems: "baseline", gap: 10, margin: "0 0 14px" };
const stepNo: React.CSSProperties = { fontSize: 13, color: "var(--slate)", fontWeight: 600 };
const stepTitle: React.CSSProperties = { fontWeight: 600, fontSize: 20, letterSpacing: "-0.01em" };
const panel: React.CSSProperties = { background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8 };
const selected: React.CSSProperties = { background: "var(--ink)", border: "1px solid var(--ink)", color: "var(--paper)" };
const unselected: React.CSSProperties = { background: "var(--panel)", border: "1px solid var(--line)", color: "var(--ink)" };
const disabledChip: React.CSSProperties = { background: "var(--panel-alt)", border: "1px dashed var(--line-strong)", color: "var(--slate-mute)", cursor: "not-allowed" };
const regionBtn: React.CSSProperties = { textAlign: "left", cursor: "pointer", borderRadius: 8, padding: "13px 15px", minHeight: 24 };
const tariffBtn: React.CSSProperties = { cursor: "pointer", borderRadius: 7, padding: "11px 15px", display: "inline-flex", alignItems: "baseline", minHeight: 24 };
const chip: React.CSSProperties = { cursor: "pointer", borderRadius: 20, padding: "9px 15px", fontSize: 14, minHeight: 24 };
const objBtn: React.CSSProperties = { cursor: "pointer", borderRadius: 7, padding: "10px 16px", fontSize: 14.5, fontWeight: 500, minHeight: 24 };
const removeBtn: React.CSSProperties = { background: "transparent", border: "1px solid transparent", color: "var(--slate)", fontSize: 13, cursor: "pointer", textDecoration: "underline", textUnderlineOffset: 2, minHeight: 24, padding: "2px 6px", borderRadius: 5 };
const selectStyle: React.CSSProperties = { width: "100%", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontSize: 14, padding: "9px 10px", border: "1px solid var(--line-strong)", borderRadius: 7, background: "#fff", color: "var(--ink)", cursor: "pointer", minHeight: 24 };
const ctaPrimary: React.CSSProperties = { fontSize: 16, fontWeight: 600, color: "var(--paper)", background: "var(--ink)", border: "1px solid var(--ink)", borderRadius: 7, padding: "13px 24px", cursor: "pointer", minHeight: 24 };
const ctaGhost: React.CSSProperties = { fontSize: 15, fontWeight: 500, color: "var(--ink)", background: "transparent", border: "1px solid var(--line-strong)", borderRadius: 7, padding: "11px 18px", cursor: "pointer", minHeight: 24 };
const ctaGhostSm: React.CSSProperties = { fontSize: 13, fontWeight: 500, color: "var(--ink)", background: "transparent", border: "1px solid var(--line-strong)", borderRadius: 6, padding: "7px 12px", cursor: "pointer", minHeight: 24 };
const th: React.CSSProperties = { textAlign: "left", padding: "8px 14px", borderBottom: "1px solid var(--line)", fontSize: 11, letterSpacing: "0.05em", textTransform: "uppercase", color: "var(--ink-soft-2)" };
const td: React.CSSProperties = { padding: "6px 14px", borderBottom: "1px solid var(--panel-alt)" };
const srcLi: React.CSSProperties = { fontSize: 12.5, color: "var(--slate)", lineHeight: 1.5 };
const shimmer: React.CSSProperties = { background: "linear-gradient(90deg,#dde3e9 0%,#eff3f6 45%,#dde3e9 90%)", backgroundSize: "520px 100%", animation: "cef-shimmer 1.4s linear infinite" };
