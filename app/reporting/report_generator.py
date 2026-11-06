"""Report exporters: JSON (machine), Markdown (GitHub/readme), PDF (reviewer)."""
from __future__ import annotations

from pathlib import Path

from app.extraction.schemas import Finding, ReviewReport
from app.reporting.explainer import _fmt, _where

VERDICT_ICON = {"match": "✅", "within_tolerance": "🟡", "conflict": "❌", "missing": "⚠️"}


def to_json(report: ReviewReport, path: Path) -> Path:
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def to_markdown(report: ReviewReport) -> str:
    s = report.summary
    lines = [
        f"# Review report: {report.project_name}",
        f"_Generated {report.generated_at:%Y-%m-%d %H:%M UTC}_",
        "",
        f"**Documents:** {', '.join(report.documents)}  ",
        f"**Parameters extracted:** {report.parameters_extracted}  ",
        f"**Findings:** {s['match']} match · {s['within_tolerance']} within tolerance · "
        f"{s['conflict']} conflict · {s['missing']} missing · **{s['needs_review']} need review**",
        "",
        "| | Parameter | Values (source) | Severity | Confidence | Review |",
        "|---|---|---|---|---|---|",
    ]
    for f in report.findings:
        vals = "<br>".join(f"{_fmt(p)} — {_where(p)}" for p in f.values)
        lines.append(
            f"| {VERDICT_ICON[f.verdict.value]} | {f.parameter_label} | {vals} | {f.severity.value} "
            f"| {f.confidence:.2f} | {f.review_status.value} |"
        )
    lines += ["", "## Explanations", ""]
    lines += [f"- **{f.finding_id} {f.parameter_label}:** {f.explanation}" for f in report.findings]
    return "\n".join(lines)


def to_pdf(report: ReviewReport, path: Path) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    small = styles["BodyText"].clone("small", fontSize=8, leading=10)
    color = {"match": colors.HexColor("#E6F4EA"), "within_tolerance": colors.HexColor("#FFF8E1"),
             "conflict": colors.HexColor("#FDECEA"), "missing": colors.HexColor("#FFF3E0")}

    s = report.summary
    story = [
        Paragraph(f"BuildDoc AI review: {report.project_name}", styles["Title"]),
        Paragraph(f"Documents: {', '.join(report.documents)}", styles["Normal"]),
        Paragraph(f"{s['conflict']} conflicts, {s['missing']} missing, {s['needs_review']} need human review",
                  styles["Normal"]),
        Spacer(1, 12),
    ]
    data = [["Verdict", "Parameter", "Evidence", "Severity", "Conf.", "Review", "Explanation"]]
    for f in report.findings:
        data.append([
            f.verdict.value, f.parameter_label,
            Paragraph("<br/>".join(f"{_fmt(p)} — {_where(p)}" for p in f.values), small),
            f.severity.value, f"{f.confidence:.2f}", f.review_status.value,
            Paragraph(f.explanation or "", small),
        ])
    t = Table(data, colWidths=[60, 90, 200, 50, 35, 70, 255], repeatRows=1)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
             ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#263238")),
             ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
             ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i, f in enumerate(report.findings, start=1):
        style.append(("BACKGROUND", (0, i), (0, i), color[f.verdict.value]))
    t.setStyle(TableStyle(style))
    story.append(t)
    SimpleDocTemplate(str(path), pagesize=landscape(A4)).build(story)
    return path


def finding_rows(findings: list[Finding]) -> list[dict]:
    """Flat rows for dataframes / UI tables."""
    rows = []
    for f in findings:
        row = {"id": f.finding_id, "parameter": f.parameter_label, "verdict": f.verdict.value,
               "severity": f.severity.value, "confidence": f.confidence, "review": f.review_status.value}
        for p in f.values:
            row[p.source.document_name] = _fmt(p)
        rows.append(row)
    return rows
