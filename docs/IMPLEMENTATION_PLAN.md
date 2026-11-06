# Implementation plan (4 days)

The scaffold already contains working versions of every module plus a passing test suite
on synthetic data. The plan below is about replacing synthetic inputs with real documents,
hardening each stage, and producing the demo.

Tick boxes as you go; they render as checklists on GitHub.

## Day 1: OCR and PDF extraction
**Deliverable:** real PDFs (one native, one scanned) → `ParsedDocument` JSON

- [ ] `make install`, confirm PaddleOCR downloads its models
- [ ] Create a scanned spec PDF (see `data/README.md`) with 2 deliberate conflicts
- [ ] Run `python -m app.pipeline.orchestrator data/specifications/spec_scanned.pdf`
- [ ] Inspect OCR blocks: are confidences sensible? tune `OCR_DPI` (200–300)
- [ ] Test `pdfplumber` on a BOQ PDF; check header detection
- [ ] Add `tests/test_pdf_parser.py` with a tiny native PDF fixture
- [ ] Commit: `feat(ocr): pdf + scanned page pipeline`

## Day 2: BIM and CAD parsing
**Deliverable:** public IFC model → `BIMModel` JSON with walls, slabs, doors, materials

- [ ] `make sample` (or pick a richer model from buildingSMART Sample-Test-Files)
- [ ] Check which `Qto_*` / `Pset_*` the model actually has; extend `QTO_MAP` if needed
- [ ] Verify unit handling on a metre-based model (values must come out in mm)
- [ ] If the model lacks concrete grade, add it to materials in a copy and document that
- [ ] Optional: one DXF with text annotations through `cad_parser`
- [ ] Add a small IFC fixture + `tests/test_ifc_parser.py` (skip if ifcopenshell missing)
- [ ] Commit: `feat(bim): ifc element + quantity extraction`

## Day 3: Extraction and validation
**Deliverable:** spec vs IFC report reproducing the brief's conflict table

- [ ] Run the full pipeline on real spec + IFC; read every finding
- [ ] Tune `catalog.py` keyword groups / ranges for phrases that were missed
- [ ] Optional: start Ollama with `qwen2.5:7b-instruct`, set `BUILDDOC_LLM_PROVIDER=openai`,
      compare recall with and without LLM; note how many LLM proposals were dropped by quote check
- [ ] Write 2–3 more validation tests from real cases
- [ ] Commit: `feat(validation): evidence-backed findings`

## Day 4: API, demo, Docker
**Deliverable:** `docker compose up` → dashboard at :8501

- [ ] Walk through all four Streamlit tabs; approve/reject a finding
- [ ] Export JSON / MD / PDF; put a sample report in `docs/sample_report.md`
- [ ] Screenshots / GIF into `docs/images/` and the README
- [ ] `docker compose up --build` from a clean clone
- [ ] Final README pass: only claim what works
- [ ] Tag `v0.1.0`

## Interview talking points
1. **Why deterministic validation?** Reproducibility, auditability, no hallucinated "match".
2. **How do you stop the LLM hallucinating values?** Catalogue-only keys + verbatim quote must
   exist on the cited page + same normalisers as the rule path.
3. **OCR vs IFC** OCR recovers text from pixels with uncertainty; IFC gives typed objects
   with GlobalIds. The system uses confidence to treat them differently.
4. **Units** All lengths normalised to mm at the edges (IFC unit scale, text units).
5. **Scaling up** Element-level matching via door/wall marks, RAG over spec clauses,
   persistent review store.
