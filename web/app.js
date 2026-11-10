/* Next Call - front end. Plain JS, hash routing, talks to the Flask API in server.py. */
'use strict';

const view = document.getElementById('view');
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const pct = (x) => (x == null ? '-' : Math.round(x * 100) + '%');

async function api(path, opts) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}
const post = (path, body) => api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.remove('show'), 2200);
}

/* ---------- labels ---------- */
const COURSES = { ux_ui: 'UX/UI', ai_developers: 'מפתחי AI', cyber: 'סייבר', fullstack: 'Full Stack', data_analyst: 'דאטה אנליסט', qa_automation: 'QA אוטומציה' };
const SOURCES = { organic_site: 'האתר', referral: 'חבר מביא חבר', facebook_form: 'פייסבוק', webinar: 'וובינר', google_ads: 'גוגל' };
const OUTCOMES = [['enrolled', 'נרשם/ה', ''], ['call_back', 'לחזור אליו/ה', 'wait'], ['no_answer', 'אין מענה', 'wait'], ['not_interested', 'לא מעוניין/ת', 'no']];
const REASONS = [
  [/^new lead \((\d+)h old\)$/, (m) => `ליד חדש, לפני ${m[1]} שעות`],
  [/^asked when the next cohort starts$/, () => 'שאל/ה מתי המחזור הבא'],
  [/^attended a webinar$/, () => 'השתתף/ה בוובינר'],
  [/^referred by a friend$/, () => 'הגיע/ה מהמלצה של חבר'],
  [/^viewed (\d+) pages$/, (m) => `צפה/תה ב-${m[1]} עמודים באתר`],
  [/^asked about price\/financing$/, () => 'שאל/ה על מחיר ומימון'],
  [/^nobody has called yet$/, () => 'עוד לא התקשרו אליו/ה'],
  [/^said 'just browsing'/, () => 'כתב/ה "רק בודק/ת", לקצר'],
];
const reason = (r) => { for (const [re, f] of REASONS) { const m = r.match(re); if (m) return f(m); } return r; };
const age = (h) => (h < 1 ? 'פחות משעה' : h < 48 ? `${Math.round(h)} שעות` : `${Math.round(h / 24)} ימים`);

const SAMPLES = {
  weekly: ['יצוא שבועי מה-CRM', '5,000 לידים של מכללה לקורסי הייטק. הקובץ הרגיל של תחילת השבוע.'],
  weekly_v2: ['יצוא אחרי שדרוג ה-CRM', 'אותו קובץ, אחרי ששם עמודה ויחידת זמן השתנו בלי הודעה. כך נראה קובץ שנעצר.'],
  kaggle: ['נתוני Kaggle: Lead Scoring', '9,240 לידים אמיתיים של חברת קורסים אונליין. מודל ודוחות, בלי רשימת שיחות.'],
};
const RUN_NAMES = { leads_weekly_export: 'יצוא שבועי', leads_weekly_export_v2: 'אחרי שדרוג ה-CRM', leads_weekly_export_llm: 'יצוא שבועי, ריצת LLM', kaggle_lead_scoring: 'Kaggle' };
const runName = (n) => RUN_NAMES[n] || n.replace(/^upload_/, 'העלאה: ');
const MODELS = { logistic_regression: 'Logistic Regression', hist_gradient_boosting: 'Gradient Boosting', baseline_arrival_order: 'סדר הגעה (המצב היום)' };

