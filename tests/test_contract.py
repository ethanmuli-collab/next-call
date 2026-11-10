"""Unit tests for the contract gate. Run: python -m unittest -v  (or pytest, if installed)."""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract.validate import validate  # noqa: E402
from data.generate_data import add_mess, generate  # noqa: E402
from tools.cleaning import clean_leads  # noqa: E402
from tools.contract_tools import build_contract  # noqa: E402
from tools.eda import load_clean  # noqa: E402


class ContractGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        raw = d / "raw.csv"
        add_mess(generate(n=1500, seed=7), seed=7).to_csv(raw, index=False, encoding="utf-8")
        clean_leads(raw, d / "clean_data.csv")
        cls.contract = build_contract(d / "clean_data.csv", d / "dataset_contract.json", raw.name)
        cls.df = load_clean(d / "clean_data.csv")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def _errors(self, df, contract=None) -> list:
        report = validate(df, contract or self.contract)
        return report.errors

    def test_clean_data_passes(self) -> None:
        report = validate(self.df, self.contract)
        self.assertTrue(report.passed, report.summary())

    def test_renamed_column_fails_with_hint(self) -> None:
        errs = self._errors(self.df.rename(columns={"source": "lead_source"}))
        msgs = " ".join(e.message for e in errs)
        self.assertIn("missing_column", [e.check for e in errs])
        self.assertIn("'source'", msgs)
        self.assertIn("lead_source", msgs)  # the readable rename hint

    def test_minutes_to_seconds_detected(self) -> None:
        df = self.df.copy()
        df["response_time_min"] = df["response_time_min"] * 60
        errs = self._errors(df)
        self.assertIn("unit", [e.check for e in errs])
        self.assertTrue(any("seconds" in e.message for e in errs), [e.message for e in errs])

    def test_out_of_range_value_fails(self) -> None:
        df = self.df.copy()
        df.loc[df.index[:3], "pages_viewed"] = 999
        errs = self._errors(df)
        self.assertTrue(any(e.check == "range" and e.column == "pages_viewed" for e in errs))

    def test_unknown_category_fails(self) -> None:
        df = self.df.copy()
        df.loc[df.index[0], "source"] = "tiktok"
        errs = self._errors(df)
        self.assertTrue(any(e.check == "allowed_values" and "tiktok" in e.message for e in errs))

    def test_broken_contract_fails(self) -> None:
        contract = copy.deepcopy(self.contract)
        del contract["columns"]["response_time_min"]  # "delete a row of the contract"
        errs = self._errors(self.df, contract)
        self.assertTrue(any(e.check == "contract_structure" and "response_time_min" in e.message for e in errs))


if __name__ == "__main__":
    unittest.main(verbosity=2)
