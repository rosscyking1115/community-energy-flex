"""Report capture continuity from the manifest.

The archive is only worth what its coverage record says it is. This reads the
manifest and reports what is actually held, including the gaps - it does not
infer coverage from whatever Parquet files happen to be on disk, because a file
that was never written leaves no trace to infer from.

    python -m research.forecast_vintages.continuity
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from research.forecast_vintages.capture import DEFAULT_ROOT, MANIFEST_NAME


@dataclass(frozen=True)
class Continuity:
    attempts: int
    captured: int
    failed: int
    rows: int
    first_observed_at: datetime | None
    last_observed_at: datetime | None
    gaps: list[tuple[datetime, datetime]]
    stale_for: timedelta | None

    @property
    def longest_gap(self) -> timedelta:
        return max((b - a for a, b in self.gaps), default=timedelta(0))

    def is_stalled(self, expected_interval_minutes: int = 60) -> bool:
        """Has the archive stopped collecting?

        Gaps only appear *between* successful captures, so a job that dies and
        never returns leaves no gap to find - the report would show a clean run
        of captures and a `last_observed_at` quietly receding into the past. That
        is the failure mode of a scheduled task whose interpreter or working
        directory has moved, and it is the one this check exists to catch.
        """
        if self.stale_for is None:
            return True
        return self.stale_for > timedelta(minutes=expected_interval_minutes * 2)


def read_manifest(root: Path = DEFAULT_ROOT) -> list[dict]:
    path = root / MANIFEST_NAME
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def continuity(
    records: list[dict], *, expected_interval_minutes: int = 60, now: datetime | None = None
) -> Continuity:
    """Summarise coverage. A gap is any gap between successful captures longer
    than twice the expected interval - one missed run is noise, a run of them is
    a hole in the evidence."""
    successes = sorted(
        datetime.fromisoformat(r["observed_at"]) for r in records if r["status"] == "ok"
    )
    tolerance = timedelta(minutes=expected_interval_minutes * 2)
    gaps = [
        (earlier, later)
        for earlier, later in zip(successes, successes[1:], strict=False)
        if later - earlier > tolerance
    ]
    moment = now or datetime.now(UTC)
    return Continuity(
        attempts=len(records),
        captured=len(successes),
        failed=sum(1 for r in records if r["status"] != "ok"),
        rows=sum(r["rows"] for r in records),
        first_observed_at=successes[0] if successes else None,
        last_observed_at=successes[-1] if successes else None,
        gaps=gaps,
        stale_for=(moment - successes[-1]) if successes else None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--interval-minutes", type=int, default=60)
    args = parser.parse_args(argv)

    report = continuity(read_manifest(args.root), expected_interval_minutes=args.interval_minutes)
    if not report.attempts:
        print(f"no capture attempts recorded under {args.root}")
        return 1
    print(f"attempts        : {report.attempts}")
    print(f"captured        : {report.captured}")
    print(f"failed          : {report.failed}")
    print(f"rows            : {report.rows}")
    print(f"first observed  : {report.first_observed_at}")
    print(f"last observed   : {report.last_observed_at}")
    print(f"gaps            : {len(report.gaps)} (longest {report.longest_gap})")
    for earlier, later in report.gaps:
        print(f"  missing between {earlier.isoformat()} and {later.isoformat()}")

    stalled = report.is_stalled(args.interval_minutes)
    print(f"last capture was: {report.stale_for} ago")
    print(f"state           : {'STALLED - nothing is collecting' if stalled else 'collecting'}")
    return 2 if stalled else 0


if __name__ == "__main__":
    raise SystemExit(main())
