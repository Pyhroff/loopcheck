# loopcheck Evaluation Methodology

Evaluate agent-loop regressions from deterministic JSON traces.

Core metrics should include duplicate-call rate, retry/thrashing counts, estimated wasted tokens/cost, and regression pass/fail against an approved baseline.

For semantic judge experiments, record model identifier, prompt version, trial count and judge configuration. Never mix judge-dependent results with deterministic metrics.

A benchmark should include clean traces, known-wasteful traces, and changed traces where the expected regression outcome is explicitly labeled.

The benchmark is a controlled engineering regression suite, not a claim about the efficiency of arbitrary production agents.