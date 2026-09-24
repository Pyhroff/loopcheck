"""
The pluggable judge interface behind `semantic_redundancy` (v0.4+).

duplicate_calls (v0.1) only catches EXACT repeats -- same tool, same args.
It can't see a model that calls `web_search(query="chip shortage causes")`
and later `web_search(query="reasons for the 2026 chip shortage")` -- two
different queries chasing the same already-answered sub-goal. Catching
that requires judgment about meaning, which is exactly what a deterministic
check can't do without false positives. So it's opt-in and pluggable:
`Judge` is a small Protocol, not tied to any one provider, and the
deterministic checks (v0.1-v0.3) keep working with zero setup regardless
of whether a judge is configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class JudgeVerdict:
    is_redundant: bool
    reason: str


@runtime_checkable
class Judge(Protocol):
    async def compare(
        self,
        goal: str,
        tool_name: str,
        args_a: dict[str, Any],
        result_a: str,
        args_b: dict[str, Any],
        result_b: str,
    ) -> JudgeVerdict:
        """Given the trace's overall goal and two calls to the SAME tool
        with DIFFERENT arguments (exact-duplicate args are already handled
        by duplicate_calls and never reach a Judge), decide whether the
        second call was redundant -- i.e. it pursued a sub-goal the first
        call's result had already answered."""
        ...
