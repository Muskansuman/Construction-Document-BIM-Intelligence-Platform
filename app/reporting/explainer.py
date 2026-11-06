"""Explanations for findings.

A template explanation is always produced. If an LLM is configured it may
rewrite the text for readability, but it receives the verdict as a fixed
fact and is told not to change it.
"""
from __future__ import annotations

from app.extraction.llm_client import chat, llm_enabled
from app.extraction.schemas import EngineeringParameter, Finding, Verdict


def _where(p: EngineeringParameter) -> str:
    s = p.source
    if s.element_id:
        return f"{s.document_name} (BIM element {s.element_id})"
    loc = f"page {s.page}" if s.page else ""
    if s.table_index is not None:
        loc += f", table {s.table_index + 1} row {s.row + 1}" if s.row is not None else f", table {s.table_index + 1}"
    return f"{s.document_name} ({loc.strip(', ')})" if loc else s.document_name


def _fmt(p: EngineeringParameter) -> str:
    return f"{p.value:g} {p.unit}" if isinstance(p.value, (int, float)) and p.unit else str(p.value)


def template_explanation(f: Finding) -> str:
    vals = "; ".join(f"{_fmt(p)} in {_where(p)}" for p in f.values)
    if f.verdict == Verdict.MATCH:
        return f"{f.parameter_label} is consistent across sources: {vals}."
    if f.verdict == Verdict.WITHIN_TOLERANCE:
        return (f"{f.parameter_label} differs by {f.difference_pct:.1f}% ({vals}), "
                f"which is inside the allowed tolerance. No action needed.")
    if f.verdict == Verdict.MISSING:
        return (f"{f.parameter_label} is stated as {vals}, but no other source gives a value "
                f"to cross-check it ({f.rule_applied}). Please confirm the value.")
    diff = f" (difference {f.difference:g} mm, {f.difference_pct:.1f}%)" if f.difference is not None else ""
    return (f"Conflict: {f.parameter_label} is {vals}{diff}. "
            f"Severity {f.severity.value}. A reviewer should decide which document is authoritative.")


SYSTEM = ("You rewrite construction QA findings for a site engineer in 1-2 sentences. "
          "The verdict and numbers are FINAL facts; do not change, soften or dispute them. "
          "Mention the source documents. No preamble.")


def explain(f: Finding) -> str:
    base = template_explanation(f)
    if llm_enabled() and f.verdict in (Verdict.CONFLICT, Verdict.MISSING):
        rewritten = chat(SYSTEM, f"Verdict: {f.verdict.value}\nFinding: {base}")
        if rewritten:
            return rewritten.strip()
    return base
