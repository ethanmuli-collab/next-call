"""The validation gate: check clean data against dataset_contract.json (plain pandas).

Every check appends a readable Issue; nothing raises. The Flow decides what to do
with the report (stop before Crew 2 when `passed` is False).
"""
from __future__ import annotations

import difflib
import hashlib
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

REQUIRED_CONTRACT_KEYS = ["contract_version", "columns", "model_features", "target", "constraints"]
REQUIRED_COLUMN_KEYS = ["dtype"]
UNIT_FACTORS = {  # observed/expected ratio -> what probably happened, per declared unit
    "minutes": {60.0: "seconds", 60000.0: "milliseconds", 1 / 60: "hours", 1 / 1440: "days"},
    "pages": {},
    "calls": {},
}


@dataclass
class Issue:
    check: str
    column: str | None
    message: str


@dataclass
class GateReport:
    passed: bool = True
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    checks_run: int = 0

    def fail(self, check: str, column: str | None, message: str) -> None:
        self.passed = False
        self.errors.append(Issue(check, column, message))

    def warn(self, check: str, column: str | None, message: str) -> None:
        self.warnings.append(Issue(check, column, message))

    def summary(self) -> str:
        """A human-readable message, suitable for logs and the UI."""
        if self.passed:
            head = f"Contract gate PASSED ({self.checks_run} checks)."
        else:
            head = (f"Contract gate FAILED - {len(self.errors)} problem(s); "
                    "Crew 2 (modeling) was NOT started.")
        lines = [head]
        lines += [f"  {i}. [{e.check}] {e.message}" for i, e in enumerate(self.errors, 1)]
        lines += [f"  warning [{w.check}] {w.message}" for w in self.warnings]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"passed": self.passed, "checks_run": self.checks_run,
                "errors": [asdict(e) for e in self.errors],
                "warnings": [asdict(w) for w in self.warnings], "summary": self.summary()}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_contract_structure(contract: dict, report: GateReport) -> None:
    """The contract itself must be complete (e.g. nobody deleted a section or a column spec)."""
    report.checks_run += 1
    for key in REQUIRED_CONTRACT_KEYS:
        if key not in contract:
            report.fail("contract_structure", None, f"dataset_contract.json has no '{key}' section.")
    cols = contract.get("columns", {})
    for feat in contract.get("model_features", []):
        if feat not in cols:
            report.fail("contract_structure", feat,
                        f"model feature '{feat}' is listed in the contract but has no column spec.")
    for name, spec in cols.items():
        for key in REQUIRED_COLUMN_KEYS:
            if key not in spec:
                report.fail("contract_structure", name, f"column spec for '{name}' has no '{key}'.")


def _rename_hint(missing: str, spec: dict, df: pd.DataFrame, extras: list[str]) -> str:
    """Guess which unexpected column is the renamed one (same values or similar name)."""
    allowed = spec.get("allowed")
    for col in extras:
        if allowed is not None:
            vals = set(df[col].dropna().astype(str).unique())
            if vals and vals <= {str(a) for a in allowed}:
                return f" Column '{col}' holds exactly the allowed values of '{missing}' - it looks renamed to '{col}'."
    close = difflib.get_close_matches(missing, extras, n=1, cutoff=0.5)
    if close:
        return f" Did it get renamed to '{close[0]}'?"
    return ""


def check_schema(df: pd.DataFrame, contract: dict, report: GateReport) -> list[str]:
    """Required columns present; unexpected columns reported. Returns the present contract columns."""
    report.checks_run += 1
    cols = contract.get("columns", {})
    extras = [c for c in df.columns if c not in cols]
    present = []
    for name, spec in cols.items():
        if name in df.columns:
            present.append(name)
            continue
        report.fail("missing_column", name,
                    f"Column '{name}' is required by the contract but missing from clean_data.csv."
                    + _rename_hint(name, spec, df, extras))
    for col in extras:
        report.warn("unexpected_column", col, f"Column '{col}' is not in the contract; Crew 2 will ignore it.")
    return present


def _unit_hint(spec: dict, median: float) -> str:
    ref = spec.get("reference_median")
    unit = spec.get("unit")
    if not ref or not median or median <= 0:
        return ""
    ratio = median / ref
    best = None
    for factor, name in UNIT_FACTORS.get(unit, {}).items():
        dist = abs(math.log10(ratio) - math.log10(factor))
        if dist < 0.35 and (best is None or dist < best[0]):
            best = (dist, name, factor)
    if best:
        return (f" Values are ~{ratio:.0f}x the contract's reference median ({ref} {unit}) - "
                f"the unit looks like it changed from {unit} to {best[1]}.") if ratio >= 1 else (
                f" Values are ~{1 / ratio:.0f}x smaller than the reference median ({ref} {unit}) - "
                f"the unit looks like it changed from {unit} to {best[1]}.")
    return ""


