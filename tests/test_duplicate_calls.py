from loopcheck.checks.duplicate_calls import check_duplicate_calls
from loopcheck.trace import Step, Trace


def _trace(steps):
    return Trace(agent_name="t", goal="g", input_cost_per_1k=1.0, output_cost_per_1k=1.0, steps=steps)


def test_no_findings_for_clean_trace():
    trace = _trace([
        Step(index=0, tool_name="search", tool_args={"q": "a"}, input_tokens=100),
        Step(index=1, tool_name="search", tool_args={"q": "b"}, input_tokens=100),
        Step(index=2, tool_name=None),
    ])
    assert check_duplicate_calls(trace) == []


def test_flags_exact_repeat_after_success():
    trace = _trace([
        Step(index=0, tool_name="search", tool_args={"q": "a"}, input_tokens=1000, output_tokens=0),
        Step(index=1, tool_name="search", tool_args={"q": "b"}),
        Step(index=2, tool_name="search", tool_args={"q": "a"}, input_tokens=1000, output_tokens=0),
    ])
    findings = check_duplicate_calls(trace)
    assert len(findings) == 1
    f = findings[0]
    assert f.check == "duplicate_calls"
    assert f.step_indices == [2]
    assert f.wasted_cost == 1.0  # 1000 input tokens @ $1/1k


def test_retry_after_error_is_not_flagged():
    trace = _trace([
        Step(index=0, tool_name="read", tool_args={"path": "x"}, is_error=True),
        Step(index=1, tool_name="read", tool_args={"path": "x"}, is_error=False),
    ])
    # First succeeded on step 1 (step 0 was an error) -- no *further* repeat exists, so nothing to flag.
    assert check_duplicate_calls(trace) == []


def test_repeat_after_the_successful_retry_is_flagged():
    trace = _trace([
        Step(index=0, tool_name="read", tool_args={"path": "x"}, is_error=True),
        Step(index=1, tool_name="read", tool_args={"path": "x"}, is_error=False),
        Step(index=2, tool_name="read", tool_args={"path": "x"}, is_error=False, input_tokens=500),
    ])
    findings = check_duplicate_calls(trace)
    assert len(findings) == 1
    assert findings[0].step_indices == [2]


def test_multiple_distinct_tools_each_flagged_separately():
    trace = _trace([
        Step(index=0, tool_name="search", tool_args={"q": "a"}),
        Step(index=1, tool_name="fetch", tool_args={"url": "u"}),
        Step(index=2, tool_name="search", tool_args={"q": "a"}),
        Step(index=3, tool_name="fetch", tool_args={"url": "u"}),
    ])
    findings = check_duplicate_calls(trace)
    assert {f.step_indices[0] for f in findings} == {2, 3}


def test_identical_calls_within_one_parallel_turn_are_flagged():
    """If a model requests the same tool+args twice in ONE turn (a
    modeling mistake, not a looping one), that's still waste -- turn
    number doesn't exempt it from duplicate detection."""
    from loopcheck.recorder import TraceRecorder

    rec = TraceRecorder(agent_name="t", goal="g", input_cost_per_1k=1.0, output_cost_per_1k=0.0)
    rec.record_parallel_steps([
        {"tool_name": "search", "tool_args": {"q": "a"}, "input_tokens": 1000},
        {"tool_name": "search", "tool_args": {"q": "a"}, "input_tokens": 1000},
    ])
    findings = check_duplicate_calls(rec.trace)
    assert len(findings) == 1
    assert findings[0].step_indices == [1]
