from loopcheck.compare import compare_findings
from loopcheck.findings import Finding, Severity


def _f(check, tool, title, wasted_cost=0.0, step_indices=None):
    return Finding(
        check=check, severity=Severity.MEDIUM, title=title,
        detail="d", step_indices=step_indices or [0], wasted_cost=wasted_cost, tool=tool,
    )


def test_identical_findings_produce_no_new_or_resolved():
    before = [_f("duplicate_calls", "search", "Repeated tool call with identical arguments")]
    after = [_f("duplicate_calls", "search", "Repeated tool call with identical arguments")]
    result = compare_findings(before, after)
    assert result.new_findings == []
    assert result.resolved_findings == []
    assert result.is_regression is False


def test_new_finding_in_after_is_a_regression():
    before = []
    after = [_f("loop_thrash", "search", "Tool called far more than expected for a single trace")]
    result = compare_findings(before, after)
    assert len(result.new_findings) == 1
    assert result.resolved_findings == []
    assert result.is_regression is True


def test_finding_only_in_before_is_resolved_not_a_regression():
    before = [_f("duplicate_calls", "search", "Repeated tool call with identical arguments")]
    after = []
    result = compare_findings(before, after)
    assert result.new_findings == []
    assert len(result.resolved_findings) == 1
    assert result.is_regression is False


def test_cost_increase_with_same_findings_is_still_a_regression():
    before = [_f("duplicate_calls", "search", "t", wasted_cost=0.01)]
    after = [_f("duplicate_calls", "search", "t", wasted_cost=0.05)]
    result = compare_findings(before, after)
    assert result.new_findings == []  # same fingerprint, not "new"
    assert result.delta_cost == 0.04
    assert result.is_regression is True


def test_matching_by_check_tool_title_ignores_step_indices():
    """The same underlying issue at different step positions across two
    runs must still match -- step_indices are expected to shift."""
    before = [_f("duplicate_calls", "search", "t", step_indices=[3])]
    after = [_f("duplicate_calls", "search", "t", step_indices=[9])]
    result = compare_findings(before, after)
    assert result.new_findings == []
    assert result.resolved_findings == []


def test_different_tool_is_a_different_fingerprint():
    before = [_f("duplicate_calls", "search", "t")]
    after = [_f("duplicate_calls", "fetch", "t")]
    result = compare_findings(before, after)
    assert len(result.new_findings) == 1
    assert len(result.resolved_findings) == 1


def test_delta_cost_can_be_negative_when_waste_shrinks():
    before = [_f("duplicate_calls", "search", "t", wasted_cost=0.10)]
    after = [_f("duplicate_calls", "search", "t", wasted_cost=0.02)]
    result = compare_findings(before, after)
    assert result.delta_cost == -0.08
    assert result.is_regression is False
