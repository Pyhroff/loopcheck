"""
A real gap left open by duplicate_calls' own design, documented in its
docstring: "a retry after an error on the same call is often legitimate."
That assumption is right for the *first* retry -- transient network
blips, rate limits, a tool that briefly errors and then works -- so
duplicate_calls deliberately never counts a repeat that follows an error
as waste. But it's wrong once the identical (tool, args) call has already
failed two or more times: nothing about the call changed between
attempts, so if it was going to succeed on a plain retry, it already
would have. A third identical attempt at a call that's failed twice with
zero changes to the arguments is almost never "still legitimately
retrying" -- it's the agent stuck hammering a call that has a systematic
problem (bad args, a permission it doesn't have, a tool that's actually
down), and every attempt past the second is pure wasted cost that
duplicate_calls' success-gated logic can never see, and that loop_thrash
often misses too since its default threshold (4) is tuned for thrashing
across *varying* arguments, not a tight failure loop that can rack up
real cost at 2-3 repeats.

Deliberately deterministic and conservative for the same reason as
duplicate_calls: exact (tool, args) signature match only, and the first
failure is never counted as waste -- only the identical attempts that
follow it once the "maybe it's transient" benefit of the doubt has
already been used up once.
"""

from __future__ import annotations

from collections import defaultdict

from loopcheck.findings import Finding, Severity
from loopcheck.trace import Trace

DEFAULT_MIN_FAILURES = 2


def check_stale_retry(trace: Trace, min_failures: int = DEFAULT_MIN_FAILURES) -> list[Finding]:
    error_indices_by_sig: dict[tuple, list[int]] = defaultdict(list)

    for step in trace.steps:
        sig = step.call_signature()
        if sig is None or not step.is_error:
            continue
        error_indices_by_sig[sig].append(step.index)

    findings: list[Finding] = []
    steps_by_index = {s.index: s for s in trace.steps}

    for sig, error_indices in error_indices_by_sig.items():
        if len(error_indices) < min_failures:
            continue

        # The first failure is the legitimate "try it and see" attempt --
        # only the repeats after that, once the call has already proven it
        # fails with these exact arguments, count as waste.
        wasted_indices = error_indices[1:]
        wasted_cost = sum(trace.step_cost(steps_by_index[i]) for i in wasted_indices)

        tool_name, args_tuple = sig
        findings.append(Finding(
            check="stale_retry",
            severity=Severity.HIGH if len(error_indices) >= min_failures * 2 else Severity.MEDIUM,
            title="Identical failing call retried with no changes",
            tool=tool_name,
            detail=(
                f"Tool '{tool_name}' failed with the exact same arguments "
                f"{dict(args_tuple)} at steps {error_indices} -- {len(error_indices)} "
                f"identical attempts, none of which changed anything about the "
                f"call. A retry after one failure can be a legitimate transient "
                f"blip, but retrying the identical failing call again past that "
                f"point means the failure is systematic, not transient -- every "
                f"attempt past the first is wasted cost on a call that was never "
                f"going to succeed unchanged."
            ),
            step_indices=wasted_indices,
            wasted_cost=wasted_cost,
        ))

    return findings
