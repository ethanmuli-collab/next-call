"""Ingest & clean tool (Crew 1): raw CRM export -> clean_data.csv."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from contract.spec import COLUMNS

SOURCE_MAP = {
    "facebook": "facebook_form", "facebook_form": "facebook_form", "fb lead ad": "facebook_form",
    "google ads": "google_ads", "google_ads": "google_ads", "google": "google_ads",
    "webinar": "webinar", "organic_site": "organic_site", "site": "organic_site", "organic": "organic_site",
    "referral": "referral", "friend": "referral",
}
REGION_MAP = {
    "tel aviv": "tel_aviv", "tel_aviv": "tel_aviv", "tlv": "tel_aviv", "center": "center", "merkaz": "center",
    "sharon": "sharon", "jerusalem": "jerusalem", "haifa_north": "haifa_north", "haifa": "haifa_north",
    "north": "haifa_north", "south": "south", "beer sheva": "south",
}
TARGET_MAP = {"yes": 1, "no": 0, "1": 1, "0": 0, "true": 1, "false": 0}


def _norm(s: pd.Series, mapping: dict[str, str]) -> pd.Series:
    low = s.astype("string").str.strip().str.lower()
    return low.map(lambda v: mapping.get(v, v) if pd.notna(v) else v)


def clean_leads(raw_path: Path, out_path: Path, feedback: dict[str, int] | None = None) -> dict:
    """Clean a raw export and write clean_data.csv. Returns a JSON-able cleaning log.

    Unknown columns are kept (and reported) instead of guessed - mapping a renamed
    column is a human decision, and the contract gate will flag it.
    """
    df = pd.read_csv(raw_path, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8")
    log: dict = {"input_file": Path(raw_path).name, "rows_in": int(len(df)), "steps": []}
    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in COLUMNS if c not in df.columns]
    extras = [c for c in df.columns if c not in COLUMNS]
    if missing:
        log["steps"].append(f"WARNING: expected columns missing from export: {missing}")
    if extras:
        log["steps"].append(f"WARNING: unknown columns kept as-is: {extras}")

    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].str.strip()

    if "lead_id" in df:
        before = len(df)
        df = df.drop_duplicates(subset="lead_id", keep="first")
        log["steps"].append(f"removed {before - len(df)} duplicate lead_id rows (double submissions)")
    if "created_at" in df:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        bad = int(df["created_at"].isna().sum())
        df = df[df["created_at"].notna()]
        log["steps"].append(f"parsed created_at; dropped {bad} unparseable rows")
    if "source" in df:
        df["source"] = _norm(df["source"], SOURCE_MAP)
        log["steps"].append("normalised source spellings (e.g. 'FB Lead Ad' -> facebook_form)")
    if "region" in df:
        df["region"] = _norm(df["region"], REGION_MAP)
        log["steps"].append("normalised region spellings (e.g. 'TLV' -> tel_aviv)")
    for col in ["course_interest", "age_band"]:
        if col in df:
            df[col] = df[col].astype("string").str.strip().str.lower()
    if "age_band" in df:
        n = int(df["age_band"].isna().sum())
        df["age_band"] = df["age_band"].fillna("unknown")
        log["steps"].append(f"filled {n} blank age_band values with 'unknown'")
    for col in ["webinar_attended", "n_contacts"]:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    if "pages_viewed" in df:
        pv = pd.to_numeric(df["pages_viewed"], errors="coerce")
        med = float(pv.median())
        log["steps"].append(f"imputed {int(pv.isna().sum())} missing pages_viewed with median {med:g}")
        df["pages_viewed"] = pv.fillna(med).round().astype(int)
    if "response_time_min" in df:
        rt = pd.to_numeric(df["response_time_min"], errors="coerce")
        neg = int((rt < 0).sum())
        df["response_time_min"] = rt.where(rt >= 0, np.nan)
        log["steps"].append(f"set {neg} negative response times (CRM glitch) to null")
    if "form_text" in df:
        df["form_text"] = df["form_text"].fillna("")
    if "converted" in df:
        df["converted"] = df["converted"].astype("string").str.lower().map(TARGET_MAP).astype("Float64")
        if feedback:
            hit = df["lead_id"].isin(feedback.keys()) & df["converted"].isna()
            df.loc[hit, "converted"] = df.loc[hit, "lead_id"].map(feedback).astype(float)
            log["steps"].append(f"applied {int(hit.sum())} rep-recorded outcomes from the feedback store")

    order = [c for c in COLUMNS if c in df.columns] + [c for c in df.columns if c not in COLUMNS]
    df = df[order].sort_values(["created_at", "lead_id"] if "created_at" in df else order[:1], kind="stable")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8", date_format="%Y-%m-%d %H:%M")
    log["rows_out"] = int(len(df))
    log["columns_out"] = list(df.columns)
    log["missing_columns"] = missing
    log["unknown_columns"] = extras
    return log


def clean_leads_json(raw_path: Path, out_path: Path, feedback: dict[str, int] | None = None) -> str:
    """Same as clean_leads but returns a JSON string (what a CrewAI tool hands to the LLM)."""
    return json.dumps(clean_leads(raw_path, out_path, feedback), ensure_ascii=False, indent=1)
