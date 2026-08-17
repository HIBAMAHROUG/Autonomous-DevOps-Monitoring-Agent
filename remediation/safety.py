from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class SafetyConfig:
    max_actions_per_hour: int = 10
    max_replicas: int = 5
    max_blast_radius: int = 3
    critical_requires_approval: bool = True
    circuit_breaker_failures: int = 3


@dataclass
class SafetyState:
    action_times: list[datetime] = field(default_factory=list)
    consecutive_failures: int = 0
    circuit_open: bool = False
    kill_switch: bool = False
    audit_log: list[dict[str, Any]] = field(default_factory=list)


class SafetyPolicy:

    def __init__(self, config: SafetyConfig | None = None):
        self.config = config or SafetyConfig()
        self.state = SafetyState()

    def check(
        self,
        action_id: str,
        params: dict[str, Any],
        severity: str = "NORMAL",
        approved: bool = False,
    ) -> tuple[bool, str]:

        now = datetime.now()

        # Kill switch
        if self.state.kill_switch:
            return False, "Kill switch is active"

        # Circuit breaker
        if self.state.circuit_open:
            return False, "Circuit breaker is open"

        # Max actions/hour
        one_hour_ago = now - timedelta(hours=1)
        self.state.action_times = [
            t for t in self.state.action_times
            if t > one_hour_ago
        ]

        if len(self.state.action_times) >= self.config.max_actions_per_hour:
            return False, "Maximum actions per hour exceeded"

        # Blast radius
        replicas = params.get("replicas")

        if replicas is not None:
            try:
                replicas = int(replicas)
            except (TypeError, ValueError):
                return False, "Invalid replicas value"

            if replicas > self.config.max_replicas:
                return False, "Blast radius limit exceeded"

        # Critical actions require approval
        if (
            severity.upper() == "CRITICAL"
            and self.config.critical_requires_approval
            and not approved
        ):
            return False, "Human approval required for critical action"

        self.state.action_times.append(now)

        return True, "Safety checks passed"

    def record_result(self, success: bool) -> None:

        if success:
            self.state.consecutive_failures = 0
            return

        self.state.consecutive_failures += 1

        if (
            self.state.consecutive_failures
            >= self.config.circuit_breaker_failures
        ):
            self.state.circuit_open = True

    def activate_kill_switch(self) -> None:
        self.state.kill_switch = True

    def deactivate_kill_switch(self) -> None:
        self.state.kill_switch = False

    def reset_circuit_breaker(self) -> None:
        self.state.consecutive_failures = 0
        self.state.circuit_open = False

    def get_audit_log(self) -> list[dict[str, Any]]:
        return self.state.audit_log

    def audit(
        self,
        action_id: str,
        success: bool,
        message: str,
    ) -> None:

        self.state.audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action_id": action_id,
                "success": success,
                "message": message,
            }
        )
