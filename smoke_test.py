"""End-to-end smoke test, offline and with outbound network blocked.

(a) normal export  -> all 8 artifacts + call list
(b) broken v2      -> gate stops before Crew 2 with a readable message
(c) determinism    -> a second run reproduces the same files byte for byte
(d) edited handoff -> a unit changed by hand in clean_data.csv is refused
(e) Flask endpoint -> /health and /call-list respond
Run:  python smoke_test.py
"""
from __future__ import annotations

import hashlib
import os
import socket
import sys
import tempfile
from pathlib import Path

os.environ.pop("OPENAI_API_KEY", None)
os.environ["NEXT_CALL_OFFLINE"] = "1"

_real_connect = socket.socket.connect


def _no_network(self, address):  # allow only loopback
    host = address[0] if isinstance(address, tuple) else str(address)
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ConnectionError(f"smoke test blocks outbound network (tried {address})")
    return _real_connect(self, address)


socket.socket.connect = _no_network

import pandas as pd  # noqa: E402

from config import BROKEN_EXPORT, CLEAN_EXPORT, CREW1_FILES, CREW2_FILES, run_dir_for  # noqa: E402
from flow import run_pipeline  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def check(cond: bool, msg: str) -> None:
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        sys.exit(1)


def main() -> None:
    print("\n[a] full Flow on the normal weekly export")
    s = run_pipeline(CLEAN_EXPORT, offline=True)
    rd = run_dir_for(CLEAN_EXPORT)
    check(s["status"] == "ok", f"status ok ({s['message']})")
    for f in CREW1_FILES:
        check((rd / "crew1" / f).exists(), f"crew1/{f}")
    for f in CREW2_FILES:
        check((rd / "crew2" / f).exists(), f"crew2/{f}")
    cl = pd.read_json(rd / "call_list.json")
    check(len(cl) > 0 and cl["opening_line"].str.len().min() > 10, f"call list has {len(cl)} leads with openers")
    m = s["metrics"]
    print(f"  selected model: {m['selected_model']}  split: {m['split']}")
    for name, r in m["results"].items():
        print(f"  {name:24s} {r}")
    print("  top 3 calls:")
    for r in cl.head(3).itertuples():
        print(f"    #{r.rank} {r.lead_id} {r.course_interest:14s} p={r.p_enroll:.2f} prio={r.priority:.3f} | {r.reasons}")

    print("\n[b] broken export v2 (renamed column + minutes->seconds)")
    b = run_pipeline(BROKEN_EXPORT, offline=True)
    brd = run_dir_for(BROKEN_EXPORT)
    check(b["status"] == "gate_failed", "gate stopped the Flow")
    check(not any((brd / "crew2" / f).exists() for f in CREW2_FILES), "no Crew 2 artifacts were produced")
    check(not (brd / "call_list.json").exists(), "no call list was produced")
    check("course_interest" in b["message"] and "program_interest" in b["message"], "message names the renamed column")
    check("seconds" in b["message"], "message names the unit change (minutes -> seconds)")
    print("  gate message:\n" + "\n".join("    " + line for line in b["message"].splitlines()))

    with tempfile.TemporaryDirectory() as tmp:
        print("\n[c] determinism: rerun into a temp folder and compare files")
        t = run_pipeline(CLEAN_EXPORT, offline=True, run_dir=Path(tmp))
        check(t["status"] == "ok", "second run ok")
        for f in ["crew1/clean_data.csv", "crew2/features.csv", "crew2/evaluation_report.md", "call_list.json"]:
            check(sha(rd / f) == sha(Path(tmp) / f), f"{f} identical ({sha(rd / f)})")

        print("\n[d] someone changes a unit in clean_data.csv by hand, then re-runs from the handoff")
        clean = Path(tmp) / "crew1" / "clean_data.csv"
        df = pd.read_csv(clean, encoding="utf-8")
        df["response_time_min"] = df["response_time_min"] / 60  # minutes -> hours, same column name
        df.to_csv(clean, index=False, encoding="utf-8")
        h = run_pipeline(CLEAN_EXPORT, offline=True, run_dir=Path(tmp), from_handoff=True)
        check(h["status"] == "gate_failed" and "hours" in h["message"], "gate refuses to train (unit -> hours)")

    print("\n[e] Flask endpoint")
    from webhook import app

    c = app.test_client()
    check(c.get("/health").get_json() == {"status": "ok"}, "/health ok")
    r = c.get("/call-list?top=5")
    check(r.status_code == 200 and r.get_json()["count"] == 5, "/call-list?top=5 returns 5 leads")
    check("Next Call" in c.get("/call-list?top=3&format=text").get_json()["text"], "/call-list?format=text")
    check(c.get(f"/call-list?dataset={BROKEN_EXPORT.stem}").status_code == 409, "broken run -> 409 with message")
    check(c.get("/call-list?dataset=..%2F..%2Fetc").status_code == 404, "path tricks rejected")
    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    main()
