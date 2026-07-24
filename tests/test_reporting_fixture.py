from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "data" / "fixtures" / "reporting_contract_v1.json"


def _generated_powerbi_data_dir() -> Path:
    """Return the derived CSV export when this test lane generated it.

    The core Python matrix intentionally installs no warehouse dependencies and
    does not create ignored ``powerbi/data`` artifacts. The dedicated
    ``dbt-fixture`` CI job owns their generation and runs these assertions.
    """
    data_dir = ROOT / "powerbi" / "data"
    if not (data_dir / "fct_daily_savings.csv").exists():
        pytest.skip("Power BI CSV export is verified in the dbt-fixture CI job")
    return data_dir


def test_fixed_reporting_fixture_declares_reconcilable_sample_input():
    assert FIXTURE_PATH.exists()

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert fixture["fixture_id"] == "reporting-contract-v1"
    assert fixture["input_provenance_state"] == "sample_input"
    assert fixture["reporting_status"] == "reportable"
    assert fixture["baseline_cost_p"] - fixture["scheduled_cost_p"] == 20.0
    assert fixture["baseline_carbon_g"] - fixture["scheduled_carbon_g"] == 400.0
    assert fixture["baseline_peak_slot_count"] - fixture["scheduled_peak_slot_count"] == 2


def test_powerbi_seed_keeps_raw_values_and_reporting_lineage():
    seed_path = ROOT / "dbt_energy" / "seeds" / "seed_daily_savings.csv"
    with seed_path.open(newline="", encoding="utf-8") as handle:
        columns = set(csv.DictReader(handle).fieldnames or [])

    assert {
        "schedule_run_id",
        "input_provenance_state",
        "source_observed_at",
        "baseline_carbon_g",
        "scheduled_carbon_g",
        "baseline_peak_slot_count",
        "scheduled_peak_slot_count",
        "reporting_status",
    } <= columns

    with seed_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    fixture_row = next(row for row in rows if row["schedule_run_id"] == "fixture-run-001")
    assert float(fixture_row["baseline_cost_p"]) - float(fixture_row["scheduled_cost_p"]) == 20.0
    assert (
        float(fixture_row["baseline_carbon_g"]) - float(fixture_row["scheduled_carbon_g"])
    ) == 400.0
    assert (
        int(fixture_row["baseline_peak_slot_count"])
        - int(fixture_row["scheduled_peak_slot_count"])
    ) == 2


def test_powerbi_measures_use_reported_differences_without_null_to_zero():
    measures = (ROOT / "powerbi" / "measures.dax").read_text(encoding="utf-8")
    assert "reported_cost_saving_p" in measures
    assert "reported_carbon_saving_g" in measures
    assert "reported_peak_slots_avoided" in measures
    assert "reporting_status] = \"reportable\"" in measures
    assert "COALESCE" not in measures


def test_powerbi_tasks_planned_sums_source_task_count_at_reporting_grain():
    measures = (ROOT / "powerbi" / "measures.dax").read_text(encoding="utf-8")

    tasks_planned = measures.split("Tasks Planned =", maxsplit=1)[1].split(
        "// Format: #,##0\nHouseholds Participating", maxsplit=1
    )[0]
    assert "SUM ( fct_daily_savings[source_task_count] )" in tasks_planned
    assert "COUNTROWS ( fct_daily_savings )" not in tasks_planned


def test_powerbi_fact_export_matches_the_fixed_fixture():
    fact_path = _generated_powerbi_data_dir() / "fct_daily_savings.csv"
    with fact_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    fixture_row = next(row for row in rows if row["schedule_run_id"] == "fixture-run-001")
    assert float(fixture_row["reported_cost_saving_p"]) == 20.0
    assert float(fixture_row["reported_carbon_saving_g"]) == 400.0
    assert int(fixture_row["reported_peak_slots_avoided"]) == 2


def test_powerbi_star_tables_cover_fact_foreign_keys_and_fixture_device_label():
    """The CSV star schema must be refreshed as one coherent export."""
    data_dir = _generated_powerbi_data_dir()

    with (data_dir / "fct_daily_savings.csv").open(newline="", encoding="utf-8") as handle:
        fact_rows = list(csv.DictReader(handle))

    dimension_files = {
        "date_key": "dim_date.csv",
        "device_key": "dim_device.csv",
        "community_key": "dim_community.csv",
    }
    dimensions: dict[str, dict[str, dict[str, str]]] = {}
    for key, filename in dimension_files.items():
        with (data_dir / filename).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        dimensions[key] = {row[key]: row for row in rows}
        assert {row[key] for row in fact_rows} <= set(dimensions[key])

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    fixture_row = next(
        row
        for row in fact_rows
        if row["schedule_run_id"] == fixture["schedule_run_id"]
    )
    assert (
        dimensions["device_key"][fixture_row["device_key"]]["device_type"]
        == fixture["device_type"]
    )
