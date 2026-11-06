from app.extraction.bim_adapter import bim_to_parameters
from app.extraction.rule_extractor import extract_parameters
from app.extraction.schemas import DocumentType
from app.ocr.pdf_parser import parse_document


def test_rule_extractor_reads_spec(spec_path):
    doc = parse_document(spec_path, DocumentType.SPECIFICATION, "spec001")
    params = {p.key: p for p in extract_parameters(doc)}

    assert params["concrete.grade"].value == "M25"
    assert params["rebar.grade"].value == "Fe500D"
    assert params["wall.external.thickness"].value == 200
    assert params["wall.internal.thickness"].value == 100
    assert params["slab.thickness"].value == 150
    assert params["door.main.width"].value == 1000
    assert params["storey.height"].value == 3000
    # every value is traceable
    assert all(p.source.page == 1 and p.source.snippet for p in params.values())


def test_bim_adapter(bim_model):
    params = {p.key: p for p in bim_to_parameters(bim_model)}
    assert params["concrete.grade"].value == "M30"
    assert params["door.main.width"].value == 900       # widest door = main door
    assert params["wall.external.thickness"].value == 200
    assert params["wall.external.thickness"].source.element_id.startswith("2J$k")
    assert params["wall.external.thickness"].confidence == 1.0   # uniform model
