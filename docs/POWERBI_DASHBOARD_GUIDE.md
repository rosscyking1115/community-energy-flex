# Power BI dashboard guide

How to build `powerbi/community_energy_dashboard.pbix` from the reporting marts.
Everything except the `.pbix` authoring is in the repo: the star-schema marts
(`dbt_energy/models/marts/reporting/`), the DAX (`powerbi/measures.dax`), and the
model review ([POWERBI_MODEL_REVIEW.md](POWERBI_MODEL_REVIEW.md)).

## 0. Get the data (zero-setup path)

Build the marts and export them to CSV (no Snowflake or ODBC driver needed):

```bash
uv run --extra warehouse python scripts/generate_powerbi_seed.py
uv run --extra warehouse dbt build --full-refresh --project-dir dbt_energy --profiles-dir dbt_energy
uv run --extra warehouse python scripts/export_powerbi_star_tables.py
```

The final command regenerates all six CSVs together from the same DuckDB build;
the four star tables are the Power BI model input. For production, swap this
step for a direct Snowflake `MARTS` connection — the model and measures are
identical.

## 1. Connect and model

Import the **four star tables**: `dim_date`, `dim_device`, `dim_community`,
`fct_daily_savings` (Home → Get data → Text/CSV). The two `rpt_*` files are
optional — every page below is built from measures on the star, so you don't
need them in Power BI.

**Relationships** (Model view; each is one-to-many, single filter direction):

| From (one) | To (many) |
|---|---|
| `dim_date[date_key]` | `fct_daily_savings[date_key]` |
| `dim_device[device_key]` | `fct_daily_savings[device_key]` |
| `dim_community[community_key]` | `fct_daily_savings[community_key]` |

Then:
- mark `dim_date` as the date table (Table tools → Mark as date table → `full_date`)
  — the dimension is a **contiguous full-year date spine**, which DAX time
  intelligence requires (a date table with gaps silently breaks DATEADD);
- hide the three `*_key` columns in `fct_daily_savings` from report view;
- set `dim_date[day_name]` → Column tools → **Sort by column** → `day_of_week`
  (otherwise weekdays sort alphabetically);
- add the measures from [`../powerbi/measures.dax`](../powerbi/measures.dax)
  (New measure → paste one `Name = …` block at a time), setting each measure's
  **format string** per the `// Format:` note above it (Measure tools ribbon).

## 2. Pages

**Page 1 — Executive Summary.** Cards: `Total Cost Saving (GBP)`,
`Total Carbon Saving (kg)`, `Peak Slots Avoided`, `Tasks Optimised`,
`Avg Recommendation Robustness`.

**Page 2 — Cost & Carbon Timeline.** Line chart of `Total Cost Saving (GBP)`
over `dim_date[full_date]` (measures on the star — the `rpt_*` marts stay out
of the pbix); `Cost Saving (GBP) MoM %` KPI; baseline-vs-optimised columns; a
date-range slicer.

**Page 3 — Device Contribution.** Bar of `Total Cost Saving` by
`dim_device[device_type]`; `Peak Slots Avoided` by device.

**Page 4 — Community Comparison.** `rpt_monthly_community_savings` by
`dim_community[community_name]`; `Households Participating`; average savings.

**Page 5 — Recommendation Quality.** `Avg Recommendation Robustness` distribution;
`Robust Cost Saving (GBP)` vs total (shows how much saving has a strong robustness indicator);
data-freshness and constraint-violation indicators from `MONITORING.*`.

## 3. Apply the theme

**View ribbon → Themes dropdown → Browse for themes →** select
[`../powerbi/theme.json`](../powerbi/theme.json). One click restyles every page:
green = savings, amber = neutral, red = warnings, card callouts in the brand
green, consistent Segoe UI type, and soft card borders. After applying, spend a
few minutes on layout: select visuals → **Format ribbon → Align / Distribute**
so cards share edges and spacing, and replace any auto-generated visual titles
("Sum of x by y") with plain English via **Format visual → General → Title**.

## 4. Publish

Export a PDF and screenshots into `powerbi/screenshots/` for the README and the
case study. Keep the safety caveat visible: planning advice only, no guaranteed
savings.
