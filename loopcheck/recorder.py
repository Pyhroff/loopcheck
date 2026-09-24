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
        self._next_turn = 0

    def record_step(
        self,
        reasoning: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_args: Optional[dict[str, Any]] = None,
        tool_result: Optional[str] = None,
        is_error: bool = False,
        input_tokens: int = 0,
        output_tokens: int = 0,
        turn: Optional[int] = None,
    ) -> Step:
        """Record a single step. If `turn` is omitted, this step gets its own
        fresh turn number (the common case: one model response, one step).
        Pass an explicit `turn` to group several steps under the same
        model-turn -- record_parallel_steps() does this for you."""
        t = turn if turn is not None else self._next_turn
        if turn is None:
            self._next_turn += 1

        step = Step(
            index=len(self.trace.steps),
            turn=t,
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

    def record_parallel_steps(self, calls: list[dict[str, Any]]) -> list[Step]:
        """Record several tool calls that came from ONE model response
        (parallel tool-calling) -- they all share a single turn number, so
        checks and reports can tell this apart from the model looping
        across separate turns. `calls` is a list of record_step()-style
        kwargs dicts, in the order the model requested them."""
        if not calls:
            return []
        t = self._next_turn
        self._next_turn += 1
        return [self.record_step(turn=t, **kwargs) for kwargs in calls]

    def save(self, path: Path) -> None:
        import json
        Path(path).write_text(json.dumps(self.trace.to_dict(), indent=2), encoding="utf-8")
