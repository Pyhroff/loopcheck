from loopcheck.checks.loop_thrash import check_loop_thrash
from loopcheck.trace import Step, Trace


def _trace(steps):
    return Trace(agent_name="t", goal="g", input_cost_per_1k=1.0, output_cost_per_1k=0.0, steps=steps)


def test_below_threshold_not_flagged():
    trace = _trace([Step(index=i, tool_name="search", tool_args={"q": str(i)}) for i in range(3)])
    assert check_loop_thrash(trace) == []


def test_at_threshold_flagged_as_medium():
    trace = _trace([Step(index=i, tool_name="search", tool_args={"q": str(i)}) for i in range(4)])
    findings = check_loop_thrash(trace)
    assert len(findings) == 1
    assert findings[0].severity.value == "medium"
    assert findings[0].check == "loop_thrash"


def test_double_threshold_flagged_as_high():
    trace = _trace([Step(index=i, tool_name="search", tool_args={"q": str(i)}) for i in range(8)])
    findings = check_loop_thrash(trace)
    assert findings[0].severity.value == "high"


def test_only_excess_calls_past_threshold_cost_counted():
    steps = [Step(index=i, tool_name="search", tool_args={"q": str(i)}, input_tokens=1000) for i in range(6)]
    trace = _trace(steps)
    findings = check_loop_thrash(trace, threshold=4)
    # 6 calls, threshold 4 -> 2 excess calls -> 2000 input tokens @ $1/1k = $2.0
    assert findings[0].wasted_cost == 2.0


def test_custom_threshold_respected():
    trace = _trace([Step(index=i, tool_name="search", tool_args={"q": str(i)}) for i in range(3)])
    findings = check_loop_thrash(trace, threshold=2)
    assert len(findings) == 1


def test_tool_name_none_steps_ignored():
    trace = _trace([Step(index=i, tool_name=None) for i in range(10)])
    assert check_loop_thrash(trace) == []
