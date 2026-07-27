"""Client and parser for the GB Carbon Intensity API (carbonintensity.org.uk).

The API is free and needs no key. It returns half-hourly forecast (and, once
the period has passed, actual) carbon intensity in gCO2/kWh, at national and
regional (DNO) level. The regional endpoints also accept a postcode.

Parsing is kept separate from I/O so it can be unit-tested against fixture
JSON with no network access. The HTTP layer uses the standard library so the
core package pulls in no third-party HTTP dependency.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from community_energy_flex.data_sources.http import get_json
from community_energy_flex.domain.models import SLOTS_PER_DAY, CarbonSlot

BASE_URL = "https://api.carbonintensity.org.uk"


_UK_TIME = ZoneInfo("Europe/London")


def _next_local_midnight_utc(now: datetime | None = None) -> datetime:
    """Next UK local midnight expressed in UTC for the provider request.

    Tasks use UK local clock time. During BST, local midnight is 23:00 UTC;
    aligning the curve here keeps slot 0 consistent with the task/UI clock.
    """
    local_now = (now or datetime.now(UTC)).astimezone(_UK_TIME)
    local_midnight = (local_now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return local_midnight.astimezone(UTC)


def _forecast_from(from_dt: datetime | None) -> str:
    # The regional forward endpoints require a {from} in the path, e.g.
    # /regional/intensity/2026-07-03T00:00Z/fw24h/regionid/13
    return (from_dt or _next_local_midnight_utc()).astimezone(UTC).strftime(
        "%Y-%m-%dT%H:%MZ"
    )


def _parse_dt(value: str) -> datetime:
    # API timestamps look like "2026-07-01T00:00Z".
    return datetime.strptime(value, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)


def parse_intensity_periods(payload: dict) -> list[CarbonSlot]:
    """Parse a Carbon Intensity API payload into ordered :class:`CarbonSlot`s.

    Handles the three shapes the API returns:
    * national ``/intensity/fw48h`` -> ``data`` is a list of periods;
    * regional (dict) -> ``data`` is a dict wrapping a ``data`` list of periods;
    * regional-by-postcode -> ``data`` is a list of one region object, whose own
      ``data`` field holds the periods.
    """
    data = payload.get("data", [])
    if isinstance(data, dict):  # regional (dict) shape nests one more level
        data = data.get("data", [])
    # regional-by-postcode nests the periods inside a single region wrapper.
    if (
        isinstance(data, list)
        and data
        and isinstance(data[0], dict)
        and "data" in data[0]
        and "from" not in data[0]
    ):
        data = data[0]["data"]

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
        self._fetch = fetch or get_json

    def national_forecast_48h(self, from_dt: datetime | None = None) -> list[CarbonSlot]:
        """National 48h forecast (96 half-hourly periods).

        The ``{from}`` segment is required. Without it the provider returns HTTP
        400 - verified against the live API on 2026-07-27, where the keyless
        ``/intensity/fw48h`` failed and ``/intensity/{from}/fw48h`` returned 96
        periods. Only the injected-fetch test exercised this before, so the
        broken URL passed unnoticed.
        """
        frm = _forecast_from(from_dt)
        return parse_intensity_periods(self._fetch(f"{self.base_url}/intensity/{frm}/fw48h"))

    def regional_forecast_by_id(
        self, region_id: int, from_dt: datetime | None = None
    ) -> list[CarbonSlot]:
        """Regional 24h forecast (48 half-hourly periods) for a DNO region id
        (1-14), from the next UK local midnight by default."""
        frm = _forecast_from(from_dt)
        return parse_intensity_periods(
            self._fetch(f"{self.base_url}/regional/intensity/{frm}/fw24h/regionid/{region_id}")
        )

    def regional_forecast_by_postcode(
        self, outcode: str, from_dt: datetime | None = None
    ) -> list[CarbonSlot]:
        """Regional 24h forecast for a postcode outcode (e.g. ``"BS1"``)."""
        outcode = outcode.strip().upper()
        frm = _forecast_from(from_dt)
        return parse_intensity_periods(
            self._fetch(f"{self.base_url}/regional/intensity/{frm}/fw24h/postcode/{outcode}")
        )
