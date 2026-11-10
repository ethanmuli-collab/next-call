"""Outcome store: reps mark call outcomes in the app; enrol/not-interested become training labels."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from config import OUTCOMES_DB

OUTCOMES = {"enrolled": 1, "not_interested": 0, "no_answer": None, "call_back": None}


def _conn(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE IF NOT EXISTS outcomes (
        lead_id TEXT PRIMARY KEY, outcome TEXT NOT NULL, note TEXT, marked_at TEXT NOT NULL)""")
    return con


def record_outcome(lead_id: str, outcome: str, note: str = "", db: Path = OUTCOMES_DB) -> None:
    """Upsert the latest outcome for a lead (parameterised SQL)."""
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome '{outcome}'; expected one of {list(OUTCOMES)}")
    with closing(_conn(db)) as con, con:
        con.execute("INSERT INTO outcomes VALUES (?,?,?,?) ON CONFLICT(lead_id) DO UPDATE SET "
                    "outcome=excluded.outcome, note=excluded.note, marked_at=excluded.marked_at",
                    (lead_id, outcome, note[:500], datetime.now().isoformat(timespec="seconds")))


def clear_outcome(lead_id: str, db: Path = OUTCOMES_DB) -> None:
    """Undo a mark made by mistake."""
    with closing(_conn(db)) as con, con:
        con.execute("DELETE FROM outcomes WHERE lead_id = ?", (lead_id,))


def list_outcomes(db: Path = OUTCOMES_DB) -> list[dict]:
    if not db.exists():
        return []
    with closing(_conn(db)) as con:
        rows = con.execute("SELECT lead_id, outcome, note, marked_at FROM outcomes ORDER BY marked_at").fetchall()
    return [dict(zip(["lead_id", "outcome", "note", "marked_at"], r)) for r in rows]


def training_labels(db: Path = OUTCOMES_DB) -> dict[str, int]:
    """lead_id -> 0/1 for final outcomes only (used by the cleaning step when retraining)."""
    return {r["lead_id"]: OUTCOMES[r["outcome"]] for r in list_outcomes(db) if OUTCOMES[r["outcome"]] is not None}
