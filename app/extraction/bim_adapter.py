"""Turn a list of BIM elements into catalogue parameters.

A model has many walls/doors, so for each key we take the dominant (modal)
value, keep a representative element id as evidence, and lower confidence
when the model itself is not uniform.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from app.extraction.catalog import BY_KEY
from app.extraction.normalizers import find_grade
from app.extraction.schemas import (
    BIMElement,
    BIMModel,
    DocumentType,
    EngineeringParameter,
    SourceKind,
    SourceRef,
)


def _is_external(e: BIMElement) -> bool | None:
    for k, v in e.properties.items():
        if k.endswith(".IsExternal"):
            return bool(v)
    return None


def _is_door(e: BIMElement) -> bool:
    return e.element_type == "IfcDoor"


Selector = Callable[[BIMElement], bool]
Getter = Callable[[BIMElement], object]

RULES: dict[str, tuple[Selector, Getter]] = {
    "wall.external.thickness": (lambda e: e.element_type.startswith("IfcWall") and _is_external(e) is True,
                                lambda e: e.thickness_mm),
    "wall.internal.thickness": (lambda e: e.element_type.startswith("IfcWall") and _is_external(e) is False,
                                lambda e: e.thickness_mm),
    "slab.thickness": (lambda e: e.element_type == "IfcSlab", lambda e: e.thickness_mm),
    "door.main.width": (_is_door, lambda e: e.width_mm),
    "door.main.height": (_is_door, lambda e: e.height_mm),
    "concrete.grade": (lambda e: e.element_type in {"IfcWall", "IfcSlab", "IfcBeam", "IfcColumn"},
                       lambda e: find_grade(e.material or "", "concrete.grade")
                       or find_grade(" ".join(map(str, e.properties.values())), "concrete.grade")),
    "rebar.grade": (lambda e: True,
                    lambda e: find_grade(" ".join(map(str, e.properties.values())), "rebar.grade")),
}


def bim_to_parameters(bim: BIMModel) -> list[EngineeringParameter]:
    params: list[EngineeringParameter] = []
    for key, (select, get) in RULES.items():
        values: list[tuple[object, BIMElement]] = [
            (v, e) for e in bim.elements if select(e) and (v := get(e)) is not None
        ]
        if not values:
            continue
        if key == "door.main.width":  # main door = widest door in the model
            v, rep = max(values, key=lambda x: x[0])
            count, total = sum(1 for x, _ in values if x == v), len(values)
            conf = 0.9
        else:
            counts = Counter(v for v, _ in values)
            v, count = counts.most_common(1)[0]
            total = len(values)
            rep = next(e for x, e in values if x == v)
            conf = round(0.6 + 0.4 * count / total, 3)  # uniform model -> 1.0

        spec = BY_KEY[key]
        params.append(
            EngineeringParameter(
                key=key, label=spec.label, value=v, unit=spec.unit, raw_value=str(v),
                confidence=conf, extractor="ifc",
                source=SourceRef(
                    document_id=bim.document_id, document_name=bim.name,
                    document_type=DocumentType.BIM, kind=SourceKind.IFC,
                    element_id=rep.element_id,
                    snippet=f"{rep.element_type} '{rep.name}' on {rep.storey}; "
                            f"{count}/{total} elements share this value",
                ),
            )
        )
    return params