const STAGES = {
  crew1: ['צוות 1', 'ניקוי וחוזה נתונים', (s) => ({ run: 'מנקה ובודק את הקובץ...', ok: `${s.n ?? 4}/4 תוצרים`, skip: 'דולג: נבדק הקובץ הנקי הקיים', fail: `${s.n ?? 0}/4 תוצרים` })],
  gate: ['בדיקה', 'שער החוזה', (s) => ({ ok: s.checks ? `${s.checks} בדיקות עברו` : 'עבר', fail: s.problems === 1 ? 'נמצאה בעיה אחת' : s.problems ? `${s.problems} בעיות נמצאו` : 'נעצר', blocked: 'לא הגיע לבדיקה' })],
  crew2: ['צוות 2', 'פיצ\'רים ומודל', (s) => ({ run: 'מאמן ומשווה מודלים...', ok: `${s.n ?? 4}/4 תוצרים`, blocked: 'לא הופעל', fail: 'נכשל' })],
  list: ['תוצאה', 'רשימת שיחות', (s) => ({ run: 'מדרג ומנסח פתיחות...', ok: s.rows ? `${s.rows} לידים דורגו` : 'מוכנה', blocked: 'לא נוצרה', none: 'אין לידים פתוחים בקובץ' })],
};
const ISSUES = {
  missing_column: 'עמודה שהחוזה דורש חסרה', unit: 'יחידת המידה השתנתה', range: 'ערכים מחוץ לטווח המותר', dtype: 'סוג הנתונים לא תואם',
  allowed_values: 'ערכים שלא מופיעים בחוזה', null_rate: 'יותר מדי ערכים חסרים', unique: 'מזהים כפולים', row_count: 'מעט מדי שורות',
  target: 'שיעור ההמרה חריג', model_features: 'חסרות עמודות שהמודל צריך', contract_structure: 'החוזה עצמו לא תקין',
  unexpected_column: 'עמודה שלא מופיעה בחוזה', fingerprint: 'הקובץ השתנה אחרי שהחוזה נחתם',
};

/* ---------- shared pieces ---------- */
function stagesHtml(stages) {
  return '<div class="stages">' + stages.map((s) => {
    const [k, t, d] = STAGES[s.key];
    const mark = { ok: '✓', fail: '!', skip: '↷', none: '-' }[s.state] || '';
    return `<div class="stage ${s.state}"><span class="dot" aria-hidden="true">${mark}</span><div class="k">${k}</div><div class="t">${t}</div><div class="d">${d(s)[s.state] || 'ממתין'}</div></div>`;
  }).join('') + '</div>';
}

function issueHtml(e, warn) {
  const col = e.column ? ` <code>${esc(e.column)}</code>` : '';
  return `<div class="issue${warn ? ' warn' : ''}"><h3>${ISSUES[e.check] || esc(e.check)}${col}</h3><p class="raw ltr">${esc(e.message)}</p></div>`;
}

function kpisHtml(d) {
  const m = d.summary.metrics || {}, res = m.results || {}, best = res[m.selected_model] || {}, base = res.baseline_arrival_order || {};
  return `<div class="kpis">
    <div class="kpi"><div class="l">לידים בקובץ הנקי</div><div class="v">${d.rows ? d.rows.toLocaleString() : '-'}</div><div class="s">אחרי ניקוי של צוות 1</div></div>
    <div class="kpi"><div class="l">בדיקות בשער</div><div class="v">${d.summary.gate?.checks_run ?? '-'}</div><div class="s">כולן עברו לפני האימון</div></div>
    <div class="kpi"><div class="l">ROC-AUC</div><div class="v">${best.roc_auc?.toFixed(3) ?? '-'}</div><div class="s ltr">${MODELS[m.selected_model] || ''}</div></div>
    <div class="kpi"><div class="l">הרשמות ב-20% הראשונים</div><div class="v">${pct(best.capture_at_20pct)}</div><div class="s">מול ${pct(base.capture_at_20pct)} בסדר הגעה</div></div>
  </div>`;
}

