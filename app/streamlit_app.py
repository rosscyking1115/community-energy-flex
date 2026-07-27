"""Community Energy Flex - Streamlit decision app.

Run with:  streamlit run app/streamlit_app.py

Tell the app about your flexible appliances (in plain clock times), pick what to
optimise for, and it recommends when to run each one - with a baseline
comparison, savings, robustness, and a downloadable action report.

Design notes: times are entered as clock times (not half-hour slot indices);
inputs are batched in a form so the optimiser runs on submit, not on every
keystroke; the theme lives in .streamlit/config.toml (no CSS).

The plan lives in session state and is rendered on every rerun, not only the one
straight after submit - otherwise clicking a download button, which is itself a
rerun, would wipe the plan off the screen. Because a stored plan can outlive the
inputs that produced it, it is checked against the current set-up on each render
and labelled stale rather than quietly presented as current.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from community_energy_flex.auth import Permission, Role, User, can
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
from community_energy_flex.reporting.summary import (
    ReportingContext,
    build_action_summary,
    format_text_report,
    report_basis_for_input_provenance,
)

st.set_page_config(
    page_title="Community Energy Flex",
    page_icon=":material/bolt:",
    layout="wide",
)

DEVICE_OPTIONS = [
    "Dishwasher", "Washing machine", "Tumble dryer", "EV charge",
    "Water heater", "Heat pump", "Other",
]
# Named for what it is. The optimisation modules use _SLOT_HOURS for the
# reciprocal (0.5 hours per slot), so do not shorten this back to _SLOT_HOURS.
_SLOTS_PER_HOUR = SLOTS_PER_DAY / 24  # = 2

# This app plans against a forecast, or against the labelled sample curve - never
# against settlement-grade measured carbon. No code path here can supply measured
# data, so the robustness heuristic always applies its forecast data factor. This
# is a fixed property of the app, not a flag that was left unwired.
USING_MEASURED_CARBON = False


def _tasks_to_frame(tasks: list[Task]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Task": t.task_id,
                "Device": t.device_type,
                "Energy (kWh)": t.energy_kwh,
                "Duration (h)": t.duration_slots / _SLOTS_PER_HOUR,
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
            if pd.isna(row["Energy (kWh)"]) or pd.isna(row["Duration (h)"]):
                errors.append(f"Task '{name}': needs an energy (kWh) and a duration (h).")
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
                    duration_slots=max(1, round(float(row["Duration (h)"]) * _SLOTS_PER_HOUR)),
                    earliest_start=clock_to_slot(row["Earliest start"]),
                    latest_finish=finish,
                    preferred_start=None if pd.isna(preferred) else clock_to_slot(preferred),
                )
            )
        except (ValueError, TypeError) as exc:
            errors.append(f"Task '{name}': {exc}")
    # The editor happily accepts the same name twice, but the name becomes the
    # task_id and downstream code keys on it - see build_tasks in the API service
    # for the same guard at the same point.
    duplicates = sorted(name for name, count in Counter(t.task_id for t in tasks).items()
                        if count > 1)
    for duplicate in duplicates:
        errors.append(f"Task '{duplicate}': appliance names must be unique - rename one.")
    if duplicates:
        tasks = []
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


_ROLE_LABELS = {r: r.value.replace("_", " ").title() for r in Role}


# Building a workbook or a PDF is expensive and the download buttons re-render on
# every rerun, so cache the bytes against the plan they describe. The summary and
# context are underscore-prefixed to keep them out of the hash; ``plan_key``
# carries the identity. Bounded so a long session cannot grow the cache forever.
@st.cache_data(show_spinner=False, max_entries=8)
def _text_report_bytes(_summary, _context, plan_key: str) -> str:
    return format_text_report(_summary, reporting_context=_context)


@st.cache_data(show_spinner=False, max_entries=8)
def _excel_report_bytes(_summary, _context, plan_key: str) -> bytes:
    from community_energy_flex.reporting.excel_report import write_workbook_bytes

    return write_workbook_bytes(_summary, reporting_context=_context)


@st.cache_data(show_spinner=False, max_entries=8)
def _pdf_report_bytes(_summary, _context, plan_key: str) -> bytes:
    from community_energy_flex.reporting.pdf_report import write_pdf_bytes

    return write_pdf_bytes(_summary, reporting_context=_context)


def _user_from_oidc(email: str) -> User:
    """Map a verified OIDC email to a role/community from the configured
    directory (`[user_roles]` in secrets, the same source that populates
    APP.USER_ACCESS). An authenticated but unmapped user gets least privilege -
    PUBLIC (demo only) - never a fabricated household identity."""
    try:
        entry = dict(st.secrets.get("user_roles", {})).get(email)
    except Exception:  # noqa: BLE001 - no secrets file
        entry = None
    if entry:
        return User(
            user_id=email,
            role=Role(entry["role"]),
            community_id=entry.get("community_id"),
        )
    return User(user_id=email, role=Role.PUBLIC)


def _resolve_user() -> User:
    """The signed-in user. Uses OIDC (st.user) when configured, otherwise a demo
    role picker so the RBAC behaviour can be explored without a provider."""
    st.subheader("Account")
    try:
        oidc = getattr(st, "user", None)
        logged_in = bool(oidc is not None and getattr(oidc, "is_logged_in", False))
    except Exception:  # noqa: BLE001 - auth provider not configured / unavailable
        oidc, logged_in = None, False
    if logged_in:
        user = _user_from_oidc(oidc.email)
        st.caption(f"Signed in as {oidc.email} ({_ROLE_LABELS[user.role]})")
        if st.button("Log out"):
            st.logout()
        return user

    role = st.selectbox(
        "Demo role", list(Role), index=1, format_func=lambda r: _ROLE_LABELS[r],
        help="Try each role to see what it can and can't do.",
    )
    st.caption(f"Exploring as **{_ROLE_LABELS[role]}** (demo)")
    try:
        if "auth" in st.secrets and st.button("Sign in with your account"):
            st.login()
    except Exception:  # noqa: BLE001 - no secrets file / OIDC not set up
        pass
    return User(user_id=f"demo-{role}", role=role, community_id="C1")


# --- Sidebar: set-up --------------------------------------------------------
with st.sidebar:
    user = _resolve_user()
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
input_provenance_state = "sample_input"
if use_live:
    try:
        carbon = _live_carbon_curve(outcode)
        input_provenance_state = "live_forecast"
        st.sidebar.success("Live forecast loaded.")
    except Exception as exc:  # noqa: BLE001 - surface any fetch failure to the user
        st.sidebar.warning(f"Couldn't load the live forecast ({exc}). Using sample data.")
        carbon = sample_carbon_curve()
else:
    carbon = sample_carbon_curve()

# --- Header + task form -----------------------------------------------------
st.title("Community Energy Flex")
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
st.session_state.setdefault("plan_runs", 0)

# A stored plan must not outlive the role that was allowed to produce it. Switching
# the demo role picker down to one without RUN_OPTIMISER drops it immediately,
# rather than leaving the previous role's output on screen.
if not can(user.role, Permission.RUN_OPTIMISER):
    st.session_state.pop("plan", None)

with st.form("tasks_form"):
    edited = st.data_editor(
        st.session_state.task_frame,
        column_config=_TASK_COLUMN_CONFIG,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key="editor",
    )
    submitted = st.form_submit_button("Find the best times", type="primary")

def _plan_inputs_key() -> str:
    """Identify the inputs a plan was computed from.

    A download button, or any sidebar change, triggers a rerun. The plan is
    re-rendered from session state on those reruns, so it can outlive the inputs
    that produced it - and this app does not present stale output as current.
    Comparing this key against the stored one is how that is detected.
    """
    tasks_repr = edited.to_csv(index=False) if edited is not None else ""
    return "|".join(
        [
            tariff_name,
            objective.value,
            f"{weights.cost:.4f}/{weights.carbon:.4f}/{weights.comfort:.4f}",
            input_provenance_state,
            tasks_repr,
        ]
    )


@st.fragment
def _render_plan() -> None:
    """Render the stored plan.

    A fragment so that clicking a download button reruns only this block rather
    than the whole script - the report bytes and the schedule are untouched.
    """
    plan = st.session_state.get("plan")
    if plan is None:
        return
    summary = plan["summary"]
    reporting_context = plan["reporting_context"]

    st.subheader("Your plan")
    if plan["inputs_key"] != _plan_inputs_key():
        st.warning(
            "Your set-up has changed since this plan was built. Press **Find the best "
            "times** again to plan against the current inputs.",
            icon=":material/update:",
        )
    if reporting_context.is_reportable:
        c1, c2 = st.columns(2)
        if plan["input_provenance_state"] == "live_forecast":
            metric_prefix = "Estimated"
            st.caption(
                "Illustrative forecast planning differences; not a savings guarantee."
            )
        else:
            metric_prefix = "Illustrative"
            st.caption(
                "Synthetic-household, illustrative sample-input planning differences; "
                "not a savings guarantee."
            )
        c1.metric(
            f"{metric_prefix} cost difference",
            f"£{summary.total_cost_saving_pounds:.2f}",
        )
        c2.metric(
            f"{metric_prefix} carbon difference",
            f"{summary.total_carbon_saving_kg:.2f} kg CO₂",
        )
    else:
        st.caption(
            "Not reportable: add an explicit preferred start to compare cost and carbon."
        )

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Appliance": ln.device_type,
                    "Run at": ln.recommended_window,
                    "Robustness": ln.robustness_band,
                    **(
                        {
                            "Instead of": ln.baseline_window,
                            "Cost difference (p)": ln.cost_saving_p,
                            "Carbon difference (g CO₂)": ln.carbon_saving_g,
                        }
                        if reporting_context.is_reportable
                        else {}
                    ),
                }
                for ln in summary.lines
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    with st.expander("How sensitive is this recommendation? (robustness & caveats)"):
        for ln in summary.lines:
            st.markdown(f"**{ln.device_type}** ({ln.robustness_band}): {ln.caveat}")
        st.caption(summary.safety_statement)

    st.subheader("Take it with you")
    plan_key = plan["plan_key"]
    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "Text (.txt)",
        _text_report_bytes(summary, reporting_context, plan_key),
        file_name="energy_action_report.txt",
    )
    try:
        d2.download_button(
            "Excel (.xlsx)",
            _excel_report_bytes(summary, reporting_context, plan_key),
            file_name="community_energy_action_report.xlsx",
        )
    except ImportError:
        d2.caption("Excel needs `pip install '.[reports]'`")
    try:
        d3.download_button(
            "PDF (.pdf)",
            _pdf_report_bytes(summary, reporting_context, plan_key),
            file_name="community_energy_action_report.pdf",
        )
    except ImportError:
        d3.caption("PDF needs `pip install '.[reports]'`")


if submitted and not can(user.role, Permission.RUN_OPTIMISER):
    st.session_state.pop("plan", None)
    st.info(
        f"The **{_ROLE_LABELS[user.role]}** role can view reports but can't run the "
        "optimiser. Switch to the Household role (demo) to try it.",
        icon=":material/lock:",
    )
elif submitted:
    tasks, errors = _frame_to_tasks(edited)
    for err in errors:
        st.error(err, icon=":material/error:")
    if errors:
        st.session_state.pop("plan", None)
    elif not tasks:
        st.session_state.pop("plan", None)
        st.warning("Add at least one appliance above.")
    else:
        slots = build_planning_slots(carbon, tariff)
        try:
            schedule = optimise(
                tasks, slots, objective, weights,
                using_actual_carbon=USING_MEASURED_CARBON,
                tariff_is_manual=getattr(tariff, "is_manual", True),
            )
        except Exception as exc:  # noqa: BLE001
            st.session_state.pop("plan", None)
            st.error(f"Couldn't build a schedule: {exc}", icon=":material/error:")
            st.stop()

        inputs_key = _plan_inputs_key()
        st.session_state.plan = {
            "summary": build_action_summary(schedule),
            "reporting_context": ReportingContext(
                basis=report_basis_for_input_provenance(input_provenance_state),
                status=(
                    "reportable"
                    if all(task.preferred_start is not None for task in tasks)
                    else "not_reportable"
                ),
                reason=(
                    "No explicit preferred start was supplied; cost and carbon differences "
                    "are unavailable."
                ),
            ),
            "input_provenance_state": input_provenance_state,
            "inputs_key": inputs_key,
            # Cache identity for the report bytes. The run counter keeps two plans
            # built from identical inputs from sharing a cache entry.
            "plan_key": f"{st.session_state.plan_runs}:{inputs_key}",
        }
        st.session_state.plan_runs += 1

# Rendered on every rerun, not only the one straight after submit, so a download
# click or a sidebar change no longer wipes the plan off the screen.
_render_plan()
