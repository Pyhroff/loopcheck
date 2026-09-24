"""GroqJudge's HTTP call is fully mocked -- these tests never hit the
network, they verify GroqJudge builds the right prompt and parses the
model's JSON response correctly (including malformed output)."""

from unittest.mock import AsyncMock, MagicMock

from loopcheck.judges.groq_judge import GroqJudge


def _mock_client(content: str):
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


async def test_parses_redundant_verdict():
    judge = GroqJudge.__new__(GroqJudge)  # bypass __init__ (which needs the real groq package)
    judge._client = _mock_client('{"is_redundant": true, "reason": "same sub-goal"}')
    judge._model = "test-model"

    verdict = await judge.compare("goal", "search", {"q": "a"}, "result a", {"q": "b"}, "result b")
    assert verdict.is_redundant is True
    assert verdict.reason == "same sub-goal"


async def test_parses_not_redundant_verdict():
    judge = GroqJudge.__new__(GroqJudge)
    judge._client = _mock_client('{"is_redundant": false, "reason": "different sub-goal"}')
    judge._model = "test-model"

    verdict = await judge.compare("goal", "search", {"q": "a"}, "result a", {"q": "b"}, "result b")
    assert verdict.is_redundant is False


async def test_malformed_json_fails_closed_as_not_redundant():
    judge = GroqJudge.__new__(GroqJudge)
    judge._client = _mock_client("not valid json at all")
    judge._model = "test-model"

    verdict = await judge.compare("goal", "search", {"q": "a"}, "result a", {"q": "b"}, "result b")
    assert verdict.is_redundant is False
    assert "unparseable" in verdict.reason


async def test_prompt_includes_goal_and_both_calls():
    judge = GroqJudge.__new__(GroqJudge)
    client = _mock_client('{"is_redundant": false, "reason": "x"}')
    judge._client = client
    judge._model = "test-model"

    await judge.compare("summarize causes", "search", {"q": "first query"}, "res a", {"q": "second query"}, "res b")

    call_kwargs = client.chat.completions.create.call_args.kwargs
    user_message = call_kwargs["messages"][1]["content"]
    assert "summarize causes" in user_message
    assert "first query" in user_message
    assert "second query" in user_message


def test_missing_groq_package_raises_clear_error(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "groq":
            raise ImportError("no module named groq")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    try:
        GroqJudge(api_key="fake-key")
        assert False, "expected ImportError"
    except ImportError as exc:
        assert "loopcheck[judge]" in str(exc)
