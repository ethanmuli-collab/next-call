"""Contract tool (Crew 1): declared spec + observed profile -> dataset_contract.json."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd

from contract import get_spec
from contract.validate import file_sha256
from tools.eda import load_clean


def _observed(s: pd.Series, dtype: str) -> dict:
    obs: dict = {"null_frac": round(float(s.isna().mean()), 4), "n_unique": int(s.nunique())}
    if dtype in {"int", "float", "binary"}:
        num = pd.to_numeric(s, errors="coerce")
        if num.notna().any():
            obs.update(min=float(num.min()), max=float(num.max()), median=float(num.median()))
    elif dtype == "datetime":
        obs.update(min=str(s.min()), max=str(s.max()))
    return obs


def build_contract(clean_path: Path, out_json: Path, input_name: str, dataset: str = "synthetic") -> dict:
    """Write dataset_contract.json for the clean data and return it."""
    spec = get_spec(dataset)
    df = load_clean(clean_path)
    columns = copy.deepcopy(spec.COLUMNS)
    for name, col in columns.items():
        col.setdefault("nullable", False)
        col["observed"] = _observed(df[name], col["dtype"]) if name in df else "MISSING IN CLEAN DATA"
    as_of = str(df[spec.TIME_COLUMN].max()) if spec.TIME_COLUMN and spec.TIME_COLUMN in df else None
    contract = {
        "contract_version": spec.CONTRACT_VERSION,
        "dataset": spec.DATASET_NAME,
        "produced_by": "Crew 1 - Data Analyst (contract agent)",
        "consumed_by": "Crew 2 - Data Scientist",
        "source_export": input_name,
        "file": "clean_data.csv",
        "row_count": int(len(df)),
        "as_of": as_of,
        "primary_key": spec.DATASET_RULES["unique_key"],
        "target": {"column": "converted", "positive_label": 1, "definition": spec.TARGET_DEFINITION},
        "time_column": spec.TIME_COLUMN,
        "split_policy": spec.SPLIT_POLICY,
        "columns": columns,
        "model_features": spec.MODEL_FEATURES,
        "excluded_from_model": spec.EXCLUDED_FROM_MODEL,
        "constraints": spec.DATASET_RULES,
        "assumptions": spec.ASSUMPTIONS,
        "data_fingerprint": {"sha256": file_sha256(clean_path), "rows": int(len(df))},
    }
    out_json.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return contract


def load_contract(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
