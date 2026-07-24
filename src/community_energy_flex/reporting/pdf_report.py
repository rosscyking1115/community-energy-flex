"""Write a one-page PDF action report. Requires the ``reports`` extra
(reportlab)."""

from __future__ import annotations

from io import BytesIO

from community_energy_flex.reporting.summary import (
    ActionSummary,
    ReportingContext,
    _report_language,
)


def _require_reportlab():
    try:
        import reportlab  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on env
        raise ImportError(
            "PDF reports need reportlab. Install with: pip install '.[reports]'"
        ) from exc
    return reportlab


def write_pdf_bytes(
    summary: ActionSummary, *, reporting_context: ReportingContext | None = None
) -> bytes:
    _require_reportlab()
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    context = reporting_context or ReportingContext(
        basis="forecast",
        status="not_reportable",
        reason=(
            "No explicit preferred start was supplied; "
            "cost and carbon differences are unavailable."
        ),
    )
    heading, metric_prefix = _report_language(context)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Energy Action Report")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Community Energy Flex - Action Report", styles["Title"]),
        Paragraph(heading, styles["Normal"]),
        Paragraph(f"Objective: {summary.objective}", styles["Normal"]),
        Spacer(1, 0.4 * cm),
    ]
    if context.is_reportable:
        story += [
            Paragraph(
                f"<b>{metric_prefix} cost difference:</b> £{summary.total_cost_saving_pounds:.2f} "
                f"&nbsp;&nbsp; <b>{metric_prefix} carbon difference:</b> "
                f"{summary.total_carbon_saving_kg:.2f} kg CO2",
                styles["Normal"],
            ),
            Spacer(1, 0.4 * cm),
        ]
    elif context.reason:
        story += [Paragraph(context.reason, styles["Normal"]), Spacer(1, 0.4 * cm)]
    story.append(Paragraph("What to do", styles["Heading2"]))
    items = [
        ListItem(Paragraph(
            (
                f"<b>{line.device_type}</b>: run {line.recommended_window} "
                f"(was {line.baseline_window}) - {metric_prefix.lower()} difference "
                f"{line.cost_saving_p:.0f}p, {line.carbon_saving_g:.0f} gCO2. {line.caveat}"
                if context.is_reportable
                else f"<b>{line.device_type}</b>: run {line.recommended_window}. {line.caveat}"
            ),
            styles["Normal"],
        ))
        for line in summary.lines
    ]
    story.append(ListFlowable(items, bulletType="bullet"))
    story += [
        Spacer(1, 0.6 * cm),
        Paragraph(f"<i>{summary.safety_statement}</i>", styles["Italic"]),
    ]
    doc.build(story)
    return buffer.getvalue()


def write_pdf(
    summary: ActionSummary, path: str, *, reporting_context: ReportingContext | None = None
) -> str:
    with open(path, "wb") as fh:
        fh.write(write_pdf_bytes(summary, reporting_context=reporting_context))
    return path
