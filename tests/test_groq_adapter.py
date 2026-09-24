"""Groq is OpenAI-compatible -- this just checks the re-export actually
works and behaves identically to the OpenAI adapter."""

from loopcheck.adapters.groq_adapter import record_groq_step
from loopcheck.recorder import TraceRecorder


def test_groq_adapter_parses_openai_shaped_response():
    response = {
        "choices": [{"message": {"content": None, "tool_calls": [
            {"function": {"name": "get_weather", "arguments": '{"city": "Tokyo"}'}}
        ]}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 15},
    }
    rec = TraceRecorder(agent_name="a", goal="g")
    step = record_groq_step(rec, response, tool_result="24C, clear")
    assert step.tool_name == "get_weather"
    assert step.tool_args == {"city": "Tokyo"}
    assert step.tool_result == "24C, clear"


from loopcheck.adapters.groq_adapter import record_groq_turn


def test_groq_turn_fans_out_parallel_calls():
    response = {
        "choices": [{"message": {"content": None, "tool_calls": [
            {"function": {"name": "get_weather", "arguments": '{"city": "Paris"}'}},
            {"function": {"name": "get_weather", "arguments": '{"city": "Tokyo"}'}},
        ]}}],
        "usage": {"prompt_tokens": 200, "completion_tokens": 20},
    }
    rec = TraceRecorder(agent_name="a", goal="g")
    steps = record_groq_turn(rec, response)
    assert len(steps) == 2
    assert steps[0].turn == steps[1].turn
