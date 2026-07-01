"""A presentation-neutral summary of a schedule.

Both the Excel and PDF writers - and the Streamlit app - render from this, so
the numbers and wording stay consistent across every output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from community_energy_flex.domain.models import slot_to_time
from community_energy_flex.optimisation.rule_based import Schedule

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
    confidence_band: str
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
            confidence_band=t.confidence_band,
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


def format_text_report(summary: ActionSummary) -> str:
    """A plain-text report - handy for the CLI, logs, and MLflow artifacts."""
    out = [
        "COMMUNITY ENERGY FLEXIBILITY - ACTION REPORT",
        f"Objective: {summary.objective}",
        "",
        f"Estimated cost saving:   £{summary.total_cost_saving_pounds:.2f}",
        f"Estimated carbon saving: {summary.total_carbon_saving_kg:.2f} kg CO2",
        "",
        "What to do:",
    ]
    for line in summary.lines:
        out.append(
            f"  - {line.device_type}: run {line.recommended_window} "
            f"(was {line.baseline_window}) "
            f"| saves {line.cost_saving_p:.1f}p, {line.carbon_saving_g:.0f} g "
            f"| confidence: {line.confidence_band}"
        )
        out.append(f"      {line.caveat}")
    out += ["", summary.safety_statement]
    return "\n".join(out)
