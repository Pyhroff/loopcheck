"""All tests here use a fake in-memory Judge -- semantic_redundancy is
fully testable without any network access or API key, since it only
depends on the Judge Protocol, not any concrete implementation."""

from loopcheck.checks.semantic_redundancy import check_semantic_redundancy, _candidate_pairs
from loopcheck.judge import JudgeVerdict
from loopcheck.trace import Step, Trace


class FakeJudge:
    """Always returns the same verdict, or looks up a per-pair verdict by
    (args_a, args_b) if `verdicts` is given -- covers both the simple
    always-same-answer tests and ones that need per-pair control."""

    def __init__(self, always_redundant: bool = False, verdicts: dict | None = None):
        self.always_redundant = always_redundant
        self.verdicts = verdicts or {}
        self.calls: list[tuple] = []

    async def compare(self, goal, tool_name, args_a, result_a, args_b, result_b):
        self.calls.append((tool_name, args_a, args_b))
        key = (tuple(sorted(args_a.items())), tuple(sorted(args_b.items())))
        if key in self.verdicts:
            return self.verdicts[key]
        return JudgeVerdict(is_redundant=self.always_redundant, reason="fake")


def _trace(steps):
    return Trace(agent_name="t", goal="find the causes", input_cost_per_1k=1.0, output_cost_per_1k=0.0, steps=steps)


def test_candidate_pairs_skips_exact_duplicate_args():
    trace = _trace([
        Step(index=0, tool_name="search", tool_args={"q": "a"}),
        Step(index=1, tool_name="search", tool_args={"q": "a"}),  # exact dup -- duplicate_calls' job
    ])
    assert _candidate_pairs(trace, max_pairs=20) == []


def test_candidate_pairs_only_within_same_tool():
    trace = _trace([
        Step(index=0, tool_name="search", tool_args={"q": "a"}),
        Step(index=1, tool_name="fetch", tool_args={"url": "x"}),
    ])
    assert _candidate_pairs(trace, max_pairs=20) == []


def test_candidate_pairs_respects_max_pairs_cap():
    steps = [Step(index=i, tool_name="search", tool_args={"q": str(i)}) for i in range(5)]
    trace = _trace(steps)
    # 5 steps, all same tool, all distinct args -> C(5,2) = 10 possible pairs
    assert len(_candidate_pairs(trace, max_pairs=3)) == 3
    assert len(_candidate_pairs(trace, max_pairs=100)) == 10


async def test_no_findings_when_judge_says_not_redundant():
    trace = _trace([
        Step(index=0, tool_name="search", tool_args={"q": "a"}),
        Step(index=1, tool_name="search", tool_args={"q": "b"}),
    ])
    findings = await check_semantic_redundancy(trace, FakeJudge(always_redundant=False))
    assert findings == []


async def test_flags_pair_judge_calls_redundant():
    trace = _trace([
        Step(index=0, tool_name="search", tool_args={"q": "chip shortage causes"}, input_tokens=100),
        Step(index=1, tool_name="search", tool_args={"q": "reasons for chip shortage"}, input_tokens=200),
    ])
    findings = await check_semantic_redundancy(trace, FakeJudge(always_redundant=True))
    assert len(findings) == 1
    f = findings[0]
    assert f.check == "semantic_redundancy"
    assert f.step_indices == [1]
    assert f.wasted_cost == 0.2  # step 1's 200 input tokens @ $1/1k


async def test_judge_is_never_called_on_exact_duplicate_or_cross_tool_pairs():
    trace = _trace([
        Step(index=0, tool_name="search", tool_args={"q": "a"}),
        Step(index=1, tool_name="search", tool_args={"q": "a"}),   # exact dup
        Step(index=2, tool_name="fetch", tool_args={"url": "x"}),  # different tool
    ])
    judge = FakeJudge(always_redundant=True)
    await check_semantic_redundancy(trace, judge)
    assert judge.calls == []


async def test_mixed_verdicts_only_flags_the_redundant_pair():
    a = Step(index=0, tool_name="search", tool_args={"q": "a"})
    b = Step(index=1, tool_name="search", tool_args={"q": "b"})
    c = Step(index=2, tool_name="search", tool_args={"q": "c"})
    trace = _trace([a, b, c])

    verdicts = {
        ((("q", "a"),), (("q", "b"),)): JudgeVerdict(is_redundant=True, reason="same sub-goal"),
        ((("q", "a"),), (("q", "c"),)): JudgeVerdict(is_redundant=False, reason="different sub-goal"),
        ((("q", "b"),), (("q", "c"),)): JudgeVerdict(is_redundant=False, reason="different sub-goal"),
    }
    findings = await check_semantic_redundancy(trace, FakeJudge(verdicts=verdicts))
    assert len(findings) == 1
    assert findings[0].step_indices == [1]
