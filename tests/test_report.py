import json

from loopcheck.checks.duplicate_calls import check_duplicate_calls
from loopcheck.report import render_text, to_json, total_wasted_cost, sort_findings
from loopcheck.findings import Finding, Severity
from loopcheck.trace import Step, Trace


def test_clean_trace_reports_no_waste():
    trace = Trace(agent_name="a", goal="g", steps=[Step(index=0, tool_name="x", tool_args={})])
    text = render_text(trace, [])
    assert "No waste detected" in text


def test_sort_findings_orders_high_first():
    findings = [
        Finding(check="c", severity=Severity.LOW, title="t", detail="d", step_indices=[0]),
        Finding(check="c", severity=Severity.HIGH, title="t", detail="d", step_indices=[0]),
        Finding(check="c", severity=Severity.MEDIUM, title="t", detail="d", step_indices=[0]),
    ]
    ordered = sort_findings(findings)
    assert [f.severity for f in ordered] == [Severity.HIGH, Severity.MEDIUM, Severity.LOW]


def test_total_wasted_cost_sums_findings():
    findings = [
        Finding(check="c", severity=Severity.HIGH, title="t", detail="d", step_indices=[0], wasted_cost=1.5),
        Finding(check="c", severity=Severity.HIGH, title="t", detail="d", step_indices=[1], wasted_cost=0.5),
    ]
    assert total_wasted_cost(findings) == 2.0


def test_to_json_round_trips_shape():
    trace = Trace(agent_name="a", goal="g", input_cost_per_1k=1.0, output_cost_per_1k=1.0, steps=[
        Step(index=0, tool_name="x", tool_args={}, input_tokens=1000, output_tokens=0),
        Step(index=1, tool_name="x", tool_args={}, input_tokens=1000, output_tokens=0),
    ])
    findings = check_duplicate_calls(trace)
    data = json.loads(to_json(trace, findings))
    assert data["agent_name"] == "a"
    assert data["wasted_cost"] == 1.0
    assert len(data["findings"]) == 1
    assert data["findings"][0]["check"] == "duplicate_calls"
