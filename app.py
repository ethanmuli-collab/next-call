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

from config import (ARTIFACTS_DIR, BROKEN_EXPORT, CLEAN_EXPORT, CREW1_FILES, CREW2_FILES, KAGGLE_EXPORT, is_offline,
                    run_dir_for)
from feedback import OUTCOMES, list_outcomes, record_outcome

st.set_page_config(page_title="Next Call", page_icon="📞", layout="wide")

# label -> (dataset profile, raw input, run folder, numeric column the "break it" button rescales)
INPUTS = {
    "Synthetic CRM - weekly export (normal)":
        ("synthetic", CLEAN_EXPORT, run_dir_for(CLEAN_EXPORT), "response_time_min"),
    "Synthetic CRM - weekly export v2 (broken: renamed column + minutes → seconds)":
        ("synthetic", BROKEN_EXPORT, run_dir_for(BROKEN_EXPORT), "response_time_min"),
}
if KAGGLE_EXPORT.exists():
    INPUTS["Kaggle - Lead Scoring Dataset (real data, 9,240 leads)"] = (
        "kaggle", KAGGLE_EXPORT, ARTIFACTS_DIR / "kaggle_lead_scoring", "time_on_site_sec")

CSS = """
<style>
.block-container{padding-top:2.2rem;max-width:1200px}
.nc-hero{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;
  background:linear-gradient(135deg,#12224b 0%,#1f4fd8 100%);color:#fff;border-radius:16px;padding:22px 26px;margin-bottom:18px}
.nc-hero h1{margin:0;font-size:1.9rem;line-height:1.15;color:#fff;padding:0}
.nc-hero p{margin:6px 0 0;color:#dbe6ff;font-size:.98rem;max-width:720px}
.nc-badge{white-space:nowrap;padding:6px 14px;border-radius:999px;font-weight:700;font-size:.82rem}
.nc-badge.llm{background:#d7f5e3;color:#0b6b3a}.nc-badge.off{background:#fff1c9;color:#7a5200}
.nc-steps{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:4px 0 18px}
.nc-step{background:#fff;border:1px solid #dde5f0;border-top:4px solid #c4cedd;border-radius:12px;padding:14px 16px;position:relative}
.nc-step .k{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#6b7890;font-weight:700}
.nc-step .t{font-size:1.05rem;font-weight:700;color:#16202e;margin:2px 0 8px}
.nc-step .d{font-size:.85rem;color:#43516b;margin-top:8px;min-height:1.2em}
.nc-step.ok{border-top-color:#0f9d58}.nc-step.fail{border-top-color:#d64545;background:#fff7f7}
.nc-step.blocked{opacity:.62}.nc-step.skip{border-top-color:#c98a00}
.nc-pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.75rem;font-weight:700}
.nc-pill.ok{background:#d7f5e3;color:#0b6b3a}.nc-pill.fail{background:#fde0e0;color:#a32020}
.nc-pill.idle{background:#eef1f6;color:#5a6679}.nc-pill.blocked{background:#eef1f6;color:#5a6679}
.nc-pill.skip{background:#fff1c9;color:#7a5200}
.nc-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:6px 0 18px}
.nc-kpi{background:#fff;border:1px solid #dde5f0;border-radius:12px;padding:14px 16px}
.nc-kpi .l{font-size:.78rem;color:#6b7890;font-weight:600}
.nc-kpi .v{font-size:1.7rem;font-weight:800;color:#12224b;line-height:1.2}
.nc-kpi .s{font-size:.8rem;color:#43516b}
.nc-banner{border-radius:12px;padding:14px 18px;margin:6px 0 14px;font-weight:600}
.nc-banner.ok{background:#e6f7ee;border:1px solid #9ad9b6;color:#0b6b3a}
.nc-banner.fail{background:#fdecec;border:1px solid #f0a9a9;color:#8f1d1d}
.nc-banner small{display:block;font-weight:400;margin-top:2px}
.nc-err{background:#fff;border:1px solid #f0c2c2;border-left:5px solid #d64545;border-radius:10px;padding:12px 16px;margin:8px 0}
.nc-err.warn{border-color:#ecd9a6;border-left-color:#c98a00}
.nc-err .h{display:flex;gap:8px;align-items:center;margin-bottom:4px;font-weight:700;color:#16202e}
.nc-err code{background:#f2f5fa;padding:1px 6px;border-radius:5px;font-size:.85em}
.nc-err .m{color:#43516b;font-size:.92rem}
.nc-files{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:4px 0 14px}
.nc-file{background:#fff;border:1px solid #dde5f0;border-radius:10px;padding:8px 12px;font-size:.85rem;
  display:flex;justify-content:space-between;gap:8px;font-family:Consolas,Menlo,monospace}
.nc-file.miss{color:#9aa5b8;background:#f6f8fb}
.nc-lead{display:grid;grid-template-columns:54px 1fr 110px;gap:14px;align-items:start}
.nc-rank{width:46px;height:46px;border-radius:12px;background:#12224b;color:#fff;font-weight:800;
  display:grid;place-items:center;font-size:1.05rem}
.nc-lead .n{font-weight:700;font-size:1.05rem;color:#16202e}
.nc-lead .meta{font-size:.82rem;color:#6b7890;margin:2px 0 8px}
.nc-open{direction:rtl;text-align:right;background:#f3f6fc;border-radius:10px;padding:10px 14px;font-size:1rem;line-height:1.55}
.nc-open .f{color:#6b7890;font-size:.85rem;margin-top:6px}
.nc-why{font-size:.82rem;color:#43516b;margin-top:8px}
.nc-p{text-align:right}.nc-p .v{font-size:1.5rem;font-weight:800;color:#1f4fd8;line-height:1}
.nc-p .l{font-size:.72rem;color:#6b7890}
.nc-bar{height:6px;border-radius:4px;background:#e3e9f3;margin-top:8px;overflow:hidden}
.nc-bar i{display:block;height:100%;background:#1f4fd8}
.nc-done{display:inline-block;margin-left:8px;padding:1px 9px;border-radius:999px;background:#d7f5e3;color:#0b6b3a;font-size:.75rem;font-weight:700}
@media (max-width:800px){.nc-steps,.nc-kpis,.nc-files{grid-template-columns:repeat(2,1fr)}.nc-hero{flex-direction:column}
  .nc-lead{grid-template-columns:46px 1fr}.nc-p{grid-column:2;text-align:left}}
</style>
"""

