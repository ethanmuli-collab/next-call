"""2-line personalised call openers: LLM when a key is set, Hebrew templates offline."""
from __future__ import annotations

import json
import logging

import pandas as pd

from config import LLM_MODEL

log = logging.getLogger("next_call")

COURSE_HE = {"ai_developers": "פיתוח AI", "data_analyst": "דאטה אנליסט", "fullstack": "פולסטאק",
             "cyber": "סייבר", "qa_automation": "QA אוטומציה", "ux_ui": "UX/UI"}


def template_opening(row: pd.Series) -> str:
    """Deterministic opener built from what the lead wrote."""
    name = row.get("first_name") or ""
    course = COURSE_HE.get(str(row.get("course_interest")), "הקורס")
    text = str(row.get("form_text") or "")
    line1 = f"היי {name}, מדבר/ת מהמכללה - ראיתי שהשארת פרטים על קורס {course}."
    if any(w in text for w in ["מתי", "מחזור", "נפתח"]):
        line2 = "שאלת מתי מתחיל המחזור הבא - יש לי תאריך ועוד כמה מקומות פנויים, יש לך 2 דקות?"
    elif any(w in text for w in ["מימון", "הנחה", "מחיר", "עולה", "תשלומים"]):
        line2 = "שאלת על מחיר ומימון - אני יכול/ה לעבור איתך על מסלולי התשלום והמימון בקצרה."
    elif "הסבה" in text:
        line2 = "כתבת שאת/ה שוקל/ת הסבה - אשמח להבין מאיפה את/ה מגיע/ה ולהראות איך בוגרים דומים השתלבו."
    elif "ערב" in text:
        line2 = "שאלת על לימודי ערב - יש מסלול ערב שמתאים למי שעובד במשרה מלאה, אספר בקצרה?"
    elif any(w in text for w in ["רק בודק", "סתם", "בלי שיחה"]):
        line2 = "כתבת שאת/ה רק בודק/ת - אז בקצרה: אשלח סילבוס בוואטסאפ, ותגיד/י לי אם שווה לדבר."
    else:
        line2 = "רציתי להבין מה הביא אותך להתעניין ולבדוק אם המסלול מתאים לך."
    return f"{line1}\n{line2}"


def llm_openings(df: pd.DataFrame) -> list[str] | None:
    """One OpenAI call for the whole list; returns None on any failure (caller falls back)."""
    try:
        from openai import OpenAI

        leads = [{"lead_id": r.lead_id, "first_name": r.first_name, "course": COURSE_HE.get(r.course_interest, ""),
                  "form_text": r.form_text, "why_now": r.reasons} for r in df.itertuples()]
        prompt = ("You write call openers for an admissions rep at an Israeli tech college. For each lead write "
                  "exactly 2 full sentences in warm, natural spoken Hebrew, as the rep would say them on the phone. "
                  "Sentence 1 greets by first name, says the rep is calling from the college and names the course "
                  "they left details for. Sentence 2 quotes or paraphrases the specific thing they wrote in the form "
                  "(form_text) and ends with one open question about it; if form_text is empty use why_now. "
                  "Use the neutral form 'את/ה'. No promises about prices or discounts. Example:\n"
                  "היי דנה, מדבר/ת מהמכללה, ראיתי שהשארת פרטים על קורס סייבר.\n"
                  "כתבת שאת/ה מחפש/ת לימודי ערב - מה חשוב לך שיהיה במסלול כדי שיסתדר עם העבודה?\n"
                  "Return JSON {\"openers\": [{\"lead_id\": ..., \"text\": \"sentence1\\nsentence2\"}]}.\n"
                  + json.dumps(leads, ensure_ascii=False))
        resp = OpenAI(timeout=60).chat.completions.create(
            model=LLM_MODEL, temperature=0.3, response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}])
        data = json.loads(resp.choices[0].message.content)
        by_id = {o["lead_id"]: o["text"] for o in data.get("openers", [])}
        return [by_id.get(lid) or template_opening(df.iloc[i]) for i, lid in enumerate(df["lead_id"])]
    except Exception as exc:  # network, quota, bad JSON -> template fallback
        log.warning("LLM openers failed (%s); using templates", type(exc).__name__)
        return None


def add_openings(df: pd.DataFrame, offline: bool) -> tuple[pd.DataFrame, str]:
    """Attach an `opening_line` column; returns (df, how it was written)."""
    out = df.copy()
    lines = None if offline or out.empty else llm_openings(out)
    mode = "llm" if lines else "template"
    out["opening_line"] = lines or [template_opening(r) for _, r in out.iterrows()]
    return out, mode
