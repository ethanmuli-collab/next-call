"""Ingest & clean tool (Crew 1) for the Kaggle Lead Scoring dataset: raw CSV -> clean_data.csv."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from contract.spec_kaggle import COLUMNS, LEAD_SOURCES

RENAME = {
    "Lead Number": "lead_id", "Lead Origin": "lead_origin", "Lead Source": "lead_source",
    "Do Not Email": "do_not_email", "TotalVisits": "total_visits",
    "Total Time Spent on Website": "time_on_site_sec", "Page Views Per Visit": "pages_per_visit",
    "Specialization": "specialization", "What is your current occupation": "occupation", "City": "city",
    "A free copy of Mastering The Interview": "free_copy_requested", "Converted": "converted",
}
YES_NO = {"yes": 1, "no": 0}


def _slug(s: pd.Series) -> pd.Series:
    """'Thane & Outskirts' -> 'thane_outskirts'. Blanks stay null."""
    return s.astype("string").str.strip().str.lower().map(
        lambda v: re.sub(r"[^a-z0-9]+", "_", v).strip("_") if pd.notna(v) else v)


def clean_kaggle(raw_path: Path, out_path: Path, feedback: dict | None = None) -> dict:
    """Clean the raw Kaggle export and write clean_data.csv. Returns a JSON-able cleaning log.

    Expected source columns that are missing are reported, never guessed: the contract gate will flag them.
    """
    raw = pd.read_csv(raw_path, encoding="utf-8")
    log: dict = {"input_file": Path(raw_path).name, "rows_in": int(len(raw)), "steps": []}
    raw.columns = [c.strip() for c in raw.columns]
    missing_src = [c for c in RENAME if c not in raw.columns]
    if missing_src:
        log["steps"].append(f"WARNING: expected columns missing from export: {missing_src}")
    dropped = [c for c in raw.columns if c not in RENAME]
    df = raw[[c for c in RENAME if c in raw.columns]].rename(columns=RENAME)
    log["steps"].append(f"kept {df.shape[1]} of {raw.shape[1]} columns; dropped {len(dropped)} "
                        "(sales-entered leakage columns, constants, mostly-blank columns - see the contract)")

    if "lead_id" in df:
        before = len(df)
        df["lead_id"] = df["lead_id"].astype(str)
        df = df.drop_duplicates(subset="lead_id", keep="first")
        log["steps"].append(f"removed {before - len(df)} duplicate lead_id rows")
    for col, blank in [("specialization", "not_selected"), ("city", "not_selected"), ("occupation", "unknown"),
                       ("lead_source", "unknown"), ("lead_origin", None)]:
        if col not in df:
            continue
        s = _slug(df[col])
        n_select = int((s == "select").sum())
        s = s.mask(s == "select")
        if col == "lead_source":
            rare = s.notna() & ~s.isin(LEAD_SOURCES)
            log["steps"].append(f"lead_source: grouped {int(rare.sum())} rows from rare sources into 'other'")
            s = s.mask(rare, "other")
        if blank:
            log["steps"].append(f"{col}: {n_select} 'Select' (form default) and {int(s.isna().sum()) - n_select} "
                                f"blank values set to '{blank}'")
            s = s.fillna(blank)
        df[col] = s
    for col in ["do_not_email", "free_copy_requested"]:
        if col in df:
            df[col] = df[col].astype("string").str.strip().str.lower().map(YES_NO).astype("Int64")
    for col, as_int in [("total_visits", True), ("pages_per_visit", False)]:
        if col in df:
            num = pd.to_numeric(df[col], errors="coerce")
            med = float(num.median())
            log["steps"].append(f"imputed {int(num.isna().sum())} missing {col} with median {med:g}")
            df[col] = num.fillna(med).round().astype(int) if as_int else num.fillna(med).round(2)
    if "time_on_site_sec" in df:
        df["time_on_site_sec"] = pd.to_numeric(df["time_on_site_sec"], errors="coerce").astype("Int64")
    if "converted" in df:
        df["converted"] = pd.to_numeric(df["converted"], errors="coerce").astype("Int64")

    df = df[[c for c in COLUMNS if c in df.columns]].sort_values("lead_id", kind="stable")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8")
    log["rows_out"] = int(len(df))
    log["columns_out"] = list(df.columns)
    log["missing_columns"] = [c for c in COLUMNS if c not in df.columns]
    log["unknown_columns"] = []
    return log
