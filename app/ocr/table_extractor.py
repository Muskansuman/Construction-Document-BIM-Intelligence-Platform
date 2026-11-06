"""Table extraction: pdfplumber for PDFs, pandas for Excel BOQs."""
from __future__ import annotations

import logging
from pathlib import Path

from app.extraction.schemas import Table

log = logging.getLogger(__name__)


def _clean(cell) -> str | None:
    if cell is None:
        return None
    s = str(cell).replace("\n", " ").strip()
    return s or None


def extract_pdf_tables(path: Path) -> list[Table]:
    import pdfplumber

    tables: list[Table] = []
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            for raw in page.extract_tables():
                if not raw or len(raw) < 2:
                    continue
                header = [_clean(c) or f"col_{i}" for i, c in enumerate(raw[0])]
                rows = [[_clean(c) for c in r] for r in raw[1:]]
                tables.append(Table(page=page_no, index=len(tables), header=header, rows=rows))
    log.info("pdfplumber found %d tables in %s", len(tables), path.name)
    return tables


def extract_excel_tables(path: Path) -> list[Table]:
    import pandas as pd

    tables: list[Table] = []
    for sheet, df in pd.read_excel(path, sheet_name=None).items():
        df = df.dropna(how="all")
        tables.append(
            Table(
                page=None,
                index=len(tables),
                header=[str(c) for c in df.columns],
                rows=[[_clean(v) for v in r] for r in df.astype(object).values.tolist()],
            )
        )
        log.info("Sheet %s: %d rows", sheet, len(df))
    return tables
