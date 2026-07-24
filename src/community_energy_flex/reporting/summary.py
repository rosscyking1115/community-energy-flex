"""A presentation-neutral summary of a schedule.

Both the Excel and PDF writers - and the Streamlit app - render from this, so
the numbers and wording stay consistent across every output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from community_energy_flex.domain.models import Schedule, slot_to_time

SAFETY_STATEMENT = (
    "This tool provides planning recommendations only. It does not directly "
    "control appliances, guarantee savings, or replace official energy, safety, "
    "or supplier advice."
)


@dataclass(frozen=True)
class TaskLine:
    task_id: str
    device_type: str
    recommended_window: str
    baseline_window: str
    cost_saving_p: float
    carbon_saving_g: float
    robustness_band: str
    caveat: str


@dataclass(frozen=True)
class ActionSummary:
    objective: str
    total_cost_saving_p: float
    total_carbon_saving_g: float
    lines: list[TaskLine] = field(default_factory=list)
    safety_statement: str = SAFETY_STATEMENT

    @property
    def total_cost_saving_pounds(self) -> float:
        return self.total_cost_saving_p / 100.0

    @property
    def total_carbon_saving_kg(self) -> float:
        return self.total_carbon_saving_g / 1000.0


def _window(start: int, end: int) -> str:
    return f"{slot_to_time(start)}-{slot_to_time(end)}"


def build_action_summary(schedule: Schedule) -> ActionSummary:
    lines = [
        TaskLine(
            task_id=t.task_id,
            device_type=t.device_type,
            recommended_window=_window(t.start_index, t.end_index),
            baseline_window=_window(
                t.baseline_start_index, t.baseline_start_index + (t.end_index - t.start_index)
            ),
            cost_saving_p=round(t.cost_saving_p, 2),
            carbon_saving_g=round(t.carbon_saving_g, 1),
            robustness_band=t.robustness_band,
            caveat=t.caveat,
        )
        for t in schedule.tasks
    ]
    return ActionSummary(
        objective=schedule.objective.value,
        total_cost_saving_p=round(schedule.total_cost_saving_p, 2),
        total_carbon_saving_g=round(schedule.total_carbon_saving_g, 1),
        lines=lines,
    )


ReportBasis = Literal["forecast", "sample_input", "fallback", "conditional_ex_post"]
ReportingStatus = Literal["reportable", "not_reportable"]
PlanningInputProvenance = Literal["live_forecast", "sample_input", "last_good_fallback"]
_MISSING_PREFERRED_REASON = (
    "No explicit preferred start was supplied; cost and carbon differences are unavailable."
)


@dataclass(frozen=True)
class ReportingContext:
    """Evidence basis and metric availability shared by every report consumer."""

    basis: ReportBasis
    status: ReportingStatus = "reportable"
    reason: str | None = None

    @property
    def is_reportable(self) -> bool:
        return self.status == "reportable"


def _report_language(context: ReportingContext) -> tuple[str, str]:
    if not context.is_reportable:
        return (
            "Not reportable: no explicit preferred start was supplied; "
            "cost and carbon differences are unavailable.",
            "Unavailable",
        )

    return {
        "forecast": (
            "Illustrative forecast planning result; not a savings guarantee.",
            "Estimated",
        ),
        "sample_input": (
            "Illustrative sample-input planning result; not a savings guarantee.",
            "Illustrative",
        ),
        "fallback": (
            "Illustrative fallback planning result; not a savings guarantee.",
            "Illustrative",
        ),
        "conditional_ex_post": (
            "Illustrative planning result — conditional ex-post; not a savings guarantee.",
            "Conditional",
        ),
    }[context.basis]


def report_basis_for_input_provenance(
    input_provenance_state: PlanningInputProvenance,
) -> ReportBasis:
    """Choose report language from the input actually used for planning."""
    if input_provenance_state == "live_forecast":
        return "forecast"
    if input_provenance_state == "last_good_fallback":
        return "fallback"
    return "sample_input"


def format_text_report(
    summary: ActionSummary,
    *,
    report_basis: ReportBasis = "forecast",
    reporting_context: ReportingContext | None = None,
) -> str:
    """Render a report with terminology appropriate to its evidence basis."""
    context = reporting_context or ReportingContext(
        basis=report_basis,
        status="not_reportable",
        reason=_MISSING_PREFERRED_REASON,
    )
    heading, metric_prefix = _report_language(context)
    out = [
        "COMMUNITY ENERGY FLEXIBILITY - ACTION REPORT",
        heading,
        f"Objective: {summary.objective}",
        "",
        "",
    ]
    if context.is_reportable:
        out += [
            f"{metric_prefix} cost difference:   £{summary.total_cost_saving_pounds:.2f}",
            f"{metric_prefix} carbon difference: {summary.total_carbon_saving_kg:.2f} kg CO2",
            "",
        ]
    elif context.reason:
        out += [context.reason, ""]
    out.append("What to do:")
    for line in summary.lines:
        if context.is_reportable:
            out.append(
                f"  - {line.device_type}: run {line.recommended_window} "
                f"(was {line.baseline_window}) "
                f"| {metric_prefix.lower()} difference {line.cost_saving_p:.1f}p, "
                f"{line.carbon_saving_g:.0f} g "
                f"| robustness: {line.robustness_band}"
            )
        else:
            out.append(
                f"  - {line.device_type}: run {line.recommended_window} "
                f"| robustness: {line.robustness_band}"
            )
        out.append(f"      {line.caveat}")
    out += ["", summary.safety_statement]
    return "\n".join(out)
