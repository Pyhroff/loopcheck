from loopcheck.aggregate import aggregate
from loopcheck.findings import Finding, Severity
from loopcheck.trace import Trace


def _f(check, tool, wasted_cost=0.0):
    return Finding(check=check, severity=Severity.MEDIUM, title="t", detail="d",
                    step_indices=[0], wasted_cost=wasted_cost, tool=tool)


def _trace(cost_in=0.0, cost_out=0.0):
    return Trace(agent_name="a", goal="g", input_cost_per_1k=1.0, output_cost_per_1k=1.0)


def test_empty_batch():
    result = aggregate([])
    assert result.trace_count == 0
    assert result.total_wasted_cost == 0.0
    assert result.worst_traces == []


def test_counts_traces_with_and_without_findings():
    entries = [
        ("a.json", _trace(), [_f("duplicate_calls", "search")]),
        ("b.json", _trace(), []),
        ("c.json", _trace(), [_f("loop_thrash", "fetch")]),
    ]
    result = aggregate(entries)
    assert result.trace_count == 3
    assert result.traces_with_findings == 2


def test_findings_by_check_and_tool_tallied_across_all_traces():
    entries = [
        ("a.json", _trace(), [_f("duplicate_calls", "search"), _f("duplicate_calls", "fetch")]),
        ("b.json", _trace(), [_f("duplicate_calls", "search")]),
    ]
    result = aggregate(entries)
    assert result.findings_by_check == {"duplicate_calls": 3}
    assert result.findings_by_tool == {"search": 2, "fetch": 1}


def test_worst_traces_sorted_descending_and_excludes_zero_waste():
    entries = [
        ("low.json", _trace(), [_f("duplicate_calls", "x", wasted_cost=0.01)]),
        ("clean.json", _trace(), []),
        ("high.json", _trace(), [_f("duplicate_calls", "x", wasted_cost=0.50)]),
        ("mid.json", _trace(), [_f("duplicate_calls", "x", wasted_cost=0.10)]),
    ]
    result = aggregate(entries)
    assert [label for label, _ in result.worst_traces] == ["high.json", "mid.json", "low.json"]


def test_top_n_caps_worst_traces_list():
    entries = [(f"{i}.json", _trace(), [_f("x", "t", wasted_cost=float(i))]) for i in range(10)]
    result = aggregate(entries, top_n=3)
    assert len(result.worst_traces) == 3
    assert result.worst_traces[0][0] == "9.json"


def test_wasted_pct_zero_when_total_cost_zero():
    entries = [("a.json", Trace(agent_name="a", goal="g"), [])]
    result = aggregate(entries)
    assert result.wasted_pct == 0.0
