"""In-memory store for documents and analyses.

Deliberately simple for the 4-day scope. The interface is small, so it can
be swapped for SQLite/Postgres later without touching the API routes.
"""
from __future__ import annotations

import threading
import uuid

from app.extraction.schemas import BIMModel, ParsedDocument, ReviewReport


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.documents: dict[str, ParsedDocument | BIMModel] = {}
        self.reports: dict[str, ReviewReport] = {}

    def add_document(self, doc: ParsedDocument | BIMModel) -> str:
        with self._lock:
            self.documents[doc.document_id] = doc
        return doc.document_id

    def add_report(self, report: ReviewReport) -> str:
        rid = "R-" + uuid.uuid4().hex[:8]
        with self._lock:
            self.reports[rid] = report
        return rid


store = Store()