PILL_TEXT = {"ok": "done", "fail": "failed", "idle": "not run", "blocked": "not started", "skip": "skipped"}
esc = html.escape


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _summary(run_dir: Path) -> dict:
    return _json(run_dir / "run_summary.json")


def _steps(summary: dict) -> list[tuple[str, str, str, str]]:
    """(kicker, title, state, detail) for the four pipeline stages, derived from run_summary.json."""
    if not summary:
        return [("Crew 1", "Data Analyst", "idle", "clean → EDA → contract"),
                ("Validation", "Contract gate", "idle", "data vs. contract"),
                ("Crew 2", "Data Scientist", "idle", "features → models → model card"),
                ("Output", "Call list", "idle", "ranked leads + openers")]
    arts, gate, status = summary.get("artifacts", {}), summary.get("gate", {}), summary.get("status")
    n1 = sum(arts.get(f"crew1/{f}", False) for f in CREW1_FILES)
    n2 = sum(arts.get(f"crew2/{f}", False) for f in CREW2_FILES)
    crew1 = ("skip", "handoff re-validated, crew not re-run") if summary.get("from_handoff") else \
            ("ok" if n1 == 4 else "fail", f"{n1}/4 artifacts")
    if not gate:
        gate_s = ("blocked", "not reached")
    elif gate.get("passed"):
        gate_s = ("ok", f"{gate.get('checks_run', 0)} checks passed")
    else:
        gate_s = ("fail", f"{len(gate.get('errors', []))} problem(s) found")
    down = "blocked" if status != "ok" and n2 < 4 else ("ok" if n2 == 4 else "fail")
    model = summary.get("metrics", {}).get("selected_model", "").replace("_", " ")
    crew2 = (down, f"{n2}/4 artifacts" + (f" · {model}" if model else "") if down != "blocked" else "no model was trained")
    calls = ("ok", f"{summary.get('call_list_rows', 0)} leads ranked") if summary.get("call_list_rows") else \
            ("blocked" if status != "ok" else "idle", "no call list")
    return [("Crew 1", "Data Analyst", *crew1), ("Validation", "Contract gate", *gate_s),
            ("Crew 2", "Data Scientist", *crew2), ("Output", "Call list", *calls)]


def _stepper(summary: dict) -> str:
    cards = "".join(
        f"<div class='nc-step {s}'><div class='k'>{esc(k)}</div><div class='t'>{esc(t)}</div>"
        f"<span class='nc-pill {s}'>{PILL_TEXT[s]}</span><div class='d'>{esc(d)}</div></div>"
        for k, t, s, d in _steps(summary))
    return f"<div class='nc-steps'>{cards}</div>"


