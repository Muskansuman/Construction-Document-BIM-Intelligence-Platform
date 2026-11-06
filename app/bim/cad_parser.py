"""DXF (CAD) parsing with ezdxf.

Scope is deliberately small: read text annotations and dimension entities,
which is where drawings state sizes like "WALL 230 THK" or a 1000 mm door.
Output is a ParsedDocument, so the same rule extractor can read it.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from app.extraction.schemas import DocumentType, ParsedDocument, SourceKind, TextBlock

log = logging.getLogger(__name__)


def parse_dxf(path: Path, document_id: str | None = None) -> ParsedDocument:
    import ezdxf

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    blocks: list[TextBlock] = []

    for e in msp.query("TEXT MTEXT"):
        text = e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text
        if text and text.strip():
            blocks.append(TextBlock(page=1, text=f"[{e.dxf.layer}] {text.strip()}", source=SourceKind.DXF))

    for d in msp.query("DIMENSION"):
        try:
            measurement = d.get_measurement()
            value = measurement if isinstance(measurement, (int, float)) else abs(measurement)
            label = d.dxf.text if d.dxf.text not in ("", "<>") else f"{value:.0f}"
            blocks.append(TextBlock(page=1, text=f"[{d.dxf.layer}] DIM {label}", source=SourceKind.DXF))
        except Exception:  # some dimension types lack measurement support
            continue

    log.info("Parsed %s: %d text/dimension entities", path.name, len(blocks))
    return ParsedDocument(
        document_id=document_id or uuid.uuid4().hex[:12],
        name=path.name,
        doc_type=DocumentType.CAD,
        page_count=1,
        text_blocks=blocks,
    )
