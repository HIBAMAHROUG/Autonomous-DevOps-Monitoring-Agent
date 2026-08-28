"""Persistent human approval queue shared by API and collector."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from storage import audit_store


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
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decided_by": self.decided_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalRequest":
        return cls(
            action_id=data["action_id"],
            executor=data["executor"],
            params=data.get("params") or {},
            severity=data["severity"],
            reason=data["reason"],
            requested_at=datetime.fromisoformat(data["requested_at"]),
            status=ApprovalStatus(data["status"]),
            decided_at=(
                datetime.fromisoformat(data["decided_at"])
                if data.get("decided_at")
                else None
            ),
            decided_by=data.get("decided_by"),
        )


class ApprovalStore:
    def __init__(self, persist: bool = True) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self.persist = persist
        self._reload()

    def _reload(self) -> None:
        if not self.persist:
            return
        self._requests = {
            request.action_id: request
            for row in audit_store.load_approvals()
            for request in [ApprovalRequest.from_dict(row)]
        }

    def create(self, action_id, executor, params, severity, reason):
        request = ApprovalRequest(
            action_id=action_id,
            executor=executor,
            params=params,
            severity=severity,
            reason=reason,
        )
        self._requests[action_id] = request
        if self.persist:
            audit_store.upsert_approval(request.to_dict())
        return request

    def get(self, action_id: str):
        self._reload()
        return self._requests.get(action_id)

    def list_pending(self):
        self._reload()
        return [
            request
            for request in self._requests.values()
            if request.status == ApprovalStatus.PENDING
        ]

    def list_all(self):
        self._reload()
        return sorted(
            self._requests.values(),
            key=lambda request: request.requested_at,
            reverse=True,
        )

    def decide(self, action_id, approve, decided_by=None):
        self._reload()
        request = self._requests.get(action_id)
        if request is None or request.status != ApprovalStatus.PENDING:
            return None

        request.status = (
            ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
        )
        request.decided_at = datetime.now(timezone.utc)
        request.decided_by = decided_by

        if self.persist:
            audit_store.upsert_approval(request.to_dict())
        return request


approval_store = ApprovalStore(persist=True)
