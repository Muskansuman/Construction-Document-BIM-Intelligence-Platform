"""PaddleOCR wrapper. Imported lazily so the rest of the app runs without it."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from app.extraction.schemas import BBox, SourceKind, TextBlock

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_ocr(lang: str):
    from paddleocr import PaddleOCR  # heavy import, only when OCR is needed

    log.info("Loading PaddleOCR (lang=%s)", lang)
    return PaddleOCR(use_angle_cls=True, lang=lang)


def ocr_image(image: np.ndarray, page: int, lang: str = "en") -> list[TextBlock]:
    """Run OCR on one rendered page image and return text blocks with boxes."""
    result = _get_ocr(lang).ocr(image, cls=True)
    blocks: list[TextBlock] = []
    for line in (result[0] or []) if result else []:
        box, (text, score) = line
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        blocks.append(
            TextBlock(
                page=page,
                text=text,
                bbox=BBox(x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys)),
                confidence=float(score),
                source=SourceKind.OCR,
            )
        )
    return blocks
