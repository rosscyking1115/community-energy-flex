"""Export the Power BI CSV inputs from one local DuckDB reporting build.

This is deliberately a local, fixture-compatible export. It reads no live
service and keeps the three dimensions and reporting fact in the same build so
Power BI relationships cannot be refreshed from mismatched CSV generations.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "energy.duckdb"
OUTPUT_DIR = ROOT / "powerbi" / "data"
TABLES = (
    "dim_date",
    "dim_device",
    "dim_community",
    "fct_daily_savings",
    "rpt_daily_savings",
    "rpt_monthly_community_savings",
)


def main() -> int:
    if not DATABASE.exists():
        raise FileNotFoundError(
            f"DuckDB reporting build not found: {DATABASE}. Run dbt build first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(DATABASE), read_only=True)
    try:
        available = {
            row[0]
            for row in connection.execute(
                "select table_name from information_schema.tables "
                "where table_schema = 'main'"
            ).fetchall()
        }
        missing = sorted(set(TABLES) - available)
        if missing:
            raise RuntimeError(
                "DuckDB reporting build is missing Power BI export tables: "
                + ", ".join(missing)
            )

        for table in TABLES:
            target = (OUTPUT_DIR / f"{table}.csv").as_posix().replace("'", "''")
            connection.execute(
                f"COPY (SELECT * FROM {table} ORDER BY ALL) TO '{target}' (HEADER)"
            )
            print(f"Exported {table} -> powerbi/data/{table}.csv")
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
