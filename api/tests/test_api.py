from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from community_energy_api.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    assert client.get("/v1/health").json() == {"status": "ok"}


def test_regions_cover_all_uk_including_ni():
    regions = client.get("/v1/regions").json()
    assert len(regions) == 15  # 14 GB + NI
    ni = next(r for r in regions if r["id"] == "northern-ireland")
    assert ni["has_live_forecast"] is False and ni["supports_agile"] is False
    london = next(r for r in regions if r["id"] == "london")
    assert london["has_live_forecast"] is True and london["supports_agile"] is True


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
    assert "planning recommendations only" in data["safety_statement"]


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
    assert len(resp.json()["tasks"]) == 1


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
