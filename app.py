"""Next Call - Streamlit UI: run the Flow, inspect artifacts, work today's call list.

Run:  streamlit run app.py
"""
from __future__ import annotations

import html
import json
import threading
import time
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from config import ARTIFACTS_DIR, BROKEN_EXPORT, CLEAN_EXPORT, is_offline, run_dir_for
from feedback import OUTCOMES, list_outcomes, record_outcome

st.set_page_config(page_title="Next Call", page_icon="📞", layout="wide")

INPUTS = {
    "Weekly export (normal)": CLEAN_EXPORT,
    "Weekly export v2 (broken: renamed column + minutes->seconds)": BROKEN_EXPORT,
}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _summary(run_dir: Path) -> dict:
    p = run_dir / "run_summary.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _status_box(summary: dict) -> None:
    if not summary:
        st.info("No run yet for this input. Press **Run the Flow**.")
    elif summary["status"] == "ok":
        st.success(f"Gate PASSED - {summary['message']}")
    elif summary["status"] == "gate_failed":
        st.error("The contract gate stopped the Flow before Crew 2 (modeling).")
        st.code(summary["message"], language=None)
        errs = summary.get("gate", {}).get("errors", [])
        if errs:
            st.dataframe(pd.DataFrame(errs), hide_index=True, width="stretch")
    else:
        st.error(summary.get("message", "Run failed"))


# ---------- header ----------
offline = is_offline()
left, right = st.columns([4, 1])
left.title("📞 Next Call")
left.caption("Who should the admissions rep call first today - and what to say. "
             "CrewAI Flow: Analyst crew -> contract gate -> Data-science crew -> call list.")
right.markdown(f"<div style='text-align:right;margin-top:28px'><span style='padding:4px 10px;border-radius:12px;"
               f"background:{'#fff3cd' if offline else '#d1f2d9'};color:#222;font-weight:600'>"
               f"{'OFFLINE mode (no LLM)' if offline else 'LLM mode'}</span></div>", unsafe_allow_html=True)

tab_run, tab_art, tab_calls = st.tabs(["1 - Run pipeline", "2 - Artifacts", "3 - Today's call list"])

# ---------- tab 1: run ----------
with tab_run:
    choice = st.radio("Input export", list(INPUTS), horizontal=False)
    input_path = INPUTS[choice]
    run_dir = run_dir_for(input_path)
    c1, c2 = st.columns(2)
    use_fb = c1.checkbox("Retrain with outcomes recorded by reps", value=False,
                         help="Final outcomes (enrolled / not interested) become training labels.")
    from_handoff = c2.checkbox("Skip Crew 1 - re-validate the existing clean_data.csv",
                               help="Edit artifacts/<input>/crew1/clean_data.csv by hand (e.g. change a unit), "
                                    "then run with this on: the gate must refuse to train.")
    if st.button("▶ Run the Flow", type="primary"):
        from flow import run_pipeline

        log_path = run_dir / "flow.log"
        log_path.unlink(missing_ok=True)
        holder: dict = {}

        def _work() -> None:
            try:
                holder["state"] = run_pipeline(input_path, use_feedback=use_fb, from_handoff=from_handoff)
            except Exception as exc:  # surfaced below, never swallowed
                holder["error"] = f"{type(exc).__name__}: {exc}"

        th = threading.Thread(target=_work, daemon=True)
        th.start()
        box = st.empty()
        with st.spinner("Flow running..."):
            while th.is_alive():
                box.code(_read(log_path)[-6000:] or "starting...", language=None)
                time.sleep(0.5)
        box.code(_read(log_path)[-12000:], language=None)
        if "error" in holder:
            st.error(holder["error"])
    else:
        log_text = _read(run_dir / "flow.log")
        if log_text:
            with st.expander("Log of the last run", expanded=False):
                st.code(log_text, language=None)
    _status_box(_summary(run_dir))

