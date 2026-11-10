"""Score open leads and build today's call list (probability x recency decay)."""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from config import HALF_LIFE_HOURS
from tools.contract_tools import load_contract
from tools.eda import load_clean
from tools.features import build_feature_frame

DECAY_FLOOR = 0.1  # an old lead never drops fully off the list


def _reasons(row: pd.Series, f: pd.Series) -> str:
    """Up to three plain-language reasons a rep can trust."""
    r: list[str] = []
    if row["age_hours"] < 24:
        r.append(f"new lead ({row['age_hours']:.0f}h old)")
    if f.get("txt_asks_start", 0):
        r.append("asked when the next cohort starts")
    if f.get("webinar_attended", 0):
        r.append("attended a webinar")
    if row.get("source") == "referral":
        r.append("referred by a friend")
    if row.get("pages_viewed", 0) >= 6:
        r.append(f"viewed {int(row['pages_viewed'])} pages")
    if f.get("txt_asks_price", 0) or f.get("txt_financing", 0):
        r.append("asked about price/financing")
    if f.get("awaiting_first_call", 0):
        r.append("nobody has called yet")
    if f.get("txt_just_browsing", 0):
        r.append("said 'just browsing' - keep it short")
    return "; ".join(r[:3]) or "baseline fit"


def build_call_list(clean_path: Path, contract_path: Path, model_path: Path, top_n: int) -> pd.DataFrame:
    """Rank open leads by p(enroll) x 0.5^(age/48h); return the top_n rows."""
    contract = load_contract(contract_path)
    bundle = joblib.load(model_path)
    df = load_clean(clean_path)
    open_df = df[df["converted"].isna()].copy()
    if open_df.empty:
        return pd.DataFrame()
    X = build_feature_frame(open_df, contract)[bundle["feature_columns"]]
    open_df["p_enroll"] = bundle["model"].predict_proba(X)[:, 1]
    as_of = pd.Timestamp(contract["as_of"])
    open_df["age_hours"] = ((as_of - open_df["created_at"]).dt.total_seconds() / 3600).clip(lower=0)
    open_df["recency"] = np.maximum(0.5 ** (open_df["age_hours"] / HALF_LIFE_HOURS), DECAY_FLOOR)
    open_df["priority"] = open_df["p_enroll"] * open_df["recency"]
    open_df["reasons"] = [_reasons(open_df.loc[i], X.loc[i]) for i in open_df.index]
    top = open_df.sort_values(["priority", "lead_id"], ascending=[False, True], kind="stable").head(top_n)
    top.insert(0, "rank", range(1, len(top) + 1))
    keep = ["rank", "lead_id", "first_name", "course_interest", "source", "created_at", "age_hours",
            "p_enroll", "recency", "priority", "reasons", "form_text", "n_contacts"]
    out = top[keep].reset_index(drop=True)
    out["created_at"] = out["created_at"].dt.strftime("%Y-%m-%d %H:%M")
    for c in ["age_hours", "p_enroll", "recency", "priority"]:
        out[c] = out[c].round(4 if c != "age_hours" else 1)
    return out
