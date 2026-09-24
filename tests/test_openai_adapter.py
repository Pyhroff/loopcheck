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


from loopcheck.adapters.openai_adapter import record_openai_turn


def _parallel_tool_call_response():
    return {
        "choices": [{
            "message": {
                "content": "I'll check both cities.",
                "tool_calls": [
                    {"function": {"name": "get_weather", "arguments": '{"city": "Paris"}'}},
                    {"function": {"name": "get_weather", "arguments": '{"city": "Tokyo"}'}},
                ],
            },
        }],
        "usage": {"prompt_tokens": 400, "completion_tokens": 50},
    }


def test_turn_fans_out_parallel_calls_into_separate_steps():
    rec = TraceRecorder(agent_name="a", goal="g")
    steps = record_openai_turn(rec, _parallel_tool_call_response(), tool_results=["18C", "24C"])
    assert len(steps) == 2
    assert steps[0].tool_name == "get_weather"
    assert steps[0].tool_args == {"city": "Paris"}
    assert steps[1].tool_args == {"city": "Tokyo"}
    assert steps[0].tool_result == "18C"
    assert steps[1].tool_result == "24C"


def test_turn_shares_one_turn_number_across_parallel_calls():
    rec = TraceRecorder(agent_name="a", goal="g")
    steps = record_openai_turn(rec, _parallel_tool_call_response())
    assert steps[0].turn == steps[1].turn


def test_turn_attributes_usage_only_to_first_call():
    rec = TraceRecorder(agent_name="a", goal="g")
    steps = record_openai_turn(rec, _parallel_tool_call_response())
    assert steps[0].input_tokens == 400
    assert steps[0].output_tokens == 50
    assert steps[1].input_tokens == 0
    assert steps[1].output_tokens == 0


def test_turn_reasoning_attached_only_to_first_call():
    rec = TraceRecorder(agent_name="a", goal="g")
    steps = record_openai_turn(rec, _parallel_tool_call_response())
    assert steps[0].reasoning == "I'll check both cities."
    assert steps[1].reasoning is None


def test_turn_single_call_returns_list_of_one():
    rec = TraceRecorder(agent_name="a", goal="g")
    steps = record_openai_turn(rec, _dict_tool_call_response())
    assert len(steps) == 1
    assert steps[0].tool_name == "web_search"


def test_turn_final_answer_returns_list_of_one_with_no_tool():
    rec = TraceRecorder(agent_name="a", goal="g")
    steps = record_openai_turn(rec, _final_answer_response(as_dict=True))
    assert len(steps) == 1
    assert steps[0].tool_name is None


def test_turn_missing_results_padded_with_none():
    rec = TraceRecorder(agent_name="a", goal="g")
    steps = record_openai_turn(rec, _parallel_tool_call_response())  # no tool_results passed
    assert steps[0].tool_result is None
    assert steps[1].tool_result is None
