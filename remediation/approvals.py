"""File d'approbations humaines pour les actions critiques (US 4.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class ApprovalRequest:
    action_id: str
    executor: str
    params: dict[str, Any]
    severity: str
    reason: str
    requested_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_at: datetime | None = None
    decided_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "executor": self.executor,
            "params": self.params,
            "severity": self.severity,
            "reason": self.reason,
            "requested_at": self.requested_at.isoformat(),
            "status": self.status.value,
            "decided_at": (
                self.decided_at.isoformat()
                if self.decided_at
                else None
            ),
            "decided_by": self.decided_by,
        }


class ApprovalStore:
    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    def create(
        self,
        action_id: str,
        executor: str,
        params: dict[str, Any],
        severity: str,
        reason: str,
    ) -> ApprovalRequest:
        """Crée ou remplace une demande d'approbation."""
        request = ApprovalRequest(
            action_id=action_id,
            executor=executor,
            params=params,
            severity=severity,
            reason=reason,
        )

        self._requests[action_id] = request
        return request

    def get(self, action_id: str) -> ApprovalRequest | None:
        return self._requests.get(action_id)

    def list_pending(self) -> list[ApprovalRequest]:
        return [
            request
            for request in self._requests.values()
            if request.status == ApprovalStatus.PENDING
        ]

    def list_all(self) -> list[ApprovalRequest]:
        return sorted(
            self._requests.values(),
            key=lambda request: request.requested_at,
            reverse=True,
        )

    def decide(
        self,
        action_id: str,
        approve: bool,
        decided_by: str | None = None,
    ) -> ApprovalRequest | None:
        """
        Décide une demande uniquement si elle est encore PENDING.

        Retourne None si elle n'existe pas ou si elle a déjà été décidée.
        """
        request = self._requests.get(action_id)

        if request is None:
            return None

        if request.status != ApprovalStatus.PENDING:
            return None

        request.status = (
            ApprovalStatus.APPROVED
            if approve
            else ApprovalStatus.REJECTED
        )

        request.decided_at = datetime.now(timezone.utc)
        request.decided_by = decided_by

        return request


# Instance partagée par l'API Flask et l'ExecutionService.
approval_store = ApprovalStore()