def _kpis(items: list[tuple[str, str, str]]) -> str:
    return "<div class='nc-kpis'>" + "".join(
        f"<div class='nc-kpi'><div class='l'>{esc(l)}</div><div class='v'>{esc(v)}</div><div class='s'>{esc(s)}</div></div>"
        for l, v, s in items) + "</div>"


def _issue(e: dict, warn: bool = False) -> str:
    col = f"<code>{esc(str(e['column']))}</code>" if e.get("column") else ""
    return (f"<div class='nc-err{' warn' if warn else ''}'><div class='h'>"
            f"<span class='nc-pill {'skip' if warn else 'fail'}'>{esc(e.get('check', ''))}</span>{col}</div>"
            f"<div class='m'>{esc(e.get('message', ''))}</div></div>")


def _result(summary: dict, run_dir: Path) -> None:
    """Outcome of the last run: banner, KPIs and model comparison, or the gate's findings."""
    if not summary:
        st.info("No run yet for this input. Press **Run the Flow**.")
        return
    gate = summary.get("gate", {})
    if summary["status"] == "ok":
        st.markdown(f"<div class='nc-banner ok'>Contract gate passed<small>{esc(summary['message'])}</small></div>",
                    unsafe_allow_html=True)
        m = summary.get("metrics", {})
        res, sel = m.get("results", {}), m.get("selected_model", "")
        best, base = res.get(sel, {}), res.get("baseline_arrival_order", {})
        rows = _json(run_dir / "crew1" / "dataset_contract.json").get("row_count")
        st.markdown(_kpis([
            ("Leads in clean data", f"{rows:,}" if rows else "-", "published by Crew 1"),
            ("Gate checks", str(gate.get("checks_run", "-")), "all passed before modeling"),
            ("ROC-AUC (holdout)", f"{best.get('roc_auc', 0):.3f}", f"{sel.replace('_', ' ')} · PR-AUC {best.get('pr_auc', 0):.3f}"),
            ("Enrolments in top 20%", f"{best.get('capture_at_20pct', 0):.0%}",
             f"vs {base.get('capture_at_20pct', 0):.0%} calling in arrival order"),
        ]), unsafe_allow_html=True)
        if res:
            table = pd.DataFrame(res).T.rename_axis("model").reset_index()
            table["model"] = table["model"].str.replace("_", " ") + table["model"].map(lambda x: "  ★" if x == sel else "")
            cols = [c for c in ["model", "roc_auc", "pr_auc", "capture_at_20pct", "lift_at_top10pct", "brier"] if c in table]
            st.markdown(f"##### Model comparison ({'stratified' if m.get('split', {}).get('policy') else 'time-based'} holdout)")
            st.dataframe(table[cols], hide_index=True, width="stretch", column_config={
                "roc_auc": st.column_config.NumberColumn("ROC-AUC", format="%.3f"),
                "pr_auc": st.column_config.NumberColumn("PR-AUC", format="%.3f"),
                "capture_at_20pct": st.column_config.ProgressColumn("Enrolments in top 20%", min_value=0, max_value=1,
                                                                    format="percent"),
                "lift_at_top10pct": st.column_config.NumberColumn("Lift @ top 10%", format="%.2f"),
                "brier": st.column_config.NumberColumn("Brier", format="%.3f")})
            st.caption("★ selected model. The baseline calls leads in arrival order, as the team does today.")
        if not summary.get("call_list_rows"):
            st.info("No call list for this dataset: every lead already has an outcome. "
                    "The daily call list comes from the synthetic CRM profile.")
    elif summary["status"] == "gate_failed":
        errs, warns = gate.get("errors", []), gate.get("warnings", [])
        st.markdown(f"<div class='nc-banner fail'>The contract gate stopped the Flow - {len(errs)} problem(s)"
                    "<small>Crew 2 was not started: no features, no model, no call list. "
                    "Fix the data or publish a new contract version, then run again.</small></div>",
                    unsafe_allow_html=True)
        st.markdown("".join(_issue(e) for e in errs) + "".join(_issue(w, warn=True) for w in warns),
                    unsafe_allow_html=True)
    else:
        st.error(summary.get("message", "Run failed"))
    modes = summary.get("narratives", {})
    if modes:
        st.caption("Text written by: " + " · ".join(f"{k} = {v}" for k, v in modes.items())
                   + ". Numbers always come from the deterministic tools.")


