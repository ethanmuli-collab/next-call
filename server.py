"""Next Call - the web app: Flask API + a plain HTML/CSS/JS front end (web/).

Run:  python server.py        ->  http://127.0.0.1:8000
The n8n endpoints of webhook.py (/health, /call-list, /run) are served by the same app.
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

import pandas as pd
from flask import jsonify, request, send_from_directory

from config import (ARTIFACTS_DIR, BROKEN_EXPORT, CLEAN_EXPORT, CREW1_FILES, CREW2_FILES, DATA_DIR, KAGGLE_EXPORT,
                    ROOT, is_offline, run_dir_for)
from feedback import OUTCOMES, clear_outcome, list_outcomes, record_outcome
from webhook import _run_dir, app

WEB_DIR = ROOT / "web"
UPLOAD_DIR = DATA_DIR / "uploads"
UNIT_COL = {"synthetic": "response_time_min", "kaggle": "time_on_site_sec"}
FILES = ({f: f"crew1/{f}" for f in CREW1_FILES} | {f: f"crew2/{f}" for f in CREW2_FILES}
         | {f: f for f in ("gate_report.json", "run_summary.json", "flow.log")})

app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024  # uploads
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

JOB: dict = {"state": "idle"}          # idle | running | done  (one Flow run at a time)
JOB_LOCK = threading.Lock()
ACTIVE = {"run": CLEAN_EXPORT.stem}    # the run whose call list the reps work today


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _json(p: Path) -> dict:
    return json.loads(_read(p)) if p.exists() else {}


def _profile(csv_path: Path) -> str:
    """Dataset profile of an uploaded file, from its header row."""
    with csv_path.open(encoding="utf-8-sig", errors="replace") as fh:
        return "kaggle" if "Prospect ID" in fh.readline() else "synthetic"


def _sources() -> dict[str, dict]:
    """Everything the Flow can run on: the sample exports, the Kaggle file if present, and uploads."""
    src = {"weekly": {"dataset": "synthetic", "path": CLEAN_EXPORT, "run_dir": run_dir_for(CLEAN_EXPORT)},
           "weekly_v2": {"dataset": "synthetic", "path": BROKEN_EXPORT, "run_dir": run_dir_for(BROKEN_EXPORT)}}
    if KAGGLE_EXPORT.exists():
        src["kaggle"] = {"dataset": "kaggle", "path": KAGGLE_EXPORT, "run_dir": ARTIFACTS_DIR / "kaggle_lead_scoring"}
    if UPLOAD_DIR.exists():
        for p in sorted(UPLOAD_DIR.glob("upload_*.csv")):
            src[p.stem] = {"dataset": _profile(p), "path": p, "run_dir": run_dir_for(p), "upload": True}
    return src


def _stages(rd: Path, summary: dict, running: bool) -> list[dict]:
    """State of the four pipeline stages: from flow.log while running, from run_summary.json afterwards."""
    if running:
        text = _read(rd / "flow.log")
        gate = "ok" if "Contract gate PASSED" in text else "fail" if "Contract gate FAILED" in text else None
        c1 = ("skip" if "[crew1] skipped" in text else "ok") if gate else "run"
        c2 = "blocked" if gate == "fail" else "wait" if not gate else \
            "ok" if "[crew2] artifact model_card.md" in text else "run"
        cl = "blocked" if gate == "fail" else "ok" if "[call-list]" in text else "run" if c2 == "ok" else "wait"
        return [{"key": "crew1", "state": c1}, {"key": "gate", "state": gate or "wait"},
                {"key": "crew2", "state": c2}, {"key": "list", "state": cl}]
    if not summary:
        return [{"key": k, "state": "wait"} for k in ("crew1", "gate", "crew2", "list")]
    arts, gate, ok = summary.get("artifacts", {}), summary.get("gate", {}), summary.get("status") == "ok"
    n1 = sum(arts.get(f"crew1/{f}", False) for f in CREW1_FILES)
    n2 = sum(arts.get(f"crew2/{f}", False) for f in CREW2_FILES)
    rows = summary.get("call_list_rows", 0)
    return [
        {"key": "crew1", "n": n1, "state": "skip" if summary.get("from_handoff") else "ok" if n1 == 4 else "fail"},
        {"key": "gate", "checks": gate.get("checks_run", 0), "problems": len(gate.get("errors", [])),
         "state": "blocked" if not gate else "ok" if gate.get("passed") else "fail"},
        {"key": "crew2", "n": n2, "model": summary.get("metrics", {}).get("selected_model", ""),
         "state": "ok" if n2 == 4 else "blocked" if not ok else "fail"},
        {"key": "list", "rows": rows, "state": "ok" if rows else "none" if ok else "blocked"},
    ]


def _detail(rd: Path, running: bool = False) -> dict:
    summary = {} if running else _json(rd / "run_summary.json")
    key = next((k for k, s in _sources().items() if s["run_dir"].name == rd.name), None)
    return {"name": rd.name, "source": key, "summary": summary, "stages": _stages(rd, summary, running),
            "files": {f: (rd / rel).exists() for f, rel in FILES.items()},
            "rows": _json(rd / "crew1" / "dataset_contract.json").get("row_count"),
            "can_break": bool(key) and (rd / "crew1" / "clean_data.csv").exists(),
            "log": _read(rd / "flow.log")[-8000:]}


def _start(key: str, retrain: bool = False, break_unit: bool = False):
    """Start one Flow run in a background thread; the front end polls /api/job."""
    src = _sources().get(key)
    if src is None:
        return jsonify(error="unknown source"), 404
    rd = src["run_dir"]
    if break_unit and not (rd / "crew1" / "clean_data.csv").exists():
        return jsonify(error="no clean data yet - run the flow on this file first"), 409
    with JOB_LOCK:
        if JOB["state"] == "running":
            return jsonify(error="a run is already in progress"), 409
        JOB.clear()
        JOB.update(state="running", source=key, run=rd.name, error=None)

    def work() -> None:
        try:
            from flow import run_pipeline

            if break_unit:  # the brief's scenario: same column name, different unit, in the handoff file
                clean, col = rd / "crew1" / "clean_data.csv", UNIT_COL[src["dataset"]]
                df = pd.read_csv(clean, encoding="utf-8")
                df[col] = df[col] / 60
                df.to_csv(clean, index=False, encoding="utf-8")
            state = run_pipeline(src["path"], use_feedback=retrain, from_handoff=break_unit, run_dir=rd,
                                 dataset=src["dataset"])
            if state["status"] == "ok" and state["call_list_rows"]:
                ACTIVE["run"] = rd.name
        except Exception as exc:  # reported to the UI through /api/job
            JOB["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            JOB["state"] = "done"

    (rd / "flow.log").unlink(missing_ok=True)
    threading.Thread(target=work, daemon=True).start()
    return jsonify(run=rd.name), 202


# ---------- pages ----------
@app.get("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/assets/<path:name>")
def assets(name: str):
    return send_from_directory(WEB_DIR, name)


# ---------- API ----------
@app.get("/api/overview")
def overview():
    sources = [{"key": k, "dataset": s["dataset"], "file": s["path"].name, "upload": s.get("upload", False),
                "status": _json(s["run_dir"] / "run_summary.json").get("status")} for k, s in _sources().items()]
    return jsonify(mode="offline" if is_offline() else "llm", sources=sources, job=JOB["state"], active=ACTIVE["run"])


@app.post("/api/run")
def api_run():
    body = request.get_json(silent=True) or {}
    return _start(str(body.get("source", "")), retrain=bool(body.get("retrain")))


@app.post("/api/break")
def api_break():
    body = request.get_json(silent=True) or {}
    return _start(str(body.get("source", "")), break_unit=True)


@app.get("/api/job")
def api_job():
    job = dict(JOB)
    if job["state"] != "idle":
        job["detail"] = _detail(ARTIFACTS_DIR / job["run"], running=job["state"] == "running")
    return jsonify(job)


@app.post("/api/upload")
def api_upload():
    f = request.files.get("file")
    if f is None or not (f.filename or "").lower().endswith(".csv"):
        return jsonify(error="a .csv file is required"), 400
    stem = re.sub(r"[^A-Za-z0-9_\-]+", "_", Path(f.filename).stem).strip("_")[:40] or "leads"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"upload_{stem}.csv"
    f.save(dest)
    return jsonify(key=dest.stem)


@app.get("/api/calls")
def api_calls():
    rd = ARTIFACTS_DIR / ACTIVE["run"]
    summary = _json(rd / "run_summary.json")
    leads = json.loads(_read(rd / "call_list.json") or "[]")
    done = {o["lead_id"]: o["outcome"] for o in list_outcomes()}
    for lead in leads:
        lead["outcome"] = done.get(lead["lead_id"])
    m = summary.get("metrics", {})
    res = m.get("results", {})
    return jsonify(run=rd.name, status=summary.get("status"), leads=leads, rows=_detail(rd)["rows"],
                   capture=res.get(m.get("selected_model"), {}).get("capture_at_20pct"),
                   baseline=res.get("baseline_arrival_order", {}).get("capture_at_20pct"),
                   checks=summary.get("gate", {}).get("checks_run"))


@app.post("/api/outcome")
def api_outcome():
    body = request.get_json(silent=True) or {}
    lead_id, outcome = str(body.get("lead_id", "")), str(body.get("outcome", ""))
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,32}", lead_id) or (outcome and outcome not in OUTCOMES):
        return jsonify(error="invalid lead or outcome"), 400
    record_outcome(lead_id, outcome) if outcome else clear_outcome(lead_id)  # empty outcome = undo
    return jsonify(ok=True)


@app.get("/api/runs")
def api_runs():
    names = sorted(p.name for p in ARTIFACTS_DIR.glob("*") if p.is_dir()) if ARTIFACTS_DIR.exists() else []
    return jsonify(runs=[{"name": n, "status": _json(ARTIFACTS_DIR / n / "run_summary.json").get("status")}
                         for n in names], active=ACTIVE["run"])


@app.get("/api/runs/<name>")
def api_run_detail(name: str):
    rd = _run_dir(name)
    return jsonify(_detail(rd)) if rd else (jsonify(error="unknown run"), 404)


@app.get("/api/runs/<name>/file/<fname>")
def api_run_file(name: str, fname: str):
    """One artifact of a run. Only the known artifact names are served."""
    rd, rel = _run_dir(name), FILES.get(fname)
    if rd is None or rel is None or not (rd / rel).exists():
        return jsonify(error="not found"), 404
    path = rd / rel
    if request.args.get("raw") or fname.endswith((".html", ".joblib")):
        return send_from_directory(rd, rel, as_attachment=bool(request.args.get("raw")) or fname.endswith(".joblib"))
    if fname.endswith(".csv"):
        df = pd.read_csv(path, encoding="utf-8", nrows=100)
        with path.open(encoding="utf-8") as fh:
            total = sum(1 for _ in fh) - 1
        return jsonify(kind="table", columns=list(df.columns), total=total,
                       rows=json.loads(df.to_json(orient="values", force_ascii=False)))
    return jsonify(kind="markdown" if fname.endswith(".md") else "text", text=_read(path))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("NEXT_CALL_PORT", "8000")), threaded=True)
