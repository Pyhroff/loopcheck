"""
Shared helper: every adapter has to deal with the fact that real SDK
responses are typed objects (pydantic models in openai>=1.0 and
anthropic>=0.25) with attribute access, but the tests in this repo --
and anyone doing a quick manual trace -- reasonably use plain dicts
instead. _get() reads a field either way so adapters don't have to care.
"""

from __future__ import annotations

from typing import Any


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
