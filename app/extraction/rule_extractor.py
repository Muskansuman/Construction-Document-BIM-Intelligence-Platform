"""Deterministic keyword + regex extractor.

This is the baseline that always runs (no GPU, no API key). The optional LLM
extractor adds recall on messy text; both emit the same EngineeringParameter.
"""
from __future__ import annotations

import re

from app.extraction.catalog import CATALOG, ParameterSpec
from app.extraction.normalizers import find_grade, find_lengths_mm
from app.extraction.schemas import (
    EngineeringParameter,
    ParsedDocument,
    SourceKind,
    SourceRef,
)

# Split on ; , and sentence-ending dots, but not decimal points (0.23 m).
_CLAUSE_SPLIT = re.compile(r"[;,]|\.(?!\d)")


def _matches(spec: ParameterSpec, text: str) -> bool:
    t = text.lower()
    if any(x in t for x in spec.exclude):
        return False
    return any(all(w in t for w in group) for group in spec.keyword_groups)


def _extract_from_line(spec: ParameterSpec, text: str) -> tuple[float | str, str] | None:
    if spec.kind == "grade":
        g = find_grade(text, spec.key)
        return (g, g) if g else None
    for value_mm, raw in find_lengths_mm(text):
        if spec.min_mm is not None and value_mm < spec.min_mm:
            continue
        if spec.max_mm is not None and value_mm > spec.max_mm:
            continue
        return value_mm, raw
    return None


def extract_parameters(doc: ParsedDocument) -> list[EngineeringParameter]:
    """Scan text blocks and table rows; keep the first hit per key per document."""
    found: dict[str, EngineeringParameter] = {}

    def consider(text: str, src: SourceRef, base_conf: float, extractor: str) -> None:
        for spec in CATALOG:
            if spec.key in found or not _matches(spec, text):
                continue
            hit = _extract_from_line(spec, text)
            if hit is None:
                continue
            value, raw = hit
            found[spec.key] = EngineeringParameter(
                key=spec.key, label=spec.label, value=value, unit=spec.unit,
                raw_value=raw, confidence=round(base_conf * 0.95, 3),
                extractor=extractor, source=src.model_copy(update={"snippet": text[:200]}),
            )

    base = dict(document_id=doc.document_id, document_name=doc.name, document_type=doc.doc_type)

    for b in doc.text_blocks:
        src = SourceRef(**base, kind=b.source, page=b.page, bbox=b.bbox)
        # One line often states several facts: "door width 1000 mm, door height 2100 mm"
        for clause in _CLAUSE_SPLIT.split(b.text):
            if clause.strip():
                consider(clause.strip(), src, b.confidence, "rule")

    for t in doc.tables:
        for r_idx, row in enumerate(t.rows):
            text = " | ".join(f"{h}: {c}" for h, c in zip(t.header, row, strict=False) if c)
            src = SourceRef(**base, kind=SourceKind.TABLE, page=t.page, table_index=t.index, row=r_idx)
            consider(text, src, 1.0, "table")

    return list(found.values())
