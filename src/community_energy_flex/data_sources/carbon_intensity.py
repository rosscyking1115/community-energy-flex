"""Client and parser for the GB Carbon Intensity API (carbonintensity.org.uk).

The API is free and needs no key. It returns half-hourly forecast (and, once
the period has passed, actual) carbon intensity in gCO2/kWh, at national and
regional (DNO) level. The regional endpoints also accept a postcode.

Parsing is kept separate from I/O so it can be unit-tested against fixture
JSON with no network access. The HTTP layer uses the standard library so the
core package pulls in no third-party HTTP dependency.
"""

from __future__ import annotations

import json
from datetime import datetime
from urllib.request import Request, urlopen

from community_energy_flex.domain.models import SLOTS_PER_DAY, CarbonSlot

BASE_URL = "https://api.carbonintensity.org.uk"
_USER_AGENT = "community-energy-flexibility-os/0.1 (+https://github.com)"


def _parse_dt(value: str) -> datetime:
    # API timestamps look like "2026-07-01T00:00Z".
    return datetime.strptime(value, "%Y-%m-%dT%H:%MZ")


def parse_intensity_periods(payload: dict) -> list[CarbonSlot]:
    """Parse a Carbon Intensity API payload into ordered :class:`CarbonSlot`s.

    Handles both national (``data`` is a list of periods) and regional
    (``data`` is a dict containing a ``data`` list of periods) shapes.
    """
    data = payload.get("data", [])
    if isinstance(data, dict):  # regional shape nests one more level
        data = data.get("data", [])

    slots: list[CarbonSlot] = []
    for i, period in enumerate(data):
        intensity = period.get("intensity", {})
        slots.append(
            CarbonSlot(
                index=i,
                start=_parse_dt(period["from"]),
                end=_parse_dt(period["to"]),
                forecast_gco2_per_kwh=intensity.get("forecast"),
                actual_gco2_per_kwh=intensity.get("actual"),
            )
        )
    return slots


def carbon_curve(slots: list[CarbonSlot], num_slots: int = SLOTS_PER_DAY) -> list[float]:
    """Reduce carbon slots to a per-slot gCO2/kWh array aligned to a planning
    day. Missing trailing slots are filled with the last known value."""
    if not slots:
        raise ValueError("no carbon slots to build a curve from")
    values = [s.best_estimate for s in slots[:num_slots]]
    while len(values) < num_slots:
        values.append(values[-1])
    return values


class CarbonIntensityClient:
    """Thin HTTP client. Inject ``fetch`` to test without a network."""

    def __init__(self, base_url: str = BASE_URL, fetch=None) -> None:
        self.base_url = base_url.rstrip("/")
        self._fetch = fetch or self._http_get

    def _http_get(self, url: str) -> dict:
        req = Request(url, headers={"Accept": "application/json", "User-Agent": _USER_AGENT})
        with urlopen(req, timeout=20) as resp:  # noqa: S310 - fixed https host
            return json.loads(resp.read().decode("utf-8"))

    def national_forecast_48h(self) -> list[CarbonSlot]:
        return parse_intensity_periods(self._fetch(f"{self.base_url}/intensity/fw48h"))

    def regional_forecast_by_postcode(self, outcode: str) -> list[CarbonSlot]:
        """Regional 24h forecast for a postcode outcode (e.g. ``"BS1"``)."""
        outcode = outcode.strip().upper()
        return parse_intensity_periods(
            self._fetch(f"{self.base_url}/regional/intensity/fw24h/postcode/{outcode}")
        )
