"""Pydantic data contracts shared by every pipeline stage.

Every value the system reports carries a `SourceRef`, so any finding can be
traced back to a PDF page, a table cell, or a BIM element GlobalId.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class DocumentType(str, Enum):
    DRAWING = "drawing"              # architectural / structural drawing PDF
    SPECIFICATION = "specification"  # structural spec (often scanned)
    BOQ = "boq"                      # bill of quantities (PDF / XLSX)
    BIM = "bim"                      # IFC model
    CAD = "cad"                      # DXF drawing


class SourceKind(str, Enum):
    PDF_TEXT = "pdf_text"
    OCR = "ocr"
    TABLE = "table"
    IFC = "ifc"
    DXF = "dxf"


class Verdict(str, Enum):
    MATCH = "match"
    CONFLICT = "conflict"
    WITHIN_TOLERANCE = "within_tolerance"
    MISSING = "missing"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewStatus(str, Enum):
    AUTO_ACCEPTED = "auto_accepted"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


# --------------------------------------------------------------------------- #
# Provenance
# --------------------------------------------------------------------------- #
class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class SourceRef(BaseModel):
    """Where a value came from. This is the evidence trail."""

    document_id: str
    document_name: str
    document_type: DocumentType
    kind: SourceKind
    page: int | None = None            # 1-based PDF page
    table_index: int | None = None
    row: int | None = None
    bbox: BBox | None = None
    element_id: str | None = None      # IFC GlobalId / DXF handle
    snippet: str | None = None         # raw text the value was read from


# --------------------------------------------------------------------------- #
# Stage 1: parsed documents
# --------------------------------------------------------------------------- #
class TextBlock(BaseModel):
    page: int
    text: str
    bbox: BBox | None = None
    confidence: float = 1.0               # 1.0 for native text, OCR score otherwise
    source: SourceKind = SourceKind.PDF_TEXT


class Table(BaseModel):
    page: int | None = None
    index: int
    header: list[str] = Field(default_factory=list)
    rows: list[list[str | None]] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    document_id: str
    name: str
    doc_type: DocumentType
    page_count: int = 0
    text_blocks: list[TextBlock] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    used_ocr: bool = False

    def full_text(self) -> str:
        return "\n".join(b.text for b in self.text_blocks)


# --------------------------------------------------------------------------- #
# Stage 1b: BIM / CAD elements
# --------------------------------------------------------------------------- #
class BIMElement(BaseModel):
    element_id: str                       # IFC GlobalId
    element_type: str                     # IfcWall, IfcSlab, IfcDoor ...
    name: str | None = None
    storey: str | None = None
    material: str | None = None
    thickness_mm: float | None = None
    height_mm: float | None = None
    width_mm: float | None = None
    length_mm: float | None = None
    area_m2: float | None = None
    volume_m3: float | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class BIMModel(BaseModel):
    document_id: str
    name: str
    schema_version: str | None = None
    storeys: list[str] = Field(default_factory=list)
    elements: list[BIMElement] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Stage 2: normalised engineering parameters
# --------------------------------------------------------------------------- #
ParamValue = float | str


class EngineeringParameter(BaseModel):
    """One normalised fact, e.g. wall.external.thickness = 200 mm."""

    key: str = Field(..., description="Canonical key, e.g. 'wall.external.thickness'")
    label: str = Field(..., description="Human label, e.g. 'External wall thickness'")
    value: ParamValue
    unit: str | None = None            # always SI-normalised: mm, m2, m3, or None
    raw_value: str | None = None       # value as written in the source
    confidence: float = Field(1.0, ge=0, le=1)
    extractor: Literal["rule", "llm", "ifc", "dxf", "table"] = "rule"
    source: SourceRef


# --------------------------------------------------------------------------- #
# Stage 3: validation findings
# --------------------------------------------------------------------------- #
class Finding(BaseModel):
    finding_id: str
    parameter_key: str
    parameter_label: str
    verdict: Verdict
    severity: Severity
    values: list[EngineeringParameter]    # the evidence, one per source
    difference: float | None = None    # absolute numeric diff, if numeric
    difference_pct: float | None = None
    rule_applied: str                     # e.g. "numeric_tolerance(±2%)"
    confidence: float = Field(..., ge=0, le=1)
    review_status: ReviewStatus
    explanation: str | None = None     # LLM / template narrative (never decides)


class ReviewReport(BaseModel):
    project_name: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    documents: list[str]
    parameters_extracted: int
    findings: list[Finding]

    @property
    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {v.value: 0 for v in Verdict}
        for f in self.findings:
            out[f.verdict.value] += 1
        out["needs_review"] = sum(
            f.review_status == ReviewStatus.NEEDS_REVIEW for f in self.findings
        )
        return out
