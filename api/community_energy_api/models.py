"""API request/response models (the OpenAPI contract). Pydantic is the single
source of truth; the web app generates its TypeScript types from the schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RegionOut(BaseModel):
    id: str
    name: str
    nation: str
    carbon_source: str
    has_live_forecast: bool
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
    energy_kwh: float = Field(gt=0)
    duration_hours: float = Field(gt=0)
    earliest: str = ""  # "HH:MM", empty = start of day
    latest: str = ""  # "HH:MM", empty or "00:00" = end of day
    preferred: str | None = None  # "HH:MM"


class OptimiseRequest(BaseModel):
    region_id: str
    tariff: TariffSpec
    tasks: list[TaskSpec] = Field(min_length=1)
    objective: Literal["cheapest", "lowest_carbon", "balanced", "avoid_peak"] = "balanced"
    cost_weight: float = Field(default=0.5, ge=0.0, le=1.0)  # balanced only


class ScheduledTaskOut(BaseModel):
    name: str
    device_type: str
    run_window: str
    baseline_window: str
    cost_saving_p: float
    carbon_saving_g: float
    confidence: float
    confidence_band: str
    caveat: str


class OptimiseResponse(BaseModel):
    objective: str
    region: str
    carbon_source: str  # "live_forecast" | "typical_profile" | "sample"
    total_cost_saving_p: float
    total_carbon_saving_g: float
    tasks: list[ScheduledTaskOut]
    safety_statement: str
