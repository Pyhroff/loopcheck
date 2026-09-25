"""
Finding-suppression policy -- the same real gap mcpaudit's v0.5 solved,
applied to loopcheck: a real scan turns up findings that are true but
already reviewed and accepted (a loop_thrash threshold that's genuinely
fine for a known polling pattern, a duplicate call that's actually
intentional cache-busting). Without a way to say "reviewed, this is fine,"
--fail-on becomes unusable in CI -- the first accepted finding blocks
every future run forever.

Deliberately NOT a blanket severity suppression -- a rule targets a
specific (tool, check[, title]), matching Finding's own fingerprint from
compare.py, so a new, different finding on the same tool still surfaces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from loopcheck.findings import Finding


@dataclass
class PolicyRule:
    tool: str = "*"           # "*" matches any tool (including findings with tool=None)
    check: str | None = None  # e.g. "loop_thrash"; None matches any check
    title: str | None = None  # exact Finding.title; None matches any title
    reason: str = ""          # human-readable justification, not enforced, just recorded

    def matches(self, finding: Finding) -> bool:
        if self.tool != "*" and self.tool != finding.tool:
            return False
        if self.check is not None and self.check != finding.check:
            return False
        if self.title is not None and self.title != finding.title:
            return False
        return True


@dataclass
class Policy:
    rules: list[PolicyRule] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Policy":
        return cls(rules=[PolicyRule(**r) for r in d.get("ignore", [])])

    @classmethod
    def load(cls, path: Path) -> "Policy":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def apply(self, findings: list[Finding]) -> tuple[list[Finding], list[Finding]]:
        """Returns (kept, suppressed). A finding is suppressed if ANY rule matches it."""
        kept: list[Finding] = []
        suppressed: list[Finding] = []
        for f in findings:
            if any(rule.matches(f) for rule in self.rules):
                suppressed.append(f)
            else:
                kept.append(f)
        return kept, suppressed