# ---------- tab 2: artifacts ----------
with tab_art:
    runs = sorted(p.name for p in ARTIFACTS_DIR.glob("*") if p.is_dir()) if ARTIFACTS_DIR.exists() else []
    if not runs:
        st.info("No artifacts yet - run the Flow first.")
    else:
        rname = st.selectbox("Run", runs, index=runs.index(CLEAN_EXPORT.stem) if CLEAN_EXPORT.stem in runs else 0)
        rd = ARTIFACTS_DIR / rname
        summ = _summary(rd)
        st.caption(f"Status: **{summ.get('status', '?')}** · artifacts: "
                   + ", ".join(f"{k} {'✓' if v else '✗'}" for k, v in summ.get("artifacts", {}).items()))
        a = st.radio("Artifact", ["insights.md", "eda_report.html", "dataset_contract.json", "gate_report.json",
                                  "evaluation_report.md", "model_card.md"], horizontal=True)
        where = {"evaluation_report.md": "crew2", "model_card.md": "crew2", "gate_report.json": ""}.get(a, "crew1")
        path = rd / where / a if where else rd / a
        if not path.exists():
            st.warning(f"{a} was not produced in this run (did the gate stop the Flow?).")
        elif a.endswith(".html"):
            components.html(_read(path), height=900, scrolling=True)
        elif a.endswith(".json"):
            st.json(json.loads(_read(path)), expanded=2)
        else:
            st.markdown(_read(path))
        if path.exists():
            st.download_button(f"Download {a}", path.read_bytes(), file_name=a)

# ---------- tab 3: call list ----------
with tab_calls:
    rd = run_dir_for(CLEAN_EXPORT)
    cl_path = rd / "call_list.json"
    if not cl_path.exists():
        st.info("No call list yet - run the Flow on the normal weekly export.")
    else:
        calls = pd.DataFrame(json.loads(_read(cl_path)))
        done = {o["lead_id"]: o["outcome"] for o in list_outcomes()}
        calls["outcome"] = calls["lead_id"].map(done).fillna("")
        st.subheader(f"Today's call list - {len(calls)} leads")
        st.caption("Ranked by P(enroll) x recency decay (half-life 48h). Reasons are rule-based and auditable.")
        st.dataframe(calls[["rank", "first_name", "lead_id", "course_interest", "source", "age_hours", "p_enroll",
                            "priority", "reasons", "outcome"]],
                     hide_index=True, width="stretch",
                     column_config={"p_enroll": st.column_config.ProgressColumn("P(enroll)", min_value=0, max_value=1,
                                                                                format="%.2f"),
                                    "priority": st.column_config.NumberColumn(format="%.3f")})
        st.markdown("#### Openers and outcomes")
        for _, r in calls.iterrows():
            tag = f" · ✔ {r['outcome']}" if r["outcome"] else ""
            with st.expander(f"#{r['rank']}  {r['first_name']} ({r['lead_id']}) - {r['course_interest']} - "
                             f"p={r['p_enroll']:.0%}{tag}"):
                st.markdown(f"<div dir='rtl' style='font-size:1.05rem'><b>{html.escape(r['opening_line']).replace(chr(10), '<br>')}</b>"
                            f"<br><span style='color:#666'>מה כתב/ה בטופס: {html.escape(r['form_text'] or '-')}</span></div>",
                            unsafe_allow_html=True)
                st.caption(f"Why now: {r['reasons']}")
                with st.form(f"f_{r['lead_id']}"):
                    oc = st.selectbox("Outcome", list(OUTCOMES), key=f"o_{r['lead_id']}")
                    note = st.text_input("Note", key=f"n_{r['lead_id']}")
                    if st.form_submit_button("Save outcome"):
                        record_outcome(r["lead_id"], oc, note)
                        st.success("Saved - it will be used at the next retraining.")
        outs = list_outcomes()
        if outs:
            st.markdown("#### Recorded outcomes (feedback store)")
            st.dataframe(pd.DataFrame(outs), hide_index=True, width="stretch")
