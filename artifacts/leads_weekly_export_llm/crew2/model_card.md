# Model card - Next Call lead prioritisation

_Narrative written by: LLM (model card agent). Metrics and data facts filled in by the run._

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
The logistic regression model is designed to prioritize calls to leads based on their likelihood of enrollment in courses. It utilizes 38 model-ready features derived from a dataset that includes indicators for the time of creation, source of leads, course interests, and user engagement. The model aims to maximize enrollment potential by effectively identifying the most promising leads, thereby improving the efficiency of the call list.

## Limitations
While the logistic regression model demonstrates strong performance with a PR-AUC of 0.3921 and captures 53.85% of enrollments at the top 20% of the call list, it is important to note its limitations. The model is trained on a dataset with a positive rate of 13.02% and tested on a slightly lower positive rate of 12.04%. Additionally, certain features such as lead ID and first names are excluded to protect personally identifiable information (PII), which may limit the model's ability to leverage all available data. The model's performance may also vary across different age bands and regions, and it should be used with caution in diverse contexts.

## Ethical considerations
The development and deployment of the logistic regression model adhere to ethical standards, particularly concerning fairness and privacy. The model is designed to avoid bias across different age bands and regions, ensuring equitable treatment of all leads. Privacy is prioritized by excluding PII such as lead IDs and first names from the model's features. Furthermore, a human-in-the-loop approach is recommended for critical decisions, allowing for oversight and intervention when necessary to ensure ethical outcomes in lead prioritization and engagement.
