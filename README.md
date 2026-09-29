# loopcheck

[![CI](https://github.com/Pyhroff/loopcheck/actions/workflows/ci.yml/badge.svg)](https://github.com/Pyhroff/loopcheck/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Zero-instrumentation waste auditor for hand-rolled AI agent loops.**

You built an agent with a raw tool-calling loop -- OpenAI, Anthropic, Groq,
whatever -- no LangChain, no OpenTelemetry collector, no framework. You want
to know: is this thing wasting money, is it getting better or worse as you
iterate, and is a CI gate on that actually usable without drowning in
already-reviewed findings? `loopcheck` answers all three from a plain JSON
trace, no SDK integration required.

```bash
$ loopcheck analyze samples/wasteful_trace.json

loopcheck -- research-bot (6 step(s), goal: 'Summarize the top 3 causes of the 2026 chip shortage.')

MEDIUM   duplicate_calls  Repeated tool call with identical arguments
          Tool 'web_search' was called with the same arguments {'query': '2026
chip shortage causes'} at steps [0, 4], after already succeeding earlier in
the trace. Repeat call(s) at [4] produced no new information.
          est. wasted cost: $0.0001

MEDIUM   loop_thrash      Tool called far more than expected for a single trace
          Tool 'web_search' was called 5 times in one trace (steps [0, 1, 2,
3, 4]) -- past 4 calls to the same tool in a single agent run usually means
it's stuck refining/retrying rather than making progress.
          est. wasted cost: $0.0001

Total trace cost: $0.0005  |  Estimated wasted: $0.0001 (32.1%)
```

## Why

Agent observability platforms (LangSmith, Langfuse, Arize Phoenix and others) assume a production agent with instrumentation already in place. If you have a hand-rolled tool-calling loop and want to know whether one run wasted money, or whether a prompt change made things better or worse, you mostly end up reading logs.

loopcheck reads a plain JSON trace and reports wasted tool calls. It does not try to be an observability platform. It looks past exact duplicate calls for thrashing (the same tool called repeatedly with slightly different arguments, never converging) and for failing calls retried unchanged.

## Features

| Command / feature | What it does |
|---|---|
| `analyze` | Runs the checks on one trace, prints findings and estimated wasted cost, optional CI gate |
| `TraceRecorder` + adapters | Record a trace from an OpenAI, Anthropic, or Groq tool-calling loop, including parallel tool calls |
| `compare` | Regression detection between two runs of the same agent, with `--fail-on-regression` |
| `report` | Aggregate waste across a directory of traces (by check, by tool, worst runs) |
| `--policy` | Suppress reviewed findings across `analyze`, `compare`, and `report` |
| `--judge groq` | Optional model-backed `semantic_redundancy` check |

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

## Aggregating across many runs (v0.6+)

`analyze` is one run, `compare` is two. `report` is however many you have --
point it at a directory of trace files and it rolls waste up across the
whole batch: total cost and wasted cost, which check fires most, which tool
is the worst offender, and the worst individual traces by wasted cost.
This is the view that catches an agent bleeding money steadily across many
runs even when no single run is bad enough to trip `analyze --fail-on`:

```bash
loopcheck report traces/
loopcheck report traces/ --json rollup.json --fail-on high --top 10
```

`--fail-on` here gates on any SINGLE trace in the batch having a finding at
or above that severity (a per-run check applied across the batch), distinct
from `compare --fail-on-regression`'s "did this get worse" and `analyze
--fail-on`'s "is this one run bad."

## Suppressing accepted findings (v0.7+)

A real scan turns up findings that are true but already reviewed and
accepted -- a `loop_thrash` threshold that's genuinely fine for a known
polling pattern, a `duplicate_calls` hit that's actually intentional
cache-busting. Without a way to say "reviewed, this is fine," `--fail-on`
becomes unusable in CI: the first accepted finding blocks every future run
forever. `--policy` fixes that, the same way it does in
[mcpaudit](https://github.com/Pyhroff/mcpaudit) -- and works across
all three commands:

```bash
loopcheck analyze trace.json --policy policy.json --fail-on high
loopcheck compare before.json after.json --policy policy.json --fail-on-regression
loopcheck report traces/ --policy policy.json --fail-on high
```

```json
{
  "ignore": [
    {
      "tool": "web_search",
      "check": "loop_thrash",
      "reason": "why this is accepted -- shown for humans, not enforced"
    }
  ]
}
```

`tool: "*"` matches any tool; omitting `title` matches any finding for that
`(tool, check)`. See [`samples/example-policy.json`](samples/example-policy.json).
Suppressed findings are dropped before the printed report, `--json`, and
`--fail-on`/`--fail-on-regression` all see them. In `compare`, a policy is
applied to BOTH runs before matching -- a suppressed finding never shows up
as a "regression" or a "resolved" improvement either, it's just gone, the
same as if the check had never fired.

## CLI reference

```
loopcheck analyze <trace.json>
  --json PATH       write a JSON report
  --fail-on LEVEL   exit 1 if any finding >= LEVEL (info|low|medium|high) -- for CI gates
  --judge PROVIDER      also run semantic_redundancy against a live model (currently: groq)
  --judge-model MODEL   model for --judge groq [default: openai/gpt-oss-120b]
  --max-judge-pairs N   cap on same-tool pairs compared by --judge [default: 20]
  --policy PATH         suppress reviewed findings (see samples/example-policy.json)

loopcheck compare <before.json> <after.json>
  --json PATH             write a JSON comparison report
  --fail-on-regression    exit 1 if the after run has a new finding or higher wasted cost
  --policy PATH           suppress reviewed findings from BOTH runs before comparing

loopcheck report <trace_dir>
  --json PATH       write a JSON rollup report
  --fail-on LEVEL   exit 1 if any single trace in the batch has a finding >= LEVEL
  --top N           how many worst-offending traces to list [default: 5]
  --policy PATH     suppress reviewed findings from every trace before aggregating
```

## Project structure

```
loopcheck/
  trace.py                    Step/Trace dataclasses -- the framework-agnostic schema (v0.1)
  recorder.py                  TraceRecorder -- record a trace from a real loop (v0.2)
  findings.py                   Finding/Severity
  judge.py                      Judge Protocol for semantic_redundancy (v0.4)
  policy.py                     PolicyRule/Policy -- suppress reviewed findings (v0.7)
  compare.py                    regression detection between two runs (v0.5)
  aggregate.py                   fleet-level rollup across many runs (v0.6)
  report.py                      text + JSON rendering for all four report shapes
  cli.py                          typer CLI -- analyze / compare / report
  checks/
    duplicate_calls.py           exact-repeat detection (v0.1)
    loop_thrash.py                same-tool-hammered detection (v0.1)
    semantic_redundancy.py         judge-backed, opt-in (v0.4)
  adapters/                     OpenAI / Anthropic / Groq response -> Step (v0.2, v0.3)
  judges/
    groq_judge.py                 the one concrete Judge today (v0.4)
samples/                       real example traces (clean, wasteful, a legitimate-retry
                                case, a regressed variant) plus an example policy file
tests/                          121 tests
.github/workflows/ci.yml        tests + a CLI smoke test against real sample traces,
                                 on every push, across Python 3.10/3.11/3.12
```

## Development

```bash
git clone https://github.com/Pyhroff/loopcheck.git
cd loopcheck
pip install -e ".[dev,judge]"
pytest -q      # 121 tests
```

Every check in `checks/` (except `semantic_redundancy`, which needs a
`Judge`) is pure and deterministic -- no network, no API key, no mocking
required to test it end to end. The judge-backed and CLI tests mock only
the boundary that actually needs it (the Groq SDK client, typer's own
`CliRunner`), never the logic being tested.

## Limitations

- `semantic_redundancy` only compares pairs within the SAME tool, and only
  up to `--max-judge-pairs` of them -- it's a bounded sample, not an
  exhaustive pairwise audit of a long trace.
- `GroqJudge` is the only `Judge` implementation. Another provider means a new class implementing the same small Protocol.
- Cost estimates are only as accurate as the token counts and per-1K prices
  you put in the trace; loopcheck doesn't call any pricing API.

## License

MIT