/* What happened in a run, in the rep's words. `where` = 'import' | 'system'. */
function resultHtml(d, error) {
  const s = d.summary;
  if (error || !s.status) return `<div class="banner fail"><div><h2>הריצה לא הושלמה</h2><p class="ltr">${esc(error || 'no summary was written')}</p></div></div>`;
  if (s.status === 'ok') {
    const hasList = s.call_list_rows > 0;
    return `<div class="banner ok"><div><h2>${hasList ? `הרשימה מוכנה: ${s.call_list_rows} לידים מדורגים` : 'הקובץ עבר את כל הבדיקות והמודל אומן'}</h2>
      <p>${hasList ? 'הקובץ עבר את שער החוזה, המודל אומן, ולכל ליד יש משפט פתיחה.' : 'בקובץ הזה כל הלידים כבר סגורים, ולכן אין רשימת שיחות.'}</p></div>
      ${hasList ? '<a class="btn primary" href="#/today">לרשימת השיחות</a>' : ''}</div>${kpisHtml(d)}`;
  }
  if (s.status === 'gate_failed') {
    const g = s.gate || {};
    return `<div class="banner fail"><div><h2>עצרנו את הקובץ לפני שהגיע למודל</h2>
      <p>${(g.errors || []).length === 1 ? 'נמצאה בעיה אחת' : `נמצאו ${(g.errors || []).length} בעיות`} בנתונים. לא אומן מודל ולא נוצרה רשימה, כדי שאף נציג לא יעבוד לפי דירוג שגוי.</p></div></div>
      ${(g.errors || []).map((e) => issueHtml(e)).join('')}${(g.warnings || []).map((e) => issueHtml(e, true)).join('')}`;
  }
  return `<div class="banner fail"><div><h2>לא הצלחנו לקרוא את הקובץ</h2><p>ודאו שזה יצוא לידים מה-CRM במבנה הרגיל.</p><p class="ltr">${esc(s.message)}</p></div></div>`;
}

/* Start a run, show live stages in `box`, resolve with the finished job. */
async function watchRun(box, startPath, body) {
  if (startPath) await post(startPath, body);
  let shown = null, job;
  for (;;) {
    job = await api('/api/job');
    if (job.state !== 'running') break;
    shown = job.detail.stages;
    box.innerHTML = stagesHtml(shown);
    await sleep(600);
  }
  // fast (offline) runs finish in ~2s: reveal the stages one by one so the flow is still readable
  const final = job.detail.stages;
  shown = shown || final.map((s) => ({ key: s.key, state: 'wait' }));
  for (let i = 0; i < final.length; i++) {
    if (shown[i].state === final[i].state) continue;
    if (!['blocked', 'none'].includes(final[i].state)) { shown[i] = { key: final[i].key, state: 'run' }; box.innerHTML = stagesHtml(shown); await sleep(450); }
    shown[i] = final[i];
    box.innerHTML = stagesHtml(shown);
  }
  return job;
}

