"""Community Energy Flexibility OS - Streamlit decision app (MVP).

Run with:  streamlit run app/streamlit_app.py

This is the Milestone A vertical slice: pick a tariff, edit your flexible tasks,
choose an objective, and get a recommended schedule with baseline comparison,
savings, confidence, and downloadable reports. Visual/accessibility polish (via
the developing-with-streamlit + web-design-guidelines skills) is a later
milestone.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from community_energy_flex.data_sources.carbon_intensity import (
    CarbonIntensityClient,
)
from community_energy_flex.data_sources.carbon_intensity import (
    carbon_curve as curve_from_slots,
)
from community_energy_flex.demo import sample_carbon_curve, sample_tariffs, sample_tasks
from community_energy_flex.domain.models import (
    SLOTS_PER_DAY,
    Objective,
    ObjectiveWeights,
    Task,
    slot_to_time,
)
from community_energy_flex.optimisation.planning import build_planning_slots
from community_energy_flex.optimisation.rule_based import optimise
from community_energy_flex.reporting.summary import build_action_summary, format_text_report

st.set_page_config(page_title="Community Energy Flexibility OS", page_icon="⚡", layout="wide")

TASK_COLUMNS = [
    "task_id", "device_type", "energy_kwh", "duration_slots",
    "earliest_start", "latest_finish", "preferred_start",
]


def _tasks_to_frame(tasks: list[Task]) -> pd.DataFrame:
    return pd.DataFrame(
        [{c: getattr(t, c) for c in TASK_COLUMNS} for t in tasks]
    )


def _frame_to_tasks(frame: pd.DataFrame) -> tuple[list[Task], list[str]]:
    tasks, errors = [], []
    for _, row in frame.iterrows():
        try:
            preferred = row["preferred_start"]
            tasks.append(
                Task(
                    task_id=str(row["task_id"]),
                    device_type=str(row["device_type"]),
                    energy_kwh=float(row["energy_kwh"]),
                    duration_slots=int(row["duration_slots"]),
                    earliest_start=int(row["earliest_start"]),
                    latest_finish=int(row["latest_finish"]),
                    preferred_start=None if pd.isna(preferred) else int(preferred),
                )
            )
        except (ValueError, TypeError) as exc:
            errors.append(f"Task '{row.get('task_id', '?')}': {exc}")
    return tasks, errors


@st.cache_data(show_spinner=False)
def _live_carbon_curve(outcode: str) -> list[float]:
    slots = CarbonIntensityClient().regional_forecast_by_postcode(outcode)
    return curve_from_slots(slots, num_slots=SLOTS_PER_DAY)


st.title("⚡ Community Energy Flexibility OS")
st.caption(
    "Recommends when to run flexible electricity loads to cut cost and carbon - "
    "respecting your comfort constraints. Planning advice only; no guaranteed savings."
)

# --- Sidebar: data + tariff -------------------------------------------------
with st.sidebar:
    st.header("Set-up")
    tariffs = sample_tariffs()
    tariff_name = st.selectbox("Tariff", list(tariffs))
    tariff = tariffs[tariff_name]

    st.subheader("Carbon data")
    use_live = st.toggle("Use live regional forecast", value=False)
    outcode = st.text_input("Postcode outcode", value="BS1", disabled=not use_live)

    st.subheader("Objective")
    objective = st.selectbox(
        "Optimise for", list(Objective), format_func=lambda o: o.value.replace("_", " ").title()
    )
    weights = ObjectiveWeights()
    if objective is Objective.BALANCED:
        cost_w = st.slider("Cost priority", 0.0, 1.0, 0.5, 0.05)
        weights = ObjectiveWeights(cost=cost_w, carbon=1.0 - cost_w, comfort=0.0)

# --- Carbon curve -----------------------------------------------------------
using_actual = False
if use_live:
    try:
        carbon = _live_carbon_curve(outcode)
        st.sidebar.success("Live forecast loaded.")
    except Exception as exc:  # noqa: BLE001 - show any fetch failure to the user
        st.sidebar.error(f"Live fetch failed ({exc}). Using sample data.")
        carbon = sample_carbon_curve()
else:
    carbon = sample_carbon_curve()

# --- Task editor ------------------------------------------------------------
st.subheader("Your flexible tasks")
st.caption(
    "Times are half-hour slot indices (0 = 00:00, 2 = 01:00 ... 48 = 24:00). "
    "`latest_finish` is exclusive; leave `preferred_start` blank to use `earliest_start`."
)
if "task_frame" not in st.session_state:
    st.session_state.task_frame = _tasks_to_frame(sample_tasks())
edited = st.data_editor(
    st.session_state.task_frame, num_rows="dynamic", use_container_width=True, key="editor"
)

run = st.button("Run optimiser", type="primary")

if run:
    tasks, errors = _frame_to_tasks(edited)
    if errors:
        for err in errors:
            st.error(err)
    elif not tasks:
        st.warning("Add at least one task.")
    else:
        slots = build_planning_slots(carbon, tariff)
        try:
            schedule = optimise(
                tasks, slots, objective, weights,
                using_actual_carbon=using_actual,
                tariff_is_manual=getattr(tariff, "is_manual", True),
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not build a schedule: {exc}")
            st.stop()

        summary = build_action_summary(schedule)

        c1, c2, c3 = st.columns(3)
        c1.metric("Cost saving", f"£{summary.total_cost_saving_pounds:.2f}")
        c2.metric("Carbon saving", f"{summary.total_carbon_saving_kg:.2f} kg CO₂")
        c3.metric("Objective", objective.value.replace("_", " ").title())

        chart_df = pd.DataFrame(
            {
                "Slot": [slot_to_time(i) for i in range(len(slots))],
                "Carbon (gCO₂/kWh)": [s.carbon_gco2_per_kwh for s in slots],
                "Price (p/kWh)": [s.price_p_per_kwh for s in slots],
            }
        ).set_index("Slot")
        st.line_chart(chart_df)

        st.subheader("Recommended schedule")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Device": ln.device_type,
                        "Recommended": ln.recommended_window,
                        "Baseline": ln.baseline_window,
                        "Saving (p)": ln.cost_saving_p,
                        "Saving (gCO₂)": ln.carbon_saving_g,
                        "Confidence": ln.confidence_band,
                    }
                    for ln in summary.lines
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Confidence & caveats"):
            for ln in summary.lines:
                st.markdown(f"**{ln.device_type}** ({ln.confidence_band}): {ln.caveat}")
            st.info(summary.safety_statement)

        st.subheader("Download report")
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
            d2.caption("Excel: `pip install '.[reports]'`")
        try:
            from community_energy_flex.reporting.pdf_report import write_pdf_bytes

            d3.download_button(
                "PDF (.pdf)", write_pdf_bytes(summary),
                file_name="community_energy_action_report.pdf",
            )
        except ImportError:
            d3.caption("PDF: `pip install '.[reports]'`")
