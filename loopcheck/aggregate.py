"""
`analyze` answers "is this one run wasteful." `compare` answers "did my
last change make it better or worse." `aggregate` answers the third
question that only shows up once you have a pile of traces: across
everything this agent has done recently, where is the money actually
going -- which check fires most, which tool is the worst offender, which
runs were the worst outliers. A CI-gated single-run check can be green on
every individual run while the agent is still bleeding money in aggregate
across a fleet of runs; this is the rollup that catches that.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loopcheck.findings import Finding
from loopcheck.trace import Trace


@dataclass
class AggregateResult:
    trace_count: int
    total_cost: float
    total_wasted_cost: float
    traces_with_findings: int
    findings_by_check: dict[str, int] = field(default_factory=dict)
    findings_by_tool: dict[str, int] = field(default_factory=dict)
    worst_traces: list[tuple[str, float]] = field(default_factory=list)  # (label, wasted_cost), desc, wasted>0 only

    @property
    def wasted_pct(self) -> float:
        return (self.total_wasted_cost / self.total_cost * 100) if self.total_cost else 0.0


def aggregate(
    entries: list[tuple[str, Trace, list[Finding]]],
    top_n: int = 5,
) -> AggregateResult:
    """`entries` is (label, trace, findings) for each trace already
    checked -- aggregate() doesn't run checks itself, so it works
    identically whether the caller ran deterministic-only checks or
    included a judge."""
    total_cost = 0.0
    total_wasted = 0.0
    traces_with_findings = 0
    findings_by_check: dict[str, int] = {}
    findings_by_tool: dict[str, int] = {}
    per_trace_waste: list[tuple[str, float]] = []

    for label, trace, findings in entries:
        wasted = sum(f.wasted_cost for f in findings)
        total_cost += trace.total_cost()
        total_wasted += wasted
        if findings:
            traces_with_findings += 1
        for f in findings:
            findings_by_check[f.check] = findings_by_check.get(f.check, 0) + 1
            if f.tool:
                findings_by_tool[f.tool] = findings_by_tool.get(f.tool, 0) + 1
        per_trace_waste.append((label, wasted))

    worst_traces = [w for w in sorted(per_trace_waste, key=lambda x: x[1], reverse=True) if w[1] > 0][:top_n]

    return AggregateResult(
        trace_count=len(entries),
        total_cost=total_cost,
        total_wasted_cost=total_wasted,
        traces_with_findings=traces_with_findings,
        findings_by_check=findings_by_check,
        findings_by_tool=findings_by_tool,
        worst_traces=worst_traces,
    )
