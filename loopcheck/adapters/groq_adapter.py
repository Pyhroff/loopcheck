"""
Groq's chat-completions API is OpenAI-compatible, so there's nothing to
reimplement -- this module exists so `from loopcheck.adapters.groq_adapter
import record_groq_step` reads naturally in a Groq-based loop, without
making the reader go find out that Groq == OpenAI shape for themselves.
"""

from __future__ import annotations

from loopcheck.adapters.openai_adapter import record_openai_step as record_groq_step

__all__ = ["record_groq_step"]
