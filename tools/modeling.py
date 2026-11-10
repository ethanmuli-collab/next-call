"""Model training & comparison tool (Crew 2): features.csv -> model.joblib + metrics."""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import SEED
from tools.features import feature_columns

TEST_FRACTION = 0.2


def candidate_models() -> dict:
    """The two model variations we compare (both deterministic)."""
    return {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=3000)),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=250, learning_rate=0.05, max_leaf_nodes=15, l2_regularization=1.0,
            min_samples_leaf=40, early_stopping=False, random_state=SEED),
    }


def ranking_metrics(y: np.ndarray, score: np.ndarray) -> dict:
    """Metrics a call-list user cares about: how many enrolments sit at the top of the list."""
    order = np.argsort(-score, kind="stable")
    ys = y[order]
    k20, k10 = max(1, int(0.2 * len(y))), max(1, int(0.1 * len(y)))
    base = y.mean()
    return {"capture_at_20pct": round(float(ys[:k20].sum() / max(1, y.sum())), 4),
            "precision_at_top10pct": round(float(ys[:k10].mean()), 4),
            "lift_at_top10pct": round(float(ys[:k10].mean() / base), 2) if base else None}


def evaluate(y: np.ndarray, p: np.ndarray) -> dict:
    m = {"roc_auc": round(float(roc_auc_score(y, p)), 4),
         "pr_auc": round(float(average_precision_score(y, p)), 4),
         "brier": round(float(brier_score_loss(y, p)), 4),
         "log_loss": round(float(log_loss(y, p)), 4)}
    m.update(ranking_metrics(y, p))
    return m


