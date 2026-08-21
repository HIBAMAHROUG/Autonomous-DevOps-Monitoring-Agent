from __future__ import annotations

import subprocess

from .base import BaseExecutor, ExecutionResult
from .kubectl_client import run_kubectl


class RollbackExecutor(BaseExecutor):

    def execute(
        self,
        action_id: str,
        params: dict,
        dry_run: bool = True,
    ) -> ExecutionResult:

        deployment = params.get("deployment")

        if not deployment:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="rollback",
                dry_run=dry_run,
                message="Missing deployment",
                error="deployment is required",
            )

        command = [
            "kubectl",
            "rollout",
            "undo",
            f"deployment/{deployment}",
        ]

        if dry_run:
            return ExecutionResult(
                success=True,
                action_id=action_id,
                executor="rollback",
                dry_run=True,
                message=f"DRY-RUN: would rollback '{deployment}'",
                output=" ".join(command),
                metadata={"deployment": deployment},
            )

        try:
            result = run_kubectl(command, timeout=120)

            success = result.returncode == 0

            return ExecutionResult(
                success=success,
                action_id=action_id,
                executor="rollback",
                dry_run=False,
                message="Rollback completed" if success else "Rollback failed",
                output=result.stdout.strip(),
                error=result.stderr.strip() if not success else None,
                metadata={"deployment": deployment},
            )

        except Exception as exc:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="rollback",
                dry_run=False,
                message="Rollback execution failed",
                error=str(exc),
            )
