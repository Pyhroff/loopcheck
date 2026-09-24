"""
Regression detection: did the last change to this agent (a prompt tweak, a
model swap, a new tool) make it MORE wasteful, or less? A single `analyze`
run tells you the current state; `compare` tells you whether it got better
or worse, which is the question that actually matters once you're
iterating on an agent rather than looking at it for the first time.

Findings are matched between two runs by a stable fingerprint --
(check, tool, title) -- rather than step_indices, since step count and
positions shift between two runs of "the same" trace even when nothing
meaningful changed. A finding present in `after` with no match in `before`
is a regression (something got worse); one present in `before` with no
match in `after` was resolved (something got better).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loopcheck.findings import Finding


def _fingerprint(f: Finding) -> tuple:
    return (f.check, f.tool, f.title)


@dataclass
class ComparisonResult:
    before_wasted_cost: float
    after_wasted_cost: float
    delta_cost: float
    new_findings: list[Finding] = field(default_factory=list)       # regressions: in after, not before
    resolved_findings: list[Finding] = field(default_factory=list)  # improvements: in before, not after

    @property
    def is_regression(self) -> bool:
        """True if anything got worse: new findings appeared, or wasted
        cost went up, even if some other finding also got resolved."""
        return bool(self.new_findings) or self.delta_cost > 0


def compare_findings(before: list[Finding], after: list[Finding]) -> ComparisonResult:
    before_fp = {_fingerprint(f) for f in before}
    after_fp = {_fingerprint(f) for f in after}

    new_findings = [f for f in after if _fingerprint(f) not in before_fp]
    resolved_findings = [f for f in before if _fingerprint(f) not in after_fp]

    before_cost = sum(f.wasted_cost for f in before)
    after_cost = sum(f.wasted_cost for f in after)

    return ComparisonResult(
        before_wasted_cost=before_cost,
        after_wasted_cost=after_cost,
        delta_cost=after_cost - before_cost,
        new_findings=new_findings,
        resolved_findings=resolved_findings,
    )
