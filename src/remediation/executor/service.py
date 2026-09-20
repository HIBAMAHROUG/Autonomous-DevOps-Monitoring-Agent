from __future__ import annotations

from typing import Any

from remediation.approvals import approval_store
from remediation.models import Action
from remediation.notifications import notify_approval_required
from remediation.safety import SafetyPolicy
from remediation.verification import (
    DEFAULT_WAIT_SECONDS,
    VerificationResult,
    verify_remediation,
)
from .ansible_executor import AnsibleExecutor
from .base import ExecutionResult
from .cleanup_executor import CleanupExecutor
from .docker_executor import DockerExecutor
from .failover_executor import FailoverExecutor
from .k8s_pod_executor import K8sPodExecutor
from .rollback_executor import RollbackExecutor
from .scaling_executor import ScalingExecutor

APPROVAL_REQUIRED_REASON = "Human approval required for critical action"


class ExecutionService:
    def __init__(self):
        # Persist audit state so the collector and dashboard processes share it.
        self.safety = SafetyPolicy(persist=True)
        self.executors = {
            "docker": DockerExecutor(),
            "docker_restart": DockerExecutor(),
            "k8s_pod_restart": K8sPodExecutor(),
            "kubectl_pod_restart": K8sPodExecutor(),
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
        metric_query: str | None = None,
        threshold: float | None = None,
        comparison: str = "below",
        component: str | None = None,
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
            self.safety.audit(action.action_id, False, reason)

            if reason == APPROVAL_REQUIRED_REASON:
                approval_params = dict(params)
                if metric_query is not None:
                    approval_params["_verification"] = {
                        "metric_query": metric_query,
                        "threshold": threshold,
                        "comparison": comparison,
                        "component": component or action.action_id,
                    }

                approval_store.create(
                    action_id=action.action_id,
                    executor=executor_name,
                    params=approval_params,
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
        self.safety.audit(action.action_id, result.success, result.message)
        return result

    def execute_and_verify(
        self,
        action: Action,
        params: dict[str, Any],
        metric_query: str,
        threshold: float,
        component: str,
        comparison: str = "below",
        dry_run: bool = True,
        severity: str = "NORMAL",
        approved: bool = False,
        wait_seconds: int = DEFAULT_WAIT_SECONDS,
    ) -> tuple[ExecutionResult, VerificationResult | None]:
        result = self.execute(
            action,
            params=params,
            dry_run=dry_run,
            severity=severity,
            approved=approved,
            metric_query=metric_query,
            threshold=threshold,
            comparison=comparison,
            component=component,
        )

        if dry_run or not result.success:
            return result, None

        verification = verify_remediation(
            action_id=action.action_id,
            component=component,
            metric_query=metric_query,
            threshold=threshold,
            comparison=comparison,
            wait_seconds=wait_seconds,
        )
        return result, verification

    def execute_approved(
        self,
        action: Action,
        dry_run: bool = False,
    ) -> ExecutionResult:
        request = approval_store.get(action.action_id)
        if request is None:
            return ExecutionResult(
                success=False,
                action_id=action.action_id,
                executor=action.executor.lower(),
                dry_run=dry_run,
                message="No approval request found",
                error="unknown action_id",
            )

        exec_params = dict(request.params)
        verification_info = exec_params.pop("_verification", None)

        result = self.execute(
            action,
            params=exec_params,
            dry_run=dry_run,
            severity=request.severity,
            approved=True,
        )

        if verification_info and not dry_run and result.success:
            verify_remediation(
                action_id=action.action_id,
                component=verification_info["component"],
                metric_query=verification_info["metric_query"],
                threshold=verification_info["threshold"],
                comparison=verification_info.get("comparison", "below"),
            )

        return result


execution_service = ExecutionService()
