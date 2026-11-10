"""Flask endpoint for n8n: GET /call-list returns today's ranked call list.

Run:  python webhook.py            (http://127.0.0.1:5055)
"""
from __future__ import annotations

import json
import os
import re

from flask import Flask, jsonify, request

from config import ARTIFACTS_DIR, CLEAN_EXPORT

app = Flask(__name__)
DEFAULT_DATASET = CLEAN_EXPORT.stem


def _run_dir(name: str):
    """Only plain names of existing run folders under artifacts/ are accepted (no path tricks)."""
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", name):
        return None
    d = ARTIFACTS_DIR / name
    return d if d.is_dir() else None


def _as_text(rows: list[dict]) -> str:
    lines = [f"*Next Call - today's top {len(rows)} leads*"]
    for r in rows:
        opener = r["opening_line"].replace("\n", " / ")
        lines.append(f"{r['rank']}. {r['first_name']} ({r['lead_id']}) - {r['course_interest']}, "
                     f"p={r['p_enroll']:.0%}, {r['age_hours']:.0f}h old - {r['reasons']}\n    > {opener}")
    return "\n".join(lines)


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/call-list")
def call_list():
    run_dir = _run_dir(request.args.get("dataset", DEFAULT_DATASET))
    if run_dir is None:
        return jsonify(error="unknown dataset"), 404
    try:
        top = int(request.args.get("top", 20))
    except ValueError:
        return jsonify(error="top must be an integer"), 400
    top = max(1, min(top, 100))
    summary_path, list_path = run_dir / "run_summary.json", run_dir / "call_list.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    if summary.get("status") not in (None, "ok"):
        return jsonify(error="last pipeline run did not finish", status=summary.get("status"),
                       message=summary.get("message", "")), 409
    if not list_path.exists():
        return jsonify(error="no call list yet - run the flow first (python flow.py)"), 404
    rows = json.loads(list_path.read_text(encoding="utf-8"))[:top]
    if request.args.get("format") == "text":
        return jsonify(text=_as_text(rows), count=len(rows))
    return jsonify(dataset=run_dir.name, count=len(rows), leads=rows,
                   model=summary.get("metrics", {}).get("selected_model"))


@app.post("/run")
def run():
    """Re-run the whole Flow on the normal weekly export (n8n calls this before /call-list)."""
    token = os.getenv("WEBHOOK_TOKEN")
    if token and request.headers.get("X-Token") != token:
        return jsonify(error="unauthorized"), 401
    from flow import run_pipeline

    state = run_pipeline(CLEAN_EXPORT, use_feedback=True)
    code = 200 if state["status"] == "ok" else 409
    return jsonify(status=state["status"], message=state["message"]), code


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("WEBHOOK_PORT", "5055")))
