# Model card - Next Call lead prioritisation

_Narrative written by: offline template. Metrics and data facts filled in by the run._

| field | value |
|---|---|
| model | `hist_gradient_boosting` (scikit-learn) |
| task | binary classification: will this lead enroll? (`converted`) |
| artifact | `model.joblib` |
| dataset contract | v1.0 (from `Lead Scoring.csv`, data as of n/a - no time column) |
| training rows | 9,240 labelled leads, 53 features |
| split | stratified random split, seed 42 |

## Metrics (stratified holdout)

| metric | model | call in arrival order |
|---|---|---|
| ROC-AUC | 0.8843 | - |
| PR-AUC | 0.8359 | - |
| Brier score | 0.1304 | - |
| capture@20% | 45.2% | 19.7% |
| precision@top10% | 96.2% | 37.5% |

Strongest signals: time_on_site_sec, lead_origin=lead_add_form, occupation=working_professional, occupation=unknown, total_visits, specialization=not_selected.

## Training data
Clean lead table produced by Crew 1 and validated by the contract gate. Excluded columns:
- `lead_id`: identifier
- `Tags`: dropped at cleaning - LEAKAGE: written by the sales team after talking to the lead
- `Lead Quality`: dropped at cleaning - LEAKAGE: sales rep's judgement after contact
- `Lead Profile`: dropped at cleaning - LEAKAGE: assigned by sales after contact
- `Last Activity / Last Notable Activity`: dropped at cleaning - LEAKAGE: includes post-contact events
- `Asymmetrique * (4 columns)`: dropped at cleaning - vendor scores computed after engagement, 46% missing
- `Country`: dropped at cleaning - 27% missing and almost a single value
- `How did you hear / What matters most`: dropped at cleaning - mostly blank or the form default 'Select'
- `Do Not Call, Search, Magazine, Newspaper, ... (11 flags)`: dropped at cleaning - constant or near constant

## Purpose and intended use
Rank the leads of an online-course company (X Education, public Kaggle dataset) by how likely they are to become
paying customers, so the sales team calls the most promising leads first. It supports a human decision about call
order; it never decides who is *not* contacted.

**Intended users:** sales reps and their team lead. **Out of scope:** pricing, eligibility or any automated rejection.

## Limitations
- Trained on 9,240 historical leads of one company; the public file has **no timestamp**, so the holdout is a
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
- **Human in the loop:** the score orders the list, a person makes the call and records the outcome.
