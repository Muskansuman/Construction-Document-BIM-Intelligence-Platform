"""Parameter catalogue: the single source of truth for what the system compares.

Adding a new check = adding one ParameterSpec here. The rule extractor, the
LLM prompt, the BIM adapter and the consistency checker all read this list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ParameterSpec:
    key: str
    label: str
    kind: Literal["length", "grade"]
    # A text line must contain ALL words from one of these groups to be a candidate.
    keyword_groups: tuple[tuple[str, ...], ...]
    unit: str | None = "mm"
    # Plausible range in mm, used to reject OCR junk (e.g. page numbers).
    min_mm: float | None = None
    max_mm: float | None = None
    # Exclude lines containing any of these words.
    exclude: tuple[str, ...] = field(default_factory=tuple)
    severity_on_conflict: Literal["low", "medium", "high", "critical"] = "medium"


CATALOG: list[ParameterSpec] = [
    ParameterSpec(
        key="wall.external.thickness", label="External wall thickness", kind="length",
        keyword_groups=(("external", "wall"), ("outer", "wall")),
        min_mm=75, max_mm=600, exclude=("height",), severity_on_conflict="high",
    ),
    ParameterSpec(
        key="wall.internal.thickness", label="Internal wall thickness", kind="length",
        keyword_groups=(("internal", "wall"), ("partition", "wall"), ("inner", "wall")),
        min_mm=50, max_mm=400, exclude=("height",),
    ),
    ParameterSpec(
        key="slab.thickness", label="Slab thickness", kind="length",
        keyword_groups=(("slab", "thick"), ("slab", "depth")),
        min_mm=75, max_mm=600, severity_on_conflict="high",
    ),
    ParameterSpec(
        key="door.main.width", label="Main door width", kind="length",
        keyword_groups=(("door", "width"), ("main", "door")),
        min_mm=600, max_mm=3000, exclude=("height",),
    ),
    ParameterSpec(
        key="door.main.height", label="Main door height", kind="length",
        keyword_groups=(("door", "height"),),
        min_mm=1800, max_mm=3500,
    ),
    ParameterSpec(
        key="storey.height", label="Floor-to-floor height", kind="length",
        keyword_groups=(("floor", "height"), ("storey", "height")),
        min_mm=2400, max_mm=6000,
    ),
    ParameterSpec(
        key="concrete.grade", label="Concrete grade", kind="grade", unit=None,
        keyword_groups=(("concrete",), ("grade",), ("rcc",)),
        severity_on_conflict="critical",
    ),
    ParameterSpec(
        key="rebar.grade", label="Reinforcement steel grade", kind="grade", unit=None,
        keyword_groups=(("steel",), ("reinforcement",), ("rebar",)),
        severity_on_conflict="critical",
    ),
]

BY_KEY = {s.key: s for s in CATALOG}
