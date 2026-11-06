# data/

Input files go here. Contents are git-ignored; only the folder layout is committed.

| Folder | What to put in it | Parsed by |
|---|---|---|
| `drawings/` | Architectural / structural drawing PDFs | PyMuPDF + PaddleOCR |
| `specifications/` | Structural specification PDFs (scanned is fine) | PyMuPDF + PaddleOCR + pdfplumber |
| `boq/` | Bill of Quantities, PDF or Excel | pdfplumber / pandas |
| `bim_models/` | IFC models (`make sample` downloads one) | IfcOpenShell |
| `cad/` | DXF drawings | ezdxf |

Good public sources for demo data:
- IFC models: buildingSMART Sample-Test-Files on GitHub, or the Open IFC Model Repository.
- To create a *scanned* spec, print `tests/fixtures/structural_spec.txt` to PDF and rasterise it
  (e.g. `pdftoppm` → `img2pdf`). Change a value or two so the demo shows conflicts.
