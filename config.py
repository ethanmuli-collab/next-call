"""Central paths, constants and mode detection for Next Call."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")  # only this project's .env, never anything else

# Keep CrewAI quiet and offline-friendly (no telemetry, no tracing prompt).
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
# In crewai 1.14 this flag only skips the first-run "view your traces? (20s)" prompt.
os.environ.setdefault("CREWAI_TESTING", "true")
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")  # no download at import time

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
ARTIFACTS_DIR = ROOT / "artifacts"
OUTCOMES_DB = DATA_DIR / "outcomes.db"

CLEAN_EXPORT = RAW_DIR / "leads_weekly_export.csv"
BROKEN_EXPORT = RAW_DIR / "leads_weekly_export_v2.csv"
KAGGLE_EXPORT = DATA_DIR / "kaggle" / "Lead Scoring.csv"  # downloaded manually, not in git

SEED = 42
LLM_MODEL = os.getenv("NEXT_CALL_LLM_MODEL", "gpt-4o-mini")
CALL_LIST_SIZE = 25
HALF_LIFE_HOURS = 48.0  # "hot leads go cold in 48 hours"

CREW1_FILES = ["clean_data.csv", "eda_report.html", "insights.md", "dataset_contract.json"]
CREW2_FILES = ["features.csv", "model.joblib", "evaluation_report.md", "model_card.md"]


def is_offline() -> bool:
    """Offline when no OpenAI key is set or NEXT_CALL_OFFLINE=1 is forced."""
    if os.getenv("NEXT_CALL_OFFLINE", "").strip() in {"1", "true", "yes"}:
        return True
    return not os.getenv("OPENAI_API_KEY", "").strip()


def run_dir_for(input_path: Path) -> Path:
    """Artifacts of a run live in artifacts/<input file stem>/."""
    return ARTIFACTS_DIR / Path(input_path).stem
