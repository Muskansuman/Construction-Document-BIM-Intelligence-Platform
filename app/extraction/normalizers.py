"""Unit and grade normalisation. Deterministic and fully unit-tested."""
from __future__ import annotations

import re

_UNIT_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "\"": 25.4, "ft": 304.8, "'": 304.8}

# 200mm | 200 mm | 0.2 m | 20 cm | 200 THK | 9"
LENGTH_RE = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>mm|cm|m|in|ft|\"|')?(?![a-z])\s*(?:thk|thick)?",
    re.IGNORECASE,
)

# Indian (IS 456) M20/M25..., Eurocode C25/30, rebar Fe415/Fe500/Fe500D
CONCRETE_RE = re.compile(r"\b(M\s?\d{2,3}|C\d{2}/\d{2})\b", re.IGNORECASE)
REBAR_RE = re.compile(r"\b(Fe\s?\d{3}[A-Z]?|B500[A-C]?|Grade\s?60)\b", re.IGNORECASE)


def to_mm(value: float, unit: str | None) -> float:
    """Convert to millimetres. Unit-less numbers are assumed to already be mm."""
    if not unit:
        return float(value)
    return float(value) * _UNIT_TO_MM[unit.lower()]


def find_lengths_mm(text: str) -> list[tuple[float, str]]:
    """Return (value_mm, raw_match) for every length-like token in text."""
    out = []
    for m in LENGTH_RE.finditer(text):
        num, unit = float(m.group("num")), m.group("unit")
        out.append((round(to_mm(num, unit), 1), m.group(0).strip()))
    return out


def normalize_concrete_grade(raw: str) -> str:
    """'m 25' -> 'M25'; 'c25/30' -> 'C25/30'."""
    return re.sub(r"\s+", "", raw).upper()


def normalize_rebar_grade(raw: str) -> str:
    s = re.sub(r"\s+", "", raw)
    return s[:2].capitalize() + s[2:].upper() if s.lower().startswith("fe") else s.upper()


def find_grade(text: str, key: str) -> str | None:
    if key == "concrete.grade":
        m = CONCRETE_RE.search(text)
        return normalize_concrete_grade(m.group(1)) if m else None
    if key == "rebar.grade":
        m = REBAR_RE.search(text)
        return normalize_rebar_grade(m.group(1)) if m else None
    return None
