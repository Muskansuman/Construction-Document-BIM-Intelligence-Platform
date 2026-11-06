"""End-to-end pipeline: ingest -> extract -> validate -> explain -> report.

Usable from the API, the Streamlit app, or the CLI:
    python -m app.pipeline.orchestrator spec.pdf model.ifc boq.xlsx
"""
from __future__ import annotations

import logging
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.extraction.schemas import (
    BIMModel,
    DocumentType,
    EngineeringParameter,
    ParsedDocument,
    ReviewReport,
)

log = logging.getLogger(__name__)


def infer_doc_type(path: Path) -> DocumentType:
    suf, name = path.suffix.lower(), path.name.lower()
    if suf == ".ifc":
        return DocumentType.BIM
    if suf == ".dxf":
        return DocumentType.CAD
    if suf in {".xlsx", ".xls"} or "boq" in name or "quantit" in name:
        return DocumentType.BOQ
    if any(w in name for w in ("plan", "drawing", "dwg", "layout", "elevation")):
        return DocumentType.DRAWING
    return DocumentType.SPECIFICATION


@dataclass
class PipelineResult:
    documents: list[ParsedDocument] = field(default_factory=list)
    bim_models: list[BIMModel] = field(default_factory=list)
    parameters: list[EngineeringParameter] = field(default_factory=list)
    report: ReviewReport | None = None


def ingest(path: Path, doc_type: DocumentType | None = None) -> ParsedDocument | BIMModel:
    doc_type = doc_type or infer_doc_type(path)
    doc_id = uuid.uuid4().hex[:12]
    if doc_type == DocumentType.BIM:
        from app.bim.ifc_parser import parse_ifc
        return parse_ifc(path, doc_id)
    if doc_type == DocumentType.CAD:
        from app.bim.cad_parser import parse_dxf
        return parse_dxf(path, doc_id)
    from app.ocr.pdf_parser import parse_document
    return parse_document(path, doc_type, doc_id)


def analyse(items: list[ParsedDocument | BIMModel], project_name: str = "Untitled project") -> PipelineResult:
    """Run extraction + validation on already-ingested documents."""
    from app.extraction.bim_adapter import bim_to_parameters
    from app.extraction.llm_extractor import extract
    from app.reporting.explainer import explain
    from app.validation.consistency_checker import check_consistency

    res = PipelineResult()
    present: dict[str, DocumentType] = {}
    for it in items:
        if isinstance(it, BIMModel):
            res.bim_models.append(it)
            res.parameters += bim_to_parameters(it)
            present[it.name] = DocumentType.BIM
        else:
            res.documents.append(it)
            res.parameters += extract(it)
            present[it.name] = it.doc_type

    findings = check_consistency(res.parameters, present)
    for f in findings:
        f.explanation = explain(f)

    res.report = ReviewReport(
        project_name=project_name,
        documents=list(present),
        parameters_extracted=len(res.parameters),
        findings=findings,
    )
    return res


def run(paths: list[Path], project_name: str = "Untitled project") -> PipelineResult:
    return analyse([ingest(p) for p in paths], project_name)


if __name__ == "__main__":  # pragma: no cover
    from app.core.config import get_settings
    from app.core.logging import setup_logging
    from app.reporting.report_generator import to_json, to_markdown

    setup_logging()
    result = run([Path(p) for p in sys.argv[1:]], project_name="CLI run")
    out = get_settings().output_dir
    to_json(result.report, out / "report.json")
    (out / "report.md").write_text(to_markdown(result.report), encoding="utf-8")
    print(to_markdown(result.report))
