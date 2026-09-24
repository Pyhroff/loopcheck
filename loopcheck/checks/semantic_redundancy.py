"""
The opt-in, judgment-requiring counterpart to duplicate_calls: two calls to
the SAME tool with DIFFERENT arguments, where a judge model decides the
second one was chasing a sub-goal the first call's result had already
answered. Needs a Judge (see judge.py) -- with none configured, this check
simply isn't run; every other check in loopcheck stays fully deterministic
and free.

Deliberately bounded: comparing every pair of same-tool calls in a trace is
O(n^2) judge calls, which gets expensive (and slow) fast on a long trace.
`max_pairs` caps how many comparisons a single run will make -- pairs
beyond the cap are silently skipped rather than erroring, since this check
is inherently best-effort (a sample of the risk, not an exhaustive audit).
"""

from __future__ import annotations

from loopcheck.findings import Finding, Severity
from loopcheck.judge import Judge
from loopcheck.trace import Trace

DEFAULT_MAX_PAIRS = 20


def _candidate_pairs(trace: Trace, max_pairs: int) -> list[tuple]:
    by_tool: dict[str, list] = {}
    for step in trace.steps:
        if step.tool_name is None:
            continue
        by_tool.setdefault(step.tool_name, []).append(step)

    pairs = []
    for steps in by_tool.values():
        for i in range(len(steps)):
            for j in range(i + 1, len(steps)):
                a, b = steps[i], steps[j]
                if a.tool_args == b.tool_args:
                    continue  # exact repeat -- duplicate_calls' job, not this check's
                pairs.append((a, b))
    return pairs[:max_pairs]


async def check_semantic_redundancy(
    trace: Trace, judge: Judge, max_pairs: int = DEFAULT_MAX_PAIRS
) -> list[Finding]:
    findings: list[Finding] = []

    for a, b in _candidate_pairs(trace, max_pairs):
        verdict = await judge.compare(
            goal=trace.goal,
            tool_name=a.tool_name,
            args_a=a.tool_args,
            result_a=a.tool_result or "",
            args_b=b.tool_args,
            result_b=b.tool_result or "",
        )
        if not verdict.is_redundant:
            continue

        findings.append(Finding(
            check="semantic_redundancy",
            severity=Severity.MEDIUM,
            title="Semantically redundant tool call (different arguments, same sub-goal)",
            detail=(
                f"Steps {a.index} and {b.index} both called '{a.tool_name}' with "
                f"different arguments ({a.tool_args} vs {b.tool_args}), but the "
                f"judge found step {b.index} pursued a sub-goal step {a.index}'s "
                f"result had already answered: {verdict.reason}"
            ),
            step_indices=[b.index],
            wasted_cost=trace.step_cost(b),
        ))

    return findings
