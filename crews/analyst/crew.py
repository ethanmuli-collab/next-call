"""Crew 1 - Data Analyst crew: ingest/clean agent, EDA agent, contract agent."""
from __future__ import annotations

import json

from crewai import LLM, Agent, Crew, Process, Task
from crewai.tools import tool

from crews.common import RunContext
from tools.cleaning import clean_leads
from tools.contract_tools import build_contract
from tools.eda import build_eda_report


def make_tools(ctx: RunContext) -> dict:
    """CrewAI tools bound to this run's paths (the LLM cannot point them elsewhere)."""
    clean_csv = ctx.crew1 / "clean_data.csv"

    @tool("clean_leads_export")
    def clean_tool() -> str:
        """Ingest the raw weekly CRM lead export, normalise spellings, remove duplicates, fix glitches
        and write clean_data.csv. Returns a JSON cleaning log."""
        ctx.results["cleaning"] = clean_leads(ctx.raw_path, clean_csv, ctx.feedback)
        return json.dumps(ctx.results["cleaning"], ensure_ascii=False)

    @tool("build_eda_report")
    def eda_tool() -> str:
        """Compute descriptive statistics and conversion rates, draw charts into eda_report.html and
        return the computed facts as JSON. Quote only these numbers."""
        ctx.results["facts"] = build_eda_report(clean_csv, ctx.crew1 / "eda_report.html")
        return json.dumps(ctx.results["facts"], ensure_ascii=False)

    @tool("publish_dataset_contract")
    def contract_tool() -> str:
        """Write dataset_contract.json (schema, allowed values, units, ranges, assumptions, observed
        profile) for clean_data.csv and return a short JSON summary of it."""
        c = build_contract(clean_csv, ctx.crew1 / "dataset_contract.json", ctx.raw_path.name)
        ctx.results["contract"] = c
        cols = {k: (v["observed"] if isinstance(v["observed"], str) else "ok") for k, v in c["columns"].items()}
        return json.dumps({"row_count": c["row_count"], "as_of": c["as_of"], "columns": cols,
                           "model_features": c["model_features"]}, ensure_ascii=False)

    return {"clean": clean_tool, "eda": eda_tool, "contract": contract_tool}


def build_analyst_crew(ctx: RunContext, llm: LLM) -> Crew:
    """Three agents, three sequential tasks; each agent owns exactly one deterministic tool."""
    t = make_tools(ctx)
    cleaner = Agent(role="Ingest & Cleaning Analyst", llm=llm, tools=[t["clean"]], verbose=False,
                    goal="Turn the raw weekly lead export into a trustworthy clean table.",
                    backstory="You have cleaned CRM exports for years and never guess what a renamed column means.")
    eda = Agent(role="EDA & Insights Analyst", llm=llm, tools=[t["eda"]], verbose=False,
                goal="Explain to the admissions manager who converts, from which channel, and how fast to call.",
                backstory="You turn numbers into decisions and never invent a figure the tool did not return.")
    contract = Agent(role="Data Contract Owner", llm=llm, tools=[t["contract"]], verbose=False,
                     goal="Publish the dataset contract the modeling crew must honour.",
                     backstory="You write the interface between the analyst and data-science teams.")
    tasks = [
        Task(agent=cleaner, description="Call the clean_leads_export tool once, then report what was cleaned and any "
                                        "WARNING about missing or unknown columns.",
             expected_output="A short bullet list of cleaning steps and warnings."),
        Task(agent=eda, description="Call the build_eda_report tool once. Using ONLY numbers it returns, write a "
                                    "business summary for an admissions manager: 4-6 markdown bullets (speed to "
                                    "lead, channels, webinar effect, courses) and one recommendation.",
             expected_output="4-6 markdown bullets plus a one-line recommendation."),
        Task(agent=contract, description="Call the publish_dataset_contract tool once. Then list, in 3 bullets, the "
                                         "assumptions the modeling crew must respect and any column marked missing.",
             expected_output="3 markdown bullets."),
    ]
    return Crew(agents=[cleaner, eda, contract], tasks=tasks, process=Process.sequential, verbose=False)
