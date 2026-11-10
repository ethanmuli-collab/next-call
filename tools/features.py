"""Feature engineering tool (Crew 2). Reads ONLY clean_data.csv + dataset_contract.json."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tools.contract_tools import load_contract
from tools.eda import load_clean

# Intent cues in the Hebrew form text (word stems, deliberately simple and explainable).
TEXT_FLAGS = {
    "txt_asks_start": r"מתי|מחזור|נפתח",
    "txt_asks_price": r"מחיר|עולה|תשלומים",
    "txt_financing": r"מימון|הנחה",
    "txt_career_change": r"הסבה",
    "txt_evening": r"ערב",
    "txt_just_browsing": r"רק בודק|סתם|בלי שיחה",
}
ID_COLS = ["lead_id", "created_at", "converted"]


def build_feature_frame(df: pd.DataFrame, contract: dict) -> pd.DataFrame:
    """Turn contract-described clean columns into a numeric feature table."""
    cols = contract["columns"]
    feats = contract["model_features"]
    out = pd.DataFrame(index=df.index)
    for name in feats:
        spec = cols[name]
        if spec["dtype"] == "category":
            for val in spec["allowed"]:  # fixed column set from the contract -> deterministic
                out[f"{name}={val}"] = (df[name].astype(str) == val).astype(int)
        elif spec["dtype"] == "binary":
            out[name] = df[name].astype(int)
        elif name == "response_time_min":
            rt = df[name]
            out["awaiting_first_call"] = rt.isna().astype(int)
            filled = rt.fillna(spec.get("reference_median", rt.median()))
            out["response_hours_log"] = np.log1p(filled.clip(spec["min"], spec["max"]) / 60.0)
        elif spec["dtype"] in {"int", "float"}:
            out[name] = df[name].clip(spec.get("min"), spec.get("max"))
        elif spec["dtype"] == "datetime":
            ts = df[name]
            out["created_hour"] = ts.dt.hour
            out["created_weekend"] = ts.dt.dayofweek.isin([4, 5]).astype(int)  # Fri/Sat
            out["created_office_hours"] = ts.dt.hour.between(9, 18).astype(int)
        elif spec["dtype"] == "text":
            text = df[name].fillna("").astype(str)
            for flag, pattern in TEXT_FLAGS.items():
                out[flag] = text.str.contains(pattern, regex=True).astype(int)
            out["txt_len_log"] = np.log1p(text.str.len())
            out["txt_empty"] = (text.str.strip() == "").astype(int)
    return out


def engineer_features(clean_path: Path, contract_path: Path, out_csv: Path) -> dict:
    """Write features.csv (ids + target + features) and return a summary."""
    contract = load_contract(contract_path)
    df = load_clean(clean_path)
    X = build_feature_frame(df, contract)
    full = pd.concat([df[ID_COLS].reset_index(drop=True), X.reset_index(drop=True)], axis=1)
    full.to_csv(out_csv, index=False, encoding="utf-8", date_format="%Y-%m-%d %H:%M")
    return {"rows": int(len(full)), "n_features": int(X.shape[1]),
            "feature_columns": list(X.columns),
            "labelled_rows": int(df["converted"].notna().sum()),
            "open_rows": int(df["converted"].isna().sum()),
            "text_flags": list(TEXT_FLAGS)}


def feature_columns(features: pd.DataFrame) -> list[str]:
    return [c for c in features.columns if c not in ID_COLS]
