from __future__ import annotations

from typing import Any

from remediation.approvals import approval_store
from remediation.models import Action
from remediation.notifications import notify_approval_required
from remediation.safety import SafetyPolicy

from .ansible_executor import AnsibleExecutor
from .base import ExecutionResult
from .cleanup_executor import CleanupExecutor
from .docker_executor import DockerExecutor
from .failover_executor import FailoverExecutor
from .rollback_executor import RollbackExecutor
from .scaling_executor import ScalingExecutor


APPROVAL_REQUIRED_REASON = "Human approval required for critical action"


class ExecutionService:

    def __init__(self):
        self.safety = SafetyPolicy()

        self.executors = {
            "docker": DockerExecutor(),
            "docker_restart": DockerExecutor(),
            "scaling": ScalingExecutor(),
            "kubectl_scale": ScalingExecutor(),
            "cleanup": CleanupExecutor(),
            "log_cleanup": CleanupExecutor(),
            "failover": FailoverExecutor(),
            "rollback": RollbackExecutor(),
            "ansible": AnsibleExecutor(),
        }

    def execute(
        self,
        action: Action,
        params: dict[str, Any],
        dry_run: bool = True,
        severity: str = "NORMAL",
        approved: bool = False,
    ) -> ExecutionResult:

        executor_name = action.executor.lower()

        executor = self.executors.get(executor_name)

        if executor is None:
            return ExecutionResult(
                success=False,
                action_id=action.action_id,
                executor=executor_name,
                dry_run=dry_run,
                message=f"Unsupported executor: {executor_name}",
                error=f"No executor registered for '{executor_name}'",
            )

        allowed, reason = self.safety.check(
            action_id=action.action_id,
            params=params,
            severity=severity,
            approved=approved,
        )

        if not allowed:
            result = ExecutionResult(
                success=False,
                action_id=action.action_id,
                executor=executor_name,
                dry_run=dry_run,
                message=f"BLOCKED: {reason}",
                error=reason,
            )

            self.safety.audit(
                action.action_id,
                False,
                reason,
            )

            # US 4.2 : une action bloquée faute d'approbation déclenche la
            # notification et alimente la file consultable via le dashboard.
            if reason == APPROVAL_REQUIRED_REASON:
                approval_store.create(
                    action_id=action.action_id,
                    executor=executor_name,
                    params=params,
                    severity=severity,
                    reason=reason,
                )

                notify_approval_required(
                    action.action_id,
                    executor_name,
                    severity,
                    reason,
                )

            return result

        result = executor.execute(
            action_id=action.action_id,
            params=params,
            dry_run=dry_run,
        )

        self.safety.record_result(result.success)

        self.safety.audit(
            action.action_id,
            result.success,
            result.message,
        )

        return result

    def execute_approved(
        self,
        action: Action,
        dry_run: bool = True,
    ) -> ExecutionResult:
        """
        À appeler après qu'une ApprovalRequest a été approuvée via
        POST /api/approvals/<action_id>/approve. Rejoue l'exécution avec
        approved=True (elle reste soumise aux autres garde-fous : rate
        limiting, circuit breaker, kill switch).
        """

        request = approval_store.get(action.action_id)

        if request is None:
            return ExecutionResult(
                success=False,
                action_id=action.action_id,
                executor=action.executor.lower(),
                dry_run=dry_run,
                message="No approval request found for this action",
                error="unknown action_id",
            )

        return self.execute(
            action,
            params=request.params,
            dry_run=dry_run,
            severity=request.severity,
            approved=True,
        )


# Instance partagée par l'API Flask (dashboard, approvals) et le moteur de
# décision, pour que le journal d'audit et la file d'approbation soient
# cohérents sur tout le process.
execution_service = ExecutionService()
