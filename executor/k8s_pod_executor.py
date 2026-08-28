from __future__ import annotations

from typing import Any

from .base import BaseExecutor, ExecutionResult


class K8sPodExecutor(BaseExecutor):
    """Stub temporaire pour les actions de remediation Kubernetes
    (ex: k8s_pod_restart). A brancher sur le module k8s existant."""

    def execute(
        self,
        action_id: str,
        params: dict[str, Any],
        dry_run: bool = True,
    ) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            action_id=action_id,
            executor="k8s_pod",
            dry_run=dry_run,
            message="K8sPodExecutor non implemente pour le moment",
        )