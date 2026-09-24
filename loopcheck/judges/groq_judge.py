"""
A Judge (see loopcheck/judge.py) backed by a real model over the Groq API.
This is the only piece of loopcheck that needs network access and an API
key -- everything else (v0.1-v0.3, and semantic_redundancy itself) works
fully offline. Requires the optional `judge` extra: `pip install
"loopcheck[judge]"`.
"""

from __future__ import annotations

import json
from typing import Any

from loopcheck.judge import JudgeVerdict

_SYSTEM_PROMPT = (
    "You audit AI agent traces for wasted tool calls. You will be given the "
    "agent's overall goal and two calls it made to the SAME tool with "
    "DIFFERENT arguments. Decide whether the SECOND call was redundant -- "
    "i.e. it was pursuing a sub-goal that the FIRST call's result had "
    "already answered, given the agent's overall goal. Respond with ONLY a "
    "JSON object: {\"is_redundant\": true|false, \"reason\": \"one sentence\"}. "
    "Do not add anything else to your response."
)


class GroqJudge:
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b") -> None:
        try:
            from groq import AsyncGroq
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "GroqJudge needs the 'groq' package -- install with "
                "pip install \"loopcheck[judge]\""
            ) from exc
        self._client = AsyncGroq(api_key=api_key)
        self._model = model

    async def compare(
        self,
        goal: str,
        tool_name: str,
        args_a: dict[str, Any],
        result_a: str,
        args_b: dict[str, Any],
        result_b: str,
    ) -> JudgeVerdict:
        user_prompt = (
            f"Agent's goal: {goal}\n\n"
            f"Tool: {tool_name}\n\n"
            f"First call -- args: {args_a}\nresult: {result_a}\n\n"
            f"Second call -- args: {args_b}\nresult: {result_b}\n\n"
            "Was the second call redundant?"
        )
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
            return JudgeVerdict(
                is_redundant=bool(data.get("is_redundant", False)),
                reason=str(data.get("reason", "")),
            )
        except (json.JSONDecodeError, AttributeError):
            # A judge that returns unparseable output is a reason to skip
            # this pair, not to crash the whole check -- fail closed
            # (not redundant) rather than fail loud.
            return JudgeVerdict(is_redundant=False, reason=f"judge returned unparseable output: {raw!r}")