/* ---------- home ---------- */
async function viewHome() {
  const c = await api('/api/calls');
  const top = c.leads.slice(0, 3).map((l) => `<a class="mini" href="#/today"><span class="rk">${l.rank}</span>
      <span><div class="nm">${esc(l.first_name)} · ${esc(COURSES[l.course_interest] || l.course_interest)}</div>
      <div class="sub">${esc(l.reasons.split('; ').map(reason).join(' · '))}</div></span><span class="pc">${pct(l.p_enroll)}</span></a>`).join('');
  view.innerHTML = `
  <section class="hero">
    <div>
      <p class="eyebrow">למוקדי רישום של מכללות וקורסים</p>
      <h1>למי מתקשרים עכשיו?</h1>
      <p class="lead">מעלים את קובץ הלידים מה-CRM, ומקבלים רשימת שיחות מדורגת לפי הסיכוי להירשם, עם משפט פתיחה לכל ליד.</p>
      <div class="cta"><a class="btn primary" href="#/today">לרשימת השיחות של היום</a><a class="btn" href="#/import">העלאת קובץ לידים</a></div>
    </div>
    <div class="preview" aria-label="תצוגה מקדימה של הרשימה">
      <div class="preview-head"><span>השיחות של היום</span><span>${c.leads.length ? c.leads.length + ' לידים' : ''}</span></div>
      ${top || '<p class="sub" style="padding:18px 4px;color:#B9C2D6">עוד אין רשימה. מעלים קובץ, והיא מופיעה כאן.</p>'}
    </div>
  </section>
  <h2 class="section-title">איך זה עובד</h2>
  <section class="how">
    <div class="card"><div class="n">01</div><h3>מעלים</h3><p>גוררים את קובץ ה-CSV השבועי מה-CRM.</p></div>
    <div class="card"><div class="n">02</div><h3>בודקים</h3><p>הקובץ מנוקה ונבדק מול חוזה נתונים. קובץ שגוי נעצר כאן.</p></div>
    <div class="card"><div class="n">03</div><h3>מדרגים</h3><p>מודל מדרג כל ליד פתוח לפי הסיכוי להירשם ולפי כמה הוא טרי.</p></div>
    <div class="card"><div class="n">04</div><h3>מתקשרים</h3><p>עוברים על הרשימה מלמעלה ומסמנים מה קרה בכל שיחה.</p></div>
  </section>
  ${c.capture ? `<h2 class="section-title">מה זה נותן</h2>
  <section class="proof">
    <div class="stat dark"><div class="v">${pct(c.capture)}</div><div class="l">מההרשמות נמצאות ב-20% הראשונים של הרשימה, מול ${pct(c.baseline)} כשמתקשרים לפי סדר הגעה</div></div>
    <div class="stat"><div class="v">${c.checks}</div><div class="l">בדיקות אוטומטיות עובר כל קובץ לפני שמודל רואה אותו</div></div>
    <div class="stat"><div class="v">${(c.rows || 0).toLocaleString()}</div><div class="l">לידים בקובץ האחרון, נוקו ודורגו בהרצה אחת</div></div>
  </section>` : ''}`;
}

/* ---------- today ---------- */
let filter = 'all';
async function viewToday() {
  const c = await api('/api/calls');
  if (!c.leads.length) {
    const stopped = c.status === 'gate_failed';
    view.innerHTML = `<div class="card empty"><h2>${stopped ? 'אין רשימה: הקובץ האחרון נעצר בבדיקה' : 'עוד אין רשימת שיחות'}</h2>
      <p>${stopped ? 'הנתונים לא עמדו בחוזה, ולכן לא נוצרה רשימה. עדיף בלי רשימה מאשר רשימה שגויה.' : 'מעלים קובץ לידים, והרשימה המדורגת מופיעה כאן.'}</p>
      <a class="btn primary" href="#/import">${stopped ? 'להריץ קובץ תקין' : 'העלאת קובץ לידים'}</a></div>`;
    return;
  }
  const draw = () => {
    const done = c.leads.filter((l) => l.outcome).length;
    const rows = c.leads.filter((l) => filter === 'all' || (filter === 'open') === !l.outcome);
    view.innerHTML = `
    <div class="page-head">
      <div><h1>${c.leads.length} שיחות להיום</h1><p>מדורגות לפי הסיכוי להירשם ולפי כמה הליד טרי. מתחילים מלמעלה.</p></div>
      <div class="progress"><strong>${done} מתוך ${c.leads.length} טופלו</strong><div class="bar"><i style="width:${(done / c.leads.length) * 100}%"></i></div></div>
    </div>
    <div class="chips" role="tablist">
      ${[['all', 'הכול'], ['open', 'ממתינים לשיחה'], ['done', 'טופלו']].map(([k, t]) => `<button class="chip${filter === k ? ' on' : ''}" data-filter="${k}" type="button">${t}</button>`).join('')}
    </div>
    ${rows.map(leadHtml).join('') || '<div class="card empty"><p>אין לידים בתצוגה הזו.</p></div>'}`;
  };
  view.onclick = async (ev) => {
    const f = ev.target.closest('[data-filter]');
    if (f) { filter = f.dataset.filter; draw(); return; }
    const cp = ev.target.closest('[data-copy]');
    if (cp) {
      const lead = c.leads.find((l) => l.lead_id === cp.dataset.copy);
      try { await navigator.clipboard.writeText(lead.opening_line); toast('משפט הפתיחה הועתק'); } catch { toast('ההעתקה נחסמה בדפדפן'); }
      return;
    }
    const oc = ev.target.closest('[data-outcome]');
    if (oc) {
      const lead = c.leads.find((l) => l.lead_id === oc.dataset.lead);
      try {
        const next = lead.outcome === oc.dataset.outcome ? '' : oc.dataset.outcome; // second click = undo
        await post('/api/outcome', { lead_id: lead.lead_id, outcome: next });
        lead.outcome = next || null;
        draw();
        toast(next ? `נשמר: ${lead.first_name}` : 'הסימון בוטל');
      } catch (e) { toast('השמירה נכשלה: ' + e.message); }
    }
  };
  draw();
}

