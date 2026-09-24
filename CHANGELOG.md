# Changelog

This project is built as an explicit version-incremental prototype: each
stage is a small, working, tested slice rather than one big-bang commit.

## [Unreleased]

## [0.5.0] -- Regression detection between two runs
- `findings.py`: `Finding` gains a `tool` field, populated by all three
  checks -- gives every finding a stable fingerprint that survives step
  positions shifting between two runs of "the same" trace.
- `compare.py`: `compare_findings(before, after) -> ComparisonResult`.
  Matches findings by `(check, tool, title)`, not `step_indices`. Splits
  into `new_findings` (regressions -- in after, not before) and
  `resolved_findings` (improvements -- in before, not after), plus a wasted-
  cost delta. `.is_regression` is true if anything got worse: a new finding
  appeared, or total wasted cost went up, even if something else also
  improved in the same run.
- `report.py`: `render_comparison`/`to_json_comparison`.
- `loopcheck compare <before.json> <after.json> [--json PATH]
  [--fail-on-regression]` -- a CI gate specifically for "did my prompt/model
  change make this agent more wasteful," distinct from `analyze
  --fail-on`'s "is this run currently over a severity threshold."
- New sample (`samples/wasteful_trace_v2.json`) exercising the realistic
  mixed case: one issue resolved (fewer redundant searches) while a
  different, new one appears (an unrelated duplicate call) -- confirms
  `compare` reports both correctly rather than only netting them out.
- 16 new tests (compare.py fingerprint matching and regression logic, CLI
  compare command against real sample traces both directions, report
  rendering).

87 tests total (was 71).

## [0.4.0] -- Judge-backed semantic redundancy check
- `loopcheck/judge.py`: `Judge` -- a small async Protocol (`.compare(goal,
  tool_name, args_a, result_a, args_b, result_b) -> JudgeVerdict`). Nothing
  else in loopcheck depends on a concrete implementation.
- `checks/semantic_redundancy.py`: catches what duplicate_calls and
  loop_thrash structurally can't -- two calls to the same tool with
  DIFFERENT arguments that a judge decides chased the same already-answered
  sub-goal. Bounded by `max_pairs` (default 20): comparing every same-tool
  pair is O(n^2) judge calls, so this is a sample of the risk on a long
  trace, not an exhaustive audit. Exact-duplicate-argument pairs are never
  sent to the judge -- that's duplicate_calls' job.
- `judges/groq_judge.py`: `GroqJudge`, the first concrete `Judge`, backed by
  a real model over the Groq API. Fails closed (not redundant) on
  unparseable model output rather than crashing the check.
- `loopcheck analyze --judge groq` (needs `GROQ_API_KEY`, `pip install
  "loopcheck[judge]"`) -- `--judge-model` and `--max-judge-pairs` to
  configure it. Every deterministic check still runs with zero setup
  regardless of whether `--judge` is passed.
- 14 new tests -- semantic_redundancy against a fake in-memory Judge
  (candidate-pair generation, exact-dup skipping, mixed verdicts),
  GroqJudge's prompt-building and JSON-parsing (mocked client, no network),
  and two CLI tests for graceful degradation (missing API key, unsupported
  provider name).

71 tests total (was 57). Same honest handling as mcpaudit's --dynamic
check: this is the one piece of loopcheck that needs a live model and
network access, and it's fully isolated behind the Judge Protocol so
everything else stays free and deterministic.

## [0.3.0] -- Parallel tool-call support
- `trace.py`: `Step` gains a `turn` field -- distinguishes the model-turn a
  step belongs to from its flat `index`, so several tool calls requested in
  one model response can be recorded as separate steps that share a turn.
  Backward compatible: a trace with no `turn` field (v0.1/v0.2) loads with
  `turn` defaulting to each step's own `index`.
- `recorder.py`: `TraceRecorder.record_parallel_steps(calls)` records a
  batch of steps under one shared turn number; `record_step()` still gives
  each call its own turn by default, so mixing single and parallel calls in
  one trace keeps turn numbers consistent throughout.
- `adapters/openai_adapter.py`, `adapters/anthropic_adapter.py`,
  `adapters/groq_adapter.py`: each gains a `record_*_turn()` function that
  fans out EVERY tool call in a response (not just the first) into its own
  step. The single-call `record_*_step()` functions are unchanged --
  existing v0.1/v0.2 code and traces keep working exactly as before.
- Token usage in a parallel turn is attributed entirely to the first step
  and 0 to the rest (a response's `usage` describes the whole API call, not
  each tool request within it) -- documented explicitly so summing a
  trace's cost never silently double-counts.
- `duplicate_calls` correctly flags two identical calls requested in the
  SAME turn, not just across separate turns -- a model asking for the same
  tool+args twice in one response is still waste.
- 16 new tests (recorder turn-tracking, both `record_*_turn()` adapters
  against parallel-call fixtures, groq's re-export, and the same-turn
  duplicate-detection case).

57 tests total (was 41). Closes the limitation v0.2's README flagged and
left undone rather than hidden.

## [0.2.0] -- Framework adapters
- `loopcheck/recorder.py`: `TraceRecorder` -- the shared core every adapter
  builds on (`record_step()` appends a `Step`, `.save()` writes trace JSON).
  Adapters only ever translate one provider's response shape into a
  `record_step()` call; they never touch `Trace`/`Step` internals directly.
- `adapters/openai_adapter.py`: parses the OpenAI chat-completions
  tool-calling shape (`choices[0].message.tool_calls`, `.content`,
  `usage.{prompt_tokens,completion_tokens}`).
- `adapters/anthropic_adapter.py`: parses the Anthropic Messages API shape
  (`content` blocks of type `text`/`tool_use`, `usage.{input_tokens,
  output_tokens}`) -- correctly captures a text block as `reasoning` even
  when a `tool_use` block is also present in the same response.
- `adapters/groq_adapter.py`: thin re-export of the OpenAI adapter under a
  Groq-specific name, since Groq's API is OpenAI-compatible -- no
  reimplementation needed, just a name that reads naturally in a Groq loop.
- Every adapter accepts BOTH a real SDK response object (attribute access --
  what `openai>=1.0`/`anthropic>=0.25` actually return) and a plain dict
  (`.model_dump()`, or a hand-built fixture) -- tested against both shapes
  explicitly, not just one.
- 14 new tests (recorder + all three adapters, dict-shaped and
  SimpleNamespace-shaped fixtures for each).
- Known limitation, documented rather than silently handled: only the first
  tool call in a response is recorded as that step's call. Parallel
  tool-calling isn't split into multiple steps yet.

41 tests total (was 27). README updated with a real before/after usage
example showing a loop unchanged except for one `record_*_step()` call per
turn.

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
