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
| **v0.2** | `TraceRecorder` + adapters for OpenAI, Anthropic, and Groq tool-calling responses -- record a trace directly from your real loop, no hand-written JSON |
| **v0.3** | Parallel tool-call support -- `record_*_turn()` fans every tool call in a single model response out into its own step, sharing a `turn` number |
| **v0.4** | `semantic_redundancy` -- an opt-in, judge-backed check for redundant calls that duplicate_calls can't see (different args, same already-answered sub-goal), via `--judge groq` |
| **v0.5** | `compare` -- regression detection between two runs of the same agent (e.g. before/after a prompt change), `--fail-on-regression` for CI |

## Quickstart

```bash
pip install -e ".[dev]"

loopcheck analyze samples/wasteful_trace.json
loopcheck analyze samples/clean_trace.json --json report.json --fail-on medium
```

## Recording a trace from a real loop (v0.2+)

You don't have to hand-write the trace JSON. `TraceRecorder` plus a small
per-provider adapter turns your existing tool-calling loop into a trace with
three extra lines, whatever provider you're on:

```python
from loopcheck.recorder import TraceRecorder
from loopcheck.adapters.openai_adapter import record_openai_step
# from loopcheck.adapters.anthropic_adapter import record_anthropic_step
# from loopcheck.adapters.groq_adapter import record_groq_step

rec = TraceRecorder(agent_name="research-bot", goal=user_goal, model="gpt-4o-mini",
                     input_cost_per_1k=0.00015, output_cost_per_1k=0.0006)

while True:
    response = client.chat.completions.create(...)   # your existing call, unchanged
    tool_result, is_error = None, False
    if response.choices[0].message.tool_calls:
        tool_result, is_error = run_your_tool(response)  # your existing tool dispatch, unchanged

    step = record_openai_step(rec, response, tool_result=tool_result, is_error=is_error)
    if step.tool_name is None:
        break   # final answer

rec.save("trace.json")
```

```bash
loopcheck analyze trace.json
```

Each adapter accepts either the real SDK response object (attribute access,
what `openai>=1.0`/`anthropic>=0.25` actually return) or a plain dict (e.g.
`response.model_dump()`, or a hand-built test fixture) -- both work
identically. Groq's API is OpenAI-compatible, so `groq_adapter.py` is a thin
re-export of the OpenAI one under a name that reads naturally in a Groq loop.

`record_openai_step`/`record_anthropic_step`/`record_groq_step` record only
the FIRST tool call in a response -- fine when your loop never asks for more
than one tool at a time. If the model can request several tools in a single
response (parallel tool-calling), use the turn-aware versions instead:
`record_openai_turn`, `record_anthropic_turn`, `record_groq_turn`. Each fans
every tool call in that response out into its own step, all sharing one
`turn` number, so `duplicate_calls`/`loop_thrash` still see each call
individually while a report can tell "asked for 3 things at once" apart
from "looped 3 times":

```python
from loopcheck.adapters.openai_adapter import record_openai_turn

response = client.chat.completions.create(...)
results = [run_your_tool(call) for call in response.choices[0].message.tool_calls or []]
steps = record_openai_turn(rec, response, tool_results=results)
if not steps or steps[0].tool_name is None:
    break   # final answer
```

Token usage in a response describes the whole API call, not each individual
tool request within it, so `record_*_turn()` attributes it entirely to the
first step in the turn and 0 to the rest -- summing a trace's cost never
double-counts a parallel turn's usage.

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
- **`semantic_redundancy`** (v0.4+, opt-in) -- catches what the two checks
  above structurally can't: two calls to the same tool with *different*
  arguments that still chase the same already-answered sub-goal (e.g.
  `search(q="chip shortage causes")` then later `search(q="reasons for the
  chip shortage")`). This needs judgment about meaning, so it's the one
  check that isn't free or deterministic -- it's opt-in, and every other
  check works exactly the same with or without it configured.

`duplicate_calls` and `loop_thrash` are fully deterministic (no LLM judge,
no model variance, no API key needed) and attach an estimated wasted-cost
figure when the trace includes token counts and per-1K pricing.

### Running the judge check

```bash
GROQ_API_KEY=... loopcheck analyze trace.json --judge groq
```

`Judge` (`loopcheck/judge.py`) is a small Protocol -- `GroqJudge` is the
only implementation right now, but anything with an async `.compare()`
method works. Comparisons are capped (`--max-judge-pairs`, default 20)
since comparing every same-tool pair is O(n^2) judge calls on a long
trace -- this check is deliberately a bounded sample of the risk, not an
exhaustive audit. Requires the `judge` extra: `pip install
"loopcheck[judge]"`.

## Comparing two runs (v0.5+)

A single `analyze` tells you the current state. `compare` tells you whether
your last change -- a prompt tweak, a model swap, a new tool -- made things
better or worse, which is the question that matters once you're iterating:

```bash
loopcheck compare before.json after.json
loopcheck compare before.json after.json --fail-on-regression   # CI gate on prompt/model changes
```

Findings are matched between the two runs by `(check, tool, title)`, not
step position -- step count and positions shift between runs even when
nothing meaningful changed, so matching on that would either miss real
matches or invent fake ones. A finding present in `after` with no match in
`before` is a **regression**; one present in `before` with no match in
`after` was **resolved**. `--fail-on-regression` fails the build if either
a new finding appeared or total wasted cost went up, even if some other
finding also got resolved in the same run.

## CLI reference

```
loopcheck analyze <trace.json>
  --json PATH       write a JSON report
  --fail-on LEVEL   exit 1 if any finding >= LEVEL (info|low|medium|high) -- for CI gates
  --judge PROVIDER      also run semantic_redundancy against a live model (currently: groq)
  --judge-model MODEL   model for --judge groq [default: openai/gpt-oss-120b]
  --max-judge-pairs N   cap on same-tool pairs compared by --judge [default: 20]

loopcheck compare <before.json> <after.json>
  --json PATH             write a JSON comparison report
  --fail-on-regression    exit 1 if the after run has a new finding or higher wasted cost
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

- `semantic_redundancy` only compares pairs within the SAME tool, and only
  up to `--max-judge-pairs` of them -- it's a bounded sample, not an
  exhaustive pairwise audit of a long trace.
- `GroqJudge` is the only concrete `Judge` today; adding another provider
  is a new class implementing the same small Protocol, not a loopcheck
  code change.
- Cost estimates are only as accurate as the token counts and per-1K prices
  you put in the trace; loopcheck doesn't call any pricing API.

## License

MIT
