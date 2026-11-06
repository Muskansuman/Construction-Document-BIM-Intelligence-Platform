from pathlib import Path

import pytest

from app.extraction.schemas import BIMElement, BIMModel

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def spec_path() -> Path:
    return FIXTURES / "structural_spec.txt"


@pytest.fixture
def bim_model() -> BIMModel:
    """Synthetic BIM model with deliberate conflicts (M30 vs M25, 900 vs 1000 door)."""
    ext = {"Pset_WallCommon.IsExternal": True}
    intl = {"Pset_WallCommon.IsExternal": False}
    return BIMModel(
        document_id="bim001",
        name="block_a.ifc",
        storeys=["Ground Floor", "First Floor"],
        elements=[
            BIMElement(element_id="2J$kEW1", element_type="IfcWall", name="External Wall A",
                       storey="Ground Floor", material="Concrete M30", thickness_mm=200, height_mm=3000,
                       properties=ext),
            BIMElement(element_id="2J$kEW2", element_type="IfcWall", name="External Wall B",
                       storey="Ground Floor", material="Concrete M30", thickness_mm=200, height_mm=3000,
                       properties=ext),
            BIMElement(element_id="2J$kIW1", element_type="IfcWall", name="Partition 1",
                       storey="Ground Floor", material="Block", thickness_mm=100, properties=intl),
            BIMElement(element_id="3S$lab1", element_type="IfcSlab", name="Floor Slab GF",
                       storey="Ground Floor", material="Concrete M30", thickness_mm=150),
            BIMElement(element_id="4D$oor1", element_type="IfcDoor", name="Main Entrance",
                       storey="Ground Floor", width_mm=900, height_mm=2100),
            BIMElement(element_id="4D$oor2", element_type="IfcDoor", name="Bedroom Door",
                       storey="First Floor", width_mm=800, height_mm=2100),
        ],
    )