function leadHtml(l) {
  const oc = OUTCOMES.find((o) => o[0] === l.outcome);
  return `<article class="card lead-card${l.outcome ? ' done' : ''}">
    <div class="rank">${l.rank}</div>
    <div>
      <div class="lead-name">${esc(l.first_name)}${oc ? `<span class="tag ${oc[2]}">${oc[1]}</span>` : ''}</div>
      <div class="lead-meta">${esc(COURSES[l.course_interest] || l.course_interest)} · הגיע/ה דרך ${esc(SOURCES[l.source] || l.source)} · לפני ${age(l.age_hours)} · <span dir="ltr">${esc(l.lead_id)}</span></div>
      <div class="why">${l.reasons.split('; ').map((r) => `<span>${esc(reason(r))}</span>`).join('')}</div>
      <div class="opener"><button class="copy" data-copy="${esc(l.lead_id)}" type="button">העתקה</button>
        <div class="say">${esc(l.opening_line)}</div>
        ${l.form_text ? `<div class="wrote">מה נכתב בטופס: ${esc(l.form_text)}</div>` : ''}</div>
      <div class="outcomes"><span class="lbl">מה קרה בשיחה?</span>
        ${OUTCOMES.map(([k, t]) => `<button class="oc${l.outcome === k ? ' on' : ''}" data-outcome="${k}" data-lead="${esc(l.lead_id)}" type="button">${t}</button>`).join('')}</div>
    </div>
    <div class="score"><div class="ring" style="--p:${Math.round(l.p_enroll * 100)}"><b>${pct(l.p_enroll)}</b></div><div class="ring-l">סיכוי להירשם</div></div>
  </article>`;
}

