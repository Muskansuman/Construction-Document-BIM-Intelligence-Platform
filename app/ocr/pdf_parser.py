"""Document ingestion: native PDF text first, OCR fallback for scanned pages.

Decision per page:
    native text chars >= threshold  -> use PyMuPDF text (confidence 1.0)
    otherwise                       -> render page at `ocr_dpi`, run PaddleOCR
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.extraction.schemas import BBox, DocumentType, ParsedDocument, SourceKind, TextBlock
from app.ocr.table_extractor import extract_excel_tables, extract_pdf_tables

log = logging.getLogger(__name__)


def _page_to_array(page, dpi: int):
    import numpy as np

    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return img[:, :, :3] if pix.n == 4 else img


def parse_pdf(path: Path, doc_type: DocumentType, document_id: str | None = None) -> ParsedDocument:
    import fitz  # PyMuPDF

    s = get_settings()
    doc = ParsedDocument(
        document_id=document_id or uuid.uuid4().hex[:12],
        name=path.name,
        doc_type=doc_type,
    )

    with fitz.open(path) as pdf:
        doc.page_count = pdf.page_count
        for i, page in enumerate(pdf, start=1):
            native = page.get_text("blocks")  # (x0,y0,x1,y1,text,block_no,type)
            n_chars = sum(len(b[4].strip()) for b in native)

            if n_chars >= s.ocr_min_chars_per_page or not s.ocr_enabled:
                for x0, y0, x1, y1, text, *_ in native:
                    if text.strip():
                        doc.text_blocks.append(
                            TextBlock(page=i, text=text.strip(),
                                      bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1),
                                      source=SourceKind.PDF_TEXT)
                        )
            else:
                from app.ocr.ocr_engine import ocr_image

                log.info("%s p%d: %d native chars -> OCR", path.name, i, n_chars)
                doc.text_blocks.extend(ocr_image(_page_to_array(page, s.ocr_dpi), i, s.ocr_lang))
                doc.used_ocr = True

    try:
        doc.tables = extract_pdf_tables(path)
    except Exception as exc:  # tables are best-effort
        log.warning("Table extraction failed for %s: %s", path.name, exc)
    return doc


def parse_document(path: Path, doc_type: DocumentType, document_id: str | None = None) -> ParsedDocument:
    """Entry point for any non-BIM document (PDF or Excel BOQ)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path, doc_type, document_id)
    if suffix in {".xlsx", ".xls"}:
        return ParsedDocument(
            document_id=document_id or uuid.uuid4().hex[:12],
            name=path.name,
            doc_type=doc_type,
            tables=extract_excel_tables(path),
        )
    if suffix in {".txt", ".md"}:  # handy for tests and demos
        text = path.read_text(encoding="utf-8")
        return ParsedDocument(
            document_id=document_id or uuid.uuid4().hex[:12],
            name=path.name,
            doc_type=doc_type,
            page_count=1,
            text_blocks=[TextBlock(page=1, text=line) for line in text.splitlines() if line.strip()],
        )
    raise ValueError(f"Unsupported document type: {suffix}")
