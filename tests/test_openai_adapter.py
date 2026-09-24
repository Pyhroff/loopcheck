"""Tests against both dict-shaped and SDK-object-shaped (SimpleNamespace)
fixtures -- real openai>=1.0 responses are pydantic objects with attribute
access, not dicts, so both need to work."""

from types import SimpleNamespace

from loopcheck.adapters.openai_adapter import record_openai_step
from loopcheck.recorder import TraceRecorder


def _dict_tool_call_response():
    return {
        "choices": [{
            "message": {
                "content": "I should search for this.",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": "web_search", "arguments": '{"query": "chip shortage"}'},
                }],
            },
        }],
        "usage": {"prompt_tokens": 300, "completion_tokens": 40},
    }


def _namespace_tool_call_response():
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content="I should search for this.",
            tool_calls=[SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(name="web_search", arguments='{"query": "chip shortage"}'),
            )],
        ))],
        usage=SimpleNamespace(prompt_tokens=300, completion_tokens=40),
    )


def _final_answer_response(as_dict: bool):
    if as_dict:
        return {
            "choices": [{"message": {"content": "Here's the answer.", "tool_calls": None}}],
            "usage": {"prompt_tokens": 500, "completion_tokens": 80},
        }
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Here's the answer.", tool_calls=None))],
        usage=SimpleNamespace(prompt_tokens=500, completion_tokens=80),
    )


def test_dict_shaped_tool_call_parsed():
    rec = TraceRecorder(agent_name="a", goal="g")
    step = record_openai_step(rec, _dict_tool_call_response(), tool_result="results here")
    assert step.tool_name == "web_search"
    assert step.tool_args == {"query": "chip shortage"}
    assert step.reasoning == "I should search for this."
    assert step.tool_result == "results here"
    assert step.input_tokens == 300
    assert step.output_tokens == 40


def test_namespace_shaped_tool_call_parsed_identically():
    rec = TraceRecorder(agent_name="a", goal="g")
    step = record_openai_step(rec, _namespace_tool_call_response(), tool_result="results here")
    assert step.tool_name == "web_search"
    assert step.tool_args == {"query": "chip shortage"}


def test_final_answer_has_no_tool_name_dict():
    rec = TraceRecorder(agent_name="a", goal="g")
    step = record_openai_step(rec, _final_answer_response(as_dict=True))
    assert step.tool_name is None
    assert step.tool_result == "Here's the answer."


def test_final_answer_has_no_tool_name_namespace():
    rec = TraceRecorder(agent_name="a", goal="g")
    step = record_openai_step(rec, _final_answer_response(as_dict=False))
    assert step.tool_name is None
    assert step.tool_result == "Here's the answer."


def test_is_error_flag_propagated():
    rec = TraceRecorder(agent_name="a", goal="g")
    step = record_openai_step(rec, _dict_tool_call_response(), tool_result="failed", is_error=True)
    assert step.is_error is True


def test_arguments_already_a_dict_is_accepted():
    """Some callers may hand-construct a response with arguments already
    parsed to a dict rather than a JSON string -- should still work."""
    response = {
        "choices": [{"message": {"content": None, "tool_calls": [
            {"function": {"name": "x", "arguments": {"a": 1}}}
        ]}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    rec = TraceRecorder(agent_name="a", goal="g")
    step = record_openai_step(rec, response)
    assert step.tool_args == {"a": 1}
