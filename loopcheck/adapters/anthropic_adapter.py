"""
Adapter for the Anthropic Messages API tool-use shape:

  response.content -- a list of content blocks, each either
    {"type": "text", "text": "..."} or
    {"type": "tool_use", "name": "...", "input": {...}}
  response.usage.{input_tokens,output_tokens}

Anthropic can emit a text block (reasoning) AND a tool_use block in the
same response -- the text becomes this step's `reasoning`, the tool_use
becomes the tool call. A response with only text blocks (no tool_use) is
the final answer, same convention as the OpenAI adapter.

record_anthropic_step() records only the FIRST tool_use block, kept as-is
for the common case and backward compatibility. Anthropic can return
SEVERAL tool_use blocks in one response (parallel tool-calling) --
record_anthropic_turn() fans all of them out into their own Steps sharing
one turn, same convention as openai_adapter.record_openai_turn().
"""

from __future__ import annotations

from typing import Any

from loopcheck.adapters._shape import _get
from loopcheck.recorder import TraceRecorder
from loopcheck.trace import Step


def record_anthropic_step(
    recorder: TraceRecorder,
    response: Any,
    tool_result: str | None = None,
    is_error: bool = False,
) -> Step:
    blocks = _get(response, "content") or []

    reasoning_parts: list[str] = []
    tool_name = None
    tool_args: dict[str, Any] = {}

    for block in blocks:
        block_type = _get(block, "type")
        if block_type == "text":
            text = _get(block, "text")
            if text:
                reasoning_parts.append(text)
        elif block_type == "tool_use" and tool_name is None:
            tool_name = _get(block, "name")
            tool_args = dict(_get(block, "input") or {})

    usage = _get(response, "usage")
    input_tokens = _get(usage, "input_tokens", 0) if usage is not None else 0
    output_tokens = _get(usage, "output_tokens", 0) if usage is not None else 0
    reasoning = " ".join(reasoning_parts) if reasoning_parts else None

    if tool_name is not None:
        return recorder.record_step(
            reasoning=reasoning,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_result,
            is_error=is_error,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    return recorder.record_step(
        reasoning=None,
        tool_name=None,
        tool_result=reasoning,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def record_anthropic_turn(
    recorder: TraceRecorder,
    response: Any,
    tool_results: list[str | None] | None = None,
    errors: list[bool] | None = None,
) -> list[Step]:
    """Records EVERY tool_use block in `response` as its own Step, all
    sharing one turn -- use this instead of record_anthropic_step()
    whenever the model might request more than one tool call at once.

    Same token-attribution rule as openai_adapter.record_openai_turn():
    usage describes the whole response, so it's charged entirely to the
    first call in the turn and 0 to the rest, to avoid double-counting
    when a trace's total cost is summed.
    """
    blocks = _get(response, "content") or []

    reasoning_parts: list[str] = []
    tool_blocks: list[Any] = []
    for block in blocks:
        block_type = _get(block, "type")
        if block_type == "text":
            text = _get(block, "text")
            if text:
                reasoning_parts.append(text)
        elif block_type == "tool_use":
            tool_blocks.append(block)

    usage = _get(response, "usage")
    input_tokens = _get(usage, "input_tokens", 0) if usage is not None else 0
    output_tokens = _get(usage, "output_tokens", 0) if usage is not None else 0
    reasoning = " ".join(reasoning_parts) if reasoning_parts else None

    if not tool_blocks:
        return [recorder.record_step(
            reasoning=None,
            tool_name=None,
            tool_result=reasoning,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )]

    results = tool_results or [None] * len(tool_blocks)
    error_flags = errors or [False] * len(tool_blocks)
    results = results + [None] * (len(tool_blocks) - len(results))
    error_flags = error_flags + [False] * (len(tool_blocks) - len(error_flags))

    calls_kwargs = []
    for i, block in enumerate(tool_blocks):
        calls_kwargs.append({
            "reasoning": reasoning if i == 0 else None,
            "tool_name": _get(block, "name"),
            "tool_args": dict(_get(block, "input") or {}),
            "tool_result": results[i],
            "is_error": error_flags[i],
            "input_tokens": input_tokens if i == 0 else 0,
            "output_tokens": output_tokens if i == 0 else 0,
        })

    return recorder.record_parallel_steps(calls_kwargs)
