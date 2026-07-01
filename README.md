# Community Energy Flexibility OS

> Decision-support that tells households and small organisations **when** to run
> flexible electricity loads to cut cost and carbon — while respecting their
> comfort constraints.

It does not just show *"carbon is low at 02:00"*. It says *"run the washing
machine 02:30–04:00, charge the EV 01:30–04:30, expected saving £0.12 and
0.14 kg CO₂, high confidence"* — with the assumptions and caveats attached.

> [!NOTE]
> Planning advice only. This tool does not control appliances, guarantee
> savings, or replace official energy or supplier advice.

## Status

**Milestone A — usable vertical slice.** Working today: carbon-intensity client,
tariff models (flat / Economy 7 / time-of-use), the rule-based optimiser with
baseline comparison, confidence, and caveats, a Streamlit app, text/Excel/PDF
reports, and a dbt-on-DuckDB warehouse scaffold. See [docs/ROADMAP.md](docs/ROADMAP.md)
for the full 3-month plan (Snowflake, Dagster, MLflow, LP optimiser, Power BI).

## Quickstart

```bash
python -m pip install -e ".[dev]"     # core + tests (no heavy deps)
python -m pytest                       # 40 tests, runs in <1s
python -m community_energy_flex cheapest   # end-to-end on sample data
```

Run the app (installs Streamlit):

```bash
python -m pip install -e ".[app,reports]"
streamlit run app/streamlit_app.py
```

## How it works

```
Carbon Intensity API ─┐
Tariff (flat/E7/ToU) ─┼─► half-hourly "energy options" ─► rule-based optimiser ─► schedule
Your task constraints ┘        (dbt / DuckDB)              (cheapest / greenest /   + baseline
                                                            balanced / avoid-peak)   + savings
                                                                                     + confidence
                                                                                        │
                                                    Streamlit app · Excel/PDF report ◄──┘
```

The day is 48 half-hour **slots**. Tasks, tariffs, and carbon forecasts are all
expressed in slots, so the optimiser reasons over one clean integer axis. Every
recommendation is compared against a **baseline** (business as usual) and
carries a **confidence** band and a plain-language **caveat**. The maths behind
those three is spelled out in [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Project layout

| Path | What's there |
|---|---|
| `src/community_energy_flex/` | Core: `domain/`, `data_sources/`, `optimisation/`, `reporting/` |
| `app/streamlit_app.py` | The decision app |
| `dbt_energy/` | dbt-on-DuckDB warehouse (staging → half-hourly options mart) |
| `tests/` | Optimiser invariants, confidence, tariffs, reports, API parsing |
| `docs/` | Product thesis, data sources, methodology, safety & privacy, roadmap |

## Data sources

- **GB Carbon Intensity API** (carbonintensity.org.uk) — free, no key.
- **Tariffs** — entered manually or via CSV; time-of-use / Agile-style supported.

See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) for fields and licensing.

## Contributing

See `CONTRIBUTING.md` (to be added). Licensed under MIT — see `LICENSE`.
