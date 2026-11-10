"""Contract gate tests for the kaggle dataset profile.

The Kaggle file itself is not in git, so the tests build a small frame that conforms to the
declared spec and then break it the way a real upstream change would.
"""
from __future__ import annotations

import copy
import unittest

import numpy as np
import pandas as pd

from contract import get_spec
from contract.validate import validate

SPEC = get_spec("kaggle")


def conforming_frame(n: int = 6000) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    data = {}
    for name, col in SPEC.COLUMNS.items():
        if name == "lead_id":
            data[name] = [str(600000 + i) for i in range(n)]
        elif col["dtype"] == "category":
            data[name] = rng.choice(col["allowed"], n)
        elif col["dtype"] == "binary":
            data[name] = rng.integers(0, 2, n)
        elif name == "time_on_site_sec":
            data[name] = rng.integers(0, 600, n)  # median ~300 seconds, inside the expected range
        elif col["dtype"] == "int":
            data[name] = rng.integers(0, 20, n)
        else:
            data[name] = rng.uniform(0, 9, n).round(2)
    return pd.DataFrame(data)


def contract() -> dict:
    cols = copy.deepcopy(SPEC.COLUMNS)
    for col in cols.values():
        col.setdefault("nullable", False)
    return {"contract_version": SPEC.CONTRACT_VERSION, "columns": cols, "model_features": SPEC.MODEL_FEATURES,
            "target": {"column": "converted"}, "constraints": SPEC.DATASET_RULES}


class KaggleContractGateTests(unittest.TestCase):
    def test_conforming_data_passes(self):
        report = validate(conforming_frame(), contract())
        self.assertTrue(report.passed, report.summary())

    def test_seconds_to_minutes_detected(self):
        df = conforming_frame()
        df["time_on_site_sec"] = df["time_on_site_sec"] / 60  # same column name, different unit
        report = validate(df, contract())
        self.assertFalse(report.passed)
        self.assertIn("unit", [e.check for e in report.errors])
        self.assertIn("time_on_site_sec", report.summary())

    def test_select_placeholder_is_rejected(self):
        df = conforming_frame()
        df.loc[:50, "specialization"] = "Select"  # the form default leaking through cleaning
        report = validate(df, contract())
        self.assertFalse(report.passed)
        self.assertIn("specialization", report.summary())

    def test_leakage_column_coming_back_is_reported(self):
        df = conforming_frame()
        df["Tags"] = "Will revert after reading the email"
        report = validate(df, contract())
        self.assertIn("Tags", " ".join(w.message for w in report.warnings))


if __name__ == "__main__":
    unittest.main()
