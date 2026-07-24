"""Generate dbt seed data for the Power BI reporting star.

Runs the real rule-based optimiser over a two-week window for a handful of
demo households and writes per-task daily savings to
``dbt_energy/seeds/seed_daily_savings.csv``. Deterministic (seeded per
household/day) so the seed is reproducible.

Usage:
    PYTHONPATH=src python scripts/generate_powerbi_seed.py
Then rebuild and re-export:
    cd dbt_energy && dbt build
    (see docs/POWERBI_DASHBOARD_GUIDE.md step 0 for the CSV export)
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

from community_energy_flex.data_sources.tariffs import multiband_from_half_hour_prices
from community_energy_flex.demo import sample_carbon_curve, sample_tasks
from community_energy_flex.domain.models import SLOTS_PER_DAY, Objective, Task
from community_energy_flex.optimisation.planning import DEFAULT_PEAK_SLOTS, build_planning_slots
from community_energy_flex.optimisation.rule_based import optimise

SEEDS = Path(__file__).resolve().parents[1] / "dbt_energy" / "seeds"
OUT = SEEDS / "seed_daily_savings.csv"
DATES_OUT = SEEDS / "seed_dates.csv"
FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "fixtures" / "reporting_contract_v1.json"
)

COMMUNITIES = [("C1", "Riverside Centre"), ("C2", "Hilltop Community")]
HOUSEHOLDS_PER_COMMUNITY = 2
DAYS = 14
START = date(2026, 6, 24)

# DAX time intelligence (DATEADD etc.) requires a contiguous date table spanning
# full calendar years, so the date spine covers whole years around the fact data
# - not just the dates that happen to appear in the fact.
SPINE_START = date(2026, 1, 1)
SPINE_END = date(2026, 12, 31)


def write_date_spine() -> int:
    with DATES_OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["full_date"])
        day = SPINE_START
        while day <= SPINE_END:
            writer.writerow([day.isoformat()])
            day += timedelta(days=1)
    return (SPINE_END - SPINE_START).days + 1


def demo_tasks() -> list[Task]:
    """The household's flexible loads. The tumble dryer's *baseline* sits inside
    the 17:00-19:00 peak (preferred 17:30), so shifting it produces a real
    peak_slots_avoided signal - the other tasks live outside the peak."""
    return [
        *sample_tasks(),
        Task(
            task_id="tumble_dryer",
            device_type="Tumble dryer",
            energy_kwh=2.0,
            duration_slots=3,  # 1.5 hours
            earliest_start=28,  # 14:00
            latest_finish=46,  # by 23:00
            preferred_start=35,  # 17:30 - inside the evening peak
        ),
    ]


def peak_overlap(start: int, duration: int) -> int:
    return sum(1 for i in range(start, start + duration) if i in DEFAULT_PEAK_SLOTS)


def contract_fixture_row() -> list[object]:
    """Return the canonical sample-input row used by all reporting consumers."""
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [
        fixture["planning_date"],
        fixture["community_id"],
        fixture["household_id"],
        "fixture-dishwasher",
        fixture["device_type"],
        fixture["schedule_run_id"],
        fixture["reporting_status"],
        fixture["input_provenance_state"],
        fixture.get("fallback_reason", ""),
        fixture["carbon_source"],
        fixture["carbon_source_label"],
        fixture["price_source"],
        fixture["price_source_label"],
        fixture["source_observed_at"],
        fixture["source_valid_from"],
        fixture["source_valid_to"],
        fixture["source_promises_full_day"],
        fixture["schedule_adherence_observed"],
        fixture.get("preferred_start_index", fixture["baseline_start_index"]),
        fixture["baseline_start_index"],
        fixture["scheduled_start_index"],
        fixture["duration_slots"],
        fixture["baseline_cost_p"],
        fixture["scheduled_cost_p"],
        fixture["baseline_carbon_g"],
        fixture["scheduled_carbon_g"],
        fixture["baseline_peak_slot_count"],
        fixture["scheduled_peak_slot_count"],
        0.85,
        "High",
    ]


def main() -> int:
    base_curve = sample_carbon_curve()
    tasks = demo_tasks()
    tasks_by_id = {task.task_id: task for task in tasks}
    rows: list[list] = []

    for d in range(DAYS):
        day = START + timedelta(days=d)
        for cid, _cname in COMMUNITIES:
            for h in range(1, HOUSEHOLDS_PER_COMMUNITY + 1):
                hh = f"{cid}-H{h}"
                rng = random.Random(f"{day}{hh}")
                # deterministic per-household/day variation of the carbon day
                shift = rng.randint(-3, 3)
                scale = rng.uniform(0.9, 1.15)
                curve = [
                    max(20.0, base_curve[(i + shift) % SLOTS_PER_DAY] * scale)
                    for i in range(SLOTS_PER_DAY)
                ]
                prices = [max(5.0, c / 12.0) for c in curve]
                tariff = multiband_from_half_hour_prices(
                    prices, standing_charge_p=45.0, is_manual=False
                )
                slots = build_planning_slots(curve, tariff)
                schedule = optimise(tasks, slots, Objective.BALANCED, tariff_is_manual=False)

                for st in schedule.tasks:
                    duration = st.end_index - st.start_index
                    rows.append(
                        [
                            day.isoformat(), cid, hh, st.task_id, st.device_type,
                            f"seed-{day:%Y%m%d}-{hh}", "reportable", "sample_input", "",
                            "gb_sample_profile", "Generated synthetic carbon profile",
                            "user_entered_tariff", "Generated synthetic tariff",
                            f"{day.isoformat()}T00:00:00+00:00",
                            f"{day.isoformat()}T00:00:00+00:00",
                            f"{(day + timedelta(days=1)).isoformat()}T00:00:00+00:00",
                            True, False, tasks_by_id[st.task_id].preferred_start,
                            st.baseline_start_index, st.start_index, duration,
                            round(st.baseline_cost_p, 2), round(st.cost_p, 2),
                            round(st.baseline_carbon_g, 1), round(st.carbon_g, 1),
                            peak_overlap(st.baseline_start_index, duration),
                            peak_overlap(st.start_index, duration),
                            st.robustness_score, st.robustness_band,
                        ]
                    )

    rows.append(contract_fixture_row())
    rows.append(
        [
            "2026-07-04", "C1", "C1-HN", "fixture-missing-source", "Unavailable fixture load",
            "fixture-run-missing", "not_reportable", "sample_input", "", "", "", "", "",
            "", "", "", False, False, "", "", "", "", "", "", "", "", "", "", 0.0,
            "Fragile",
        ]
    )
    rows.extend(
        [
            [
                "2026-07-04",
                "C1",
                "C1-HP",
                "fixture-missing-preferred",
                "Missing preferred fixture load",
                "fixture-run-missing-preferred",
                "reportable",
                "sample_input",
                "",
                "gb_sample_profile",
                "Reporting-contract sample carbon profile",
                "user_entered_tariff",
                "Reporting-contract sample tariff",
                "2026-07-03T12:00:00+00:00",
                "2026-07-04T00:00:00+00:00",
                "2026-07-05T00:00:00+00:00",
                True,
                False,
                "",
                34,
                0,
                2,
                40.0,
                20.0,
                600.0,
                200.0,
                2,
                0,
                0.85,
                "High",
            ],
            [
                "2026-07-04",
                "C1",
                "C1-HC",
                "fixture-clamped-preferred",
                "Clamped preferred fixture load",
                "fixture-run-clamped-preferred",
                "reportable",
                "sample_input",
                "",
                "gb_sample_profile",
                "Reporting-contract sample carbon profile",
                "user_entered_tariff",
                "Reporting-contract sample tariff",
                "2026-07-03T12:00:00+00:00",
                "2026-07-04T00:00:00+00:00",
                "2026-07-05T00:00:00+00:00",
                True,
                False,
                34,
                33,
                0,
                2,
                40.0,
                20.0,
                600.0,
                200.0,
                2,
                0,
                0.85,
                "High",
            ],
            [
                "2026-07-04", "C1", "C1-HM", "fixture-mixed-preferred-1",
                "Mixed preferred fixture load", "fixture-run-mixed-preferred",
                "reportable", "sample_input", "", "gb_sample_profile",
                "Reporting-contract sample carbon profile", "user_entered_tariff",
                "Reporting-contract sample tariff", "2026-07-03T12:00:00+00:00",
                "2026-07-04T00:00:00+00:00", "2026-07-05T00:00:00+00:00", True,
                False, 34, 34, 0, 2, 40.0, 20.0, 600.0, 200.0, 2, 0, 0.85, "High",
            ],
            [
                "2026-07-04", "C1", "C1-HM", "fixture-mixed-preferred-2",
                "Mixed preferred fixture load", "fixture-run-mixed-preferred",
                "reportable", "sample_input", "", "gb_sample_profile",
                "Reporting-contract sample carbon profile", "user_entered_tariff",
                "Reporting-contract sample tariff", "2026-07-03T12:00:00+00:00",
                "2026-07-04T00:00:00+00:00", "2026-07-05T00:00:00+00:00", True,
                False, 34, 33, 0, 2, 40.0, 20.0, 600.0, 200.0, 2, 0, 0.85, "High",
            ],
        ]
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "savings_date",
                "community_id",
                "household_id",
                "task_id",
                "device_type",
                "schedule_run_id",
                "reporting_status",
                "input_provenance_state",
                "carbon_source",
                "fallback_reason",
                "carbon_source_label",
                "price_source",
                "price_source_label",
                "source_observed_at",
                "source_valid_from",
                "source_valid_to",
                "source_promises_full_day",
                "schedule_adherence_observed",
                "preferred_start_index",
                "baseline_start_index",
                "scheduled_start_index",
                "duration_slots",
                "baseline_cost_p",
                "scheduled_cost_p",
                "baseline_carbon_g",
                "scheduled_carbon_g",
                "baseline_peak_slot_count",
                "scheduled_peak_slot_count",
                "robustness_score",
                "robustness_band",
            ]
        )
        writer.writerows(rows)

    days = len({r[0] for r in rows})
    households = len({r[2] for r in rows})
    total_avoided = sum(
        (r[26] or 0) - (r[27] or 0)
        for r in rows
        if r[6] == "reportable"
    )
    print(
        f"{OUT.name}: {len(rows)} rows over {days} days, {households} households, "
        f"{total_avoided} peak slots avoided in total"
    )
    spine_days = write_date_spine()
    print(f"{DATES_OUT.name}: {spine_days} contiguous dates ({SPINE_START} .. {SPINE_END})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
