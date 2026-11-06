"""Deterministic cross-document validation.

Design rule: Python decides, the LLM only explains.

For every catalogue key:
  * group extracted values by source document
  * numeric -> compare spread against a relative tolerance
  * grade   -> exact match after normalisation (M25 vs M30 is never "close")
  * a key present in one primary source but absent in another -> MISSING
Then assign severity, confidence and a human-review status.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict

from app.core.config import get_settings
from app.extraction.catalog import BY_KEY
from app.extraction.schemas import (
    DocumentType,
    EngineeringParameter,
    Finding,
    ReviewStatus,
    Severity,
    Verdict,
)

# Sources that are expected to state every catalogue parameter they share.
PRIMARY_SOURCES = {DocumentType.SPECIFICATION, DocumentType.BIM, DocumentType.DRAWING, DocumentType.CAD}


def _fid(key: str) -> str:
    return "F-" + hashlib.sha1(key.encode()).hexdigest()[:8]


def _compare_numeric(values: list[float], tol_pct: float) -> tuple[Verdict, float, float]:
    lo, hi = min(values), max(values)
    diff = hi - lo
    pct = 0.0 if lo == 0 else diff / lo * 100
    if diff == 0:
        return Verdict.MATCH, diff, pct
    if pct <= tol_pct:
        return Verdict.WITHIN_TOLERANCE, diff, pct
    return Verdict.CONFLICT, diff, pct


def _severity(verdict: Verdict, key: str, pct: float | None) -> Severity:
    if verdict == Verdict.MATCH:
        return Severity.INFO
    if verdict == Verdict.WITHIN_TOLERANCE:
        return Severity.LOW
    if verdict == Verdict.MISSING:
        return Severity.MEDIUM
    base = Severity(BY_KEY[key].severity_on_conflict) if key in BY_KEY else Severity.MEDIUM
    # Large numeric deviations escalate one level.
    if pct is not None and pct >= 20 and base in (Severity.MEDIUM, Severity.HIGH):
        return Severity.HIGH if base == Severity.MEDIUM else Severity.CRITICAL
    return base


def check_consistency(
    params: list[EngineeringParameter],
    documents_present: dict[str, DocumentType] | None = None,
) -> list[Finding]:
    """
    params:            all parameters from all documents
    documents_present: {document_name: type} for MISSING detection (optional)
    """
    s = get_settings()
    by_key: dict[str, list[EngineeringParameter]] = defaultdict(list)
    for p in params:
        by_key[p.key].append(p)

    findings: list[Finding] = []
    for key, items in sorted(by_key.items()):
        # One value per document (highest confidence wins inside a document).
        per_doc: dict[str, EngineeringParameter] = {}
        for p in items:
            cur = per_doc.get(p.source.document_name)
            if cur is None or p.confidence > cur.confidence:
                per_doc[p.source.document_name] = p
        evidence = list(per_doc.values())
        label = evidence[0].label
        confidence = round(min(p.confidence for p in evidence), 3)

        diff = pct = None
        if len(evidence) < 2:
            verdict, rule = Verdict.MISSING, "presence_check"
            if documents_present:
                missing_in = [n for n, t in documents_present.items()
                              if t in PRIMARY_SOURCES and n not in per_doc]
                if not missing_in:
                    continue  # only one primary document exists: nothing to compare
                rule = f"presence_check(missing in: {', '.join(missing_in)})"
        elif all(isinstance(p.value, (int, float)) for p in evidence):
            verdict, diff, pct = _compare_numeric([float(p.value) for p in evidence], s.numeric_tolerance_pct)
            rule = f"numeric_tolerance(±{s.numeric_tolerance_pct:g}%)"
            diff, pct = round(diff, 2), round(pct, 2)
        else:
            vals = {str(p.value).upper() for p in evidence}
            verdict = Verdict.MATCH if len(vals) == 1 else Verdict.CONFLICT
            rule = "exact_match(normalised)"

        needs_review = (
            verdict in (Verdict.CONFLICT, Verdict.MISSING)
            or confidence < s.review_confidence_threshold
        )
        findings.append(
            Finding(
                finding_id=_fid(key),
                parameter_key=key,
                parameter_label=label,
                verdict=verdict,
                severity=_severity(verdict, key, pct),
                values=evidence,
                difference=diff,
                difference_pct=pct,
                rule_applied=rule,
                confidence=confidence,
                review_status=ReviewStatus.NEEDS_REVIEW if needs_review else ReviewStatus.AUTO_ACCEPTED,
            )
        )

    order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}
    return sorted(findings, key=lambda f: (order[f.severity], f.parameter_key))
