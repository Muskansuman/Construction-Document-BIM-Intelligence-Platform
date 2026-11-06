"""BuildDoc AI dashboard. Talks to the FastAPI backend only (no business logic here).

Run:  streamlit run frontend/streamlit_app.py
"""
from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

API = os.getenv("BUILDDOC_API_URL", "http://localhost:8000") + "/api/v1"
VERDICT_ICON = {"match": "✅", "within_tolerance": "🟡", "conflict": "❌", "missing": "⚠️"}

st.set_page_config(page_title="BuildDoc AI", page_icon="🏗️", layout="wide")
st.title("🏗️ BuildDoc AI")
st.caption("Construction drawing, specification and BIM consistency checker")

if "analysis" not in st.session_state:
    st.session_state.analysis = None


def api(method: str, path: str, **kw):
    r = requests.request(method, f"{API}{path}", timeout=300, **kw)
    if not r.ok:
        st.error(f"{r.status_code}: {r.text}")
        st.stop()
    return r


tab_docs, tab_extract, tab_consistency, tab_report = st.tabs(
    ["1 · Document Explorer", "2 · Extraction Results", "3 · Consistency Analysis", "4 · Review Report"]
)

# --------------------------------------------------------------------------- #
with tab_docs:
    files = st.file_uploader("Upload specification PDFs, drawings, BOQ (xlsx) and IFC models",
                             accept_multiple_files=True,
                             type=["pdf", "xlsx", "xls", "ifc", "dxf", "txt"])
    if files and st.button("Parse documents", type="primary"):
        for f in files:
            with st.spinner(f"Parsing {f.name}…"):
                api("POST", "/documents", files={"file": (f.name, f.getvalue())})
        st.success(f"Parsed {len(files)} file(s)")

    docs = api("GET", "/documents").json()
    if docs:
        st.dataframe(pd.DataFrame(docs), use_container_width=True, hide_index=True)
        project = st.text_input("Project name", "Demo building")
        chosen = st.multiselect("Documents to compare", [d["name"] for d in docs],
                                default=[d["name"] for d in docs])
        if st.button("Run consistency analysis", type="primary"):
            ids = [d["document_id"] for d in docs if d["name"] in chosen]
            st.session_state.analysis = api("POST", "/analyses",
                                            json={"document_ids": ids, "project_name": project}).json()
            st.success("Analysis complete. See tabs 2–4.")
    else:
        st.info("No documents yet. Upload files above.")

analysis = st.session_state.analysis

# --------------------------------------------------------------------------- #
with tab_extract:
    if not analysis:
        st.info("Run an analysis first.")
    else:
        rows = []
        for f in analysis["report"]["findings"]:
            for p in f["values"]:
                s = p["source"]
                rows.append({"parameter": p["label"], "value": p["value"], "unit": p["unit"],
                             "document": s["document_name"], "page": s["page"],
                             "bim_element": s["element_id"], "extractor": p["extractor"],
                             "confidence": p["confidence"], "evidence": s["snippet"]})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.subheader("Raw parsed content")
        doc_id = st.selectbox("Document", [d["document_id"] for d in docs],
                              format_func=lambda i: next(d["name"] for d in docs if d["document_id"] == i))
        st.json(api("GET", f"/documents/{doc_id}").json(), expanded=False)

# --------------------------------------------------------------------------- #
with tab_consistency:
    if not analysis:
        st.info("Run an analysis first.")
    else:
        s = analysis["summary"]
        c = st.columns(5)
        c[0].metric("Match", s["match"])
        c[1].metric("Within tolerance", s["within_tolerance"])
        c[2].metric("Conflict", s["conflict"])
        c[3].metric("Missing", s["missing"])
        c[4].metric("Needs review", s["needs_review"])

        table = []
        for f in analysis["report"]["findings"]:
            row = {"": VERDICT_ICON[f["verdict"]], "parameter": f["parameter_label"],
                   "severity": f["severity"], "confidence": f["confidence"], "rule": f["rule_applied"]}
            for p in f["values"]:
                unit = f" {p['unit']}" if p["unit"] else ""
                row[p["source"]["document_name"]] = f"{p['value']}{unit}"
            table.append(row)
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

# --------------------------------------------------------------------------- #
with tab_report:
    if not analysis:
        st.info("Run an analysis first.")
    else:
        aid = analysis["analysis_id"]
        for f in analysis["report"]["findings"]:
            with st.expander(f"{VERDICT_ICON[f['verdict']]} {f['parameter_label']} · {f['severity']} · "
                             f"{f['review_status']}", expanded=f["verdict"] == "conflict"):
                st.write(f["explanation"])
                for p in f["values"]:
                    src = p["source"]
                    where = src["element_id"] or f"page {src['page']}"
                    st.caption(f"📄 {src['document_name']} · {where} · “{src['snippet']}”")
                if f["review_status"] == "needs_review":
                    comment = st.text_input("Reviewer comment", key=f"c-{f['finding_id']}")
                    a, r = st.columns(2)
                    for col, status in ((a, "approved"), (r, "rejected")):
                        if col.button(status.title(), key=f"{status}-{f['finding_id']}"):
                            api("PATCH", f"/analyses/{aid}/findings/{f['finding_id']}",
                                json={"review_status": status, "comment": comment or None})
                            f["review_status"] = status
                            st.rerun()

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.download_button("⬇ JSON", api("GET", f"/analyses/{aid}/export", params={"fmt": "json"}).content,
                           file_name=f"{aid}.json")
        c2.download_button("⬇ Markdown", api("GET", f"/analyses/{aid}/export", params={"fmt": "md"}).content,
                           file_name=f"{aid}.md")
        c3.download_button("⬇ PDF", api("GET", f"/analyses/{aid}/export", params={"fmt": "pdf"}).content,
                           file_name=f"{aid}.pdf")
