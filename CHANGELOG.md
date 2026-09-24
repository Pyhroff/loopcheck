# Changelog

This project is built as an explicit version-incremental prototype: each
stage is a small, working, tested slice rather than one big-bang commit.

## [Unreleased]

## [0.1.0] -- Trace schema + deterministic waste checks
- `loopcheck/trace.py`: `Step`/`Trace` dataclasses -- a flat, framework-agnostic
  JSON schema. No SDK integration, no OpenTelemetry collector: any hand-rolled
  tool-calling loop (raw OpenAI/Anthropic/Groq, or anything else) can be
  logged into this shape directly.
- `checks/duplicate_calls.py`: flags a tool called with the exact same
  arguments more than once after already succeeding -- ignores legitimate
  retries immediately following an error on the same call.
- `checks/loop_thrash.py`: flags a single tool hammered past a threshold
  (default 4) even when no two calls are identical -- the "stuck refining"
  pattern that exact-duplicate detection alone misses.
- `report.py`: severity-sorted text and JSON rendering, with an estimated
  wasted-cost figure (and % of total trace cost) when the trace carries
  token counts and per-1K pricing.
- `cli.py`: `loopcheck analyze <trace.json> [--json PATH] [--fail-on LEVEL]`.
- 3 real sample traces (`samples/`): a clean trace, a wasteful one (exact
  repeat + thrashing), and an error-then-legitimate-retry trace that should
  report clean -- used directly by the CLI test suite, not synthetic mocks.
- 27 tests across trace schema, both checks, report rendering, and
  end-to-end CLI invocation via `typer.testing.CliRunner` against the real
  sample files.

Motivation: every agent-observability tool right now (LangSmith, Braintrust,
Phoenix, Langfuse, DeepEval, MLflow) assumes a production agent with
instrumentation already wired in; the closest existing analog (`redundo`)
still requires OpenTelemetry traces. Nothing targets the "I have a
hand-rolled loop and a JSON trace, tell me if it wasted money" case with
zero setup -- and nothing looks past exact duplicates at thrashing.
