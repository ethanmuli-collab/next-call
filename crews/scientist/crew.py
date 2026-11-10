"""Crew 2 - Data Scientist crew: feature engineer, model trainer, model card writer.

Its tools only ever open crew1/clean_data.csv and crew1/dataset_contract.json -
never the raw export (RunContext.raw_path is None for this crew).
"""
from __future__ import annotations

import json

from crewai import LLM, Agent, Crew, Process, Task
from crewai.tools import tool

from crews.common import RunContext
from tools.contract_tools import load_contract
from tools.features import engineer_features
from tools.model_card import model_card_facts
from tools.modeling import train_and_compare


def make_tools(ctx: RunContext) -> dict:
    clean_csv = ctx.crew1 / "clean_data.csv"
    contract_json = ctx.crew1 / "dataset_contract.json"
    features_csv = ctx.crew2 / "features.csv"

    @tool("engineer_features")
    def features_tool() -> str:
        """Build the feature table from clean_data.csv using only what dataset_contract.json declares
        (one-hot of allowed values, log response time, time-of-day, Hebrew intent keywords). Writes features.csv."""
        ctx.results["features"] = engineer_features(clean_csv, contract_json, features_csv)
        return json.dumps(ctx.results["features"], ensure_ascii=False)

    @tool("train_and_compare_models")
    def train_tool() -> str:
        """Train logistic regression and gradient boosting on the split the contract prescribes, compare them
        against calling in arrival order, save the winner to model.joblib and return all metrics as JSON."""
        ctx.results["evaluation"] = train_and_compare(features_csv, ctx.crew2 / "model.joblib",
                                                      load_contract(contract_json))
        return json.dumps(ctx.results["evaluation"], ensure_ascii=False)

    @tool("get_model_card_facts")
    def card_tool() -> str:
        """Return the verified facts (metrics, data, exclusions) the model card must be based on."""
        ctx.results["card_facts"] = model_card_facts(ctx.results["evaluation"], load_contract(contract_json),
                                                     ctx.results["features"])
        return json.dumps(ctx.results["card_facts"], ensure_ascii=False, default=str)

    return {"features": features_tool, "train": train_tool, "card": card_tool}


def build_scientist_crew(ctx: RunContext, llm: LLM) -> Crew:
    t = make_tools(ctx)
    fe = Agent(role="Feature Engineer", llm=llm, tools=[t["features"]], verbose=False,
               goal="Create model-ready features using only the dataset contract.",
               backstory="You never touch raw data; if it is not in the contract, you do not assume it.")
    trainer = Agent(role="Model Trainer & Evaluator", llm=llm, tools=[t["train"]], verbose=False,
                    goal="Pick the model that puts the most enrolments at the top of the call list.",
                    backstory="You compare models honestly on a time-based holdout and against today's process.")
    writer = Agent(role="Model Card Writer", llm=llm, tools=[t["card"]], verbose=False,
                   goal="Document purpose, limits and ethics of the model for reps and managers.",
                   backstory="You write clear, honest model cards and never overstate a metric.")
    tasks = [
        Task(agent=fe, description="Call engineer_features once and summarise the feature set in 3 bullets.",
             expected_output="3 markdown bullets."),
        Task(agent=trainer, description="Call train_and_compare_models once. Using ONLY its numbers, write 4 "
                                        "markdown bullets: which model won and why, the business gain vs arrival "
                                        "order (capture@20%), the strongest signals, and a recommendation.",
             expected_output="4 markdown bullets."),
        Task(agent=writer, description="Call get_model_card_facts once. Write these model-card sections in markdown "
                                       "(## headings): Purpose and intended use; Limitations; Ethical considerations "
                                       "(fairness across age band/region, privacy of names and form text, human in "
                                       "the loop). Do not repeat the metrics table.",
             expected_output="Three markdown sections with ## headings."),
    ]
    return Crew(agents=[fe, trainer, writer], tasks=tasks, process=Process.sequential, verbose=False)
