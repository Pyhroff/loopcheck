"""
A different waste pattern from exact duplicates: the agent hammering the
*same tool* over and over with different arguments each time, never
converging. This is the "agent stuck in a search-refinement spiral" or
"agent retrying a fundamentally broken call with cosmetic tweaks" pattern
-- duplicate_calls.py won't catch it because the arguments genuinely
differ each time, but it's still a real cost signal: N calls to one tool
in a single trace, past a threshold, is worth a human's attention even
when no single pair is an exact repeat.
"""

from __future__ import annotations

from collections import Counter

from loopcheck.findings import Finding, Severity
from loopcheck.trace import Trace

DEFAULT_THRESHOLD = 4


def check_loop_thrash(trace: Trace, threshold: int = DEFAULT_THRESHOLD) -> list[Finding]:
    counts: Counter[str] = Counter()
    indices_by_tool: dict[str, list[int]] = {}

    for step in trace.steps:
        if step.tool_name is None:
            continue
        counts[step.tool_name] += 1
        indices_by_tool.setdefault(step.tool_name, []).append(step.index)

    findings: list[Finding] = []
    for tool_name, count in counts.items():
        if count < threshold:
            continue

        indices = indices_by_tool[tool_name]
        steps_by_index = {s.index: s for s in trace.steps}
        # Cost of everything past the threshold-th call -- the first
        # `threshold` calls are plausibly legitimate iteration; only the
        # excess is charged as waste.
        excess_indices = indices[threshold:]
        wasted_cost = sum(trace.step_cost(steps_by_index[i]) for i in excess_indices)

        findings.append(Finding(
            check="loop_thrash",
            severity=Severity.HIGH if count >= threshold * 2 else Severity.MEDIUM,
            title="Tool called far more than expected for a single trace",
            detail=(
                f"Tool '{tool_name}' was called {count} times in one trace "
                f"(steps {indices}) -- past {threshold} calls to the same "
                f"tool in a single agent run usually means it's stuck "
                f"refining/retrying rather than making progress."
            ),
            step_indices=indices,
            wasted_cost=wasted_cost,
        ))

    return findings
