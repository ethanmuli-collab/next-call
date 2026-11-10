"""Render docs/PLAN.md into docs/progress.html (the user's progress page).

PLAN.md is the single source of truth; never edit progress.html by hand.
Run:  python docs/build_progress.py
"""
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

DOCS = Path(__file__).resolve().parent
PLAN, OUT = DOCS / "PLAN.md", DOCS / "progress.html"
DEADLINE = "2026-11-10"

STATUS = {  # code -> (Hebrew label, css class)
    "todo": ("לא התחיל", "todo"),
    "doing": ("בעבודה", "doing"),
    "done": ("בוצע - לא נבדק", "done"),
    "verified": ("בוצע ונבדק", "ok"),
    "blocked": ("חסום", "blocked"),
}


def parse(md: str) -> tuple[list[dict], str, list[str]]:
    phases, next_task, log, section = [], "", [], ""
    for line in md.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            if section.startswith("Phase"):
                phases.append({"title": section, "tasks": []})
            continue
        if section == "המשימה הבאה" and line.strip():
            next_task += line.strip() + " "
        elif section == "יומן" and line.startswith("- "):
            log.append(line[2:])
        elif section.startswith("Phase") and re.match(r"\|\s*T\d", line):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            tid, title, spec, status, check, result, slide = (cells + [""] * 7)[:7]
            phases[-1]["tasks"].append(dict(id=tid, title=title, spec=spec, status=status,
                                            check=check, result=result, slide=slide))
    return phases, next_task.strip(), log


def inline(text: str) -> str:
    """Escape, then turn `code` and **bold** into tags."""
    t = html.escape(text.replace("\\|", "|"))
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)


def render(phases: list[dict], next_task: str, log: list[str]) -> str:
    tasks = [t for p in phases for t in p["tasks"]]
    counts = {k: sum(t["status"] == k for t in tasks) for k in STATUS}
    pct = round(100 * counts["verified"] / len(tasks)) if tasks else 0
    chips = "".join(f'<span class="chip {STATUS[k][1]}">{STATUS[k][0]} · {n}</span>'
                    for k, n in counts.items())
    sections = []
    for p in phases:
        ok = sum(t["status"] == "verified" for t in p["tasks"])
        rows = "".join(
            f'<tr><td class="id">{t["id"]}</td><td>{inline(t["title"])}</td><td>{inline(t["spec"])}</td>'
            f'<td><span class="chip {STATUS.get(t["status"], ("?", "todo"))[1]}">'
            f'{STATUS.get(t["status"], (t["status"], ""))[0]}</span></td>'
            f'<td class="muted">{inline(t["check"])}</td><td>{inline(t["result"])}</td>'
            f'<td class="id">{inline(t["slide"])}</td></tr>'
            for t in p["tasks"])
        sections.append(
            f'<section><h2>{inline(p["title"])} <small>{ok}/{len(p["tasks"])}</small></h2>'
            '<div class="scroll"><table><thead><tr><th>ID</th><th>משימה</th><th>ספק</th><th>סטטוס</th>'
            f'<th>בדיקה</th><th>תוצאה</th><th>שקף</th></tr></thead><tbody>{rows}</tbody></table></div></section>')
    log_html = "".join(f"<li>{inline(item)}</li>" for item in reversed(log))
    return TEMPLATE.format(pct=pct, done=counts["verified"], total=len(tasks), chips=chips,
                           next=inline(next_task), sections="".join(sections), log=log_html,
                           built=datetime.now().strftime("%d.%m.%Y %H:%M"), deadline=DEADLINE)


TEMPLATE = """<!doctype html>
<html lang="he" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Next Call - התקדמות</title>
<style>
:root {{ --bg:#f7f7f5; --card:#fff; --ink:#1d1d1b; --muted:#6b6b66; --line:#e4e3de; --accent:#2f6fed;
  --ok:#1f8a4c; --done:#b7791f; --doing:#2f6fed; --blocked:#c53030; --todo:#8a8a85; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141413; --card:#1e1e1c; --ink:#ecebe6; --muted:#a3a29c;
  --line:#33322f; --accent:#7aa2ff; --ok:#4cc38a; --done:#e0b04f; --doing:#7aa2ff; --blocked:#f07070; --todo:#8f8e88; }} }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.55 system-ui,"Segoe UI",Arial,sans-serif }}
main {{ max-width:1180px; margin:0 auto; padding:24px 16px 48px }}
h1 {{ margin:0 0 4px; font-size:26px }} h2 {{ font-size:17px; margin:0 0 10px }} h2 small {{ color:var(--muted); font-weight:400 }}
.sub {{ color:var(--muted); margin:0 0 20px }}
.card, section {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; margin-bottom:16px }}
.top {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; margin-bottom:16px }}
.top .card {{ margin:0 }} .big {{ font-size:32px; font-weight:700; font-variant-numeric:tabular-nums }}
.bar {{ height:10px; background:var(--line); border-radius:99px; overflow:hidden; margin-top:8px }}
.bar i {{ display:block; height:100%; background:var(--ok); border-radius:99px }}
.label {{ color:var(--muted); font-size:13px }}
.chips {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:8px }}
.chip {{ display:inline-block; padding:2px 9px; border-radius:99px; font-size:12.5px; white-space:nowrap;
  border:1px solid currentColor }}
.chip.ok {{ color:var(--ok) }} .chip.done {{ color:var(--done) }} .chip.doing {{ color:var(--doing) }}
.chip.blocked {{ color:var(--blocked) }} .chip.todo {{ color:var(--todo) }}
.scroll {{ overflow-x:auto }} table {{ width:100%; border-collapse:collapse; min-width:820px }}
th, td {{ text-align:right; padding:8px 6px; border-top:1px solid var(--line); vertical-align:top }}
th {{ color:var(--muted); font-weight:500; font-size:13px; border-top:0 }}
td.id {{ white-space:nowrap; font-variant-numeric:tabular-nums; color:var(--muted) }} td.muted {{ color:var(--muted); font-size:13.5px }}
code {{ font:13px ui-monospace,Consolas,monospace; background:var(--line); padding:0 4px; border-radius:4px; direction:ltr; unicode-bidi:embed }}
ul {{ margin:0; padding-inline-start:20px }} li {{ margin-bottom:4px }}
</style></head><body><main>
<h1>Next Call - התקדמות הפרויקט</h1>
<p class="sub">נבנה מ-PLAN.md · עודכן {built}</p>
<div class="top">
  <div class="card"><div class="label">משימות שנבדקו</div><div class="big">{done}/{total}</div>
    <div class="bar"><i style="width:{pct}%"></i></div></div>
  <div class="card"><div class="label">ימים להגשה (10.11)</div><div class="big" id="days">-</div></div>
  <div class="card"><div class="label">המשימה הבאה</div><div>{next}</div></div>
</div>
<div class="card"><div class="label">סטטוסים</div><div class="chips">{chips}</div></div>
{sections}
<section><h2>יומן</h2><ul>{log}</ul></section>
</main>
<script>
var d = Math.ceil((new Date("{deadline}T23:59:00") - new Date()) / 864e5);
document.getElementById("days").textContent = d > 0 ? d : "היום";
</script></body></html>
"""

if __name__ == "__main__":
    phases, next_task, log = parse(PLAN.read_text(encoding="utf-8"))
    OUT.write_text(render(phases, next_task, log), encoding="utf-8")
    n = sum(len(p["tasks"]) for p in phases)
    print(f"progress.html: {len(phases)} phases, {n} tasks -> {OUT}")
