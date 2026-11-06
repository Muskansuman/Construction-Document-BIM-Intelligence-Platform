"""LLM-assisted extraction (optional).

The LLM only *reads*: it proposes values with a verbatim quote and page.
Every proposal is then
  1. checked against the catalogue (unknown keys dropped),
  2. re-normalised with the same deterministic normalisers,
  3. accepted only if the quote actually appears on the cited page (anti-hallucination).
Rule-based hits always win over LLM hits for the same key.
"""
from __future__ import annotations

import logging

from app.extraction.catalog import BY_KEY, CATALOG
from app.extraction.llm_client import chat_json, llm_enabled
from app.extraction.normalizers import find_grade, find_lengths_mm
from app.extraction.rule_extractor import extract_parameters as rule_extract
from app.extraction.schemas import EngineeringParameter, ParsedDocument, SourceKind, SourceRef

log = logging.getLogger(__name__)

SYSTEM = """You extract engineering parameters from construction documents.
Return JSON: {"parameters": [{"key": str, "value": str, "page": int, "quote": str}]}
Rules:
- Only use keys from the provided catalogue.
- "quote" must be copied VERBATIM from the text (max 25 words).
- Include units in "value" exactly as written (e.g. "230 mm", "M25").
- If a parameter is not stated, omit it. Never guess."""

MAX_CHARS = 12_000


def _catalog_prompt() -> str:
    return "\n".join(f"- {s.key}: {s.label}" for s in CATALOG)


def _pages_text(doc: ParsedDocument) -> dict[int, str]:
    pages: dict[int, list[str]] = {}
    for b in doc.text_blocks:
        pages.setdefault(b.page, []).append(b.text)
    return {p: "\n".join(t) for p, t in pages.items()}


def llm_extract(doc: ParsedDocument) -> list[EngineeringParameter]:
    pages = _pages_text(doc)
    body = "\n\n".join(f"=== PAGE {p} ===\n{t}" for p, t in sorted(pages.items()))[:MAX_CHARS]
    data = chat_json(SYSTEM, f"Catalogue:\n{_catalog_prompt()}\n\nDocument '{doc.name}':\n{body}")
    if not data:
        return []

    out: list[EngineeringParameter] = []
    for item in data.get("parameters", []):
        spec = BY_KEY.get(item.get("key", ""))
        quote, page = str(item.get("quote", "")), item.get("page")
        if spec is None or not quote:
            continue
        if quote.lower() not in pages.get(page, "").lower():
            log.info("Dropped unverifiable LLM value for %s (quote not on page %s)", spec.key, page)
            continue
        raw = str(item.get("value", ""))
        if spec.kind == "grade":
            value = find_grade(raw, spec.key)
        else:
            lens = [v for v, _ in find_lengths_mm(raw)
                    if (spec.min_mm is None or v >= spec.min_mm) and (spec.max_mm is None or v <= spec.max_mm)]
            value = lens[0] if lens else None
        if value is None:
            continue
        out.append(EngineeringParameter(
            key=spec.key, label=spec.label, value=value, unit=spec.unit, raw_value=raw,
            confidence=0.75, extractor="llm",
            source=SourceRef(document_id=doc.document_id, document_name=doc.name,
                             document_type=doc.doc_type, kind=SourceKind.OCR if doc.used_ocr else SourceKind.PDF_TEXT,
                             page=page, snippet=quote),
        ))
    return out


def extract(doc: ParsedDocument) -> list[EngineeringParameter]:
    """Rules first; LLM fills only the keys rules missed."""
    params = rule_extract(doc)
    if llm_enabled():
        have = {p.key for p in params}
        params += [p for p in llm_extract(doc) if p.key not in have]
    return params


__all__ = ["extract", "llm_extract"]
