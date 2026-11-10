"""Next Call - the CrewAI Flow: Crew 1 -> contract gate -> Crew 2 -> today's call list.

Run:  python flow.py                       (normal weekly export)
      python flow.py --input data/raw/leads_weekly_export_v2.csv   (broken export -> gate stops)
      python flow.py --from-handoff        (re-validate an edited clean_data.csv, then model)
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import traceback
from pathlib import Path

from pydantic import BaseModel, Field

import config  # noqa: F401  (sets CrewAI env flags before crewai is imported)
from config import CALL_LIST_SIZE, CLEAN_EXPORT, CREW1_FILES, CREW2_FILES, is_offline, run_dir_for
from crewai.flow.flow import Flow, listen, router, start  # noqa: E402

from contract.validate import validate  # noqa: E402
from crews.analyst.crew import build_analyst_crew  # noqa: E402
from crews.common import RunContext, get_llm, run_offline, run_online  # noqa: E402
from crews.scientist.crew import build_scientist_crew  # noqa: E402
from tools.contract_tools import load_contract  # noqa: E402
from tools.eda import load_clean, template_insights_narrative, write_insights  # noqa: E402
from tools.model_card import template_model_card_narrative, write_model_card  # noqa: E402
from tools.modeling import template_evaluation_narrative, write_evaluation_report  # noqa: E402
from tools.opening_lines import add_openings  # noqa: E402
from tools.scoring import build_call_list  # noqa: E402

log = logging.getLogger("next_call")


class NextCallState(BaseModel):
    input_path: str = ""
    run_dir: str = ""
    offline: bool = True
    use_feedback: bool = False
    from_handoff: bool = False
    status: str = "pending"          # ok | gate_failed | error
    message: str = ""
    gate: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    narratives: dict = Field(default_factory=dict)
    call_list_rows: int = 0


def _setup_logging(run_dir: Path) -> None:
    log.setLevel(logging.INFO)
    for h in list(log.handlers):
        log.removeHandler(h)
        h.close()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    fh = logging.FileHandler(run_dir / "flow.log", mode="w", encoding="utf-8")
    sh = logging.StreamHandler(sys.stdout)
    for h in (fh, sh):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.propagate = False


def _crew_outputs(crew, ctx: RunContext, offline: bool, needed: list[str]) -> tuple[list[str], str]:
    """Run a crew online (LLM) or offline (tools only). Missing tool results are filled deterministically."""
    if not offline:
        try:
            outs = run_online(crew)
            missing = [k for k in needed if k not in ctx.results]
            if missing:
                log.warning("agents skipped tool(s) for %s; running them directly", missing)
                run_offline(crew)
            return outs, "llm"
        except Exception as exc:
            log.warning("LLM crew failed (%s: %s); falling back to offline tools", type(exc).__name__, exc)
    return run_offline(crew), "template"


class NextCallFlow(Flow[NextCallState]):
    """Crew 1 -> gate -> Crew 2 -> call list. Every step logs; every artifact lands in run_dir."""

    def _ctx(self, crew: int) -> RunContext:
        """A fresh context per crew; only Crew 1 is given the raw export path."""
        return RunContext(run_dir=Path(self.state.run_dir),
                          raw_path=Path(self.state.input_path) if crew == 1 else None)

    @start()
    def prepare(self) -> None:
        run_dir = Path(self.state.run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        stale = ["crew2", "call_list.csv", "call_list.json", "gate_report.json", "run_summary.json"]
        if not self.state.from_handoff:
            stale.append("crew1")
        for name in stale:  # only our own generated outputs, so a run never shows stale results
            p = run_dir / name
            shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
        (run_dir / "crew1").mkdir(exist_ok=True)
        (run_dir / "crew2").mkdir(exist_ok=True)
        _setup_logging(run_dir)
        log.info("=== Next Call flow | input=%s | mode=%s | feedback=%s | from_handoff=%s",
                 Path(self.state.input_path).name, "OFFLINE" if self.state.offline else "LLM",
                 self.state.use_feedback, self.state.from_handoff)

    @listen(prepare)
    def analyst_crew(self) -> None:
        """Crew 1: clean -> EDA -> contract (skipped when re-validating an existing handoff)."""
        if self.state.from_handoff:
            log.info("[crew1] skipped - re-validating the existing handoff in %s", self.state.run_dir)
            return
        try:
            ctx = self._ctx(1)
            if self.state.use_feedback:
                from feedback import training_labels
                ctx.feedback = training_labels()
                log.info("[crew1] %d rep-recorded outcomes will be used as labels", len(ctx.feedback))
            crew = build_analyst_crew(ctx, get_llm(self.state.offline))
            log.info("[crew1] agents: %s", [a.role for a in crew.agents])
            outs, mode = _crew_outputs(crew, ctx, self.state.offline, ["cleaning", "facts", "contract"])
            for step in ctx.results["cleaning"]["steps"]:
                log.info("[crew1/clean] %s", step)
            narrative = outs[1] if mode == "llm" else template_insights_narrative(ctx.results["facts"])
            write_insights(ctx.results["facts"], narrative, ctx.crew1 / "insights.md",
                           "LLM (EDA agent)" if mode == "llm" else "offline template")
            self.state.narratives["crew1"] = mode
            for f in CREW1_FILES:
                log.info("[crew1] artifact %-22s %s", f, "OK" if (ctx.crew1 / f).exists() else "MISSING")
        except Exception as exc:
            self.state.status = "error"
            self.state.message = f"Crew 1 failed: {type(exc).__name__}: {exc}"
            log.error(self.state.message)
            log.debug(traceback.format_exc())

    @router(analyst_crew)
    def contract_gate(self) -> str:
        """Validate clean_data.csv against dataset_contract.json before any modeling."""
        if self.state.status == "error":
            return "gate_failed"
        crew1 = Path(self.state.run_dir) / "crew1"
        data_path, contract_path = crew1 / "clean_data.csv", crew1 / "dataset_contract.json"
        try:
            report = validate(load_clean(data_path), load_contract(contract_path), data_path)
        except FileNotFoundError as exc:
            self.state.status, self.state.message = "error", f"Handoff incomplete: {exc}"
            log.error(self.state.message)
            return "gate_failed"
        self.state.gate = report.to_dict()
        (Path(self.state.run_dir) / "gate_report.json").write_text(
            json.dumps(self.state.gate, ensure_ascii=False, indent=2), encoding="utf-8")
        for line in report.summary().splitlines():
            (log.info if report.passed else log.error)("[gate] %s", line)
        if not report.passed:
            self.state.status, self.state.message = "gate_failed", report.summary()
            return "gate_failed"
        return "gate_passed"

    @listen("gate_failed")
    def stop(self) -> dict:
        log.error("Flow stopped before Crew 2. No features, model or call list were produced.")
        self._write_summary()
        return self.state.model_dump()

    @listen("gate_passed")
    def scientist_crew(self) -> None:
        """Crew 2: features -> train & compare -> model card (reads only the handoff)."""
        try:
            ctx = self._ctx(2)
            crew = build_scientist_crew(ctx, get_llm(self.state.offline))
            log.info("[crew2] agents: %s", [a.role for a in crew.agents])
            outs, mode = _crew_outputs(crew, ctx, self.state.offline, ["features", "evaluation", "card_facts"])
            ev = ctx.results["evaluation"]
            write_evaluation_report(ev, outs[1] if mode == "llm" else template_evaluation_narrative(ev),
                                    ctx.crew2 / "evaluation_report.md",
                                    "LLM (trainer agent)" if mode == "llm" else "offline template")
            facts = ctx.results["card_facts"]
            write_model_card(facts, outs[2] if mode == "llm" else template_model_card_narrative(facts),
                             ctx.crew2 / "model_card.md",
                             "LLM (model card agent)" if mode == "llm" else "offline template")
            self.state.metrics = {"selected_model": ev["selected_model"], "split": ev["split"],
                                  "results": ev["results"]}
            self.state.narratives["crew2"] = mode
            for name, m in ev["results"].items():
                log.info("[crew2/eval] %-24s %s", name, m)
            for f in CREW2_FILES:
                log.info("[crew2] artifact %-22s %s", f, "OK" if (ctx.crew2 / f).exists() else "MISSING")
        except Exception as exc:
            self.state.status = "error"
            self.state.message = f"Crew 2 failed: {type(exc).__name__}: {exc}"
            log.error(self.state.message)

    @listen(scientist_crew)
    def call_list(self) -> dict:
        """Score open leads and publish today's call list with openers."""
        if self.state.status == "error":
            self._write_summary()
            return self.state.model_dump()
        rd = Path(self.state.run_dir)
        cl = build_call_list(rd / "crew1" / "clean_data.csv", rd / "crew1" / "dataset_contract.json",
                             rd / "crew2" / "model.joblib", CALL_LIST_SIZE)
        cl, mode = add_openings(cl, self.state.offline)
        cl.to_csv(rd / "call_list.csv", index=False, encoding="utf-8-sig")
        (rd / "call_list.json").write_text(cl.to_json(orient="records", force_ascii=False, indent=1), encoding="utf-8")
        self.state.call_list_rows = len(cl)
        self.state.narratives["openers"] = mode
        self.state.status = "ok"
        self.state.message = f"Gate passed; model trained; call list with {len(cl)} leads ready."
        log.info("[call-list] %d leads ranked; openers by %s; top lead %s (p=%.2f)", len(cl), mode,
                 cl.iloc[0]["lead_id"] if len(cl) else "-", cl.iloc[0]["p_enroll"] if len(cl) else 0)
        self._write_summary()
        return self.state.model_dump()

    def _write_summary(self) -> None:
        rd = Path(self.state.run_dir)
        files = {f"crew1/{f}": (rd / "crew1" / f).exists() for f in CREW1_FILES}
        files |= {f"crew2/{f}": (rd / "crew2" / f).exists() for f in CREW2_FILES}
        files["call_list.json"] = (rd / "call_list.json").exists()
        summary = self.state.model_dump() | {"artifacts": files}
        for key in ("input_path", "run_dir"):  # repo-relative, so committed summaries carry no local paths
            p = Path(summary[key]).resolve()
            if p.is_relative_to(config.ROOT):
                summary[key] = p.relative_to(config.ROOT).as_posix()
        (rd / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                                             encoding="utf-8")
        log.info("=== status=%s", self.state.status)
        for h in list(log.handlers):  # release flow.log (Windows keeps open files locked)
            log.removeHandler(h)
            h.close()


