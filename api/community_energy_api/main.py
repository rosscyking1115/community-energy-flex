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
from community_energy_api.models import (
    ApplianceOut,
    OptimiseRequest,
    OptimiseResponse,
    RegionOut,
)
from community_energy_api.service import run_optimise
from community_energy_flex.demo import sample_carbon_curve

app = FastAPI(
    title="Community Energy Flexibility OS API",
    version="0.1.0",
    description="When to run flexible electricity loads to cut cost and carbon. "
    "Planning advice only - no guaranteed savings.",
)


def _sample_carbon(region: dict) -> tuple[list[float], str]:
    return sample_carbon_curve(), "sample"


# Swap this for the live GB forecast / NI typical-profile provider.
carbon_provider: Callable[[dict], tuple[list[float], str]] = _sample_carbon


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


@app.post("/v1/optimise", response_model=OptimiseResponse)
def optimise_schedule(req: OptimiseRequest) -> OptimiseResponse:
    region = reference.region_by_id(req.region_id)
    if region is None:
        raise HTTPException(status_code=404, detail=f"Unknown region '{req.region_id}'")
    curve, source = carbon_provider(region)
    try:
        return run_optimise(req, curve, source, region["name"])
    except ValueError as exc:  # invalid tariff/task constraints
        raise HTTPException(status_code=422, detail=str(exc)) from exc
