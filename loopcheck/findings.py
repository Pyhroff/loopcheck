from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Finding:
    check: str
    severity: Severity
    title: str
    detail: str
    step_indices: list[int]
    wasted_cost: float = 0.0  # estimated USD burned by this finding, 0.0 if not cost-attributable