/* ---------- import ---------- */
async function viewImport() {
  const ov = await api('/api/overview');
  let picked = null;
  const chooser = () => {
    const cards = ov.sources.map((s) => {
      const [t, d] = SAMPLES[s.key] || [s.file.replace(/^upload_/, ''), 'קובץ שהועלה מהמחשב.'];
      return `<button class="card sample${picked === s.key ? ' on' : ''}" data-pick="${esc(s.key)}" type="button"><h3>${esc(t)}</h3><p>${esc(d)}</p><div class="f">${esc(s.file)}</div></button>`;
    }).join('');
    view.innerHTML = `
    <div class="page-head"><div><h1>קובץ לידים חדש</h1><p>מעלים את היצוא מה-CRM. הקובץ נבדק, המודל מתאמן, והרשימה של היום מתעדכנת.</p></div></div>
    <label class="drop" id="drop"><input type="file" id="file" accept=".csv" hidden>
      <h3>גוררים לכאן קובץ CSV, או לוחצים לבחירה</h3><p class="muted">יצוא לידים מה-CRM, עד 30MB</p></label>
    <h2 class="section-title">או מתחילים מקובץ לדוגמה</h2>
    <div class="samples">${cards}</div>
    <div class="runbar">
      <button class="btn primary" id="go" type="button" ${picked ? '' : 'disabled'}>הפעלה</button>
      <label class="check"><input type="checkbox" id="retrain"> ללמוד גם מתוצאות השיחות שהנציגים סימנו</label>
    </div>`;
    const drop = document.getElementById('drop');
    const send = async (file) => {
      if (!file) return;
      const fd = new FormData();
      fd.append('file', file);
      try { const r = await api('/api/upload', { method: 'POST', body: fd }); run(r.key, file.name); } catch (e) { toast('ההעלאה נכשלה: ' + e.message); }
    };
    document.getElementById('file').onchange = (e) => send(e.target.files[0]);
    drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('over'); };
    drop.ondragleave = () => drop.classList.remove('over');
    drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove('over'); send(e.dataTransfer.files[0]); };
  };
  const run = async (key, label, attach) => {
    const retrain = document.getElementById('retrain')?.checked || false;
    view.onclick = null;
    view.innerHTML = `<div class="page-head"><div><h1>בודקים ומדרגים</h1><p>${esc(label)}</p></div></div>
      <div id="stages">${stagesHtml(Object.keys(STAGES).map((k) => ({ key: k, state: 'wait' })))}</div><div id="result"></div>`;
    try {
      const job = await watchRun(document.getElementById('stages'), attach ? null : '/api/run', { source: key, retrain });
      document.getElementById('result').innerHTML = resultHtml(job.detail, job.error) +
        `<div class="runbar"><a class="btn" href="#/system/${esc(job.detail.name)}">מה קרה מאחורי הקלעים</a><button class="btn" id="again" type="button">קובץ אחר</button></div>`;
      document.getElementById('again').onclick = () => viewImport();
    } catch (e) {
      document.getElementById('result').innerHTML = `<div class="banner fail"><div><h2>הריצה לא התחילה</h2><p class="ltr">${esc(e.message)}</p></div></div>`;
    }
  };
  if (ov.job === 'running') { run(null, 'ריצה שכבר התחילה', true); return; }
  view.onclick = (ev) => {
    const p = ev.target.closest('[data-pick]');
    if (p) { picked = p.dataset.pick; chooser(); return; }
    if (ev.target.id === 'go' && picked) {
      const s = ov.sources.find((x) => x.key === picked);
      run(picked, (SAMPLES[picked] || [s.file])[0]);
    }
  };
  chooser();
}