def run_pipeline(input_path: Path = CLEAN_EXPORT, offline: bool | None = None, use_feedback: bool = False,
                 from_handoff: bool = False, run_dir: Path | None = None) -> dict:
    """Programmatic entry point (used by the app, the webhook-free CLI and the smoke test)."""
    from data.generate_data import ensure_data

    ensure_data()
    input_path = Path(input_path).resolve()
    flow = NextCallFlow()
    flow.kickoff(inputs={"input_path": str(input_path),
                         "run_dir": str(run_dir or run_dir_for(input_path)),
                         "offline": is_offline() if offline is None else offline,
                         "use_feedback": use_feedback, "from_handoff": from_handoff})
    return flow.state.model_dump()


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the Next Call CrewAI Flow")
    ap.add_argument("--input", default=str(CLEAN_EXPORT), help="raw weekly export CSV")
    ap.add_argument("--offline", action="store_true", help="force offline mode (no LLM)")
    ap.add_argument("--feedback", action="store_true", help="use rep-recorded outcomes as extra labels")
    ap.add_argument("--from-handoff", action="store_true", help="skip Crew 1; re-validate existing clean data")
    ap.add_argument("--run-dir", help="where to write the artifacts (default: artifacts/<input file name>)")
    a = ap.parse_args()
    state = run_pipeline(Path(a.input), offline=True if a.offline else None, use_feedback=a.feedback,
                         from_handoff=a.from_handoff, run_dir=Path(a.run_dir).resolve() if a.run_dir else None)
    print("\n" + "=" * 70 + f"\nSTATUS: {state['status']}\n{state['message']}")
    sys.exit(0 if state["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
