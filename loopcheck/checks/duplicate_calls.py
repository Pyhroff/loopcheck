"""
The simplest, highest-confidence waste signal: the agent called the exact
same tool with the exact same arguments more than once in a single trace.
Unlike a retry after an error (which is often legitimate), a repeat of a
call that already succeeded is close to always pure waste -- the agent
either forgot it already has the answer, or is stuck in a loop.

Deliberately conservative: this only flags *exact* (tool, args) repeats.
Near-duplicates (same intent, slightly different args) are a judgment call
better suited to an LLM-judge check later, not this deterministic one --
keeping this check deterministic means it's free, instant, and has zero
false-positive risk from model variance.
"""

from __future__ import annotations

from collections import defaultdict

from loopcheck.findings import Finding, Severity
from loopcheck.trace import Trace


def check_duplicate_calls(trace: Trace) -> list[Finding]:
    seen: dict[tuple, list[int]] = defaultdict(list)

    for step in trace.steps:
        sig = step.call_signature()
        if sig is None:
            continue
        # A repeat immediately after an error on the *same* call is a retry,
        # not waste -- only count repeats of calls that previously succeeded.
        seen[sig].append(step.index)

    findings: list[Finding] = []
    for sig, indices in seen.items():
        if len(indices) < 2:
            continue

        # Was the first occurrence an error? If every prior occurrence up to
        # a given repeat was an error, that repeat is a legitimate retry and
        # doesn't count as waste on its own -- but a repeat AFTER a
        # successful call is always waste, since the agent already has the
        # answer.
        steps_by_index = {s.index: s for s in trace.steps}
        wasted_indices = []
        seen_success = False
        for idx in indices:
            step = steps_by_index[idx]
            if seen_success:
                wasted_indices.append(idx)
            if not step.is_error:
                seen_success = True

        if not wasted_indices:
            continue

        tool_name, args_tuple = sig
        wasted_cost = sum(trace.step_cost(steps_by_index[i]) for i in wasted_indices)

        findings.append(Finding(
            check="duplicate_calls",
            severity=Severity.HIGH if len(wasted_indices) >= 2 else Severity.MEDIUM,
            title="Repeated tool call with identical arguments",
            detail=(
                f"Tool '{tool_name}' was called with the same arguments "
                f"{dict(args_tuple)} at steps {indices}, after already "
                f"succeeding earlier in the trace. Repeat call(s) at "
                f"{wasted_indices} produced no new information."
            ),
            step_indices=wasted_indices,
            wasted_cost=wasted_cost,
        ))

    return findings