def _run_flow(input_path: Path, run_dir: Path, **kwargs) -> None:
    """Run the Flow in a thread and stream flow.log while it works."""
    from flow import run_pipeline

    log_path = run_dir / "flow.log"
    log_path.unlink(missing_ok=True)
    holder: dict = {}

    def _work() -> None:
        try:
            holder["state"] = run_pipeline(input_path, **kwargs)
        except Exception as exc:  # surfaced below, never swallowed
            holder["error"] = f"{type(exc).__name__}: {exc}"

    th = threading.Thread(target=_work, daemon=True)
    th.start()
    box = st.empty()
    with st.spinner("Flow running..."):
        while th.is_alive():
            box.code(_read(log_path)[-6000:] or "starting...", language=None)
            time.sleep(0.5)
    box.empty()
    if "error" in holder:
        st.error(holder["error"])


# ---------- header ----------
offline = is_offline()
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(
    "<div class='nc-hero'><div><h1>📞 Next Call</h1>"
    "<p>Who should the admissions rep call first today, and what to say. Two CrewAI crews with a "
    "machine-enforced data contract between them: if the handoff is wrong, the Flow stops before a model is trained.</p></div>"
    f"<span class='nc-badge {'off' if offline else 'llm'}'>{'OFFLINE mode (no LLM)' if offline else 'LLM mode'}</span></div>",
    unsafe_allow_html=True)

tab_run, tab_art, tab_calls = st.tabs(["Run pipeline", "Artifacts", "Today's call list"])

# ---------- tab 1: run ----------
with tab_run:
    steps_slot = st.empty()
    with st.container(border=True):
        choice = st.radio("Dataset and input", list(INPUTS))
        dataset, input_path, run_dir, unit_col = INPUTS[choice]
        c1, c2 = st.columns(2)
        use_fb = c1.checkbox("Retrain with outcomes recorded by reps", value=False,
                             help="Final outcomes (enrolled / not interested) become training labels.")
        from_handoff = c2.checkbox("Skip Crew 1 - re-validate the existing clean_data.csv",
                                   help="Edit artifacts/<input>/crew1/clean_data.csv by hand (e.g. change a unit), "
                                        "then run with this on: the gate must refuse to train.")
        b1, b2 = st.columns([1, 2])
        run_clicked = b1.button("▶ Run the Flow", type="primary", width="stretch")
        clean_csv = run_dir / "crew1" / "clean_data.csv"
        break_clicked = b2.button(f"🧪 Break it on purpose: change the unit of {unit_col} in clean_data.csv",
                                  disabled=not clean_csv.exists(), width="stretch",
                                  help="The brief's Monday-morning scenario: the values are divided by 60 "
                                       "(minutes → hours, or seconds → minutes), same column name, "
                                       "then the Flow re-validates the handoff. "
                                       "Run the Flow normally afterwards to restore the clean data.")
    if break_clicked:
        df = pd.read_csv(clean_csv, encoding="utf-8")
        df[unit_col] = df[unit_col] / 60  # minutes -> hours / seconds -> minutes, same column name
        df.to_csv(clean_csv, index=False, encoding="utf-8")
        _run_flow(input_path, run_dir, from_handoff=True, dataset=dataset)
    elif run_clicked:
        _run_flow(input_path, run_dir, use_feedback=use_fb, from_handoff=from_handoff, dataset=dataset)
    summary = _summary(run_dir)
    steps_slot.markdown(_stepper(summary), unsafe_allow_html=True)
    _result(summary, run_dir)
    log_text = _read(run_dir / "flow.log")
    if log_text:
        with st.expander("Flow log of the last run"):
            st.code(log_text, language=None)

