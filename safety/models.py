from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SafetyStatus(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    KILL_SWITCH = "KILL_SWITCH"


@dataclass
class SafetyConfig:
    # Maximum d'actions autorisées pendant une fenêtre d'une heure.
    max_actions_per_hour: int = 20

    # Nombre maximum de replicas qu'une seule action peut demander.
    max_replicas: int = 10

    # Nombre maximum d'échecs consécutifs avant ouverture du circuit breaker.
    circuit_breaker_threshold: int = 3

    # Actions critiques nécessitant une validation humaine.
    critical_executors: set[str] = field(
        default_factory=lambda: {
            "failover",
            "rollback",
        }
    )


@dataclass
class SafetyDecision:
    status: SafetyStatus
    allowed: bool
    action_id: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEvent:
    timestamp: str
    action_id: str
    event: str
    status: str
    executor: str
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
