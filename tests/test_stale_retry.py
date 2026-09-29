from loopcheck.checks.stale_retry import check_stale_retry
from loopcheck.trace import Step, Trace


def _trace(steps):
    return Trace(agent_name="t", goal="g", input_cost_per_1k=1.0, output_cost_per_1k=1.0, steps=steps)


def test_no_findings_for_clean_trace():
    trace = _trace([
        Step(index=0, tool_name="search", tool_args={"q": "a"}, input_tokens=100),
        Step(index=1, tool_name="search", tool_args={"q": "b"}, input_tokens=100),
        Step(index=2, tool_name=None),
    ])
    assert check_stale_retry(trace) == []


def test_single_failure_is_not_flagged():
    """One failed attempt is a legitimate 'try it and see' -- not waste on its own."""
    trace = _trace([
        Step(index=0, tool_name="read", tool_args={"path": "x"}, is_error=True),
        Step(index=1, tool_name="read", tool_args={"path": "y"}),  # different args, no signal here
    ])
    assert check_stale_retry(trace) == []


def test_flags_second_identical_failure():
    trace = _trace([
        Step(index=0, tool_name="read", tool_args={"path": "x"}, is_error=True, input_tokens=100),
        Step(index=1, tool_name="read", tool_args={"path": "x"}, is_error=True, input_tokens=100),
    ])
    findings = check_stale_retry(trace)
    assert len(findings) == 1
    f = findings[0]
    assert f.check == "stale_retry"
    assert f.step_indices == [1]  # only the repeat counts as waste, not the first attempt
    assert f.wasted_cost == 0.1  # 100 input tokens @ $1/1k


def test_eventual_success_does_not_clear_the_finding():
    """Two identical failures followed by a change in fortune don't retroactively
    make the wasted attempts legitimate -- the finding still fires for the repeats
    that already happened."""
    trace = _trace([
        Step(index=0, tool_name="read", tool_args={"path": "x"}, is_error=True),
        Step(index=1, tool_name="read", tool_args={"path": "x"}, is_error=True),
        Step(index=2, tool_name="read", tool_args={"path": "x"}, is_error=False),
    ])
    findings = check_stale_retry(trace)
    assert len(findings) == 1
    assert findings[0].step_indices == [1]


def test_severity_escalates_past_double_the_threshold():
    trace = _trace([
        Step(index=i, tool_name="read", tool_args={"path": "x"}, is_error=True)
        for i in range(4)
    ])
    findings = check_stale_retry(trace)
    assert len(findings) == 1
    assert findings[0].severity.value == "high"


def test_different_args_are_not_conflated():
    """Failures with different arguments are different signatures -- an agent
    trying different paths that each happen to fail once isn't stale retrying."""
    trace = _trace([
        Step(index=0, tool_name="read", tool_args={"path": "x"}, is_error=True),
        Step(index=1, tool_name="read", tool_args={"path": "y"}, is_error=True),
    ])
    assert check_stale_retry(trace) == []
