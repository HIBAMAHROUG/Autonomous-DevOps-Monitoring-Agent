from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionMode(str, Enum):
    AUTO_EXECUTE = "AUTO_EXECUTE"
    SUGGEST_TO_HUMAN = "SUGGEST_TO_HUMAN"
    ESCALATE = "ESCALATE"


@dataclass
class Action:
    action_id: str
    name: str
    type: str
    executor: str
    params_schema: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "medium"
    reversible: bool = True
    avg_resolution_time_s: float = 0
    success_rate_historical: float = 0.5


@dataclass
class Problem:
    problem_id: str
    title: str
    category: str
    metric: str
    condition: str
    affected_component: str
    duration_s: int = 0
    known_causes: list[str] = field(default_factory=list)
    corrective_actions: list[str] = field(default_factory=list)
    severity_default: Severity = Severity.MEDIUM
    tags: list[str] = field(default_factory=list)
    occurrences: int = 0
    last_updated: datetime | None = None


@dataclass
class AnomalyEvent:
    anomaly_id: str
    metric: str
    component: str
    severity: Severity
    description: str = ""
    detected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class CandidateAction:
    action: Action
    source_problem: Problem
    match_score: float
    match_type: str


@dataclass
class ScoredCandidate:
    candidate: CandidateAction
    confidence: float


@dataclass
class Decision:
    decision_id: str
    anomaly_id: str
    matched_problem_id: str | None
    candidate_actions: list[dict[str, Any]]
    chosen_action_id: str | None
    decision_mode: DecisionMode
    confidence: float | None
    reason: str
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @staticmethod
    def new_id() -> str:
        return str(uuid4())


