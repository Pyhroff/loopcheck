from __future__ import annotations

import json

from loopcheck.aggregate import AggregateResult
from loopcheck.compare import ComparisonResult
from loopcheck.findings import Finding, Severity
from loopcheck.trace import Trace

_SEVERITY_ORDER = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH]
_SEVERITY_COLOR = {
    Severity.INFO: "dim",
    Severity.LOW: "cyan",
    Severity.MEDIUM: "yellow",
    Severity.HIGH: "red",
}


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: _SEVERITY_ORDER.index(f.severity), reverse=True)


def total_wasted_cost(findings: list[Finding]) -> float:
    return sum(f.wasted_cost for f in findings)


def render_text(trace: Trace, findings: list[Finding]) -> str:
    findings = sort_findings(findings)
    lines = [f"[bold]loopcheck[/] -- {trace.agent_name} ({len(trace.steps)} step(s), goal: {trace.goal!r})", ""]

    if not findings:
        lines.append("[green]No waste detected.[/] Every tool call in this trace looks necessary.")
    else:
        for f in findings:
            color = _SEVERITY_COLOR[f.severity]
            lines.append(f"[{color}]{f.severity.value.upper():8}[/] {f.check:16} {f.title}")
            lines.append(f"          {f.detail}")
            if f.wasted_cost:
                lines.append(f"          [dim]est. wasted cost: ${f.wasted_cost:.4f}[/]")
            lines.append("")

    total_cost = trace.total_cost()
    wasted = total_wasted_cost(findings)
    if total_cost:
        pct = (wasted / total_cost * 100) if total_cost else 0.0
        lines.append(f"Total trace cost: ${total_cost:.4f}  |  Estimated wasted: ${wasted:.4f} ({pct:.1f}%)")
    elif wasted:
        lines.append(f"Estimated wasted cost: ${wasted:.4f} (set input_cost_per_1k/output_cost_per_1k in the trace for a full total)")

    return "\n".join(lines)


def to_json(trace: Trace, findings: list[Finding]) -> str:
    findings = sort_findings(findings)
    return json.dumps({
        "agent_name": trace.agent_name,
        "goal": trace.goal,
        "step_count": len(trace.steps),
        "total_cost": trace.total_cost(),
        "wasted_cost": total_wasted_cost(findings),
        "findings": [
            {
                "check": f.check,
                "severity": f.severity.value,
                "title": f.title,
                "detail": f.detail,
                "step_indices": f.step_indices,
                "wasted_cost": f.wasted_cost,
                "tool": f.tool,
            }
            for f in findings
        ],
    }, indent=2)


def render_comparison(before_trace: Trace, after_trace: Trace, result: ComparisonResult) -> str:
    lines = [
        f"[bold]loopcheck compare[/] -- {before_trace.agent_name} -> {after_trace.agent_name}",
        "",
    ]

    if result.new_findings:
        lines.append("[red]Regressions (new since the before run):[/]")
        for f in sort_findings(result.new_findings):
            lines.append(f"  [red]+[/] {f.check:16} {f.title} (tool={f.tool})")
        lines.append("")

    if result.resolved_findings:
        lines.append("[green]Resolved (present before, gone now):[/]")
        for f in sort_findings(result.resolved_findings):
            lines.append(f"  [green]-[/] {f.check:16} {f.title} (tool={f.tool})")
        lines.append("")

    if not result.new_findings and not result.resolved_findings:
        lines.append("[dim]No change in findings between the two runs.[/]")
        lines.append("")

    delta = result.delta_cost
    delta_str = f"+${delta:.4f}" if delta >= 0 else f"-${abs(delta):.4f}"
    verdict = "[red]REGRESSION[/]" if result.is_regression else "[green]OK[/]"
    lines.append(
        f"Wasted cost: ${result.before_wasted_cost:.4f} -> ${result.after_wasted_cost:.4f} "
        f"({delta_str})  {verdict}"
    )
    return "\n".join(lines)


def to_json_comparison(before_trace: Trace, after_trace: Trace, result: ComparisonResult) -> str:
    def _f(finding: Finding) -> dict:
        return {
            "check": finding.check,
            "severity": finding.severity.value,
            "title": finding.title,
            "detail": finding.detail,
            "step_indices": finding.step_indices,
            "wasted_cost": finding.wasted_cost,
            "tool": finding.tool,
        }

    return json.dumps({
        "before_agent": before_trace.agent_name,
        "after_agent": after_trace.agent_name,
        "before_wasted_cost": result.before_wasted_cost,
        "after_wasted_cost": result.after_wasted_cost,
        "delta_cost": result.delta_cost,
        "is_regression": result.is_regression,
        "new_findings": [_f(f) for f in sort_findings(result.new_findings)],
        "resolved_findings": [_f(f) for f in sort_findings(result.resolved_findings)],
    }, indent=2)


def render_aggregate(result: AggregateResult, top_n: int = 5) -> str:
    lines = [
        f"[bold]loopcheck report[/] -- {result.trace_count} trace(s), "
        f"{result.traces_with_findings} with findings",
        "",
        f"Total cost: ${result.total_cost:.4f}  |  Wasted: ${result.total_wasted_cost:.4f} "
        f"({result.wasted_pct:.1f}%)",
        "",
    ]

    if result.findings_by_check:
        lines.append("[bold]By check:[/]")
        for check, count in sorted(result.findings_by_check.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"  {check:20} {count}")
        lines.append("")

    if result.findings_by_tool:
        lines.append("[bold]By tool:[/]")
        for tool, count in sorted(result.findings_by_tool.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"  {tool:20} {count}")
        lines.append("")

    if result.worst_traces:
        lines.append(f"[bold]Worst {min(top_n, len(result.worst_traces))} trace(s) by wasted cost:[/]")
        for label, wasted in result.worst_traces[:top_n]:
            lines.append(f"  [yellow]${wasted:.4f}[/]  {label}")
        lines.append("")

    if not result.findings_by_check:
        lines.append("[green]No waste detected across any trace in this batch.[/]")

    return "\n".join(lines).rstrip()


def to_json_aggregate(result: AggregateResult) -> str:
    return json.dumps({
        "trace_count": result.trace_count,
        "total_cost": result.total_cost,
        "total_wasted_cost": result.total_wasted_cost,
        "wasted_pct": result.wasted_pct,
        "traces_with_findings": result.traces_with_findings,
        "findings_by_check": result.findings_by_check,
        "findings_by_tool": result.findings_by_tool,
        "worst_traces": [{"label": label, "wasted_cost": wasted} for label, wasted in result.worst_traces],
    }, indent=2)
