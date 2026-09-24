"""
Adapter for the OpenAI (and Groq, which is OpenAI-compatible -- see
groq_adapter.py) chat-completions tool-calling shape:

  response.choices[0].message.tool_calls[0].function.{name,arguments}
  response.choices[0].message.content   (final answer, when no tool_calls)
  response.usage.{prompt_tokens,completion_tokens}

Accepts either real SDK objects (attribute access) or plain dicts (the
JSON shape you'd get from response.model_dump(), or from a hand-built
test fixture) -- see _shape.py.

record_openai_step() records only the FIRST tool call in a response --
kept as-is for the common single-tool-call case and for backward
compatibility with v0.1/v0.2 traces and code. For a response that may
contain PARALLEL tool calls (the model requesting several tools at once),
use record_openai_turn() instead: it fans every tool_calls entry out into
its own Step, all sharing one turn (see trace.py's module docstring).
"""

from __future__ import annotations

import json
from typing import Any

from loopcheck.adapters._shape import _get
from loopcheck.recorder import TraceRecorder
from loopcheck.trace import Step


def record_openai_step(
    recorder: TraceRecorder,
    response: Any,
    tool_result: str | None = None,
    is_error: bool = False,
) -> Step:
    choice = _get(response, "choices")[0]
    message = _get(choice, "message")
    tool_calls = _get(message, "tool_calls") or []
    content = _get(message, "content")

    usage = _get(response, "usage")
    input_tokens = _get(usage, "prompt_tokens", 0) if usage is not None else 0
    output_tokens = _get(usage, "completion_tokens", 0) if usage is not None else 0

    if tool_calls:
        call = tool_calls[0]
        function = _get(call, "function")
        tool_name = _get(function, "name")
        raw_args = _get(function, "arguments") or "{}"
        tool_args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
        return recorder.record_step(
            reasoning=content,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_result,
            is_error=is_error,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    # No tool call -- this is the model's final answer.
    return recorder.record_step(
        reasoning=None,
        tool_name=None,
        tool_result=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def record_openai_turn(
    recorder: TraceRecorder,
    response: Any,
    tool_results: list[str | None] | None = None,
    errors: list[bool] | None = None,
) -> list[Step]:
    """Records EVERY tool call in `response` as its own Step, all sharing
    one turn -- use this instead of record_openai_step() whenever the
    model might request more than one tool call in a single response
    (parallel tool-calling).

    `tool_results`/`errors` line up by position with the response's
    tool_calls (pad with None/False for calls you haven't executed yet,
    or omit entirely if you're recording before executing).

    Token usage is attributed entirely to the FIRST call in the turn and
    0 to the rest -- `response.usage` describes the whole API call, not
    each individual tool request within it, so splitting or repeating it
    per call would double-count cost when the trace's totals are summed.
    """
    choice = _get(response, "choices")[0]
    message = _get(choice, "message")
    tool_calls = _get(message, "tool_calls") or []
    content = _get(message, "content")

    usage = _get(response, "usage")
    input_tokens = _get(usage, "prompt_tokens", 0) if usage is not None else 0
    output_tokens = _get(usage, "completion_tokens", 0) if usage is not None else 0

    if not tool_calls:
        return [recorder.record_step(
            reasoning=None,
            tool_name=None,
            tool_result=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )]

    results = tool_results or [None] * len(tool_calls)
    error_flags = errors or [False] * len(tool_calls)
    results = results + [None] * (len(tool_calls) - len(results))
    error_flags = error_flags + [False] * (len(tool_calls) - len(error_flags))

    calls_kwargs = []
    for i, call in enumerate(tool_calls):
        function = _get(call, "function")
        tool_name = _get(function, "name")
        raw_args = _get(function, "arguments") or "{}"
        tool_args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
        calls_kwargs.append({
            "reasoning": content if i == 0 else None,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "tool_result": results[i],
            "is_error": error_flags[i],
            "input_tokens": input_tokens if i == 0 else 0,
            "output_tokens": output_tokens if i == 0 else 0,
        })

    return recorder.record_parallel_steps(calls_kwargs)
