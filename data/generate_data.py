"""Generate a realistic synthetic lead export (seeded, deterministic).

Writes two files into data/raw/:
- leads_weekly_export.csv     the normal weekly CRM export (messy, like real life)
- leads_weekly_export_v2.csv  the "break it on purpose" export: `course_interest`
  renamed to `program_interest`, and `response_time_min` silently switched
  from minutes to seconds (same column name, values x60).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import BROKEN_EXPORT, CLEAN_EXPORT, RAW_DIR, SEED  # noqa: E402

N_LEADS = 5000
START = pd.Timestamp("2025-10-27")
END = pd.Timestamp("2026-10-25 22:00")
OPEN_DAYS = 10  # leads younger than this have no outcome yet

SOURCES = {  # canonical -> (share, effect, messy spellings)
    "facebook_form": (0.38, -0.35, ["Facebook", "facebook_form", "FB Lead Ad", "facebook "]),
    "google_ads": (0.24, 0.20, ["Google Ads", "google_ads", "google"]),
    "webinar": (0.16, 0.55, ["Webinar", "webinar", "WEBINAR"]),
    "organic_site": (0.14, 0.05, ["organic_site", "Site", "organic"]),
    "referral": (0.08, 0.95, ["referral", "Referral", "friend"]),
}
COURSES = {  # canonical -> (share, effect)
    "ai_developers": (0.27, 0.15),
    "data_analyst": (0.22, 0.05),
    "fullstack": (0.18, 0.0),
    "cyber": (0.13, -0.10),
    "qa_automation": (0.12, 0.10),
    "ux_ui": (0.08, -0.20),
}
COURSE_HE = {
    "ai_developers": "פיתוח AI", "data_analyst": "דאטה אנליסט", "fullstack": "פולסטאק",
    "cyber": "סייבר", "qa_automation": "QA אוטומציה", "ux_ui": "UX/UI",
}
AGE_BANDS = {"18-24": (0.20, -0.35), "25-34": (0.36, 0.20), "35-44": (0.27, 0.25),
             "45-54": (0.13, 0.0), "55+": (0.04, -0.40)}
REGIONS = {"tel_aviv": 0.22, "center": 0.26, "sharon": 0.12, "jerusalem": 0.14,
           "haifa_north": 0.16, "south": 0.10}
REGION_MESS = {"tel_aviv": ["Tel Aviv", "tel_aviv", "TLV"], "center": ["center", "Center", "merkaz"],
               "sharon": ["sharon", "Sharon"], "jerusalem": ["Jerusalem", "jerusalem"],
               "haifa_north": ["haifa_north", "Haifa", "North"], "south": ["south", "South", "Beer Sheva"]}
NAMES = ["נועה", "דניאל", "יעל", "איתי", "מיכל", "עומר", "שירה", "אורי", "תמר", "יונתן", "מאיה",
         "אביב", "רוני", "גל", "ליאור", "הדר", "אסף", "רותם", "עדי", "ניר", "סיוון", "טל", "אלון", "ענבל"]


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _pick(rng: np.random.Generator, table: dict, n: int) -> np.ndarray:
    keys = list(table)
    shares = np.array([table[k][0] if isinstance(table[k], tuple) else table[k] for k in keys])
    return rng.choice(keys, size=n, p=shares / shares.sum())


def _form_text(rng: np.random.Generator, course: str, flags: dict[str, bool]) -> str:
    """Compose a short Hebrew form message from intent flags."""
    parts: list[str] = []
    c = COURSE_HE[course]
    if flags["just_browsing"]:
        return rng.choice(["רק בודק מה יש", "סתם מתעניין/ת כרגע", "רוצה לקבל חומר לקריאה, בלי שיחה"])
    if flags["asks_start"]:
        parts.append(rng.choice([f"מתי מתחיל המחזור הבא של {c}?", f"מתי נפתח קורס {c}?"]))
    if flags["career_change"]:
        parts.append(rng.choice(["שוקל/ת הסבה להייטק", "עובד/ת היום בתחום אחר ורוצה הסבה מקצועית"]))
    if flags["asks_price"]:
        parts.append(rng.choice(["כמה עולה הקורס?", "אשמח לפרטים על מחיר ותשלומים"]))
    if flags["financing"]:
        parts.append(rng.choice(["יש מימון או הנחה?", "האם יש מימון ממשלתי?"]))
    if flags["evening"]:
        parts.append(rng.choice(["אפשר ללמוד בערבים? אני עובד/ת במשרה מלאה", "יש מסלול ערב?"]))
    if not parts:
        parts.append(rng.choice([f"מתעניין/ת בקורס {c}", "אשמח שיחזרו אליי", ""]))
    return " ".join(parts)


def generate(n: int = N_LEADS, seed: int = SEED) -> pd.DataFrame:
    """Return the canonical (pre-mess) lead table with a hidden-signal outcome."""
    rng = np.random.default_rng(seed)
    span_h = (END - START).total_seconds() / 3600
    hours = np.sort(rng.uniform(0, span_h, n))
    created = START + pd.to_timedelta(hours, unit="h")
    created = created.floor("min")

    source = _pick(rng, SOURCES, n)
    course = _pick(rng, COURSES, n)
    age = _pick(rng, AGE_BANDS, n)
    region = _pick(rng, REGIONS, n)
    intent = rng.normal(0, 1, n)

    flags = {
        "asks_start": rng.random(n) < _sigmoid(-1.0 + 0.9 * intent),
        "asks_price": rng.random(n) < _sigmoid(-0.9 + 0.5 * intent),
        "financing": rng.random(n) < 0.15,
        "career_change": rng.random(n) < 0.30,
        "evening": rng.random(n) < 0.20,
        "just_browsing": rng.random(n) < _sigmoid(-2.3 - 1.1 * intent),
    }
    webinar = (rng.random(n) < _sigmoid(-1.4 + 0.6 * intent + 2.6 * (source == "webinar"))).astype(int)
    pages = rng.poisson(np.exp(1.2 + 0.35 * intent))
    weekend = np.isin(created.dayofweek, [4, 5])  # Fri/Sat in Israel
    resp_min = np.exp(rng.normal(np.log(140) + 0.9 * weekend, 1.3, n))
    resp_min = np.clip(resp_min, 1, 10080).round(0)

    logit = (-2.75 + 0.85 * intent
             + np.array([SOURCES[s][1] for s in source])
             + np.array([COURSES[c][1] for c in course])
             + np.array([AGE_BANDS[a][1] for a in age])
             + 0.7 * webinar + 0.05 * np.minimum(pages, 25)
             - 0.32 * np.log1p(resp_min / 60)
             + 0.55 * flags["asks_start"] + 0.25 * flags["asks_price"]
             - 1.3 * flags["just_browsing"]
             + rng.normal(0, 0.5, n))
    converted = (rng.random(n) < _sigmoid(logit)).astype(float)
    contacts = 1 + rng.poisson(1.2 + 1.3 * converted)

    is_open = created > (END - pd.Timedelta(days=OPEN_DAYS))
    converted[is_open] = np.nan
    contacts[is_open] = rng.integers(0, 3, is_open.sum())
    resp_min = resp_min.astype(float)
    not_yet = is_open & (rng.random(n) < 0.25)  # open leads nobody has called yet
    resp_min[not_yet] = np.nan
    contacts[not_yet] = 0

    q = "q" + (((created.month - 1) // 3) + 1).astype(str)
    short = {"facebook_form": "fb", "google_ads": "gads", "webinar": "web", "organic_site": "seo", "referral": "ref"}
    campaign = [f"{short[s]}_{c}_{qq}" for s, c, qq in zip(source, course, q)]
    texts = [_form_text(rng, course[i], {k: bool(v[i]) for k, v in flags.items()}) for i in range(n)]

    return pd.DataFrame({
        "lead_id": [f"L{100000 + i}" for i in range(n)],
        "created_at": created.strftime("%Y-%m-%d %H:%M"),
        "first_name": rng.choice(NAMES, n),
        "source": source, "campaign": campaign, "course_interest": course,
        "age_band": age, "region": region, "webinar_attended": webinar,
        "pages_viewed": pages.astype(float), "response_time_min": resp_min,
        "n_contacts": contacts, "form_text": texts, "converted": converted,
    })


def add_mess(df: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """Make the export look like a real CRM dump: spellings, gaps, dupes, glitches."""
    rng = np.random.default_rng(seed + 1)
    out = df.copy()
    out["source"] = [rng.choice(SOURCES[s][2]) for s in out["source"]]
    out["region"] = [rng.choice(REGION_MESS[r]) for r in out["region"]]
    n = len(out)
    out.loc[rng.random(n) < 0.04, "age_band"] = ""
    out.loc[rng.random(n) < 0.03, "pages_viewed"] = np.nan
    glitch = rng.random(n) < 0.004  # CRM bug: negative response time
    out.loc[glitch & out["response_time_min"].notna(), "response_time_min"] = -1
    out["converted"] = out["converted"].map({1.0: "yes", 0.0: "no"}).fillna("")
    dupes = out.sample(frac=0.02, random_state=seed)  # double form submissions
    out = pd.concat([out, dupes]).sort_values(["created_at", "lead_id"], kind="stable")
    return out.reset_index(drop=True)


def break_export(df: pd.DataFrame) -> pd.DataFrame:
    """The v2 export: one renamed column and one silent unit change."""
    out = df.rename(columns={"course_interest": "program_interest"})
    rt = pd.to_numeric(out["response_time_min"], errors="coerce")
    out["response_time_min"] = np.where(rt > 0, rt * 60, rt)  # now seconds, same name
    return out


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    messy = add_mess(generate())
    messy.to_csv(CLEAN_EXPORT, index=False, encoding="utf-8")
    break_export(messy).to_csv(BROKEN_EXPORT, index=False, encoding="utf-8")
    print(f"wrote {CLEAN_EXPORT.name} ({len(messy)} rows) and {BROKEN_EXPORT.name}")


def ensure_data() -> None:
    """Generate the raw exports if they are missing (they are git-ignored)."""
    if not (CLEAN_EXPORT.exists() and BROKEN_EXPORT.exists()):
        main()


if __name__ == "__main__":
    main()
