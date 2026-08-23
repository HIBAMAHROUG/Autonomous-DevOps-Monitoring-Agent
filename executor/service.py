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
        metric_query: str | None = None,
        threshold: float | None = None,
        comparison: str = "below",
        component: str | None = None,
    ) -> ExecutionResult:
        """
        Args (nouveaux, tous optionnels -- rétrocompatible) :
            metric_query, threshold, comparison, component : si fournis et
            que l'action nécessite une approbation humaine, ces infos sont
            attachées à la demande d'approbation (clé réservée
            `_verification` dans `params`) afin que `execute_approved()`
            puisse déclencher la vérification post-remédiation (US 3.2)
            une fois l'action effectivement exécutée.
        """

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
                approval_params = dict(params)

                if metric_query is not None:
                    # US 3.2 : conservé pour que execute_approved() puisse
                    # revérifier l'incident après une exécution approuvée.
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

        self.safety.audit(
            action.action_id,
            result.success,
            result.message,
        )

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
        """
        US 3.2 : exécute l'action puis vérifie que l'incident est
        réellement résolu.

        - Si `dry_run=True` ou si l'exécution a échoué/été bloquée
          (y compris bloquée en attente d'approbation), aucune
          vérification n'est effectuée (rien à vérifier).
        - Sinon, attend `wait_seconds` puis revérifie la métrique via
          Prometheus. Si le problème persiste, l'incident est escaladé à
          l'équipe de garde (voir remediation.notifications).

        C'est le point d'entrée à utiliser pour le chemin AUTO_EXECUTE
        (voir orchestrator.py) : sans lui, une décision AUTO_EXECUTE
        s'exécutait mais n'était jamais revérifiée.

        Retourne (ExecutionResult, VerificationResult | None).
        """

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
        dry_run: bool = True,
    ) -> ExecutionResult:
        """
        À appeler après qu'une ApprovalRequest a été approuvée via
        POST /api/approvals/<action_id>/approve. Rejoue l'exécution avec
        approved=True (elle reste soumise aux autres garde-fous : rate
        limiting, circuit breaker, kill switch).

        US 3.2 : si la demande d'approbation transportait des infos de
        vérification (voir execute()), et que l'exécution réussit hors
        dry-run, la métrique concernée est revérifiée après un délai
        d'observation ; en cas de persistance du problème, l'incident est
        escaladé à l'équipe de garde (remediation.notifications).
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


# Instance partagée par l'API Flask (dashboard, approvals) et le moteur de
# décision, pour que le journal d'audit et la file d'approbation soient
# cohérents sur tout le process.
execution_service = ExecutionService()