/* ---------- system ---------- */
async function viewSystem(name) {
  const list = await api('/api/runs');
  if (!list.runs.length) {
    view.innerHTML = '<div class="card empty"><h2>עוד לא הייתה ריצה</h2><p>מעלים קובץ, וכל מה שנוצר בדרך מופיע כאן.</p><a class="btn primary" href="#/import">העלאת קובץ לידים</a></div>';
    return;
  }
  const current = list.runs.find((r) => r.name === name) ? name : list.active;
  const d = await api('/api/runs/' + encodeURIComponent(current));
  const s = d.summary, m = s.metrics || {}, res = m.results || {};
  const table = Object.keys(res).length ? `<h2 class="section-title">השוואת מודלים</h2>
    <table class="t"><tr><th>מודל</th><th>ROC-AUC</th><th>PR-AUC</th><th>הרשמות ב-20% הראשונים</th><th>Lift ב-10% הראשונים</th></tr>
    ${Object.entries(res).map(([k, r]) => `<tr class="${k === m.selected_model ? 'sel' : ''}"><td>${esc(MODELS[k] || k)}${k === m.selected_model ? ' ★' : ''}</td>
      <td>${r.roc_auc?.toFixed(3) ?? '-'}</td><td>${r.pr_auc?.toFixed(3) ?? '-'}</td>
      <td><div class="hbar${k.startsWith('baseline') ? ' base' : ''}"><i style="width:${(r.capture_at_20pct || 0) * 160}px"></i>${pct(r.capture_at_20pct)}</div></td>
      <td>${r.lift_at_top10pct?.toFixed(2) ?? '-'}</td></tr>`).join('')}</table>
    <p class="muted" style="margin-top:8px">★ המודל שנבחר. ${m.split?.policy ? 'חלוקה אקראית שכבתית עם seed קבוע.' : 'חלוקה לפי זמן: המודל נבחן על הלידים החדשים ביותר.'}</p>` : '';
  const fileBtn = (f) => `<button class="file" data-file="${f}" type="button" ${d.files[f] ? '' : 'disabled'}><span>${f}</span><span class="st">${d.files[f] ? '✓' : '✗'}</span></button>`;
  const crew1 = ['clean_data.csv', 'eda_report.html', 'insights.md', 'dataset_contract.json'];
  const crew2 = ['features.csv', 'model.joblib', 'evaluation_report.md', 'model_card.md'];
  const who = s.narratives && Object.keys(s.narratives).length
    ? `הטקסטים בריצה הזו נכתבו ב${Object.values(s.narratives).includes('llm') ? 'סוכני LLM' : 'תבניות (מצב offline)'}. המספרים תמיד מגיעים מהכלים.` : '';
  view.innerHTML = `
  <div class="page-head"><div><h1>מאחורי הקלעים</h1><p>שני צוותי סוכנים וחוזה נתונים ביניהם. כאן רואים מה כל צוות ייצר, ומה השער בדק.</p></div></div>
  <div class="chips">${list.runs.map((r) => `<a class="chip${r.name === current ? ' on' : ''}" href="#/system/${esc(r.name)}" style="text-decoration:none">${esc(runName(r.name))}</a>`).join('')}</div>
  <div id="stages">${stagesHtml(d.stages)}</div>
  <div id="result">${resultHtml(d).replace(/<a class="btn primary" href="#\/today">.*?<\/a>/, '')}</div>
  ${table}
  <h2 class="section-title">התוצרים של הריצה</h2>
  <div class="files-h">צוות 1 · Data Analyst</div><div class="files">${crew1.map(fileBtn).join('')}</div>
  <div class="files-h">צוות 2 · Data Scientist</div><div class="files">${crew2.map(fileBtn).join('')}</div>
  <div class="files-h">ה-Flow</div><div class="files">${['gate_report.json', 'run_summary.json', 'flow.log'].map(fileBtn).join('')}</div>
  ${who ? `<p class="muted" style="margin-top:12px">${who}</p>` : ''}
  ${d.source ? `<h2 class="section-title">בדיקת עמידות</h2>
  <div class="card lab"><div><strong>מה קורה כשמישהו משנה יחידת מידה בלי להודיע?</strong>
    <p>הכפתור מחלק ב-60 עמודת זמן אחת בקובץ הנקי, בלי לשנות את שמה, ומריץ שוב את ה-Flow מנקודת המסירה. "הרצה מחדש" מחזירה את הקובץ המקורי.</p></div>
    <span class="cta"><button class="btn danger" id="break" type="button" ${d.can_break ? '' : 'disabled'}>שינוי יחידה והרצה</button>
    <button class="btn" id="rerun" type="button">הרצה מחדש</button></span></div>` : ''}
  <details class="log"><summary>יומן הריצה</summary><pre>${esc(d.log || 'no log')}</pre></details>`;

  view.onclick = async (ev) => {
    const f = ev.target.closest('[data-file]');
    if (f && !f.disabled) { openFile(current, f.dataset.file); return; }
    const act = ev.target.id === 'break' ? '/api/break' : ev.target.id === 'rerun' ? '/api/run' : null;
    if (!act) return;
    document.querySelectorAll('#break,#rerun').forEach((b) => { b.disabled = true; });
    document.getElementById('result').innerHTML = '';
    window.scrollTo({ top: 0, behavior: 'smooth' });
    try { await watchRun(document.getElementById('stages'), act, { source: d.source }); } catch (e) { toast(e.message); }
    viewSystem(current);
  };
}

