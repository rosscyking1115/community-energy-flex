"""FastAPI app. Keyless /v1/* endpoints wrapping the engine and reference data.

The carbon feed is behind a provider seam (``carbon_provider``): today it serves
a sample curve so the whole path works offline; wiring the live Carbon Intensity
forecast (GB) and the EirGrid typical-day profile (NI) is the next step, with no
change to the endpoints.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, HTTPException

from community_energy_api import reference
from community_energy_api.agile import PRODUCT as _AGILE_PRODUCT
from community_energy_api.agile import AgileUnavailable
from community_energy_api.agile import provider as _live_agile
from community_energy_api.carbon import provider as _live_carbon
from community_energy_api.models import (
    AgileTariffOut,
    ApplianceOut,
    OptimiseRequest,
    OptimiseResponse,
    RegionOut,
)
from community_energy_api.service import run_optimise

app = FastAPI(
    title="Community Energy Flexibility OS API",
    version="0.1.0",
    description="When to run flexible electricity loads to cut cost and carbon. "
    "Planning advice only - no guaranteed savings.",
)

# Live feeds, module-level so tests can swap them for offline stubs.
carbon_provider: Callable[[dict], tuple[list[float], str]] = _live_carbon
agile_provider: Callable[[dict], tuple[list[float], str]] = _live_agile


def _region_out(r: dict) -> RegionOut:
    return RegionOut(
        id=r["id"], name=r["name"], nation=r["nation"], carbon_source=r["carbon_source"],
        has_live_forecast=r["carbon_source"] == "gb_carbon_intensity",
        supports_agile=r.get("agile_gsp") is not None,
    )


@app.get("/v1/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/regions", response_model=list[RegionOut])
def list_regions() -> list[RegionOut]:
    return [_region_out(r) for r in reference.regions()]


@app.get("/v1/regions/by-postcode/{outcode}", response_model=RegionOut)
def region_by_postcode(outcode: str) -> RegionOut:
    region = reference.region_for_outcode(outcode)
    if region is None:
        raise HTTPException(status_code=404, detail=f"No region for postcode '{outcode}'")
    return _region_out(region)


@app.get("/v1/appliances", response_model=list[ApplianceOut])
def list_appliances() -> list[ApplianceOut]:
    return [ApplianceOut(**a) for a in reference.appliances()]


@app.get("/v1/tariffs/agile/{region_id}", response_model=AgileTariffOut)
def agile_tariff(region_id: str) -> AgileTariffOut:
    region = reference.region_by_id(region_id)
    if region is None:
        raise HTTPException(status_code=404, detail=f"Unknown region '{region_id}'")
    try:
        curve, day = agile_provider(region)
    except AgileUnavailable as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AgileTariffOut(
        region=region["name"], product=_AGILE_PRODUCT, day=day, unit_rates_p=curve
    )


@app.post("/v1/optimise", response_model=OptimiseResponse)
def optimise_schedule(req: OptimiseRequest) -> OptimiseResponse:
    region = reference.region_by_id(req.region_id)
    if region is None:
        raise HTTPException(status_code=404, detail=f"Unknown region '{req.region_id}'")
    # An 'agile' tariff is fetched live server-side for the region.
    if req.tariff.kind == "agile":
        try:
            req.tariff.prices_p, _ = agile_provider(region)
        except AgileUnavailable as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    curve, source = carbon_provider(region)
    try:
        return run_optimise(req, curve, source, region["name"])
    except ValueError as exc:  # invalid tariff/task constraints
        raise HTTPException(status_code=422, detail=str(exc)) from exc
