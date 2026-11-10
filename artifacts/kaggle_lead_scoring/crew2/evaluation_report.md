# Evaluation report - lead conversion model

_Commentary written by: offline template. All numbers computed by the training tool._

## Setup
- Target: `converted` (1 = enrolled). Open leads (no outcome yet) are excluded from training and scored later.
- **Stratified random split, seed 42** (contract split policy; the dataset has no time column): train = 7392 leads, test = 1848 leads.
- Positive rate: train 38.5%, test 38.5%. 53 features.
- Selection rule: highest PR-AUC on the stratified holdout. Winner refit on all 9240 labelled leads -> `model.joblib`.

## Model comparison (stratified holdout)

| model | ROC-AUC | PR-AUC | Brier | log loss | capture@20% | precision@top10% | lift@top10% |
|---|---|---|---|---|---|---|---|
| logistic_regression | 0.8722 | 0.8199 | 0.1386 | 0.4337 | 44.9% | 94.6% | 2.45 |
| hist_gradient_boosting | 0.8843 | 0.8359 | 0.1304 | 0.412 | 45.2% | 96.2% | 2.5 |
| baseline_arrival_order | - | - | - | - | 19.7% | 37.5% | 0.97 |

`capture@20%` = share of all enrolments found if the rep only calls the top 20% of the list.

## Selected model: `hist_gradient_boosting`

### Top features (permutation importance, PR-AUC drop)

| feature | importance |
|---|---|
| time_on_site_sec | 0.1493 |
| lead_origin=lead_add_form | 0.1008 |
| occupation=working_professional | 0.0564 |
| occupation=unknown | 0.0332 |
| total_visits | 0.0303 |
| specialization=not_selected | 0.0151 |
| do_not_email | 0.0095 |
| lead_source=welingak_website | 0.0063 |
| city=not_selected | 0.0047 |
| lead_origin=landing_page_submission | 0.0041 |
| lead_origin=api | 0.0021 |
| pages_per_visit | 0.0018 |

## Commentary

- **hist_gradient_boosting** wins on PR-AUC (0.836); logistic regression ROC-AUC 0.872 vs gradient boosting 0.884.
- Business view: calling the top 20% of leads by score reaches **45%** of the enrolments, versus **20%** when calling in arrival order.
- The strongest signals (permutation importance): time_on_site_sec, lead_origin=lead_add_form, occupation=working_professional, occupation=unknown.
- Recommendation: use the selected model to rank today's open leads; retrain weekly with the outcomes reps record in the app.
