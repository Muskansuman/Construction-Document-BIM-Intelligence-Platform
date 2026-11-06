"""IFC (BIM) parsing with IfcOpenShell.

Reads building elements, their storey, material, quantity sets (Qto_*) and
property sets (Pset_*), normalising every length to millimetres.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from app.extraction.schemas import BIMElement, BIMModel

log = logging.getLogger(__name__)

ELEMENT_TYPES = ["IfcWall", "IfcSlab", "IfcBeam", "IfcColumn", "IfcDoor", "IfcWindow"]

# Quantity-set key -> BIMElement field, per IFC class.
QTO_MAP: dict[str, dict[str, str]] = {
    "IfcWall":   {"Width": "thickness_mm", "Height": "height_mm", "Length": "length_mm",
                  "NetSideArea": "area_m2", "NetVolume": "volume_m3"},
    "IfcSlab":   {"Depth": "thickness_mm", "Width": "width_mm", "Length": "length_mm",
                  "NetArea": "area_m2", "NetVolume": "volume_m3"},
    "IfcBeam":   {"Length": "length_mm", "NetVolume": "volume_m3"},
    "IfcColumn": {"Length": "height_mm", "NetVolume": "volume_m3"},
    "IfcDoor":   {"Width": "width_mm", "Height": "height_mm", "Area": "area_m2"},
    "IfcWindow": {"Width": "width_mm", "Height": "height_mm", "Area": "area_m2"},
}
LENGTH_FIELDS = {"thickness_mm", "height_mm", "width_mm", "length_mm"}


def _material_name(element) -> str | None:
    import ifcopenshell.util.element as eu

    mat = eu.get_material(element)
    if mat is None:
        return None
    if mat.is_a("IfcMaterial"):
        return mat.Name
    if mat.is_a("IfcMaterialLayerSetUsage"):
        layers = mat.ForLayerSet.MaterialLayers
    elif mat.is_a("IfcMaterialLayerSet"):
        layers = mat.MaterialLayers
    else:
        return getattr(mat, "Name", None)
    # Use the thickest layer as the "structural" material.
    main = max(layers, key=lambda layer: layer.LayerThickness or 0)
    return main.Material.Name if main.Material else None


def _storey(element) -> str | None:
    import ifcopenshell.util.element as eu

    c = eu.get_container(element)
    while c is not None and not c.is_a("IfcBuildingStorey"):
        c = eu.get_aggregate(c)
    return c.Name if c is not None else None


def _to_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_ifc(path: Path, document_id: str | None = None) -> BIMModel:
    import ifcopenshell
    import ifcopenshell.util.element as eu
    import ifcopenshell.util.unit as uu

    model = ifcopenshell.open(str(path))
    to_mm = uu.calculate_unit_scale(model) * 1000.0   # project length unit -> mm

    bim = BIMModel(
        document_id=document_id or uuid.uuid4().hex[:12],
        name=path.name,
        schema_version=model.schema,
        storeys=[s.Name for s in model.by_type("IfcBuildingStorey")],
    )

    for ifc_type in ELEMENT_TYPES:
        for el in model.by_type(ifc_type):
            psets = eu.get_psets(el)  # includes Qto_* quantity sets
            elem = BIMElement(
                element_id=el.GlobalId,
                element_type=el.is_a(),
                name=el.Name,
                storey=_storey(el),
                material=_material_name(el),
            )
            for pset_name, props in psets.items():
                if pset_name.startswith("Qto_"):
                    for q_key, field in QTO_MAP.get(ifc_type, {}).items():
                        val = _to_float(props.get(q_key))
                        if val is not None and getattr(elem, field) is None:
                            setattr(elem, field, round(val * to_mm, 1) if field in LENGTH_FIELDS else val)
                else:
                    for k, v in props.items():
                        if k != "id" and isinstance(v, (str, int, float, bool)):
                            elem.properties[f"{pset_name}.{k}"] = v

            # Doors/windows often store size as direct attributes.
            if ifc_type in ("IfcDoor", "IfcWindow"):
                if elem.width_mm is None and _to_float(getattr(el, "OverallWidth", None)):
                    elem.width_mm = round(float(el.OverallWidth) * to_mm, 1)
                if elem.height_mm is None and _to_float(getattr(el, "OverallHeight", None)):
                    elem.height_mm = round(float(el.OverallHeight) * to_mm, 1)

            bim.elements.append(elem)

    log.info("Parsed %s: %d elements, %d storeys", path.name, len(bim.elements), len(bim.storeys))
    return bim
