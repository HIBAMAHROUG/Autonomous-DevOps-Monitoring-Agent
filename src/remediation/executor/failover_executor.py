from __future__ import annotations

import subprocess

from .base import BaseExecutor, ExecutionResult


class FailoverExecutor(BaseExecutor):

    def execute(
        self,
        action_id: str,
        params: dict,
        dry_run: bool = True,
    ) -> ExecutionResult:

        service = params.get("service")
        target = params.get("target")

        if not service or not target:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="failover",
                dry_run=dry_run,
                message="Missing failover parameters",
                error="service and target are required",
            )

        command = [
            "kubectl",
            "patch",
            "service",
            service,
            "-p",
            f'{{"spec":{{"selector":{{"app":"{target}"}}}}}}',
        ]

        if dry_run:
            return ExecutionResult(
                success=True,
                action_id=action_id,
                executor="failover",
                dry_run=True,
                message=f"DRY-RUN: would failover '{service}' to '{target}'",
                output=" ".join(command),
            )

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

            success = result.returncode == 0

            return ExecutionResult(
                success=success,
                action_id=action_id,
                executor="failover",
                dry_run=False,
                message="Failover completed" if success else "Failover failed",
                output=result.stdout.strip(),
                error=result.stderr.strip() if not success else None,
            )

        except Exception as exc:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="failover",
                dry_run=False,
                message="Failover execution failed",
                error=str(exc),
            )