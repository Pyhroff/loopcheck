# 🔁 loopcheck

<div align="center">

**Zero-instrumentation waste auditor for hand-rolled AI agent loops.**

[![CI](https://github.com/Pyhroff/loopcheck/actions/workflows/ci.yml/badge.svg)](https://github.com/Pyhroff/loopcheck/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

## Why loopcheck?

Frameworks can hide the cost and inefficiency of an agent loop.

`loopcheck` works from a plain JSON trace and answers:

- Are tools being called unnecessarily?
- Is the agent thrashing or retrying unchanged work?
- Did a prompt/model/tool change make the loop worse?
- Where is wasted cost accumulating?

It is the **behavior module inside [aisec-suite](https://github.com/Pyhroff/aisec-suite)**.

## Core capabilities

| Command | Purpose |
|---|---|
| `analyze` | Duplicate calls, loop thrashing, stale retries, wasted-cost estimates |
| `compare` | Regression detection between two runs |
| `report` | Aggregate waste across a trace directory |
| `--policy` | Suppress reviewed findings |
| `TraceRecorder` | Capture traces from OpenAI, Anthropic, or Groq-style loops |

## Usage

```bash
loopcheck analyze trace.json
loopcheck analyze trace.json --json report.json --fail-on medium
loopcheck compare before.json after.json --fail-on-regression
loopcheck report traces/ --json rollup.json
```

## Umbrella integration

```bash
aisec behavior trace.json --json behavior-findings.json
```

The umbrella adapter normalizes specialist findings into the shared suite format.

## LLM judge

Semantic redundancy is opt-in:

```bash
GROQ_API_KEY=... loopcheck analyze trace.json --judge groq
```

Deterministic checks do not require a model or API key.

## Limitations

Cost estimates depend on trace token and pricing data. The semantic judge is bounded and model-dependent.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT
