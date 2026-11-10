# Next Call - תוכנית עבודה (PLAN)

> **ל-Claude בתחילת כל שיחה:** קרא את הקובץ הזה ואת הסעיפים הרלוונטיים ב-`SPEC.md`.
> עובדים על **משימה אחת** (שורה אחת) בכל פעם, לפי "המשימה הבאה" למטה.

## פרוטוקול לכל משימה
1. סמן את השורה `doing`. פתח branch: `task/<ID>-<slug>` (מהשלב שיש גיט, T1.2 והלאה).
2. בצע רק את מה שבשורה. אם צריך לשנות התנהגות - קודם עדכן את הסעיף ב-`SPEC.md`.
3. הרץ את עמודת "בדיקה". כתוב את התוצאה בפועל בעמודת "תוצאה" (מספרים, לא "עבד").
4. סטטוס: `verified` רק אם הבדיקה רצה ועברה. `done` = בוצע אבל הבדיקה לא רצה / חלקית (כתוב למה).
5. הוסף/עדכן את השקף שבעמודת "שקף" במצגת.
6. שורה ב"יומן" למטה. הרץ `python docs/build_progress.py` (מעדכן את `progress.html`).
7. commit + PR (המשתמש עושה merge). push רק באישור המשתמש.

**סטטוסים:** `todo` לא התחיל · `doing` בעבודה · `done` בוצע, לא נבדק · `verified` בוצע ונבדק · `blocked` חסום

**Python:** `C:\Users\ethan\anaconda3\envs\rag_env\python.exe` · **מצגת:** ראה "קישורים" למטה

## המשימה הבאה
**T5.4** - הגשה ב-Slack (המשתמש): קישור הריפו + המצגת. לפני כן: merge ל-PRs וחזרה אחת על המצגת.

> **שינוי 2026-11-10:** ההגשה מחר בבוקר (11.11). עובדים על כל השלבים בשיחה אחת, branch + PR לכל שלב.
> סדר: בסיס וריפו → ריצת בסיס → LLM → UI → README → מצגת → (אם נשאר זמן) Kaggle.

---

## Phase 0 - תכנון · יעד 01.11
| ID | משימה | ספק | סטטוס | בדיקה | תוצאה | שקף |
|---|---|---|---|---|---|---|
| T0.1 | כתיבת SPEC, PLAN ודף התקדמות | S1-S13 | verified | `build_progress.py` מייצר `progress.html` בלי שגיאה | 6 שלבים, 22 שורות, כל הסטטוסים מוצגים | - |
| T0.2 | שלד מצגת: פתיח, בעיה, הסיפור, ארכיטקטורה | S1, S7 | done | המשתמש פותח את המצגת ובודק שהעברית מימין לשמאל תקינה | פורסמו 6 שקפים. לא נבדק ויזואלית; בשקף 1 יש placeholder `[שם המציג]` | 1-6 |

## Phase 1 - בסיס הריפו · יעד 02.11
| ID | משימה | ספק | סטטוס | בדיקה | תוצאה | שקף |
|---|---|---|---|---|---|---|
| T1.1 | העתקת קוד אב הטיפוס ל-`next_call/` (בלי `__pycache__`), הרצת בדיקות בסיס | S11 | verified | `unittest` 6/6 + `smoke_test.py` עובר מהתיקייה החדשה | unittest 6/6 OK; `SMOKE TEST PASSED`. ריצה ראשונה נפלה פעם אחת על חסימת DLL של pyarrow (Application Control של Windows), ריצה חוזרת עברה | - |
| T1.2 | `git init`, סקירת `.gitignore`, commit ראשון ב-main | S11 | verified | `git status` נקי; אין `.env` / `*.db` ב-`git ls-files` | 37 קבצים ב-commit הראשון; אין `.env`, `*.db`, `data/raw`, `__pycache__`; נוסף `data/kaggle/` ל-`.gitignore` | - |
| T1.3 | ריפו ציבורי ב-GitHub + push (באישור המשתמש) | S12 | verified | הקישור נפתח, README מוצג | https://github.com/ethanmuli-collab/next-call ציבורי, main עלה. ה-push הראשון נחסם כי ב-`.env.example` של אב הטיפוס היה מפתח אמיתי; הקובץ הוחלף ב-`env.example` ריק וההיסטוריה המקומית נוקתה לפני ה-push | 15 |
| T1.4 | ריצת בסיס מתועדת: Flow על export רגיל ועל v2 | S5.4, S7 | verified | רגיל: status=ok, 8 תוצרים · v2: gate_failed עם 4 בעיות | רגיל: status=ok, 8/8 תוצרים + call list 25, LR ROC-AUC 0.793 / PR-AUC 0.392, top 20% תופס 54% מול 22% בסדר הגעה · v2: gate_failed, 4 בעיות, exit code 1, אין תוצרי crew2. מצב offline | 9 |

## Phase 2 - נתונים אמיתיים (Kaggle) · יעד 05.11
| ID | משימה | ספק | סטטוס | בדיקה | תוצאה | שקף |
|---|---|---|---|---|---|---|
| T2.1 | הורדת Leads.csv (המשתמש) ל-`data/kaggle/`, תיעוד מקור ורישיון | S3.1 | verified | מספר שורות ועמודות מודפס; רישיון רשום ב-SPEC S13 | הורד מ-Kaggle (archive.zip, 420KB): 9,240 שורות, 37 עמודות. רישיון: Unknown, ולכן הנתונים לא נכנסים לגיט | 9 |
| T2.2 | פרופיילינג: target, nulls, `Select`, עמודות דליפה, יחידות | S3.1 | verified | דוח פרופיילינג; רשימת דליפה מנומקת ב-SPEC | שיעור המרה 38.5%, `Select` ב-21%-55% מ-4 עמודות, אין חותמת זמן. רשימת הדליפה מנומקת ב-`contract/spec_kaggle.py` (`EXCLUDED_FROM_MODEL`) ונכתבת לחוזה | 9 |
| T2.3 | הפרדת חוזה לפרופילים: `spec_synthetic.py` + `spec_kaggle.py` | S5.1 | verified | unittest קיימים ירוקים + בדיקה חדשה לחוזה kaggle | `contract/spec.py` (synthetic) + `contract/spec_kaggle.py`, נבחרים ב-`get_spec()`. unittest 10/10 (6 קיימות + 4 חדשות) | 9 |
| T2.4 | כלי ניקוי ל-Kaggle (`Select`→null, נרמול קטגוריות) | S4 | verified | השער עובר על הנתונים הנקיים | `tools/cleaning_kaggle.py`: 12 מתוך 37 עמודות, `Select`→`not_selected`, מקורות נדירים→`other`, השלמת חציון. השער עבר: 18 בדיקות | 9 |
| T2.5 | בחירת פרופיל ב-Flow: `--dataset kaggle\|synthetic` | S3, S7 | verified | שתי הריצות status=ok; תיקיות artifacts נפרדות | `--dataset kaggle` → `artifacts/kaggle_lead_scoring/` status=ok, 8 תוצרים; synthetic → `artifacts/leads_weekly_export/` status=ok; smoke test עובר. נבדק גם באפליקציה | 9 |
| T2.6 | צוות 2 על Kaggle: stratified split, 2 מודלים + baseline | S6 | verified | `evaluation_report.md` עם ROC-AUC/PR-AUC/lift; ריצה חוזרת זהה | stratified split (seed 42), 7,392/1,848: HistGradientBoosting ROC-AUC 0.884, PR-AUC 0.836 (נבחר); LR 0.872/0.820; top 20% תופס 45% מול 20% בסדר הרשימה. המדדים זהים בריצה חוזרת ובמצב LLM | 9 |
| T2.7 | הדגמת שבירה ב-Kaggle (שינוי יחידה) + unittest | S5.4 | verified | השער נכשל עם הודעה קריאה; הבדיקה ירוקה | `time_on_site_sec` חולק ב-60 + `--from-handoff`: gate_failed (unit: חציון 4.13 מחוץ ל-100-700 שניות), exit 1, אין תוצרי crew2. `test_seconds_to_minutes_detected` ירוקה | 9 |

## Phase 3 - מצב LLM · יעד 05.11
| ID | משימה | ספק | סטטוס | בדיקה | תוצאה | שקף |
|---|---|---|---|---|---|---|
| T3.1 | ריצה עם `OPENAI_API_KEY` (המשתמש מכניס ל-`.env`) ותיקון תקלות | S10 | verified | `run_summary.json`: narratives = llm בשני הצוותים | ריצה עם gpt-4o-mini עברה בניסיון הראשון: status=ok, narratives crew1=llm, crew2=llm, openers=llm, 8/8 תוצרים. שופר ה-prompt של שורות הפתיחה. הריצה שמורה ב-`artifacts/leads_weekly_export_llm/` (נוסף `--run-dir`) | 8 |
| T3.2 | השוואת LLM מול offline: המספרים זהים, רק הטקסט שונה | S10 | verified | diff של המדדים = 0 | `metrics` ב-`run_summary.json` זהים בין ריצת ה-LLM לריצת ה-offline (השוואת dict מלאה = True) | 8 |

