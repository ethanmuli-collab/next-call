# Model card - Next Call lead prioritisation

_Narrative written by: offline template. Metrics and data facts filled in by the run._

| field | value |
|---|---|
| model | `logistic_regression` (scikit-learn) |
| task | binary classification: will this lead enroll? (`converted`) |
| artifact | `model.joblib` |
| dataset contract | v1.0 (from `leads_weekly_export.csv`, data as of 2026-10-25 19:57:00) |
| training rows | 4,857 labelled leads, 38 features |
| split | time-based: test = leads created on/after 2026-08-04 18:55 |

## Metrics (time-based holdout)

| metric | model | call in arrival order |
|---|---|---|
| ROC-AUC | 0.7931 | - |
| PR-AUC | 0.3921 | - |
| Brier score | 0.0901 | - |
| capture@20% | 53.8% | 22.2% |
| precision@top10% | 39.2% | 11.3% |

Strongest signals: txt_asks_start, pages_viewed, source=referral, response_hours_log, webinar_attended, source=facebook_form.

## Training data
Clean lead table produced by Crew 1 and validated by the contract gate. Excluded columns:
- `lead_id`: identifier
- `first_name`: PII - used for the opener only, never as a feature
- `campaign`: high cardinality and renamed every quarter
- `n_contacts`: leakage risk - grows after the outcome is known (converted leads get more calls)

## Purpose and intended use
Rank today's **open** admissions leads by how likely they are to enroll, so a rep calls the right people first,
while the lead is still warm. It supports a human decision (who to call first); it never decides who is *not* served.

**Intended users:** admissions/sales reps and their team lead. **Out of scope:** pricing, discounts, credit or
eligibility decisions, and any use outside the college's own leads.

## Limitations
- Trained on 4,857 leads from a single (synthetic) college CRM export; real data will drift
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
- **Human in the loop:** reps record the real outcome; those labels feed the next retraining.