# ---------- tab 2: artifacts ----------
with tab_art:
    runs = sorted(p.name for p in ARTIFACTS_DIR.glob("*") if p.is_dir()) if ARTIFACTS_DIR.exists() else []
    if not runs:
        st.info("No artifacts yet - run the Flow first.")
    else:
        rname = st.selectbox("Run", runs, index=runs.index(CLEAN_EXPORT.stem) if CLEAN_EXPORT.stem in runs else 0)
        rd = ARTIFACTS_DIR / rname
        files = {f: rd / "crew1" / f for f in CREW1_FILES} | {f: rd / "crew2" / f for f in CREW2_FILES}
        for title, names in (("Crew 1 - Data Analyst", CREW1_FILES), ("Crew 2 - Data Scientist", CREW2_FILES)):
            st.markdown(f"##### {title}")
            st.markdown("<div class='nc-files'>" + "".join(
                f"<div class='nc-file{'' if files[f].exists() else ' miss'}'><span>{esc(f)}</span>"
                f"<span>{'✓' if files[f].exists() else '✗'}</span></div>" for f in names) + "</div>",
                unsafe_allow_html=True)
        files |= {f: rd / f for f in ("gate_report.json", "run_summary.json", "flow.log")}
        a = st.selectbox("Open artifact", list(files))
        path = files[a]
        if not path.exists():
            st.warning(f"{a} was not produced in this run (the gate stopped the Flow before this step).")
        else:
            if a.endswith(".csv"):
                df = pd.read_csv(path, encoding="utf-8")
                st.caption(f"{len(df):,} rows × {df.shape[1]} columns (showing the first 200)")
                st.dataframe(df.head(200), hide_index=True, width="stretch")
            elif a.endswith(".html"):
                components.html(_read(path), height=900, scrolling=True)
            elif a.endswith(".json"):
                st.json(json.loads(_read(path)), expanded=2)
            elif a.endswith(".md"):
                with st.container(border=True):
                    st.markdown(_read(path))
            elif a.endswith(".log"):
                st.code(_read(path), language=None)
            else:
                sel = _summary(rd).get("metrics", {}).get("selected_model", "?")
                st.info(f"Binary scikit-learn pipeline ({path.stat().st_size / 1024:.0f} KB). Selected model: **{sel}**. "
                        "Load it with `joblib.load`.")
            st.download_button(f"Download {a}", path.read_bytes(), file_name=a)

# ---------- tab 3: call list ----------
with tab_calls:
    rd = run_dir_for(CLEAN_EXPORT)
    cl_path = rd / "call_list.json"
    if not cl_path.exists():
        st.info("No call list yet - run the Flow on the normal weekly export. "
                "(If the gate stopped the last run, there is intentionally no list.)")
    else:
        calls = pd.DataFrame(json.loads(_read(cl_path)))
        done = {o["lead_id"]: o["outcome"] for o in list_outcomes()}
        calls["outcome"] = calls["lead_id"].map(done).fillna("")
        st.markdown(_kpis([
            ("Leads to call today", str(len(calls)), "open leads, ranked"),
            ("Average P(enroll)", f"{calls['p_enroll'].mean():.0%}", "of the leads on this list"),
            ("Newest lead", f"{calls['age_hours'].min():.1f}h old", "hot leads go cold in 48 hours"),
            ("Outcomes recorded", f"{(calls['outcome'] != '').sum()}/{len(calls)}", "feed the next retraining"),
        ]), unsafe_allow_html=True)
        st.caption("Priority = P(enroll) × recency decay (half-life 48h). Reasons are rule-based and auditable.")
        for _, r in calls.iterrows():
            with st.container(border=True):
                tag = f"<span class='nc-done'>✔ {esc(r['outcome'])}</span>" if r["outcome"] else ""
                st.markdown(
                    f"<div class='nc-lead'><div class='nc-rank'>{r['rank']}</div><div>"
                    f"<div class='n'>{esc(r['first_name'])}{tag}</div>"
                    f"<div class='meta'>{esc(r['lead_id'])} · {esc(str(r['course_interest']).replace('_', ' '))} · "
                    f"{esc(str(r['source']).replace('_', ' '))} · {r['age_hours']:.0f}h old</div>"
                    f"<div class='nc-open'><b>{esc(r['opening_line']).replace(chr(10), '<br>')}</b>"
                    f"<div class='f'>מה כתב/ה בטופס: {esc(r['form_text'] or '-')}</div></div>"
                    f"<div class='nc-why'>Why now: {esc(r['reasons'])}</div></div>"
                    f"<div class='nc-p'><div class='v'>{r['p_enroll']:.0%}</div><div class='l'>P(enroll)</div>"
                    f"<div class='nc-bar'><i style='width:{r['p_enroll'] * 100:.0f}%'></i></div></div></div>",
                    unsafe_allow_html=True)
                with st.expander("Record the call outcome"):
                    with st.form(f"f_{r['lead_id']}", border=False):
                        f1, f2 = st.columns([1, 2])
                        oc = f1.selectbox("Outcome", list(OUTCOMES), key=f"o_{r['lead_id']}")
                        note = f2.text_input("Note", key=f"n_{r['lead_id']}")
                        if st.form_submit_button("Save outcome"):
                            record_outcome(r["lead_id"], oc, note)
                            st.success("Saved - it will be used at the next retraining.")
        outs = list_outcomes()
        if outs:
            st.markdown("#### Recorded outcomes (feedback store)")
            st.dataframe(pd.DataFrame(outs), hide_index=True, width="stretch")