## Phase 4 - אפליקציה ואוטומציה · יעד 07.11
| ID | משימה | ספק | סטטוס | בדיקה | תוצאה | שקף |
|---|---|---|---|---|---|---|
| T4.1 | Streamlit: בחירת פרופיל, מסך כישלון שער, תג מצב | S9 | verified | הרצה ידנית של 3 תרחישים + צילומי מסך | נבדק בדפדפן: ריצה תקינה (4 שלבים ירוקים, KPI, השוואת מודלים), v2 (שער נכשל, 4 כרטיסי בעיה, Crew 2 לא הופעל), כפתור שבירה דקות→שעות (שער נכשל על unit). 3 צילומים ב-`docs/img/`. בחירת פרופיל נדחתה לשלב Kaggle | 13 |
| T4.2 | (אופציונלי) Flask + n8n: רשימת שיחות בבוקר | S9 | todo | `curl /call-list` מחזיר 20 לידים | | 14 |
| T4.3 | (אופציונלי) פריסה ל-Streamlit Cloud | S2 | todo | קישור ציבורי עובד | | 15 |

## Phase 5 - איכות והגשה · יעד 09.11 · הגשה 10.11
| ID | משימה | ספק | סטטוס | בדיקה | תוצאה | שקף |
|---|---|---|---|---|---|---|
| T5.1 | README לריפו: הרצה, ארכיטקטורה, מיפוי לתדריך | S12 | verified | clone נקי לתיקייה זמנית + הרצה לפי ה-README עובדת | clone מ-GitHub + venv חדש + `pip install -r requirements.txt`: `flow.py` status=ok עם 8 תוצרים (הנתונים נוצרו אוטומטית), v2 gate_failed exit 1, unittest 6/6, `SMOKE TEST PASSED` | - |
| T5.2 | מעבר על קריטריוני הקבלה S12, אחד אחד | S12 | verified | כל ה-checkboxes ב-S12 מסומנים עם הוכחה | 5/5 מסומנים ב-SPEC S12 עם ההוכחה לכל אחד | 11 |
| T5.3 | מצגת סופית + תסריט דמו + חזרה | S12 | done | המשתמש מציג פעם אחת מתחילה ועד סוף | המצגת הושלמה: 12 שקפים עם הערות דובר לכל שקף. חזרה של המשתמש עוד לא בוצעה | הכל |
| T5.4 | הגשה ב-Slack: קישור GitHub + מצגת (המשתמש) | S12 | todo | ההודעה נשלחה | | - |

---

## יומן
- 2026-11-01 · T0.1, T0.2 · נכתבו SPEC/PLAN/progress, נפתח שלד המצגת. החלטות: Kaggle + סינתטי, Slides, יחיד, שיחה לכל פיצ'ר.

- 2026-11-10 · T1.1, T1.2 · קוד אב הטיפוס הועתק ל-`next_call/`, בדיקות ירוקות, `git init` ו-commit ראשון. הוחלט: הכול בשיחה אחת, קודם מצב בטוח להגשה ואז Kaggle.
- 2026-11-10 · T1.4 · ריצת בסיס על שני הקבצים, התוצרים נכנסו לריפו. `run_summary.json` שומר עכשיו נתיבים יחסיים לריפו.
- 2026-11-10 · T1.3 · ריפו ציבורי + PR #1. מפתח OpenAI שהיה ב-`.env.example` הוסר לפני שעלה משהו לרשת.
- 2026-11-10 · T4.1 · עיצוב מחדש של `app.py`: פס שלבים, כרטיסי KPI, מסך כישלון שער, כל 8 התוצרים, רשימת שיחות ככרטיסים, כפתור "Break it on purpose".
- 2026-11-10 · T5.1 · README נכתב מחדש ונבדק ב-clone נקי עם סביבה וירטואלית חדשה.
- 2026-11-10 · T3.1, T3.2 · ריצת LLM מלאה, מדדים זהים ל-offline. T5.2, T5.3 · קריטריוני הקבלה סומנו, המצגת הושלמה (11 שקפים).
- 2026-11-10 · Phase 2 (Kaggle) בוצע בסוף היום כפרופיל נתונים שני: חוזה משלו, כלי ניקוי, stratified split, הדגמת שבירה ובדיקות. T4.2/T4.3 (אופציונליים) לא בוצעו.

## קישורים
- ריפו: https://github.com/ethanmuli-collab/next-call
- מצגת (claude.ai Slides, פרטית): https://claude.ai/artifact/2QbU38a5EW65HyfuWbVwDY
  - לעריכה בשיחה חדשה: Artifact `read` על `project/deck.json` ועל `project/slides/<id>.html`, ואז publish לאותו url.
  - שקפים (12): cover · brief · story · architecture · contract · run-ok · kaggle · break · llm · app · repo · done.
  - טקסט עברי עם מילים באנגלית עטוף ב-`&#8235;...&#8236;` (RLE/PDF) כדי שהכיוון יהיה מימין לשמאל.
- תדריך רשמי: `../../Final Project/final_project.html`