def time_split(feat: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Labelled rows only; oldest 80% train, newest 20% test (never random)."""
    lab = feat[feat["converted"].notna()].sort_values(["created_at", "lead_id"], kind="stable")
    cut = lab["created_at"].iloc[int(len(lab) * (1 - TEST_FRACTION))]
    return lab[lab["created_at"] < cut], lab[lab["created_at"] >= cut], str(cut)


def stratified_split(feat: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """For datasets without a time column: seeded 80/20 split, stratified on the target."""
    lab = feat[feat["converted"].notna()].sort_values("lead_id", kind="stable")
    train, test = train_test_split(lab, test_size=TEST_FRACTION, random_state=SEED, stratify=lab["converted"])
    return train.sort_values("lead_id", kind="stable"), test.sort_values("lead_id", kind="stable")


def train_and_compare(features_csv: Path, model_out: Path, contract: dict) -> dict:
    """Train both variations, compare on the holdout the contract prescribes, refit the winner, save it."""
    feat = pd.read_csv(features_csv, encoding="utf-8")
    cols = feature_columns(feat)
    timed = bool(contract.get("time_column"))
    if timed:
        train, test, cutoff = time_split(feat)
    else:
        (train, test), cutoff = stratified_split(feat), None
    ytr, yte = train["converted"].astype(int).values, test["converted"].astype(int).values
    results: dict = {}
    fitted = {}
    for name, model in candidate_models().items():
        model.fit(train[cols], ytr)
        results[name] = evaluate(yte, model.predict_proba(test[cols])[:, 1])
        fitted[name] = model
    # What the rep does today: call in arrival order (oldest first).
    fifo = -np.arange(len(test), dtype=float)
    results["baseline_arrival_order"] = ranking_metrics(yte, fifo)

    best = max(["logistic_regression", "hist_gradient_boosting"],
               key=lambda n: (results[n]["pr_auc"], n == "logistic_regression"))
    imp = permutation_importance(fitted[best], test[cols], yte, scoring="average_precision",
                                 n_repeats=5, random_state=SEED)
    importance = (pd.Series(imp.importances_mean, index=cols).sort_values(ascending=False).head(12).round(4))

    final = candidate_models()[best]
    lab = pd.concat([train, test])
    final.fit(lab[cols], lab["converted"].astype(int).values)
    bundle = {"model": final, "model_name": best, "feature_columns": cols, "holdout_metrics": results[best],
              "cutoff": cutoff, "train_rows": int(len(lab)), "contract_version": contract["contract_version"],
              "as_of": contract.get("as_of")}
    joblib.dump(bundle, model_out)
    split = {"train_rows": int(len(train)), "test_rows": int(len(test)), "cutoff": cutoff,
             "train_positive_rate": round(float(ytr.mean()), 4),
             "test_positive_rate": round(float(yte.mean()), 4)}
    if not timed:
        split["policy"] = f"stratified random split, seed {SEED}"
    return {"selected_model": best,
            "selection_rule": f"highest PR-AUC on the {'time-based' if timed else 'stratified'} holdout",
            "split": split,
            "results": results, "top_features": {k: float(v) for k, v in importance.items()},
            "n_features": len(cols), "final_model_trained_on_rows": int(len(lab))}


def template_evaluation_narrative(ev: dict) -> str:
    """Offline commentary built only from the metrics."""
    r = ev["results"]
    lr, gb, base = r["logistic_regression"], r["hist_gradient_boosting"], r["baseline_arrival_order"]
    best = ev["selected_model"]
    top = ", ".join(list(ev["top_features"])[:4])
    return (f"- **{best}** wins on PR-AUC ({r[best]['pr_auc']:.3f}); logistic regression ROC-AUC "
            f"{lr['roc_auc']:.3f} vs gradient boosting {gb['roc_auc']:.3f}.\n"
            f"- Business view: calling the top 20% of leads by score reaches **{r[best]['capture_at_20pct']:.0%}** "
            f"of the enrolments, versus **{base['capture_at_20pct']:.0%}** when calling in arrival order.\n"
            f"- The strongest signals (permutation importance): {top}.\n"
            "- Recommendation: use the selected model to rank today's open leads; retrain weekly with the "
            "outcomes reps record in the app.")


def write_evaluation_report(ev: dict, narrative: str, out_md: Path, mode: str) -> None:
    rows = []
    for name, m in ev["results"].items():
        rows.append(f"| {name} | {m.get('roc_auc', '-')} | {m.get('pr_auc', '-')} | {m.get('brier', '-')} | "
                    f"{m.get('log_loss', '-')} | {m['capture_at_20pct']:.1%} | {m['precision_at_top10pct']:.1%} | "
                    f"{m['lift_at_top10pct']} |")
    s = ev["split"]
    if s.get("policy"):
        holdout = "stratified"
        split_line = (f"**{s['policy'].capitalize()}** (contract split policy; the dataset has no time column): "
                      f"train = {s['train_rows']} leads, test = {s['test_rows']} leads.")
    else:
        holdout = "time-based"
        split_line = (f"**Time-based split** (contract split policy): train = {s['train_rows']} leads created before "
                      f"{s['cutoff']}, test = {s['test_rows']} newest labelled leads.")
    imp = "\n".join(f"| {k} | {v:.4f} |" for k, v in ev["top_features"].items())
    out_md.write_text(f"""# Evaluation report - lead conversion model

_Commentary written by: {mode}. All numbers computed by the training tool._

## Setup
- Target: `converted` (1 = enrolled). Open leads (no outcome yet) are excluded from training and scored later.
- {split_line}
- Positive rate: train {s['train_positive_rate']:.1%}, test {s['test_positive_rate']:.1%}. {ev['n_features']} features.
- Selection rule: {ev['selection_rule']}. Winner refit on all {ev['final_model_trained_on_rows']} labelled leads -> `model.joblib`.

## Model comparison ({holdout} holdout)

| model | ROC-AUC | PR-AUC | Brier | log loss | capture@20% | precision@top10% | lift@top10% |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

`capture@20%` = share of all enrolments found if the rep only calls the top 20% of the list.

## Selected model: `{ev['selected_model']}`

### Top features (permutation importance, PR-AUC drop)

| feature | importance |
|---|---|
{imp}

## Commentary

{narrative.strip()}
""", encoding="utf-8")
