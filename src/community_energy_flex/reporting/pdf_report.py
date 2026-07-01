"""Write a one-page PDF action report. Requires the ``reports`` extra
(reportlab)."""

from __future__ import annotations

from io import BytesIO

from community_energy_flex.reporting.summary import ActionSummary


def _require_reportlab():
    try:
        import reportlab  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on env
        raise ImportError(
            "PDF reports need reportlab. Install with: pip install '.[reports]'"
        ) from exc
    return reportlab


def write_pdf_bytes(summary: ActionSummary) -> bytes:
    _require_reportlab()
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Energy Action Report")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Community Energy Flexibility - Action Report", styles["Title"]),
        Paragraph(f"Objective: {summary.objective}", styles["Normal"]),
        Spacer(1, 0.4 * cm),
        Paragraph(
            f"<b>Estimated cost saving:</b> £{summary.total_cost_saving_pounds:.2f} "
            f"&nbsp;&nbsp; <b>Carbon saving:</b> {summary.total_carbon_saving_kg:.2f} kg CO2",
            styles["Normal"],
        ),
        Spacer(1, 0.4 * cm),
        Paragraph("What to do tomorrow", styles["Heading2"]),
    ]
    items = [
        ListItem(Paragraph(
            f"<b>{line.device_type}</b>: run {line.recommended_window} "
            f"(was {line.baseline_window}) - saves {line.cost_saving_p:.0f}p, "
            f"{line.carbon_saving_g:.0f} gCO2. {line.caveat}",
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


def write_pdf(summary: ActionSummary, path: str) -> str:
    with open(path, "wb") as fh:
        fh.write(write_pdf_bytes(summary))
    return path
