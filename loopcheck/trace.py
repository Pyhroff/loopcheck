"""
The trace schema -- loopcheck's core idea is that it doesn't care what
framework produced your agent loop (raw OpenAI/Anthropic/Groq tool-calling,
LangChain, a hand-rolled ReAct loop, whatever). If you can describe the loop
as a flat, ordered list of steps, loopcheck can audit it. No OpenTelemetry
collector, no SDK integration, no framework adapter required for v0.1 --
just a JSON file.

A Step is one iteration of the agent's loop: what it reasoned (optional --
not every framework surfaces this), which tool it called (or None if it
gave a final answer), with what arguments, and what came back.

`turn` (v0.3+) distinguishes the model-turn a step belongs to from its flat
`index`: a single model response can request several tool calls at once
(parallel tool-calling), which loopcheck records as several Steps with
distinct `index` values but the same `turn` -- so a trace stays a flat,
easy-to-read list, while checks and reports can still tell "the model asked
for 3 things at once" apart from "the model looped 3 times."
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Step:
    index: int
    turn: int = 0                        # which model-turn this step belongs to (v0.3+; see module docstring)
    reasoning: Optional[str] = None      # the model's stated plan/thought for this step, if captured
    tool_name: Optional[str] = None      # None means this step was the final answer, not a tool call
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: Optional[str] = None
    is_error: bool = False
    input_tokens: int = 0
    output_tokens: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Step":
        return cls(
            index=d["index"],
            turn=d.get("turn", d["index"]),
            reasoning=d.get("reasoning"),
            tool_name=d.get("tool_name"),
            tool_args=d.get("tool_args", {}),
            tool_result=d.get("tool_result"),
            is_error=d.get("is_error", False),
            input_tokens=d.get("input_tokens", 0),
            output_tokens=d.get("output_tokens", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "turn": self.turn,
            "reasoning": self.reasoning,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "tool_result": self.tool_result,
            "is_error": self.is_error,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }

    def call_signature(self) -> Optional[tuple]:
        """A hashable fingerprint of (tool, args) for duplicate-call detection.
        None for steps that didn't call a tool."""
        if self.tool_name is None:
            return None
        return (self.tool_name, tuple(sorted(self.tool_args.items())))


@dataclass
class Trace:
    agent_name: str
    goal: str
    steps: list[Step] = field(default_factory=list)
    model: Optional[str] = None
    # USD per 1K tokens, so cost estimates are meaningful without needing a live pricing API
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Trace":
        return cls(
            agent_name=d.get("agent_name", "unknown-agent"),
            goal=d.get("goal", ""),
            steps=[Step.from_dict(s) for s in d.get("steps", [])],
            model=d.get("model"),
            input_cost_per_1k=d.get("input_cost_per_1k", 0.0),
            output_cost_per_1k=d.get("output_cost_per_1k", 0.0),
        )

    @classmethod
    def load(cls, path: Path) -> "Trace":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "model": self.model,
            "input_cost_per_1k": self.input_cost_per_1k,
            "output_cost_per_1k": self.output_cost_per_1k,
        }

    def total_cost(self) -> float:
        total_in = sum(s.input_tokens for s in self.steps)
        total_out = sum(s.output_tokens for s in self.steps)
        return (total_in / 1000) * self.input_cost_per_1k + (total_out / 1000) * self.output_cost_per_1k

    def step_cost(self, step: Step) -> float:
        return (step.input_tokens / 1000) * self.input_cost_per_1k + (step.output_tokens / 1000) * self.output_cost_per_1k
