"""Live Octopus Agile tariff provider.

Fetches the half-hourly Agile unit rates for a region's GSP group and reduces
them to a 48-slot price curve for the planning day. Agile is GB-only; regions
without a GSP letter (Northern Ireland) raise :class:`AgileUnavailable`. Unlike
carbon there is no sample fallback - if the specific tariff isn't available the
caller gets a clear error, not made-up prices.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta

from community_energy_flex.data_sources.octopus_agile import OctopusAgileClient, day_price_curve

PRODUCT = "AGILE-24-10-01"  # current Octopus Agile import product
_TTL_SECONDS = 1800
_cache: dict[str, tuple[float, list[float], str]] = {}


class AgileUnavailable(RuntimeError):
    """Agile prices can't be served for this region (no GSP / not published)."""


def _target_day() -> date:
    return (datetime.now(UTC) + timedelta(days=1)).date()


def agile_curve(
    region: dict, client: OctopusAgileClient | None = None, day: date | None = None
) -> tuple[list[float], str]:
    """Return (48-slot p/kWh curve, day used). Tries the target day, then the
    previous day if tomorrow's prices aren't published yet."""
    gsp = region.get("agile_gsp")
    if gsp is None:
        raise AgileUnavailable(f"Agile is not available in {region['name']}")
    client = client or OctopusAgileClient()
    tariff_code = f"E-1R-{PRODUCT}-{gsp}"
    rates = client.unit_rates(PRODUCT, tariff_code)
    target = day or _target_day()
    for candidate in (target, target - timedelta(days=1)):
        try:
            return day_price_curve(rates, candidate), candidate.isoformat()
        except ValueError:
            continue
    raise AgileUnavailable(f"No Agile prices published yet for {region['name']}")


def provider(region: dict) -> tuple[list[float], str]:
    key = region["id"]
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and cached[0] > now:
        return cached[1], cached[2]
    curve, day = agile_curve(region)  # raises AgileUnavailable
    _cache[key] = (now + _TTL_SECONDS, curve, day)
    return curve, day


def clear_cache() -> None:
    _cache.clear()
