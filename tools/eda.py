"""EDA tool (Crew 1): descriptive stats, charts -> eda_report.html, facts -> insights.md."""
from __future__ import annotations

import base64
import html
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

BAR = "#2a78d6"   # single-series colour (reference palette slot 1)
INK = "#52514e"   # secondary text
SURFACE = "#fcfcfb"
RT_BINS = [-0.1, 60, 240, 1440, 4320, float("inf")]
RT_LABELS = ["< 1h", "1-4h", "4-24h", "1-3 days", "> 3 days"]


def load_clean(path: Path) -> pd.DataFrame:
    """Read clean_data.csv with proper types."""
    df = pd.read_csv(path, encoding="utf-8", keep_default_na=True)
    if "created_at" in df:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    if "form_text" in df:
        df["form_text"] = df["form_text"].fillna("")
    return df


def _rate_by(df: pd.DataFrame, col: str) -> pd.DataFrame:
    lab = df[df["converted"].notna()]
    g = lab.groupby(col, observed=True)["converted"].agg(["mean", "count"]).rename(
        columns={"mean": "conversion_rate", "count": "leads"})
    return g.sort_values("conversion_rate", ascending=False)


def compute_facts(df: pd.DataFrame) -> dict:
    """Deterministic numbers the narrative is allowed to quote."""
    lab = df[df["converted"].notna()] if "converted" in df else df.iloc[0:0]
    f: dict = {"rows": int(len(df)), "labelled": int(len(lab)),
               "open_leads": int(df["converted"].isna().sum()) if "converted" in df else 0,
               "conversion_rate": round(float(lab["converted"].mean()), 4) if len(lab) else None}
    if "created_at" in df:
        f["date_from"] = str(df["created_at"].min().date())
        f["date_to"] = str(df["created_at"].max().date())
        f["leads_per_month"] = round(len(df) / max(1, (df["created_at"].max() - df["created_at"].min()).days / 30.4), 1)
    for col in ["source", "course_interest", "age_band", "region", "webinar_attended"]:
        if col in df and len(lab):
            r = _rate_by(df, col)
            f[f"rate_by_{col}"] = {str(k): round(float(v), 4) for k, v in r["conversion_rate"].items()}
    if "response_time_min" in df and len(lab):
        b = pd.cut(lab["response_time_min"], RT_BINS, labels=RT_LABELS)
        f["rate_by_response_time"] = {str(k): round(float(v), 4) for k, v in
                                      lab.groupby(b, observed=True)["converted"].mean().items()}
        f["median_response_time_min"] = float(df["response_time_min"].median())
    if "pages_viewed" in df:
        f["median_pages_viewed"] = float(df["pages_viewed"].median())
    nulls = df.isna().mean()
    f["null_fraction"] = {k: round(float(v), 4) for k, v in nulls[nulls > 0].items()}
    return f


def _chart(series: pd.Series, title: str, pct: bool = True, horizontal: bool = True) -> str:
    """One-series bar chart as a base64 PNG <img>."""
    height = 0.45 * max(3, len(series)) + 0.8 if horizontal else 3.0
    fig, ax = plt.subplots(figsize=(6.4 if horizontal else 8.0, height), dpi=110)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    labels = [str(i) for i in series.index]
    if horizontal:
        ax.barh(labels[::-1], series.values[::-1], color=BAR, height=0.6)
        ax.xaxis.grid(True, color="#e6e5e0", linewidth=0.8)
        for y, v in enumerate(series.values[::-1]):
            ax.text(v, y, f" {v:.1%}" if pct else f" {v:,.0f}", va="center", fontsize=8, color=INK)
        if pct:
            ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    else:
        ax.bar(range(len(labels)), series.values, color=BAR, width=0.8)
        ax.yaxis.grid(True, color="#e6e5e0", linewidth=0.8)
        step = max(1, len(labels) // 8)  # a readable handful of date ticks
        ax.set_xticks(range(0, len(labels), step), labels[::step])
        ax.tick_params(axis="x", labelrotation=30, labelsize=7)
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c9c8c2")
    ax.tick_params(colors=INK, labelsize=8)
    ax.set_title(title, loc="left", fontsize=10, color="#0b0b0b")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=SURFACE)
    plt.close(fig)
    return f'<img alt="{html.escape(title)}" src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"/>'