def check_column(df: pd.DataFrame, name: str, spec: dict, rules: dict, report: GateReport) -> None:
    """dtype, nulls, allowed values, ranges, uniqueness and unit sanity for one column."""
    report.checks_run += 1
    s = df[name]
    dtype = spec["dtype"]
    nullable = spec.get("nullable", False)
    max_null = spec.get("max_null_frac", 1.0 if nullable else rules.get("default_max_null_frac", 0.0))
    if dtype == "text":
        max_null = 1.0
    null_frac = float(s.isna().mean())
    if null_frac > max_null:
        report.fail("null_rate", name, f"Column '{name}' is {null_frac:.1%} null; the contract allows at most {max_null:.1%}.")

    vals = s.dropna()
    if dtype in {"int", "float", "binary"}:
        num = pd.to_numeric(vals, errors="coerce")
        bad = int(num.isna().sum())
        if bad:
            sample = vals[num.isna()].astype(str).head(3).tolist()
            report.fail("dtype", name, f"Column '{name}' must be numeric ({dtype}) but has {bad} non-numeric values, e.g. {sample}.")
            return
        vals = num
        if dtype == "int" and len(vals) and not (vals % 1 == 0).all():
            report.fail("dtype", name, f"Column '{name}' must hold whole numbers ({spec.get('unit', 'count')}).")
    elif dtype == "datetime":
        parsed = pd.to_datetime(vals, errors="coerce")
        if parsed.isna().any():
            report.fail("dtype", name, f"Column '{name}' has {int(parsed.isna().sum())} values that are not valid datetimes.")

    if "allowed" in spec and len(vals):
        allowed = {str(a) for a in spec["allowed"]}
        as_str = vals.astype(int).astype(str) if dtype == "binary" else vals.astype(str)
        unknown = as_str[~as_str.isin(allowed)]
        frac = len(unknown) / len(as_str)
        if frac > rules.get("max_unknown_category_frac", 0.0):
            top = unknown.value_counts().head(3).index.tolist()
            report.fail("allowed_values", name,
                        f"Column '{name}' has {len(unknown)} values ({frac:.1%}) outside the allowed list, e.g. {top}. "
                        f"Allowed: {sorted(allowed)}.")

    if dtype in {"int", "float"} and len(vals):
        lo, hi, unit = spec.get("min"), spec.get("max"), spec.get("unit", "")
        below = int((vals < lo).sum()) if lo is not None else 0
        above = int((vals > hi).sum()) if hi is not None else 0
        median = float(vals.median())
        hint = _unit_hint(spec, median)
        if below or above:
            report.fail("range", name,
                        f"Column '{name}' has {below + above} values ({(below + above) / len(vals):.1%}) outside "
                        f"the declared range [{lo}, {hi}] {unit} (observed min {vals.min():g}, max {vals.max():g})." + hint)
        rng = spec.get("expected_median_range")
        if rng and not (rng[0] <= median <= rng[1]):
            report.fail("unit", name,
                        f"Column '{name}' median is {median:g}, outside the expected {rng[0]}-{rng[1]} {unit}." + hint)

    if spec.get("unique") and s.duplicated().any():
        report.fail("unique", name, f"Column '{name}' must be unique but has {int(s.duplicated().sum())} duplicates.")


def validate(df: pd.DataFrame, contract: dict, data_path: Path | None = None) -> GateReport:
    """Run every gate check and return the full report (all problems, not just the first)."""
    report = GateReport()
    check_contract_structure(contract, report)
    if not report.passed:
        return report
    rules = contract.get("constraints", {})
    present = check_schema(df, contract, report)
    for name in present:
        check_column(df, name, contract["columns"][name], rules, report)

    report.checks_run += 1
    min_rows = rules.get("min_rows", 0)
    if len(df) < min_rows:
        report.fail("row_count", None, f"clean_data.csv has {len(df)} rows; the contract requires at least {min_rows}.")

    target = contract["target"]["column"]
    if target in df.columns:
        report.checks_run += 1
        y = pd.to_numeric(df[target], errors="coerce").dropna()
        lo, hi = rules.get("target_rate_range", [0, 1])
        if len(y) == 0:
            report.fail("target", target, f"Target '{target}' has no labelled rows - nothing to train on.")
        elif not (lo <= y.mean() <= hi):
            report.fail("target", target, f"Target rate is {y.mean():.1%}, outside the contract's plausible {lo:.0%}-{hi:.0%}.")

    missing_feats = [f for f in contract["model_features"] if f not in df.columns]
    report.checks_run += 1
    if missing_feats:
        report.fail("model_features", None, f"Required model features missing before modeling: {missing_feats}.")

    expected_sha = contract.get("data_fingerprint", {}).get("sha256")
    if data_path is not None and expected_sha:
        report.checks_run += 1
        if file_sha256(data_path) != expected_sha:
            report.warn("fingerprint", None, "clean_data.csv changed after the contract was written (sha256 differs); "
                                             "the value checks above decide whether it is still compatible.")
    return report
