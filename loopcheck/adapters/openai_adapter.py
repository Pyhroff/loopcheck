"""
Adapter for the OpenAI (and Groq, which is OpenAI-compatible -- see
groq_adapter.py) chat-completions tool-calling shape:

  response.choices[0].message.tool_calls[0].function.{name,arguments}
  response.choices[0].message.content   (final answer, when no tool_calls)
  response.usage.{prompt_tokens,completion_tokens}

Accepts either real SDK objects (attribute access) or plain dicts (the
JSON shape you'd get from response.model_dump(), or from a hand-built
test fixture) -- see _shape.py.

Only the FIRST tool call in a response is recorded as this step's tool
call. Parallel tool-calling (multiple tool_calls in one response) is a
known v0.2 limitation -- see README -- because loopcheck's Step is
one-tool-per-step; a v0.3 addition would fan a multi-call response out
into multiple Steps sharing an index, or extend Step to hold a list.
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
