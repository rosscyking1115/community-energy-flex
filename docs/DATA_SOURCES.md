# Data sources

## Carbon intensity — GB Carbon Intensity API

- Base: `https://api.carbonintensity.org.uk` — **free, no API key**.
- Half-hourly **forecast** and, once a period passes, **actual** gCO₂/kWh.
- National (`/intensity/fw48h`) and regional/DNO, incl. postcode outcode
  (`/regional/intensity/fw24h/postcode/{outcode}`).
- Operated by NESO with the University of Oxford. Attribute the source in any
  published output.

Client + parser: `src/community_energy_flex/data_sources/carbon_intensity.py`
(parsing is separated from I/O and unit-tested against fixture JSON).

> [!NOTE]
> Regional data is by DNO/GSP region, not raw postcode — the postcode endpoint
> resolves the region for you. `generation_mix` is a nested array; flatten it in
> staging if/when it is ingested.

## Tariffs

MVP: manual entry or CSV. Models in `data_sources/tariffs.py`:

- **FlatTariff** — one unit rate all day.
- **Economy7Tariff** — day/night, wraps past midnight.
- **MultiBandTariff** — generic time-of-use / Agile-style (one band per slot).

Later: Octopus **Agile** public API (free, half-hourly — matches the carbon
cadence). Fields carried: `unit_rate_p_per_kwh`, `standing_charge_p` (excluded
from savings — see [METHODOLOGY.md](METHODOLOGY.md)).

## Weather (later)

Default to **Open-Meteo** (free, no key) as a demand/solar feature. Met Office
DataPoint requires registration. Pin the chosen source and its licence here when
ingested.

## Device / task constraints

User-entered. Fields: `task_id, device_type, energy_kwh, duration_slots,
earliest_start, latest_finish, must_run, preferred_start, noise_sensitive,
comfort_priority`. See `domain/models.py::Task`.