def build_eda_report(clean_path: Path, out_html: Path) -> dict:
    """Write eda_report.html (charts + tables) and return the facts dict."""
    df = load_clean(clean_path)
    facts = compute_facts(df)
    sections: list[str] = []
    lab = df[df["converted"].notna()] if "converted" in df else df.iloc[0:0]
    for col, title in [("source", "Conversion rate by lead source"),
                       ("course_interest", "Conversion rate by course"),
                       ("age_band", "Conversion rate by age band"),
                       ("webinar_attended", "Conversion rate: webinar attended (1) vs not (0)")]:
        if col in df and len(lab):
            r = _rate_by(df, col)
            sections.append(f"<h2>{title}</h2>{_chart(r['conversion_rate'], title)}"
                            + r.style.format({"conversion_rate": "{:.1%}"}).to_html())
    if "response_time_min" in df and len(lab):
        b = pd.cut(lab["response_time_min"], RT_BINS, labels=RT_LABELS)
        r = lab.groupby(b, observed=True)["converted"].agg(conversion_rate="mean", leads="count")
        sections.append("<h2>Speed to lead: conversion by time to first call</h2>"
                        + _chart(r["conversion_rate"], "Conversion by time to first call")
                        + r.style.format({"conversion_rate": "{:.1%}"}).to_html())
    if "created_at" in df:
        weekly = df.set_index("created_at").resample("W")["lead_id"].count()
        weekly.index = weekly.index.strftime("%Y-%m-%d")
        sections.append("<h2>Leads per week</h2>" + _chart(weekly, "Leads per week", pct=False, horizontal=False))
    num = df.select_dtypes("number")
    desc = num.describe().T.round(2).to_html(classes="t")
    nulls = df.isna().mean().rename("null_fraction").to_frame().style.format("{:.1%}").to_html()
    cats = "".join(f"<h3>{c}</h3>" + df[c].value_counts().head(10).to_frame().to_html()
                   for c in ["source", "course_interest", "age_band", "region"] if c in df)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>EDA - leads</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;background:{SURFACE};color:#0b0b0b;max-width:900px;margin:24px auto;padding:0 16px}}
table{{border-collapse:collapse;font-size:13px;margin:8px 0 20px}}td,th{{border-bottom:1px solid #e6e5e0;padding:4px 10px;text-align:right}}
h2{{margin-top:32px;font-size:18px}}img{{max-width:100%}} .kpi{{display:inline-block;margin:0 24px 8px 0}} .kpi b{{font-size:22px;display:block}}</style></head><body>
<h1>Exploratory data analysis - admissions leads</h1>
<p>Source file: clean_data.csv &middot; {facts['rows']:,} leads &middot; {facts.get('date_from', '?')} to {facts.get('date_to', '?')}</p>
<div><span class="kpi"><b>{facts['rows']:,}</b>leads</span><span class="kpi"><b>{facts['open_leads']:,}</b>open (no outcome yet)</span>
<span class="kpi"><b>{(facts['conversion_rate'] or 0):.1%}</b>conversion (closed leads)</span>
<span class="kpi"><b>{facts.get('leads_per_month', 0):,.0f}</b>leads / month</span></div>
{''.join(sections)}
<h2>Descriptive statistics (numeric)</h2>{desc}
<h2>Missing values</h2>{nulls}
<h2>Top categories</h2>{cats}
</body></html>"""
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(page, encoding="utf-8")
    return facts


def _pct(d: dict, key: str) -> str:
    v = d.get(key)
    return f"{v:.1%}" if isinstance(v, (int, float)) else "n/a"


def template_insights_narrative(facts: dict) -> str:
    """Offline business summary built only from computed facts."""
    lines = [f"- We received **{facts['rows']:,} leads** ({facts.get('leads_per_month', 0):.0f}/month); "
             f"**{_pct(facts, 'conversion_rate')}** of closed leads enrolled. "
             f"**{facts['open_leads']} leads are still open** and are today's call candidates."]
    rt = facts.get("rate_by_response_time", {})
    if rt:
        first, last = next(iter(rt.items())), list(rt.items())[-1]
        lines.append(f"- **Speed to lead matters most:** leads called within {first[0]} convert at {first[1]:.1%} "
                     f"vs {last[1]:.1%} when the first call comes after {last[0].replace('> ', '')}.")
    src = facts.get("rate_by_source", {})
    if src:
        best, worst = next(iter(src.items())), list(src.items())[-1]
        lines.append(f"- **Channel quality differs:** {best[0]} leads convert at {best[1]:.1%}, "
                     f"{worst[0]} at {worst[1]:.1%} - volume is not value.")
    web = facts.get("rate_by_webinar_attended", {})
    if "1" in web and "0" in web:
        lines.append(f"- **Webinar attendees** convert at {web['1']:.1%} vs {web['0']:.1%} for non-attendees.")
    crs = facts.get("rate_by_course_interest", {})
    if crs:
        top = next(iter(crs.items()))
        lines.append(f"- Highest-converting course interest: **{top[0]}** ({top[1]:.1%}).")
    lines.append("- **Recommendation:** stop calling in arrival order. Call the newest high-probability leads "
                 "first, within the first hours, and open with what they wrote in the form.")
    return "\n".join(lines)


def write_insights(facts: dict, narrative: str, out_md: Path, mode: str) -> None:
    """insights.md = business narrative + the facts table it was built from."""
    rows = [f"| {k} | {v} |" for k, v in facts.items() if not isinstance(v, dict)]
    rate_tables = []
    for k, v in facts.items():
        if isinstance(v, dict) and k.startswith("rate_by_"):
            rate_tables.append(f"\n**{k.replace('_', ' ')}**: " + ", ".join(f"{a} {b:.1%}" for a, b in v.items()))
    out_md.write_text(
        f"# Insights - who converts and when\n\n_Narrative written by: {mode}. Numbers computed by the EDA tool._\n\n"
        f"## Business summary\n\n{narrative.strip()}\n\n## Facts used\n\n| fact | value |\n|---|---|\n"
        + "\n".join(rows) + "\n" + "\n".join(rate_tables) + "\n\nFull charts: `eda_report.html`.\n",
        encoding="utf-8")
