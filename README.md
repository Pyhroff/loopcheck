# loopcheck

**Zero-instrumentation waste auditor for hand-rolled AI agent loops.**

You built an agent with a raw tool-calling loop -- OpenAI, Anthropic, Groq,
whatever -- no LangChain, no OpenTelemetry collector, no framework. You want
to know: is this thing wasting money? `loopcheck` answers that from a plain
JSON trace, no SDK integration required.

## Why this exists

Every agent observability tool right now (LangSmith, Braintrust, Arize
Phoenix, Langfuse, DeepEval, MLflow) is built for a team with a production
agent and instrumentation already wired in. The closer analog to this idea,
`redundo`, still expects OpenTelemetry traces. None of them are a "just point
this at a trace and get an answer" tool for a hand-rolled loop, and none of
them look past exact duplicate calls at *thrashing* -- an agent that keeps
calling the same tool with slightly different arguments, never converging,
without ever repeating an identical call.

`loopcheck` is deliberately narrow: it doesn't try to be an observability
platform. It answers one question -- **did this specific run waste money** --
from one file, with zero setup.

## Status: version-incremental prototype

Each version below is a complete, working, tested slice, not a stub.
See [CHANGELOG.md](CHANGELOG.md) for the running detail.

| Version | Adds |
|---|---|
| **v0.1** | Trace schema (framework-agnostic JSON) + `duplicate_calls` (exact repeat detection) + `loop_thrash` (same-tool-hammered-repeatedly detection), text/JSON report, cost estimation, CI-gate exit code |

## Quickstart

```bash
pip install -e ".[dev]"

loopcheck analyze samples/wasteful_trace.json
loopcheck analyze samples/clean_trace.json --json report.json --fail-on medium
```

## The trace format

A trace is a flat JSON list of steps -- write it yourself from whatever
loop you already have (log each tool call as you make it), no SDK required:

```json
{
  "agent_name": "research-bot",
  "goal": "what the agent was asked to do",
  "input_cost_per_1k": 0.00015,
  "output_cost_per_1k": 0.0006,
  "steps": [
    {
      "index": 0,
      "reasoning": "optional -- the model's stated plan for this step",
      "tool_name": "web_search",
      "tool_args": {"query": "..."},
      "tool_result": "...",
      "is_error": false,
      "input_tokens": 300,
      "output_tokens": 40
    }
  ]
}
```

A step with `"tool_name": null` is the agent's final answer, not a tool call.

## Checks

- **`duplicate_calls`** -- flags a tool called with the *exact same*
  arguments more than once, after the first call already succeeded. A retry
  immediately following an error on the same call is not flagged (that's
  legitimate); a repeat of a call that already worked is.
- **`loop_thrash`** -- flags a single tool called more than a threshold
  (default 4) times in one trace, even when no two calls are identical --
  the "stuck refining/retrying" pattern duplicate-detection alone can't see.

Both checks are fully deterministic (no LLM judge, no model variance, no
API key needed) and attach an estimated wasted-cost figure when the trace
includes token counts and per-1K pricing.

## CLI reference

```
loopcheck analyze <trace.json>
  --json PATH       write a JSON report
  --fail-on LEVEL   exit 1 if any finding >= LEVEL (info|low|medium|high) -- for CI gates
```

## Project structure

```
loopcheck/
  trace.py              Step/Trace dataclasses, the framework-agnostic schema
  findings.py            Finding/Severity
  report.py              text + JSON rendering, cost aggregation
  cli.py                  typer CLI
  checks/
    duplicate_calls.py    exact-repeat detection
    loop_thrash.py         same-tool-hammered detection
samples/                  real example traces (clean, wasteful, legitimate-retry)
tests/                     27 tests, all against real trace data
```

## Limitations

- v0.1 has no framework adapters (LangChain callback handler, OpenAI/Anthropic
  response parser) -- you write the trace JSON yourself for now. That's the
  natural next version.
- Deterministic checks only, by design, in v0.1 -- no LLM-judge check yet for
  semantic redundancy (two calls that *look* different but pursue the same
  already-answered sub-goal). That needs a live model and is a planned v0.2+.
- Cost estimates are only as accurate as the token counts and per-1K prices
  you put in the trace; loopcheck doesn't call any pricing API.

## License

MIT
