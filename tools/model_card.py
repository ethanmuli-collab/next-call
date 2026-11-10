"""Model card tool (Crew 2): facts from the run + narrative -> model_card.md."""
from __future__ import annotations

from pathlib import Path


def model_card_facts(ev: dict, contract: dict, feat: dict) -> dict:
    """Everything the card writer is allowed to state as fact."""
    best = ev["selected_model"]
    return {"model_name": best, "holdout": ev["results"][best],
            "baseline": ev["results"]["baseline_arrival_order"], "split": ev["split"],
            "trained_on_rows": ev["final_model_trained_on_rows"], "n_features": feat["n_features"],
            "contract_version": contract["contract_version"], "source_export": contract["source_export"],
            "as_of": contract["as_of"], "excluded_from_model": contract["excluded_from_model"],
            "dataset": contract.get("dataset", ""),
            "top_features": list(ev["top_features"])[:6]}


KAGGLE_NARRATIVE = """## Purpose and intended use
Rank the leads of an online-course company (X Education, public Kaggle dataset) by how likely they are to become
paying customers, so the sales team calls the most promising leads first. It supports a human decision about call
order; it never decides who is *not* contacted.

**Intended users:** sales reps and their team lead. **Out of scope:** pricing, eligibility or any automated rejection.

## Limitations
- Trained on {rows:,} historical leads of one company; the public file has **no timestamp**, so the holdout is a
  stratified random split. A random split can look better than real future performance.
- Columns written by the sales team after contact (Tags, Lead Quality, Lead Profile, Last Activity) were removed
  as leakage. Scores are therefore lower than in notebooks that keep them, and more honest.
- `time_on_site_sec` is assumed to be in seconds, as declared in the contract; the gate checks its median.
- About a third of the leads did not choose a specialization or city (the form default "Select"); these are kept
  as `not_selected`, which is itself a signal of low engagement.
- The dataset licence is not stated on Kaggle, so the raw and clean rows are not committed to the repository.

## Ethical considerations
- **Fairness:** occupation and city group are features. A low score must never mean "do not call"; it only changes
  the order. Monitor conversion and contact rates per occupation and city group.
- **Privacy:** the dataset has no names, emails or phone numbers; the lead number is used only as a key.
- **Human in the loop:** the score orders the list, a person makes the call and records the outcome."""


def template_model_card_narrative(f: dict) -> str:
    """Offline narrative sections (purpose, use, limitations, ethics)."""
    if f.get("dataset", "").startswith("kaggle"):
        return KAGGLE_NARRATIVE.format(rows=f["trained_on_rows"])
    return f"""## Purpose and intended use
Rank today's **open** admissions leads by how likely they are to enroll, so a rep calls the right people first,
while the lead is still warm. It supports a human decision (who to call first); it never decides who is *not* served.

**Intended users:** admissions/sales reps and their team lead. **Out of scope:** pricing, discounts, credit or
eligibility decisions, and any use outside the college's own leads.

## Limitations
- Trained on {f['trained_on_rows']:,} leads from a single (synthetic) college CRM export; real data will drift
  (new campaigns, seasonality, new courses) - retrain weekly and watch the holdout PR-AUC.
- `response_time_min` is partly in the rep's control: the model rewards fast follow-up, which is the point, but
  it also means scores for leads nobody has called yet rely on an imputed median.
- Probabilities are only roughly calibrated; use them to **rank**, not as promises.
- Form-text features are simple Hebrew keyword flags; sarcasm, typos or English text are missed.
- `n_contacts` was excluded (leakage); campaign codes were excluded (renamed every quarter).

## Ethical considerations
- **Fairness:** age band and region are features. A low score must never mean "do not call" - every lead still
  gets a call within the SLA; the score only changes the order. Monitor conversion and call rates per age band
  and region for disparities.
- **Privacy:** first names and free text are personal data. Names are used only to personalise the opener and are
  never model features; keep the CRM export out of git (`.gitignore`) and delete raw exports after use.
- **Transparency:** the call list shows the reasons behind each rank (e.g. webinar attended, asked about start date).
- **Human in the loop:** reps record the real outcome; those labels feed the next retraining."""


def write_model_card(f: dict, narrative: str, out_md: Path, mode: str) -> None:
    h, b = f["holdout"], f["baseline"]
    timed = not f["split"].get("policy")
    split_text = (f"time-based: test = leads created on/after {f['split']['cutoff']}" if timed
                  else f["split"]["policy"])
    excluded = "\n".join(f"- `{k}`: {v}" for k, v in f["excluded_from_model"].items())
    out_md.write_text(f"""# Model card - Next Call lead prioritisation

_Narrative written by: {mode}. Metrics and data facts filled in by the run._

| field | value |
|---|---|
| model | `{f['model_name']}` (scikit-learn) |
| task | binary classification: will this lead enroll? (`converted`) |
| artifact | `model.joblib` |
| dataset contract | v{f['contract_version']} (from `{f['source_export']}`, data as of {f['as_of'] or 'n/a - no time column'}) |
| training rows | {f['trained_on_rows']:,} labelled leads, {f['n_features']} features |
| split | {split_text} |

## Metrics ({'time-based' if timed else 'stratified'} holdout)

| metric | model | call in arrival order |
|---|---|---|
| ROC-AUC | {h['roc_auc']} | - |
| PR-AUC | {h['pr_auc']} | - |
| Brier score | {h['brier']} | - |
| capture@20% | {h['capture_at_20pct']:.1%} | {b['capture_at_20pct']:.1%} |
| precision@top10% | {h['precision_at_top10pct']:.1%} | {b['precision_at_top10pct']:.1%} |

Strongest signals: {', '.join(f['top_features'])}.

## Training data
Clean lead table produced by Crew 1 and validated by the contract gate. Excluded columns:
{excluded}

{narrative.strip()}
""", encoding="utf-8")
