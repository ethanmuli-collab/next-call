# Evaluation report - lead conversion model

_Commentary written by: offline template. All numbers computed by the training tool._

## Setup
- Target: `converted` (1 = enrolled). Open leads (no outcome yet) are excluded from training and scored later.
- **Time-based split** (contract split policy): train = 3885 leads created before 2026-08-04 18:55, test = 972 newest labelled leads.
- Positive rate: train 13.0%, test 12.0%. 38 features.
- Selection rule: highest PR-AUC on the time-based holdout. Winner refit on all 4857 labelled leads -> `model.joblib`.

## Model comparison (time-based holdout)

| model | ROC-AUC | PR-AUC | Brier | log loss | capture@20% | precision@top10% | lift@top10% |
|---|---|---|---|---|---|---|---|
| logistic_regression | 0.7931 | 0.3921 | 0.0901 | 0.3046 | 53.8% | 39.2% | 3.25 |
| hist_gradient_boosting | 0.742 | 0.3274 | 0.0972 | 0.332 | 49.6% | 37.1% | 3.08 |
| baseline_arrival_order | - | - | - | - | 22.2% | 11.3% | 0.94 |

`capture@20%` = share of all enrolments found if the rep only calls the top 20% of the list.

## Selected model: `logistic_regression`

### Top features (permutation importance, PR-AUC drop)

| feature | importance |
|---|---|
| txt_asks_start | 0.0866 |
| pages_viewed | 0.0634 |
| source=referral | 0.0515 |
| response_hours_log | 0.0496 |
| webinar_attended | 0.0348 |
| source=facebook_form | 0.0137 |
| txt_just_browsing | 0.0102 |
| txt_asks_price | 0.0091 |
| course_interest=cyber | 0.0051 |
| source=webinar | 0.0031 |
| region=jerusalem | 0.0022 |
| age_band=35-44 | 0.0022 |

## Commentary

- **logistic_regression** wins on PR-AUC (0.392); logistic regression ROC-AUC 0.793 vs gradient boosting 0.742.
- Business view: calling the top 20% of leads by score reaches **54%** of the enrolments, versus **22%** when calling in arrival order.
- The strongest signals (permutation importance): txt_asks_start, pages_viewed, source=referral, response_hours_log.
- Recommendation: use the selected model to rank today's open leads; retrain weekly with the outcomes reps record in the app.
