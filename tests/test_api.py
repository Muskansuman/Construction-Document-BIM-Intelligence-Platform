from fastapi.testclient import TestClient

from app.core.store import store
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_upload_analyse_review_export(spec_path, bim_model):
    with spec_path.open("rb") as fh:
        r = client.post("/api/v1/documents", files={"file": ("structural_spec.txt", fh)},
                        data={"doc_type": "specification"})
    assert r.status_code == 200
    spec_id = r.json()["document_id"]
    store.add_document(bim_model)  # IFC parsing needs ifcopenshell; inject a parsed model

    r = client.post("/api/v1/analyses", json={"document_ids": [spec_id, "bim001"], "project_name": "t"})
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["conflict"] >= 2

    aid = body["analysis_id"]
    fid = next(f["finding_id"] for f in body["report"]["findings"] if f["verdict"] == "conflict")
    r = client.patch(f"/api/v1/analyses/{aid}/findings/{fid}",
                     json={"review_status": "approved", "comment": "BIM model is outdated"})
    assert r.json()["review_status"] == "approved"

    md = client.get(f"/api/v1/analyses/{aid}/export", params={"fmt": "md"})
    assert "Concrete grade" in md.text


def test_rejects_unknown_type():
    r = client.post("/api/v1/documents", files={"file": ("x.exe", b"abc")})
    assert r.status_code == 415
