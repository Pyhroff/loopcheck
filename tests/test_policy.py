import json

from loopcheck.findings import Finding, Severity
from loopcheck.policy import Policy, PolicyRule


def _f(check="loop_thrash", tool="search", title="Tool called far more than expected for a single trace"):
    return Finding(check=check, severity=Severity.MEDIUM, title=title, detail="d", step_indices=[0], tool=tool)


def test_empty_policy_suppresses_nothing():
    policy = Policy(rules=[])
    kept, suppressed = policy.apply([_f(), _f(tool="fetch")])
    assert len(kept) == 2
    assert suppressed == []


def test_rule_matches_exact_tool_and_check():
    policy = Policy(rules=[PolicyRule(tool="search", check="loop_thrash")])
    a = _f(tool="search")
    b = _f(tool="fetch")
    kept, suppressed = policy.apply([a, b])
    assert kept == [b]
    assert suppressed == [a]


def test_wildcard_tool_matches_any_tool():
    policy = Policy(rules=[PolicyRule(tool="*", check="loop_thrash")])
    a = _f(tool="search")
    b = _f(tool="fetch")
    c = _f(tool="search", check="duplicate_calls", title="x")
    kept, suppressed = policy.apply([a, b, c])
    assert kept == [c]
    assert set(id(s) for s in suppressed) == {id(a), id(b)}


def test_title_narrows_the_match():
    policy = Policy(rules=[PolicyRule(tool="search", check="loop_thrash", title="Tool called far more than expected for a single trace")])
    matching = _f()
    different_title = _f(title="Some other finding")
    kept, suppressed = policy.apply([matching, different_title])
    assert kept == [different_title]
    assert suppressed == [matching]


def test_check_only_rule_ignores_tool_and_title():
    policy = Policy(rules=[PolicyRule(check="duplicate_calls")])
    a = _f(check="duplicate_calls", tool="x", title="a")
    b = _f(check="loop_thrash", tool="y", title="b")
    kept, suppressed = policy.apply([a, b])
    assert kept == [b]
    assert suppressed == [a]


def test_multiple_rules_are_ORed():
    policy = Policy(rules=[
        PolicyRule(tool="search", check="loop_thrash"),
        PolicyRule(tool="fetch", check="loop_thrash"),
    ])
    a = _f(tool="search")
    b = _f(tool="fetch")
    c = _f(tool="other", check="duplicate_calls", title="z")
    kept, suppressed = policy.apply([a, b, c])
    assert kept == [c]
    assert len(suppressed) == 2


def test_from_dict_and_load(tmp_path):
    data = {"ignore": [
        {"tool": "search", "check": "loop_thrash", "reason": "known iterative pattern"},
        {"tool": "*", "check": "duplicate_calls", "title": "specific title", "reason": "reviewed"},
    ]}
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps(data), encoding="utf-8")

    policy = Policy.load(policy_file)
    assert len(policy.rules) == 2
    assert policy.rules[0].reason == "known iterative pattern"

    kept, suppressed = policy.apply([
        _f(tool="search", check="loop_thrash"),
        _f(tool="anything", check="duplicate_calls", title="specific title"),
        _f(tool="anything", check="duplicate_calls", title="different title"),
    ])
    assert len(kept) == 1
    assert kept[0].title == "different title"
    assert len(suppressed) == 2


def test_rule_with_wildcard_tool_matches_finding_with_no_tool():
    """semantic_redundancy findings always have a tool, but a check that
    somehow produced tool=None shouldn't crash a wildcard rule."""
    policy = Policy(rules=[PolicyRule(tool="*", check="duplicate_calls")])
    f = Finding(check="duplicate_calls", severity=Severity.HIGH, title="t", detail="d", step_indices=[0], tool=None)
    kept, suppressed = policy.apply([f])
    assert suppressed == [f]