/* ---------- artifact viewer ---------- */
function md(src) {
  const inline = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>').replace(/^_(.+)_$/, '<em>$1</em>');
  const out = [];
  let inList = false, table = [];
  const flushList = () => { if (inList) { out.push('</ul>'); inList = false; } };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^\s*\|[\s:|-]+\|\s*$/.test(r)).map((r) => r.trim().replace(/^\||\|$/g, '').split('|'));
    out.push('<table>' + rows.map((r, i) => '<tr>' + r.map((c) => `<${i ? 'td' : 'th'}>${inline(c.trim())}</${i ? 'td' : 'th'}>`).join('') + '</tr>').join('') + '</table>');
    table = [];
  };
  for (const line of src.split(/\r?\n/)) {
    if (/^\s*\|/.test(line)) { flushList(); table.push(line); continue; }
    flushTable();
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)/))) { flushList(); out.push(`<h${m[1].length + 1}>${inline(m[2])}</h${m[1].length + 1}>`); }
    else if ((m = line.match(/^\s*[-*]\s+(.*)/))) { if (!inList) { out.push('<ul>'); inList = true; } out.push(`<li>${inline(m[1])}</li>`); }
    else if (!line.trim()) flushList();
    else { flushList(); out.push(`<p>${inline(line)}</p>`); }
  }
  flushList(); flushTable();
  return out.join('');
}

async function openFile(run, name) {
  const url = `/api/runs/${encodeURIComponent(run)}/file/${encodeURIComponent(name)}`;
  const dlg = document.getElementById('viewer'), body = document.getElementById('viewer-body');
  document.getElementById('viewer-title').textContent = name;
  document.getElementById('viewer-dl').href = url + '?raw=1';
  if (name.endsWith('.joblib')) { window.location.href = url; return; }
  body.className = 'viewer-body';
  body.innerHTML = '';
  dlg.showModal();
  if (name.endsWith('.html')) { body.innerHTML = `<iframe src="${url}" title="${esc(name)}" sandbox></iframe>`; return; }
  try {
    const r = await api(url);
    if (r.kind === 'table') {
      body.innerHTML = `<p class="muted" style="margin-bottom:10px">${r.total.toLocaleString()} rows × ${r.columns.length} columns (first ${r.rows.length} shown)</p>
        <table><tr>${r.columns.map((c) => `<th>${esc(c)}</th>`).join('')}</tr>${r.rows.map((row) => '<tr>' + row.map((c) => `<td>${esc(c)}</td>`).join('') + '</tr>').join('')}</table>`;
    } else if (r.kind === 'markdown') { body.className = 'viewer-body md'; body.innerHTML = md(r.text); }
    else {
      let text = r.text;
      if (name.endsWith('.json')) { try { text = JSON.stringify(JSON.parse(text), null, 2); } catch { /* shown as is */ } }
      body.innerHTML = `<pre>${esc(text)}</pre>`;
    }
  } catch (e) { body.innerHTML = `<p>${esc(e.message)}</p>`; }
}
document.getElementById('viewer-close').onclick = () => document.getElementById('viewer').close();
document.getElementById('viewer').addEventListener('click', (e) => { if (e.target.id === 'viewer') e.target.close(); });

/* ---------- router ---------- */
async function route() {
  const [, page = '', arg] = location.hash.split('/');
  document.querySelectorAll('[data-nav]').forEach((a) => a.classList.toggle('on', a.dataset.nav === page));
  view.onclick = null;
  view.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
  try {
    if (page === 'today') await viewToday();
    else if (page === 'import') await viewImport();
    else if (page === 'system') await viewSystem(arg);
    else await viewHome();
  } catch (e) {
    view.innerHTML = `<div class="card empty"><h2>משהו השתבש</h2><p class="ltr">${esc(e.message)}</p><button class="btn" type="button" onclick="location.reload()">ניסיון נוסף</button></div>`;
  }
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', route);
api('/api/overview').then((ov) => {
  const el = document.getElementById('mode');
  el.textContent = ov.mode === 'llm' ? 'סוכני LLM פעילים' : 'מצב offline';
  el.className = 'mode ' + ov.mode;
  el.hidden = false;
}).catch(() => {});
route();
