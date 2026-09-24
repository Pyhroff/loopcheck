from types import SimpleNamespace

from loopcheck.adapters.anthropic_adapter import record_anthropic_step
from loopcheck.recorder import TraceRecorder


def _dict_tool_use_response():
    return {
        "content": [
            {"type": "text", "text": "Let me look this up."},
            {"type": "tool_use", "name": "web_search", "input": {"query": "chip shortage"}},
        ],
        "usage": {"input_tokens": 280, "output_tokens": 35},
    }


def _namespace_tool_use_response():
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Let me look this up."),
            SimpleNamespace(type="tool_use", name="web_search", input={"query": "chip shortage"}),
        ],
        usage=SimpleNamespace(input_tokens=280, output_tokens=35),
    )


def _final_answer_response():
    return {
        "content": [{"type": "text", "text": "Here's the final answer."}],
        "usage": {"input_tokens": 400, "output_tokens": 60},
    }


def test_dict_shaped_tool_use_parsed():
    rec = TraceRecorder(agent_name="a", goal="g")
    step = record_anthropic_step(rec, _dict_tool_use_response(), tool_result="results")
    assert step.tool_name == "web_search"
    assert step.tool_args == {"query": "chip shortage"}
    assert step.reasoning == "Let me look this up."
    assert step.input_tokens == 280
    assert step.output_tokens == 35


def test_namespace_shaped_tool_use_parsed_identically():
    rec = TraceRecorder(agent_name="a", goal="g")
    step = record_anthropic_step(rec, _namespace_tool_use_response(), tool_result="results")
    assert step.tool_name == "web_search"
    assert step.tool_args == {"query": "chip shortage"}


def test_text_only_response_is_final_answer():
    rec = TraceRecorder(agent_name="a", goal="g")
    step = record_anthropic_step(rec, _final_answer_response())
    assert step.tool_name is None
    assert step.tool_result == "Here's the final answer."


def test_only_first_tool_use_block_is_recorded():
    response = {
        "content": [
            {"type": "tool_use", "name": "first_tool", "input": {"a": 1}},
            {"type": "tool_use", "name": "second_tool", "input": {"b": 2}},
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    rec = TraceRecorder(agent_name="a", goal="g")
    step = record_anthropic_step(rec, response)
    assert step.tool_name == "first_tool"


from loopcheck.adapters.anthropic_adapter import record_anthropic_turn
from loopcheck.recorder import TraceRecorder


def _parallel_tool_use_response():
    return {
        "content": [
            {"type": "text", "text": "Checking both cities."},
            {"type": "tool_use", "name": "get_weather", "input": {"city": "Paris"}},
            {"type": "tool_use", "name": "get_weather", "input": {"city": "Tokyo"}},
        ],
        "usage": {"input_tokens": 350, "output_tokens": 45},
    }


def test_turn_fans_out_all_tool_use_blocks():
    rec = TraceRecorder(agent_name="a", goal="g")
    steps = record_anthropic_turn(rec, _parallel_tool_use_response(), tool_results=["18C", "24C"])
    assert len(steps) == 2
    assert steps[0].tool_args == {"city": "Paris"}
    assert steps[1].tool_args == {"city": "Tokyo"}
    assert steps[0].turn == steps[1].turn


def test_turn_usage_attributed_only_to_first_block():
    rec = TraceRecorder(agent_name="a", goal="g")
    steps = record_anthropic_turn(rec, _parallel_tool_use_response())
    assert steps[0].input_tokens == 350
    assert steps[1].input_tokens == 0


def test_turn_no_tool_use_returns_final_answer_step():
    rec = TraceRecorder(agent_name="a", goal="g")
    steps = record_anthropic_turn(rec, _final_answer_response())
    assert len(steps) == 1
    assert steps[0].tool_name is None
