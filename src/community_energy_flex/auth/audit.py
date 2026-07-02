"""Audit trail for access decisions.

Every authorised or denied action can be recorded, so who-saw-what is
answerable. CSV-backed for the MVP (mirrors the monitoring store); on Snowflake
this becomes an APP.AUDIT_LOG table.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path

_FILENAME = "audit_log.csv"


@dataclass(frozen=True)
class AuditEvent:
    user_id: str
    role: str
    action: str
    resource: str
    allowed: bool
    detail: str = ""
    at: str = ""


class CsvAuditLog:
    """Append-only audit log backed by a CSV file."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / _FILENAME

    def record(self, event: AuditEvent) -> None:
        data = asdict(event)
        if not data["at"]:
            data["at"] = datetime.now(UTC).isoformat(timespec="seconds")
        write_header = not self.path.exists()
        with self.path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=[f.name for f in fields(AuditEvent)])
            if write_header:
                writer.writeheader()
            writer.writerow(data)

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
