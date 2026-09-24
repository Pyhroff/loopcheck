"""
TraceRecorder -- the piece that turns "hand-write your trace JSON" into
"drop three lines into your existing loop." It's the shared core that every
framework adapter (openai_adapter.py, anthropic_adapter.py, ...) builds on:
an adapter's job is only to translate one SDK's response shape into a
record_step() call, never to know about Trace/Step internals directly.

Usage in a real loop:

    rec = TraceRecorder(agent_name="research-bot", goal=user_goal, model="gpt-4o-mini")
    while True:
        response = client.chat.completions.create(...)
        step = record_openai_step(rec, response, tool_result=result, is_error=err)
        if step.tool_name is None:
            break
    rec.save("trace.json")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from loopcheck.trace import Step, Trace


class TraceRecorder:
    def __init__(
        self,
        agent_name: str,
        goal: str,
        model: Optional[str] = None,
        input_cost_per_1k: float = 0.0,
        output_cost_per_1k: float = 0.0,
    ) -> None:
        self.trace = Trace(
            agent_name=agent_name,
            goal=goal,
            model=model,
            input_cost_per_1k=input_cost_per_1k,
            output_cost_per_1k=output_cost_per_1k,
        )

    def record_step(
        self,
        reasoning: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_args: Optional[dict[str, Any]] = None,
        tool_result: Optional[str] = None,
        is_error: bool = False,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> Step:
        step = Step(
            index=len(self.trace.steps),
            reasoning=reasoning,
            tool_name=tool_name,
            tool_args=tool_args or {},
            tool_result=tool_result,
            is_error=is_error,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self.trace.steps.append(step)
        return step

    def save(self, path: Path) -> None:
        import json
        Path(path).write_text(json.dumps(self.trace.to_dict(), indent=2), encoding="utf-8")
