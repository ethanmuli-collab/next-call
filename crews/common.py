"""Shared pieces for both crews: run context, LLM factory, offline runner."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from crewai import LLM, Crew

from config import LLM_MODEL

log = logging.getLogger("next_call")


@dataclass
class RunContext:
    """Paths a crew may touch, plus results its tools record (numbers never come from the LLM)."""
    run_dir: Path
    raw_path: Path | None = None          # only Crew 1 gets this
    feedback: dict[str, int] | None = None
    results: dict = field(default_factory=dict)

    @property
    def crew1(self) -> Path:
        return self.run_dir / "crew1"

    @property
    def crew2(self) -> Path:
        return self.run_dir / "crew2"


def get_llm(offline: bool) -> LLM:
    """A real LLM online; offline the object is only built (never called)."""
    if offline:
        return LLM(model=LLM_MODEL, api_key="offline-not-used", temperature=0)
    return LLM(model=LLM_MODEL, temperature=0)


def run_offline(crew: Crew) -> list[str]:
    """Offline mode: every agent runs its own tool(s) directly, in task order, no LLM."""
    outputs = []
    for task in crew.tasks:
        for t in task.agent.tools:
            log.info("[offline] %s -> tool '%s'", task.agent.role, t.name)
            outputs.append(t.run())
    return outputs


def run_online(crew: Crew) -> list[str]:
    """Online mode: the LLM agents orchestrate; returns each task's raw text output."""
    result = crew.kickoff()
    return [t.raw for t in result.tasks_output]
