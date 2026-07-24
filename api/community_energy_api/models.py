"""API request/response models (the OpenAPI contract). Pydantic is the single
source of truth; the web app generates its TypeScript types from the schema."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RegionOut(BaseModel):
    id: str
    name: str
    nation: str
    carbon_source: str
    supports_live_forecast: bool
    supports_agile: bool


class ApplianceOut(BaseModel):
    id: str
    name: str
    category: str
    energy_kwh: float
    duration_hours: float
    typical_earliest: str = ""
    typical_latest: str = ""
    noise_sensitive: bool = False


class AgileTariffOut(BaseModel):
    region: str
    product: str
    day: str
    unit_rates_p: list[float]  # 48 half-hourly p/kWh
    source: str = "live_agile"


CarbonSource = Literal[
    "gb_live_forecast",
    "ni_eirgrid_typical_profile",
    "gb_sample_profile",
    "unavailable",
]


class CarbonProvenanceOut(BaseModel):
    carbon_source: CarbonSource
    carbon_source_label: str
    retrieved_at_utc: datetime | None = None
    valid_from_utc: datetime | None = None
    valid_to_utc: datetime | None = None
    is_live_forecast: bool
    is_fallback: bool
    fallback_reason: str | None = None


class PriceProvenanceOut(BaseModel):
    price_source: Literal["octopus_agile_live", "user_entered_tariff"] | None = None
    price_source_label: str | None = None
    price_is_live: bool = False
    price_unavailable_reason: Literal["not_supported", "not_published"] | None = None


class ForecastOut(CarbonProvenanceOut, PriceProvenanceOut):
    """The day's shape for a region: the 48-slot carbon curve the band draws,
    plus the Agile price curve when the region has one. Powers the website's
    signature day-band (home hero + results) without running an optimise."""

    region: str
    region_id: str
    carbon_g: list[float]  # 48 half-hourly gCO2/kWh
    price_p: list[float] | None = None  # 48 half-hourly p/kWh (Agile), null if unavailable
    agile_day: str | None = None  # day the price curve is for (ISO), when present
    agile_product: str | None = None
    supports_agile: bool


class TariffSpec(BaseModel):
    kind: Literal["flat", "economy7", "agile", "manual_half_hourly"] = "flat"
    standing_charge_p: float = 0.0
    # flat
    unit_rate_p: float | None = None
    # economy7
    day_rate_p: float | None = None
    night_rate_p: float | None = None
    # manual_half_hourly (48 values) or agile (fetched server-side)
    prices_p: list[float] | None = None


class TaskSpec(BaseModel):
    name: str
    device_type: str
    # Upper bounds keep a public, keyless endpoint from being handed absurd
    # inputs that balloon the solver: 500 kWh covers the largest domestic load
    # (a full EV charge is ~40-80 kWh) and a task can span at most a single day.
    energy_kwh: float = Field(gt=0, le=500)
    duration_hours: float = Field(gt=0, le=24)
    earliest: str = ""  # "HH:MM", empty = start of day
    latest: str = ""  # "HH:MM", empty or "00:00" = end of day
    preferred: str | None = None  # "HH:MM"


class OptimiseRequest(BaseModel):
    region_id: str
    tariff: TariffSpec
    # max_length caps the joint LP/MILP problem size; far more than any real
    # household or community centre schedules in one planning day.
    tasks: list[TaskSpec] = Field(min_length=1, max_length=50)
    objective: Literal["cheapest", "lowest_carbon", "balanced", "avoid_peak"] = "balanced"
    cost_weight: float = Field(default=0.5, ge=0.0, le=1.0)  # balanced only


class ScheduledTaskOut(BaseModel):
    name: str
    device_type: str
    run_window: str
    baseline_window: str
    cost_saving_p: float
    carbon_saving_g: float
    baseline_cost_p: float
    scheduled_cost_p: float
    baseline_carbon_g: float
    scheduled_carbon_g: float
    baseline_peak_slot_count: int
    scheduled_peak_slot_count: int
    robustness_score: float
    robustness_band: str
    caveat: str


class OptimiseResponse(CarbonProvenanceOut, PriceProvenanceOut):
    objective: str
    region: str
    total_cost_saving_p: float
    total_carbon_saving_g: float
    tasks: list[ScheduledTaskOut]
    safety_statement: str
