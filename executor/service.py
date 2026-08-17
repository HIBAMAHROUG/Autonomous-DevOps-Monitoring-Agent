from __future__ import annotations

from typing import Any

from remediation.models import Action
from remediation.safety import SafetyPolicy

from .base import ExecutionResult
from .cleanup_executor import CleanupExecutor
from .docker_executor import DockerExecutor
from .failover_executor import FailoverExecutor
from .rollback_executor import RollbackExecutor
from .scaling_executor import ScalingExecutor


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
