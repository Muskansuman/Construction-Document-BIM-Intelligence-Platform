"""REST API.

    POST  /documents                          upload + parse one file
    GET   /documents                          list parsed documents
    GET   /documents/{id}                     parsed content (text, tables, BIM elements)
    POST  /analyses                           run extraction + validation on document ids
    GET   /analyses/{id}                      full review report
    GET   /analyses/{id}/export?fmt=json|md|pdf
    PATCH /analyses/{id}/findings/{fid}       human review decision
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.store import store
from app.extraction.schemas import BIMModel, DocumentType, ReviewReport, ReviewStatus
from app.pipeline.orchestrator import analyse, infer_doc_type, ingest
from app.reporting.report_generator import to_json, to_markdown, to_pdf

router = APIRouter()

ALLOWED = {".pdf", ".xlsx", ".xls", ".ifc", ".dxf", ".txt", ".md"}


class DocumentSummary(BaseModel):
    document_id: str
    name: str
    doc_type: DocumentType
    pages: int = 0
    used_ocr: bool = False
    text_blocks: int = 0
    tables: int = 0
    bim_elements: int = 0


def _summary(d) -> DocumentSummary:
    if isinstance(d, BIMModel):
        return DocumentSummary(document_id=d.document_id, name=d.name, doc_type=DocumentType.BIM,
                               bim_elements=len(d.elements))
    return DocumentSummary(document_id=d.document_id, name=d.name, doc_type=d.doc_type, pages=d.page_count,
                           used_ocr=d.used_ocr, text_blocks=len(d.text_blocks), tables=len(d.tables))


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_provider": get_settings().llm_provider}


@router.post("/documents", response_model=DocumentSummary)
async def upload_document(file: UploadFile = File(...), doc_type: DocumentType | None = Form(None)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(415, f"Unsupported file type {suffix}. Allowed: {sorted(ALLOWED)}")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / Path(file.filename).name
        with path.open("wb") as fh:
            shutil.copyfileobj(file.file, fh)
        try:
            doc = ingest(path, doc_type or infer_doc_type(path))
        except Exception as exc:
            raise HTTPException(422, f"Could not parse {file.filename}: {exc}") from exc
    store.add_document(doc)
    return _summary(doc)


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents():
    return [_summary(d) for d in store.documents.values()]


@router.get("/documents/{document_id}")
def get_document(document_id: str):
    if document_id not in store.documents:
        raise HTTPException(404, "Document not found")
    return store.documents[document_id]


class AnalysisRequest(BaseModel):
    document_ids: list[str]
    project_name: str = "Untitled project"


class AnalysisResponse(BaseModel):
    analysis_id: str
    summary: dict[str, int]
    report: ReviewReport


@router.post("/analyses", response_model=AnalysisResponse)
def create_analysis(req: AnalysisRequest):
    missing = [i for i in req.document_ids if i not in store.documents]
    if missing:
        raise HTTPException(404, f"Unknown document ids: {missing}")
    result = analyse([store.documents[i] for i in req.document_ids], req.project_name)
    rid = store.add_report(result.report)
    return AnalysisResponse(analysis_id=rid, summary=result.report.summary, report=result.report)


def _report(analysis_id: str) -> ReviewReport:
    if analysis_id not in store.reports:
        raise HTTPException(404, "Analysis not found")
    return store.reports[analysis_id]


@router.get("/analyses/{analysis_id}", response_model=ReviewReport)
def get_analysis(analysis_id: str):
    return _report(analysis_id)


@router.get("/analyses/{analysis_id}/export")
def export_analysis(analysis_id: str, fmt: Literal["json", "md", "pdf"] = "json"):
    report = _report(analysis_id)
    out = get_settings().output_dir
    if fmt == "md":
        return PlainTextResponse(to_markdown(report), media_type="text/markdown")
    if fmt == "pdf":
        path = to_pdf(report, out / f"{analysis_id}.pdf")
        return FileResponse(path, media_type="application/pdf", filename=path.name)
    path = to_json(report, out / f"{analysis_id}.json")
    return FileResponse(path, media_type="application/json", filename=path.name)


class ReviewDecision(BaseModel):
    review_status: Literal[ReviewStatus.APPROVED, ReviewStatus.REJECTED]
    comment: str | None = None


@router.patch("/analyses/{analysis_id}/findings/{finding_id}")
def review_finding(analysis_id: str, finding_id: str, decision: ReviewDecision):
    report = _report(analysis_id)
    for f in report.findings:
        if f.finding_id == finding_id:
            f.review_status = decision.review_status
            if decision.comment:
                f.explanation = f"{f.explanation}\n\nReviewer: {decision.comment}"
            return f
    raise HTTPException(404, "Finding not found")
