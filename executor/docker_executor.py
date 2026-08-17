from __future__ import annotations

import subprocess

from .base import BaseExecutor, ExecutionResult


class DockerExecutor(BaseExecutor):

    def execute(
        self,
        action_id: str,
        params: dict,
        dry_run: bool = True,
    ) -> ExecutionResult:

        container = params.get("container_name") or params.get("service_name")

        if not container:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="docker",
                dry_run=dry_run,
                message="Missing container_name/service_name",
                error="container_name is required",
            )

        command = ["docker", "restart", container]

        if dry_run:
            return ExecutionResult(
                success=True,
                action_id=action_id,
                executor="docker",
                dry_run=True,
                message=f"DRY-RUN: would restart container '{container}'",
                output=" ".join(command),
                metadata={"container": container},
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
                executor="docker",
                dry_run=False,
                message=(
                    f"Container '{container}' restarted"
                    if success
                    else f"Failed to restart '{container}'"
                ),
                output=result.stdout.strip(),
                error=result.stderr.strip() if not success else None,
                metadata={"container": container},
            )

        except Exception as exc:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="docker",
                dry_run=False,
                message="Docker execution failed",
                error=str(exc),
            )