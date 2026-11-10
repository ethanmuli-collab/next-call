"""The analysts' declared semantics of the clean lead table (versioned with the code).

This is the *agreement*: names, types, allowed values, units and plausible ranges.
The Contract agent combines it with observed statistics into dataset_contract.json.
It never adapts to the data, so a renamed column or a changed unit cannot be
"absorbed" silently - the gate will see the disagreement.
"""
from __future__ import annotations

CONTRACT_VERSION = "1.0"

SOURCES = ["facebook_form", "google_ads", "webinar", "organic_site", "referral"]
COURSES = ["ai_developers", "data_analyst", "fullstack", "cyber", "qa_automation", "ux_ui"]
AGE_BANDS = ["18-24", "25-34", "35-44", "45-54", "55+", "unknown"]
REGIONS = ["tel_aviv", "center", "sharon", "jerusalem", "haifa_north", "south"]

COLUMNS: dict[str, dict] = {
    "lead_id": {"dtype": "string", "unique": True, "description": "CRM lead identifier (primary key)."},
    "created_at": {"dtype": "datetime", "description": "When the lead form was submitted (local time)."},
    "first_name": {"dtype": "string", "pii": True, "max_null_frac": 0.05,
                   "description": "First name, used only to personalise the call opener."},
    "source": {"dtype": "category", "allowed": SOURCES, "description": "Lead channel, normalised."},
    "campaign": {"dtype": "string", "description": "Ad campaign code; changes every quarter."},
    "course_interest": {"dtype": "category", "allowed": COURSES, "description": "Course the lead asked about."},
    "age_band": {"dtype": "category", "allowed": AGE_BANDS, "description": "Self-reported age band; 'unknown' if blank."},
    "region": {"dtype": "category", "allowed": REGIONS, "description": "Region, normalised."},
    "webinar_attended": {"dtype": "binary", "allowed": [0, 1], "description": "1 if the lead attended a webinar."},
    "pages_viewed": {"dtype": "int", "min": 0, "max": 200, "unit": "pages",
                     "description": "Site pages viewed before the form; missing values imputed with the median."},
    "response_time_min": {"dtype": "float", "min": 0, "max": 10080, "unit": "minutes",
                          "reference_median": 180, "expected_median_range": [30, 900], "max_null_frac": 0.05,
                          "description": "Minutes from form submission to the first call attempt "
                                         "(max 7 days). Null = not called yet."},
    "n_contacts": {"dtype": "int", "min": 0, "max": 30, "unit": "calls",
                   "description": "Number of contact attempts so far."},
    "form_text": {"dtype": "text", "description": "Free text the lead typed in the form (Hebrew). May be empty."},
    "converted": {"dtype": "binary", "allowed": [0, 1], "nullable": True, "role": "target",
                  "description": "1 = enrolled, 0 = lost, null = still open (no outcome yet)."},
}

MODEL_FEATURES = ["created_at", "source", "course_interest", "age_band", "region",
                  "webinar_attended", "pages_viewed", "response_time_min", "form_text"]

EXCLUDED_FROM_MODEL = {
    "lead_id": "identifier",
    "first_name": "PII - used for the opener only, never as a feature",
    "campaign": "high cardinality and renamed every quarter",
    "n_contacts": "leakage risk - grows after the outcome is known (converted leads get more calls)",
}

DATASET_RULES = {
    "min_rows": 1000,
    "unique_key": "lead_id",
    "target_rate_range": [0.03, 0.40],
    "max_unknown_category_frac": 0.0,
    "default_max_null_frac": 0.0,
}

ASSUMPTIONS = [
    "One row per lead; duplicates (double form submissions) were removed by lead_id.",
    "All durations are in minutes; response_time_min above 10080 (7 days) is impossible by definition.",
    "Category spellings are normalised to the allowed lists; anything else is an upstream change.",
    "converted is null only for open leads (no final outcome yet); those are scored, not trained on.",
    "created_at is the only time axis; the modeling crew must split train/test by time, not randomly.",
    "Rows are in UTF-8; form_text is Hebrew free text and may be empty.",
]
