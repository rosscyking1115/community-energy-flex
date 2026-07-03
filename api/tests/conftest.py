"""Keep API tests offline: stub the carbon provider so /v1/optimise never hits
the live carbon feed during tests."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

import community_energy_api.main as main  # noqa: E402
from community_energy_flex.demo import sample_carbon_curve  # noqa: E402


@pytest.fixture(autouse=True)
def offline_feeds(monkeypatch):
    from community_energy_api.agile import AgileUnavailable

    monkeypatch.setattr(main, "carbon_provider", lambda region: (sample_carbon_curve(), "sample"))

    def _fake_agile(region):
        if region.get("agile_gsp") is None:
            raise AgileUnavailable(f"Agile is not available in {region['name']}")
        return [15.0] * 48, "2026-07-04"

    monkeypatch.setattr(main, "agile_provider", _fake_agile)
