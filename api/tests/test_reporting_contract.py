from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from community_energy_api import main as api_main  # noqa: E402
from community_energy_api.carbon import CarbonCurveResult  # noqa: E402
from community_energy_api.main import app  # noqa: E402

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "fixtures" / "reporting_contract_v1.json"
)


def test_api_returns_the_fixed_conditional_reporting_figures(monkeypatch):
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        api_main,
        "carbon_provider",
        lambda region: CarbonCurveResult(
            values=fixture["carbon_g_per_kwh"],
            source="gb_sample_profile",
            source_label="Reporting-contract sample carbon profile",
        ),
    )

    response = TestClient(app).post("/v1/optimise", json=fixture["api_request"])

    assert response.status_code == 200
    body = response.json()
    expected = fixture["expected"]
    assert body["total_cost_saving_p"] == expected["cost_saving_p"]
    assert body["total_carbon_saving_g"] == expected["carbon_saving_g"]
    task = body["tasks"][0]
    assert task["baseline_cost_p"] - task["scheduled_cost_p"] == expected["cost_saving_p"]
    assert task["baseline_carbon_g"] - task["scheduled_carbon_g"] == expected["carbon_saving_g"]
    assert body["tasks"][0]["baseline_peak_slot_count"] == fixture["baseline_peak_slot_count"]
    assert body["tasks"][0]["scheduled_peak_slot_count"] == fixture["scheduled_peak_slot_count"]
    assert fixture["expected"]["peak_slots_avoided"] == 2
