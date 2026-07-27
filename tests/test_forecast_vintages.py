"""Tests for the forecast-vintage capture job.

No network: every test injects a fake fetch. The point of the archive is that
gaps stay visible, so failure recording is tested as carefully as success.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("pyarrow")

from research.forecast_vintages.backup import back_up  # noqa: E402
from research.forecast_vintages.capture import (  # noqa: E402
    MANIFEST_NAME,
    VINTAGES_DIR,
    capture,
    national_rows,
    regional_rows,
)
from research.forecast_vintages.continuity import continuity, read_manifest  # noqa: E402

OBSERVED = datetime(2026, 7, 27, 6, 0, tzinfo=UTC)

REGIONAL = {
    "data": [
        {
            "from": "2026-07-27T06:00Z",
            "to": "2026-07-27T06:30Z",
            "regions": [
                {
                    "regionid": 1,
                    "dnoregion": "Scottish Hydro Electric Power Distribution",
                    "shortname": "North Scotland",
                    "intensity": {"forecast": 12, "index": "very low"},
                },
                {
                    "regionid": 13,
                    "dnoregion": "UK Power Networks (South Eastern)",
                    "shortname": "South East England",
                    "intensity": {"forecast": 210, "index": "high"},
                },
            ],
        },
        {
            "from": "2026-07-27T06:30Z",
            "to": "2026-07-27T07:00Z",
            "regions": [
                {
                    "regionid": 1,
                    "dnoregion": "Scottish Hydro Electric Power Distribution",
                    "shortname": "North Scotland",
                    "intensity": {"forecast": 15, "index": "very low"},
                },
                {
                    "regionid": 13,
                    "dnoregion": "UK Power Networks (South Eastern)",
                    "shortname": "South East England",
                    "intensity": {"forecast": 205, "index": "high"},
                },
            ],
        },
    ]
}

NATIONAL = {
    "data": [
        {
            "from": "2026-07-27T06:00Z",
            "to": "2026-07-27T06:30Z",
            "intensity": {"forecast": 98, "actual": 101, "index": "moderate"},
        }
    ]
}


def _fetch(url: str) -> dict:
    return REGIONAL if "regional" in url else NATIONAL


def test_every_region_and_period_becomes_a_row():
    rows = regional_rows(REGIONAL, OBSERVED)
    assert len(rows) == 4  # 2 periods x 2 regions
    assert {r["region_shortname"] for r in rows} == {"North Scotland", "South East England"}


def test_horizon_is_measured_from_the_observation_time():
    rows = regional_rows(REGIONAL, OBSERVED)
    by_target = {(r["target_from"], r["region_id"]): r for r in rows}
    assert by_target[(OBSERVED, 1)]["horizon_minutes"] == 0
    assert by_target[(OBSERVED + timedelta(minutes=30), 1)]["horizon_minutes"] == 30


def test_national_rows_carry_no_region_id():
    rows = national_rows(NATIONAL, OBSERVED)
    assert len(rows) == 1
    assert rows[0]["region_id"] is None
    assert rows[0]["forecast_gco2_per_kwh"] == 98
    assert rows[0]["actual_gco2_per_kwh"] == 101


def test_capture_writes_parquet_and_records_the_attempt(tmp_path):
    result = capture(tmp_path, now=OBSERVED, fetch=_fetch)
    assert result.status == "ok"
    assert result.rows == 5  # 4 regional + 1 national
    assert result.parquet_path.exists()

    import pyarrow.parquet as pq

    table = pq.read_table(result.parquet_path)
    assert table.num_rows == 5

    records = read_manifest(tmp_path)
    assert len(records) == 1
    assert records[0]["status"] == "ok" and records[0]["rows"] == 5


def test_a_provider_failure_is_recorded_rather_than_raised(tmp_path):
    def failing_fetch(url: str) -> dict:
        raise OSError("connection reset")

    result = capture(tmp_path, now=OBSERVED, fetch=failing_fetch)
    assert result.status == "failed"
    assert result.parquet_path is None

    records = read_manifest(tmp_path)
    assert len(records) == 1
    assert records[0]["status"] == "failed"
    assert "connection reset" in records[0]["error"]


def test_the_same_target_period_is_stored_once_per_observation_time(tmp_path):
    """The whole point: one target half-hour, many vintages."""
    later = OBSERVED + timedelta(hours=1)
    capture(tmp_path, now=OBSERVED, fetch=_fetch)
    capture(tmp_path, now=later, fetch=_fetch)

    import pyarrow.parquet as pq

    table = pq.read_table(tmp_path / VINTAGES_DIR)
    rows = table.to_pylist()
    target = datetime(2026, 7, 27, 6, 0, tzinfo=UTC)
    vintages = {
        r["observed_at"] for r in rows if r["target_from"] == target and r["region_id"] == 1
    }
    assert vintages == {OBSERVED, later}


def test_continuity_reports_gaps_between_successful_captures():
    records = [
        {"observed_at": "2026-07-27T06:00:00+00:00", "status": "ok", "rows": 5},
        {"observed_at": "2026-07-27T07:00:00+00:00", "status": "ok", "rows": 5},
        # five hours missing here
        {"observed_at": "2026-07-27T12:00:00+00:00", "status": "ok", "rows": 5},
        {"observed_at": "2026-07-27T13:00:00+00:00", "status": "failed", "rows": 0},
    ]
    report = continuity(records, expected_interval_minutes=60)
    assert report.attempts == 4
    assert report.captured == 3
    assert report.failed == 1
    assert len(report.gaps) == 1
    assert report.longest_gap == timedelta(hours=5)


def test_continuity_is_empty_rather_than_wrong_when_nothing_was_captured(tmp_path):
    report = continuity(read_manifest(tmp_path))
    assert report.attempts == 0
    assert report.first_observed_at is None
    assert report.gaps == []
    assert report.is_stalled()  # nothing collecting is not the same as nothing wrong


def test_a_dead_job_is_reported_as_stalled_even_though_it_leaves_no_gap():
    """The failure a gap check cannot see.

    If the scheduled task dies, there is never a later success to bound a gap,
    so the record looks like an unblemished run of captures. Only the distance
    from the last capture to now reveals it.
    """
    records = [
        {"observed_at": "2026-07-27T06:00:00+00:00", "status": "ok", "rows": 5},
        {"observed_at": "2026-07-27T07:00:00+00:00", "status": "ok", "rows": 5},
    ]
    long_after = datetime(2026, 7, 29, 7, 0, tzinfo=UTC)
    report = continuity(records, expected_interval_minutes=60, now=long_after)

    assert report.gaps == []  # a gap check sees nothing wrong
    assert report.captured == 2
    assert report.stale_for == timedelta(days=2)
    assert report.is_stalled(60)


def test_backup_copies_vintages_and_manifest_then_verifies_them(tmp_path):
    source, dest = tmp_path / "src", tmp_path / "dst"
    capture(source, now=OBSERVED, fetch=_fetch)
    capture(source, now=OBSERVED + timedelta(hours=1), fetch=_fetch)

    result = back_up(source, dest=dest)
    assert len(result.copied) == 3  # two parquet files plus the manifest
    assert result.mismatched == []
    assert result.ok
    assert (dest / MANIFEST_NAME).exists()
    assert len(list((dest / VINTAGES_DIR).rglob("*.parquet"))) == 2


def test_backup_is_incremental_and_always_refreshes_the_growing_manifest(tmp_path):
    source, dest = tmp_path / "src", tmp_path / "dst"
    capture(source, now=OBSERVED, fetch=_fetch)
    back_up(source, dest=dest)

    capture(source, now=OBSERVED + timedelta(hours=1), fetch=_fetch)
    second = back_up(source, dest=dest)

    # the new parquet plus the manifest, not the parquet already copied
    assert len(second.copied) == 2
    assert second.already_present == 1
    assert (source / MANIFEST_NAME).read_text(encoding="utf-8") == (
        dest / MANIFEST_NAME
    ).read_text(encoding="utf-8")


def test_backup_never_deletes_at_the_destination(tmp_path):
    """A bug here would destroy the only copy of unrecoverable data."""
    source, dest = tmp_path / "src", tmp_path / "dst"
    capture(source, now=OBSERVED, fetch=_fetch)
    back_up(source, dest=dest)

    stray = dest / VINTAGES_DIR / "dt=2020-01-01" / "older_backup.parquet"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b"irreplaceable")

    back_up(source, dest=dest)
    assert stray.exists() and stray.read_bytes() == b"irreplaceable"


def test_a_healthy_job_is_not_reported_as_stalled():
    records = [
        {"observed_at": "2026-07-27T06:00:00+00:00", "status": "ok", "rows": 5},
        {"observed_at": "2026-07-27T07:00:00+00:00", "status": "ok", "rows": 5},
    ]
    soon_after = datetime(2026, 7, 27, 7, 40, tzinfo=UTC)
    report = continuity(records, expected_interval_minutes=60, now=soon_after)
    assert not report.is_stalled(60)


# --- The one error this archive is most likely to produce ---------------------
#
# `observed_at` is when this job READ the forecast. The provider publishes no
# issue timestamp, so it is an upper bound on issue time and never the issue
# time itself. An analysis that quietly reinterprets it as issue time would
# report horizons that are wrong in a direction that flatters the forecast, and
# nothing about the data itself would look off. These tests make that drift fail
# the build rather than pass review, in the same spirit as test_public_claims.py.

_ARCHIVE = Path(__file__).resolve().parents[1] / "research" / "forecast_vintages"
_ISSUE_TIME_NAMES = ("issued_at", "issue_time", "published_at", "publication_time")


def test_the_vintage_key_is_never_renamed_to_an_issue_time():
    rows = regional_rows(REGIONAL, OBSERVED) + national_rows(NATIONAL, OBSERVED)
    for row in rows:
        assert "observed_at" in row
        for banned in _ISSUE_TIME_NAMES:
            assert banned not in row, (
                f"{banned!r} implies the provider told us when the forecast was issued. "
                "It does not. The column is observed_at - capture time."
            )


def test_the_written_schema_carries_the_capture_time_column(tmp_path):
    result = capture(tmp_path, now=OBSERVED, fetch=_fetch)

    import pyarrow.parquet as pq

    names = pq.read_table(result.parquet_path).schema.names
    assert "observed_at" in names
    assert not [n for n in names if n in _ISSUE_TIME_NAMES]


def test_the_archive_documents_that_observed_at_is_not_publication_time():
    readme = (_ARCHIVE / "README.md").read_text(encoding="utf-8").lower()
    assert "capture time, not publication time" in readme
    assert "upper bound" in readme
    assert "horizons-from-observation" in readme


def test_the_capture_module_says_so_where_the_value_is_set():
    """The README can be missed. The comment sits on the assignment itself."""
    source = (_ARCHIVE / "capture.py").read_text(encoding="utf-8").lower()
    assert "upper bound on issue time, never the issue time itself" in source


def test_the_claim_ledger_still_carries_the_observed_at_boundary():
    ledger = (
        Path(__file__).resolve().parents[1] / "docs" / "CLAIM_LEDGER.md"
    ).read_text(encoding="utf-8")
    assert "`observed_at` in the vintage archive is the forecast's issue time." in ledger
    assert "Not supported" in ledger
