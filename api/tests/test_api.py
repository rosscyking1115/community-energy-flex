from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from community_energy_api import main as api_main  # noqa: E402
from community_energy_api.carbon import CarbonCurveResult  # noqa: E402
from community_energy_api.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    assert client.get("/v1/health").json() == {"status": "ok"}


def test_regions_cover_all_uk_including_ni():
    regions = client.get("/v1/regions").json()
    assert len(regions) == 15  # 14 GB + NI
    ni = next(r for r in regions if r["id"] == "northern-ireland")
    assert ni["supports_live_forecast"] is False and ni["supports_agile"] is False
    london = next(r for r in regions if r["id"] == "london")
    assert london["supports_live_forecast"] is True and london["supports_agile"] is True


def test_postcode_resolves_to_region():
    assert client.get("/v1/regions/by-postcode/BS1").json()["id"] == "south-west-england"
    assert client.get("/v1/regions/by-postcode/BT9").json()["id"] == "northern-ireland"
    assert client.get("/v1/regions/by-postcode/ZZ99").status_code == 404


def test_appliances_library_is_served():
    appliances = client.get("/v1/appliances").json()
    assert len(appliances) >= 20
    assert any(a["id"] == "ev_full" for a in appliances)


def test_optimise_returns_a_schedule():
    body = {
        "region_id": "south-west-england",
        "tariff": {"kind": "economy7", "day_rate_p": 32.0, "night_rate_p": 14.0},
        "objective": "balanced",
        "tasks": [
            {"name": "Washing", "device_type": "Washing machine", "energy_kwh": 0.9,
             "duration_hours": 1.5, "latest": "07:00"},
        ],
    }
    resp = client.post("/v1/optimise", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["region"] == "South West England"
    assert len(data["tasks"]) == 1
    assert "robustness_score" in data["tasks"][0]
    assert "confidence" not in data["tasks"][0]
    assert data["carbon_source"] in {
        "gb_live_forecast", "gb_sample_profile", "ni_eirgrid_typical_profile"
    }
    assert data["price_source"] == "user_entered_tariff"
    assert data["price_source_label"] == "User-entered Economy 7 tariff"
    assert data["price_is_live"] is False
    assert "planning recommendations only" in data["safety_statement"]


def test_duplicate_task_names_are_rejected():
    """Two tasks sharing a name collide on ``task_id``, which downstream code uses
    as a key. Rejecting it beats scheduling one task where two were asked for."""
    body = {
        "region_id": "south-west-england",
        "tariff": {"kind": "economy7", "day_rate_p": 32.0, "night_rate_p": 14.0},
        "tasks": [
            {"name": "Washing", "device_type": "Washing machine", "energy_kwh": 0.9,
             "duration_hours": 1.5, "latest": "07:00"},
            {"name": "Washing", "device_type": "Washing machine", "energy_kwh": 0.9,
             "duration_hours": 1.5, "latest": "23:00"},
        ],
    }
    resp = client.post("/v1/optimise", json=body)
    assert resp.status_code == 422
    assert "unique" in resp.json()["detail"]
    assert "'Washing'" in resp.json()["detail"]


def test_distinct_task_names_still_schedule_every_task():
    body = {
        "region_id": "south-west-england",
        "tariff": {"kind": "economy7", "day_rate_p": 32.0, "night_rate_p": 14.0},
        "tasks": [
            {"name": "Washing", "device_type": "Washing machine", "energy_kwh": 0.9,
             "duration_hours": 1.5, "latest": "07:00"},
            {"name": "Washing (second load)", "device_type": "Washing machine",
             "energy_kwh": 0.9, "duration_hours": 1.5, "latest": "23:00"},
        ],
    }
    resp = client.post("/v1/optimise", json=body)
    assert resp.status_code == 200
    assert len(resp.json()["tasks"]) == 2


def test_agile_endpoint_gb_and_ni():
    gb = client.get("/v1/tariffs/agile/london")
    assert gb.status_code == 200
    assert len(gb.json()["unit_rates_p"]) == 48
    ni = client.get("/v1/tariffs/agile/northern-ireland")
    assert ni.status_code == 400  # no Agile in NI


def test_optimise_with_agile_tariff_fetches_prices():
    body = {
        "region_id": "london",
        "tariff": {"kind": "agile"},  # prices fetched server-side
        "tasks": [
            {"name": "EV", "device_type": "EV charge", "energy_kwh": 40.0,
             "duration_hours": 6.0, "latest": "07:30"},
        ],
    }
    resp = client.post("/v1/optimise", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tasks"]) == 1
    assert data["price_source"] == "octopus_agile_live"
    assert data["price_source_label"] == "Octopus Agile published rates"
    assert data["price_is_live"] is True


def test_forecast_gb_has_live_provenance_and_price(monkeypatch):
    monkeypatch.setattr(
        api_main,
        "carbon_provider",
        lambda region: CarbonCurveResult(
            values=[100.0] * 48,
            source="gb_live_forecast",
            source_label="NESO / Carbon Intensity regional forecast",
        ),
    )
    resp = client.get("/v1/forecast/london")
    assert resp.status_code == 200
    data = resp.json()
    assert data["region"] == "London"
    assert len(data["carbon_g"]) == 48
    assert data["is_live_forecast"] is True and data["supports_agile"] is True
    assert data["is_fallback"] is False
    assert data["carbon_source"] == "gb_live_forecast"
    assert data["price_p"] is not None and len(data["price_p"]) == 48
    assert data["agile_product"]


def test_forecast_ni_has_carbon_but_no_price():
    resp = client.get("/v1/forecast/northern-ireland")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["carbon_g"]) == 48
    assert data["supports_agile"] is False
    assert data["price_p"] is None
    assert data["price_unavailable_reason"] == "not_supported"


def test_optimise_returns_503_when_region_carbon_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        api_main,
        "carbon_provider",
        lambda region: CarbonCurveResult(
            values=[],
            source="unavailable",
            source_label="Carbon data unavailable",
            is_fallback=True,
            fallback_reason="invalid_payload",
        ),
    )
    body = {
        "region_id": "northern-ireland",
        "tariff": {"kind": "flat", "unit_rate_p": 28},
        "tasks": [
            {
                "name": "Washing",
                "device_type": "Washing machine",
                "energy_kwh": 0.9,
                "duration_hours": 1.5,
            }
        ],
    }

    response = client.post("/v1/optimise", json=body)

    assert response.status_code == 503
    assert response.json()["detail"] == "Carbon data is unavailable for this region"


