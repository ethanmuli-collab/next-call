"""Declared semantics of the clean Kaggle "Lead Scoring Dataset" table (X Education, real data).

Same role as contract/spec.py, for the `kaggle` dataset profile. It is versioned code:
it never adapts to the data, so a renamed column or a changed unit is caught by the gate.
"""
from __future__ import annotations

CONTRACT_VERSION = "1.0"
DATASET_NAME = "kaggle_lead_scoring_clean"
TARGET_DEFINITION = "lead converted to a paying customer of X Education"
TIME_COLUMN = None  # the public dataset has no timestamp
SPLIT_POLICY = "stratified random 80/20 split with a fixed seed (the dataset has no time column)"

LEAD_ORIGINS = ["landing_page_submission", "api", "lead_add_form", "lead_import", "quick_add_form"]
LEAD_SOURCES = ["google", "direct_traffic", "olark_chat", "organic_search", "reference", "welingak_website",
                "referral_sites", "facebook", "other", "unknown"]
SPECIALIZATIONS = ["finance_management", "human_resource_management", "marketing_management",
                   "operations_management", "business_administration", "it_projects_management",
                   "supply_chain_management", "banking_investment_and_insurance", "media_and_advertising",
                   "travel_and_tourism", "international_business", "healthcare_management",
                   "hospitality_management", "e_commerce", "retail_management", "rural_and_agribusiness",
                   "e_business", "services_excellence", "not_selected"]
OCCUPATIONS = ["unemployed", "working_professional", "student", "other", "housewife", "businessman", "unknown"]
CITIES = ["mumbai", "thane_outskirts", "other_cities", "other_cities_of_maharashtra", "other_metro_cities",
          "tier_ii_cities", "not_selected"]

COLUMNS: dict[str, dict] = {
    "lead_id": {"dtype": "string", "unique": True, "description": "Lead Number from the CRM (primary key)."},
    "lead_origin": {"dtype": "category", "allowed": LEAD_ORIGINS, "description": "How the lead entered the CRM."},
    "lead_source": {"dtype": "category", "allowed": LEAD_SOURCES,
                    "description": "Traffic source, normalised; rare sources = 'other', blank = 'unknown'."},
    "do_not_email": {"dtype": "binary", "allowed": [0, 1], "description": "1 if the lead opted out of email."},
    "total_visits": {"dtype": "int", "min": 0, "max": 300, "unit": "visits",
                     "description": "Site visits; missing values imputed with the median."},
    "time_on_site_sec": {"dtype": "int", "min": 0, "max": 7200, "unit": "seconds",
                         "reference_median": 248, "expected_median_range": [100, 700],
                         "description": "Total time spent on the website, in seconds as exported by the CRM."},
    "pages_per_visit": {"dtype": "float", "min": 0, "max": 60, "unit": "pages",
                        "description": "Average pages per visit; missing values imputed with the median."},
    "specialization": {"dtype": "category", "allowed": SPECIALIZATIONS,
                       "description": "Field of interest; the form default 'Select' and blanks = 'not_selected'."},
    "occupation": {"dtype": "category", "allowed": OCCUPATIONS, "description": "Current occupation; blank = 'unknown'."},
    "city": {"dtype": "category", "allowed": CITIES, "description": "City group; 'Select' and blanks = 'not_selected'."},
    "free_copy_requested": {"dtype": "binary", "allowed": [0, 1],
                            "description": "1 if the lead asked for the free 'Mastering The Interview' copy."},
    "converted": {"dtype": "binary", "allowed": [0, 1], "role": "target",
                  "description": "1 = became a paying customer, 0 = did not."},
}

MODEL_FEATURES = ["lead_origin", "lead_source", "do_not_email", "total_visits", "time_on_site_sec",
                  "pages_per_visit", "specialization", "occupation", "city", "free_copy_requested"]

EXCLUDED_FROM_MODEL = {
    "lead_id": "identifier",
    "Tags": "dropped at cleaning - LEAKAGE: written by the sales team after talking to the lead",
    "Lead Quality": "dropped at cleaning - LEAKAGE: sales rep's judgement after contact",
    "Lead Profile": "dropped at cleaning - LEAKAGE: assigned by sales after contact",
    "Last Activity / Last Notable Activity": "dropped at cleaning - LEAKAGE: includes post-contact events",
    "Asymmetrique * (4 columns)": "dropped at cleaning - vendor scores computed after engagement, 46% missing",
    "Country": "dropped at cleaning - 27% missing and almost a single value",
    "How did you hear / What matters most": "dropped at cleaning - mostly blank or the form default 'Select'",
    "Do Not Call, Search, Magazine, Newspaper, ... (11 flags)": "dropped at cleaning - constant or near constant",
}

DATASET_RULES = {
    "min_rows": 5000,
    "unique_key": "lead_id",
    "target_rate_range": [0.20, 0.60],
    "max_unknown_category_frac": 0.0,
    "default_max_null_frac": 0.0,
}

ASSUMPTIONS = [
    "One row per lead (Lead Number is unique).",
    "time_on_site_sec is in seconds; the reference median is about 4 minutes. A median outside 100-700 means the unit changed.",
    "The form default 'Select' means the lead did not choose a value; it is treated as 'not_selected', never as a category.",
    "Columns filled in by the sales team after contact were dropped at cleaning (leakage) and must not come back as features.",
    "There is no time column: the modeling crew must use a stratified random split with a fixed seed.",
    "converted is known for every row; there are no open leads in this dataset, so no call list is produced from it.",
]
