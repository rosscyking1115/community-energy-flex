from __future__ import annotations

from community_energy_flex.data_sources.carbon_intensity import (
    CarbonIntensityClient,
    carbon_curve,
    parse_intensity_periods,
)

NATIONAL = {
    "data": [
        {"from": "2026-07-01T00:00Z", "to": "2026-07-01T00:30Z",
         "intensity": {"forecast": 120, "actual": 115}},
        {"from": "2026-07-01T00:30Z", "to": "2026-07-01T01:00Z",
         "intensity": {"forecast": 130, "actual": None}},
    ]
}

REGIONAL = {
    "data": {
        "regionid": 3, "shortname": "South West",
        "data": [
            {"from": "2026-07-01T00:00Z", "to": "2026-07-01T00:30Z",
             "intensity": {"forecast": 90, "index": "low"}},
        ],
    }
}


def test_parses_national_periods_with_actuals():
    slots = parse_intensity_periods(NATIONAL)
    assert len(slots) == 2
    assert slots[0].best_estimate == 115  # prefers actual
    assert slots[1].best_estimate == 130  # falls back to forecast


def test_parses_nested_regional_shape():
    slots = parse_intensity_periods(REGIONAL)
    assert len(slots) == 1
    assert slots[0].forecast_gco2_per_kwh == 90


def test_carbon_curve_pads_to_requested_length():
    slots = parse_intensity_periods(NATIONAL)
    curve = carbon_curve(slots, num_slots=4)
    assert curve == [115, 130, 130, 130]  # last value repeated


def test_client_uses_injected_fetch():
    client = CarbonIntensityClient(fetch=lambda url: NATIONAL)
    slots = client.national_forecast_48h()
    assert len(slots) == 2
