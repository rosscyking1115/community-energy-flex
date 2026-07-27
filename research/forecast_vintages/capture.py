"""Capture one vintage of the GB carbon-intensity forecast.

Run this on a schedule. Each run stores the *whole* forward window as it stood at
one moment, so the same target half-hour ends up stored once per observation time
it was forecast at. That is the only part of this that cannot be done later: the
API serves the current forecast and a single settled forecast value per past
period, and has no endpoint keyed by issue time (see README.md for the check).
Every observation time not captured is gone permanently.

Deliberately small. No app, no API, no dashboard, no scheduler of its own - point
cron or Task Scheduler at it:

    python -m research.forecast_vintages.capture

Requires the ``archive`` extra:  pip install '.[archive]'
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

BASE_URL = "https://api.carbonintensity.org.uk"
DEFAULT_ROOT = Path(__file__).resolve().parent / "data"
MANIFEST_NAME = "manifest.jsonl"
# Parquet lives under its own subdirectory so the manifest does not sit inside the
# dataset tree - a Parquet reader pointed at the root would otherwise try to open
# the manifest as a data file.
VINTAGES_DIR = "vintages"

# The forward window the API will serve in one call. 96 half-hourly periods.
_FORWARD_WINDOW = "fw48h"


@dataclass(frozen=True)
class CaptureResult:
    capture_id: str
    observed_at: datetime
    rows: int
    status: str
    parquet_path: Path | None
    error: str | None = None


def _get_json(url: str, timeout: int = 60) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.load(response)


def _api_time(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")


def _parse_api_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)


def national_rows(payload: dict, observed_at: datetime) -> list[dict]:
    rows = []
    for period in payload.get("data", []):
        intensity = period.get("intensity", {})
        rows.append(
            _row(
                observed_at=observed_at,
                period=period,
                intensity=intensity,
                region_id=None,
                region_shortname="GB national",
                dno_region=None,
            )
        )
    return rows


def regional_rows(payload: dict, observed_at: datetime) -> list[dict]:
    data = payload.get("data", [])
    if isinstance(data, dict):  # the API nests one extra level on some shapes
        data = data.get("data", [])
    rows = []
    for period in data:
        for region in period.get("regions", []):
            rows.append(
                _row(
                    observed_at=observed_at,
                    period=period,
                    intensity=region.get("intensity", {}),
                    region_id=region.get("regionid"),
                    region_shortname=region.get("shortname"),
                    dno_region=region.get("dnoregion"),
                )
            )
    return rows


def _row(
    *,
    observed_at: datetime,
    period: dict,
    intensity: dict,
    region_id: int | None,
    region_shortname: str | None,
    dno_region: str | None,
) -> dict:
    target_from = _parse_api_time(period["from"])
    return {
        # Transaction time. This is when *we* read the value, not when the
        # provider issued it - the API publishes no issue timestamp, so this is
        # an upper bound on issue time, never the issue time itself.
        "observed_at": observed_at,
        # Valid time.
        "target_from": target_from,
        "target_to": _parse_api_time(period["to"]),
        # Signed: negative means the target period had already started when the
        # value was read, which happens at the head of the forward window.
        "horizon_minutes": int((target_from - observed_at).total_seconds() // 60),
        "region_id": region_id,
        "region_shortname": region_shortname,
        "dno_region": dno_region,
        "forecast_gco2_per_kwh": intensity.get("forecast"),
        "actual_gco2_per_kwh": intensity.get("actual"),
        "intensity_index": intensity.get("index"),
    }


def _write_parquet(rows: list[dict], path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = pa.schema(
        [
            ("observed_at", pa.timestamp("us", tz="UTC")),
            ("target_from", pa.timestamp("us", tz="UTC")),
            ("target_to", pa.timestamp("us", tz="UTC")),
            ("horizon_minutes", pa.int32()),
            ("region_id", pa.int16()),
            ("region_shortname", pa.string()),
            ("dno_region", pa.string()),
            ("forecast_gco2_per_kwh", pa.int32()),
            ("actual_gco2_per_kwh", pa.int32()),
            ("intensity_index", pa.string()),
        ]
    )
    columns = {name: [row[name] for row in rows] for name in schema.names}
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(columns, schema=schema), path, compression="zstd")


def _append_manifest(root: Path, record: dict) -> None:
    """Record every attempt, including failures.

    Continuity is the point. A missing capture that nothing recorded is
    indistinguishable from a capture that returned nothing, and the whole value
    of the archive rests on knowing which observation times are actually held.
    """
    root.mkdir(parents=True, exist_ok=True)
    with (root / MANIFEST_NAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def capture(root: Path = DEFAULT_ROOT, *, now: datetime | None = None, fetch=None) -> CaptureResult:
    """Fetch one vintage and persist it. Never raises on a provider failure -
    the failure is recorded in the manifest so the gap stays visible."""
    fetch = fetch or _get_json
    observed_at = (now or datetime.now(UTC)).replace(microsecond=0).astimezone(UTC)
    capture_id = uuid.uuid4().hex[:12]
    stamp = _api_time(observed_at)
    endpoints = {
        "regional": f"{BASE_URL}/regional/intensity/{stamp}/{_FORWARD_WINDOW}",
        "national": f"{BASE_URL}/intensity/{stamp}/{_FORWARD_WINDOW}",
    }

    try:
        rows = regional_rows(fetch(endpoints["regional"]), observed_at)
        rows += national_rows(fetch(endpoints["national"]), observed_at)
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        result = CaptureResult(
            capture_id, observed_at, 0, "failed", None, f"{type(exc).__name__}: {exc}"
        )
        _append_manifest(root, _manifest_record(result, endpoints))
        return result

    if not rows:
        result = CaptureResult(
            capture_id, observed_at, 0, "empty", None, "provider returned no periods"
        )
        _append_manifest(root, _manifest_record(result, endpoints))
        return result

    path = (
        root
        / VINTAGES_DIR
        / f"dt={observed_at:%Y-%m-%d}"
        / f"vintage_{observed_at:%Y%m%dT%H%M%SZ}_{capture_id}.parquet"
    )
    _write_parquet(rows, path)
    result = CaptureResult(capture_id, observed_at, len(rows), "ok", path)
    _append_manifest(root, _manifest_record(result, endpoints))
    return result


def _manifest_record(result: CaptureResult, endpoints: dict[str, str]) -> dict:
    return {
        "capture_id": result.capture_id,
        "observed_at": result.observed_at.isoformat(),
        "status": result.status,
        "rows": result.rows,
        "parquet_path": (result.parquet_path.name if result.parquet_path else None),
        "endpoints": endpoints,
        "error": result.error,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="archive root directory")
    args = parser.parse_args(argv)
    result = capture(args.root)
    print(
        f"{result.status}: {result.rows} rows at {result.observed_at.isoformat()}"
        + (f" -> {result.parquet_path}" if result.parquet_path else "")
        + (f" ({result.error})" if result.error else "")
    )
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