def test_forecast_unknown_region_404():
    assert client.get("/v1/forecast/atlantis").status_code == 404


def test_optimise_rejects_impossible_window():
    body = {
        "region_id": "london",
        "tariff": {"kind": "flat", "unit_rate_p": 28.0},
        "tasks": [
            {"name": "X", "device_type": "EV charge", "energy_kwh": 40.0,
             "duration_hours": 6.0, "earliest": "23:00", "latest": "01:00"},
        ],
    }
    assert client.post("/v1/optimise", json=body).status_code == 422


def test_optimise_rejects_out_of_bounds_inputs():
    """The public solver must reject absurd inputs (energy/duration/task-count)
    at the contract layer, before they reach the optimiser."""
    base = {"region_id": "london", "tariff": {"kind": "flat", "unit_rate_p": 28.0}}
    huge_energy = {"name": "X", "device_type": "EV charge", "energy_kwh": 100_000.0,
                   "duration_hours": 2.0, "latest": "07:00"}
    huge_duration = {"name": "X", "device_type": "EV charge", "energy_kwh": 5.0,
                     "duration_hours": 999.0, "latest": "07:00"}
    ok_task = {"name": "X", "device_type": "Washing machine", "energy_kwh": 0.9,
               "duration_hours": 1.0, "latest": "07:00"}

    assert client.post("/v1/optimise", json={**base, "tasks": [huge_energy]}).status_code == 422
    assert client.post("/v1/optimise", json={**base, "tasks": [huge_duration]}).status_code == 422
    assert client.post("/v1/optimise", json={**base, "tasks": [ok_task] * 51}).status_code == 422
