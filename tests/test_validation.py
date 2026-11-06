from app.extraction.schemas import (
    DocumentType,
    EngineeringParameter,
    ReviewStatus,
    Severity,
    SourceKind,
    SourceRef,
    Verdict,
)
from app.pipeline.orchestrator import analyse, ingest
from app.validation.consistency_checker import check_consistency


def _p(key, value, doc, conf=1.0, unit="mm"):
    return EngineeringParameter(
        key=key, label=key, value=value, unit=unit, confidence=conf,
        source=SourceRef(document_id=doc, document_name=doc,
                         document_type=DocumentType.SPECIFICATION, kind=SourceKind.PDF_TEXT, page=1),
    )


def test_numeric_match():
    [f] = check_consistency([_p("slab.thickness", 150, "a"), _p("slab.thickness", 150, "b")])
    assert f.verdict == Verdict.MATCH and f.review_status == ReviewStatus.AUTO_ACCEPTED


def test_within_tolerance():
    [f] = check_consistency([_p("slab.thickness", 150, "a"), _p("slab.thickness", 152, "b")])
    assert f.verdict == Verdict.WITHIN_TOLERANCE


def test_numeric_conflict_escalates():
    [f] = check_consistency([_p("door.main.width", 1000, "a"), _p("door.main.width", 750, "b")])
    assert f.verdict == Verdict.CONFLICT
    assert f.difference == 250
    assert f.severity == Severity.HIGH          # medium escalated for >=20% deviation
    assert f.review_status == ReviewStatus.NEEDS_REVIEW


def test_grade_conflict_is_critical():
    [f] = check_consistency([_p("concrete.grade", "M25", "a", unit=None),
                             _p("concrete.grade", "M30", "b", unit=None)])
    assert f.verdict == Verdict.CONFLICT and f.severity == Severity.CRITICAL


def test_low_confidence_match_needs_review():
    [f] = check_consistency([_p("slab.thickness", 150, "a", conf=0.5), _p("slab.thickness", 150, "b")])
    assert f.verdict == Verdict.MATCH and f.review_status == ReviewStatus.NEEDS_REVIEW


def test_missing():
    findings = check_consistency([_p("slab.thickness", 150, "a")],
                                 {"a": DocumentType.SPECIFICATION, "b": DocumentType.BIM})
    assert findings[0].verdict == Verdict.MISSING


def test_end_to_end(spec_path, bim_model):
    """Spec vs BIM reproduces the example table from the project brief."""
    report = analyse([ingest(spec_path), bim_model], "Block A").report
    by_key = {f.parameter_key: f for f in report.findings}

    assert by_key["wall.external.thickness"].verdict == Verdict.MATCH
    assert by_key["slab.thickness"].verdict == Verdict.MATCH
    assert by_key["concrete.grade"].verdict == Verdict.CONFLICT
    assert by_key["door.main.width"].verdict == Verdict.CONFLICT
    assert report.findings[0].severity == Severity.CRITICAL   # sorted worst-first
    assert all(f.explanation for f in report.findings)
