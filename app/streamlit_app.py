"""Community Energy Flexibility OS - Streamlit decision app.

Run with:  streamlit run app/streamlit_app.py

Tell the app about your flexible appliances (in plain clock times), pick what to
optimise for, and it recommends when to run each one - with a baseline
comparison, savings, confidence, and a downloadable action report.

Design notes: times are entered as clock times (not half-hour slot indices);
inputs are batched in a form so the optimiser runs on submit, not on every
keystroke; the theme lives in .streamlit/config.toml (no CSS).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from community_energy_flex.data_sources.carbon_intensity import CarbonIntensityClient
from community_energy_flex.data_sources.carbon_intensity import carbon_curve as curve_from_slots
from community_energy_flex.demo import sample_carbon_curve, sample_tariffs, sample_tasks
from community_energy_flex.domain.models import (
    SLOTS_PER_DAY,
    Objective,
    ObjectiveWeights,
    Task,
    clock_to_slot,
    slot_to_clock,
)
from community_energy_flex.optimisation.planning import build_planning_slots
from community_energy_flex.optimisation.rule_based import optimise
from community_energy_flex.reporting.summary import build_action_summary, format_text_report

st.set_page_config(
    page_title="Community Energy Flexibility OS",
    page_icon=":material/bolt:",
    layout="wide",
)

DEVICE_OPTIONS = [
    "Dishwasher", "Washing machine", "Tumble dryer", "EV charge",
    "Water heater", "Heat pump", "Other",
]
_SLOT_HOURS = SLOTS_PER_DAY / 24  # slots per hour = 2


def _tasks_to_frame(tasks: list[Task]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Task": t.task_id,
                "Device": t.device_type,
                "Energy (kWh)": t.energy_kwh,
                "Duration (h)": t.duration_slots / _SLOT_HOURS,
                "Earliest start": slot_to_clock(t.earliest_start),
                "Finish by": slot_to_clock(t.latest_finish),
                "Preferred start": (
                    slot_to_clock(t.preferred_start) if t.preferred_start is not None else None
                ),
            }
            for t in tasks
        ]
    )


def _frame_to_tasks(frame: pd.DataFrame) -> tuple[list[Task], list[str]]:
    tasks, errors = [], []
    for _, row in frame.iterrows():
        name = row.get("Task") or "?"
        try:
            if pd.isna(row["Earliest start"]) or pd.isna(row["Finish by"]):
                errors.append(f"Task '{name}': needs an earliest start and a finish-by time.")
                continue
            finish = clock_to_slot(row["Finish by"])
            if finish == 0:  # 00:00 "finish by" means the end of the day
                finish = SLOTS_PER_DAY
            preferred = row["Preferred start"]
            tasks.append(
                Task(
                    task_id=str(row["Task"]),
                    device_type=str(row["Device"]),
                    energy_kwh=float(row["Energy (kWh)"]),
                    duration_slots=max(1, round(float(row["Duration (h)"]) * _SLOT_HOURS)),
                    earliest_start=clock_to_slot(row["Earliest start"]),
                    latest_finish=finish,
                    preferred_start=None if pd.isna(preferred) else clock_to_slot(preferred),
                )
            )
        except (ValueError, TypeError) as exc:
            errors.append(f"Task '{name}': {exc}")
    return tasks, errors


# Half-hourly carbon data changes through the day; cap the cache so a stale
# forecast is never served indefinitely.
@st.cache_data(show_spinner=False, ttl=1800)
def _live_carbon_curve(outcode: str) -> list[float]:
    slots = CarbonIntensityClient().regional_forecast_by_postcode(outcode)
    return curve_from_slots(slots, num_slots=SLOTS_PER_DAY)


_TASK_COLUMN_CONFIG = {
    "Task": st.column_config.TextColumn("Name", required=True, help="A label for this appliance."),
    "Device": st.column_config.SelectboxColumn(
        "Device", options=DEVICE_OPTIONS, required=True, help="Type of appliance."
    ),
    "Energy (kWh)": st.column_config.NumberColumn(
        "Energy (kWh)", min_value=0.1, step=0.1, format="%.1f",
        help="Roughly how much electricity one run uses.",
    ),
    "Duration (h)": st.column_config.NumberColumn(
        "Duration (h)", min_value=0.5, step=0.5, format="%.1f",
        help="How long one run takes, in hours.",
    ),
    "Earliest start": st.column_config.TimeColumn(
        "Earliest start", format="HH:mm", help="Not before this time.",
    ),
    "Finish by": st.column_config.TimeColumn(
        "Finish by", format="HH:mm", help="Must be finished by this time (00:00 = end of day).",
    ),
    "Preferred start": st.column_config.TimeColumn(
        "Preferred start", format="HH:mm",
        help="When you'd normally run it (used as the 'do nothing' baseline). Optional.",
    ),
}


# --- Sidebar: set-up --------------------------------------------------------
with st.sidebar:
    st.header("Set-up")
    tariffs = sample_tariffs()
    tariff_name = st.selectbox(
        "Your tariff", list(tariffs), help="How you're charged for electricity."
    )
    tariff = tariffs[tariff_name]

    st.subheader("Carbon data")
    use_live = st.toggle("Use live regional forecast", value=False)
    outcode = st.text_input(
        "Postcode area", value="BS1", disabled=not use_live,
        help="The first part of your postcode, e.g. BS1.",
    )

    st.subheader("What matters most?")
    objective = st.selectbox(
        "Optimise for", list(Objective),
        format_func=lambda o: o.value.replace("_", " ").title(),
    )
    weights = ObjectiveWeights()
    if objective is Objective.BALANCED:
        cost_w = st.slider("Cost vs carbon", 0.0, 1.0, 0.5, 0.05,
                           help="Left = prioritise cost, right = prioritise carbon.")
        weights = ObjectiveWeights(cost=cost_w, carbon=1.0 - cost_w, comfort=0.0)

# --- Carbon curve -----------------------------------------------------------
using_actual = False
if use_live:
    try:
        carbon = _live_carbon_curve(outcode)
        st.sidebar.success("Live forecast loaded.")
    except Exception as exc:  # noqa: BLE001 - surface any fetch failure to the user
        st.sidebar.warning(f"Couldn't load the live forecast ({exc}). Using sample data.")
        carbon = sample_carbon_curve()
else:
    carbon = sample_carbon_curve()

# --- Header + task form -----------------------------------------------------
st.title("Community Energy Flexibility OS")
st.caption(
    "Find the best times to run your flexible appliances to cut cost and carbon. "
    "This is planning advice - it never controls your appliances or guarantees savings."
)

st.subheader("Your flexible appliances")
st.write(
    "Add the appliances you can run at different times. Give the earliest they can "
    "start and when they must finish by; add a preferred time if you have one."
)

if "task_frame" not in st.session_state:
    st.session_state.task_frame = _tasks_to_frame(sample_tasks())

with st.form("tasks_form"):
    edited = st.data_editor(
        st.session_state.task_frame,
        column_config=_TASK_COLUMN_CONFIG,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor",
    )
    submitted = st.form_submit_button("Find the best times", type="primary")

if submitted:
    tasks, errors = _frame_to_tasks(edited)
    for err in errors:
        st.error(err, icon=":material/error:")
    if not tasks and not errors:
        st.warning("Add at least one appliance above.")
    elif tasks:
        slots = build_planning_slots(carbon, tariff)
        try:
            schedule = optimise(
                tasks, slots, objective, weights,
                using_actual_carbon=using_actual,
                tariff_is_manual=getattr(tariff, "is_manual", True),
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Couldn't build a schedule: {exc}", icon=":material/error:")
            st.stop()

        summary = build_action_summary(schedule)

        st.subheader("Your plan")
        c1, c2 = st.columns(2)
        c1.metric("Estimated cost saving", f"£{summary.total_cost_saving_pounds:.2f}")
        c2.metric("Estimated carbon saving", f"{summary.total_carbon_saving_kg:.2f} kg CO₂")

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Appliance": ln.device_type,
                        "Run at": ln.recommended_window,
                        "Instead of": ln.baseline_window,
                        "Saves (p)": ln.cost_saving_p,
                        "Saves (g CO₂)": ln.carbon_saving_g,
                        "Confidence": ln.confidence_band,
                    }
                    for ln in summary.lines
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("How sure is this? (confidence & caveats)"):
            for ln in summary.lines:
                st.markdown(f"**{ln.device_type}** ({ln.confidence_band}): {ln.caveat}")
            st.caption(summary.safety_statement)

        st.subheader("Take it with you")
        d1, d2, d3 = st.columns(3)
        d1.download_button(
            "Text (.txt)", format_text_report(summary),
            file_name="energy_action_report.txt",
        )
        try:
            from community_energy_flex.reporting.excel_report import write_workbook_bytes

            d2.download_button(
                "Excel (.xlsx)", write_workbook_bytes(summary),
                file_name="community_energy_action_report.xlsx",
            )
        except ImportError:
            d2.caption("Excel needs `pip install '.[reports]'`")
        try:
            from community_energy_flex.reporting.pdf_report import write_pdf_bytes

            d3.download_button(
                "PDF (.pdf)", write_pdf_bytes(summary),
                file_name="community_energy_action_report.pdf",
            )
        except ImportError:
            d3.caption("PDF needs `pip install '.[reports]'`")
