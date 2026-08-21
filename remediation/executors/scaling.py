from __future__ import annotations

import subprocess

from .base import BaseExecutor, ExecutionResult
from .kubectl_client import run_kubectl


class ScalingExecutor(BaseExecutor):

    def execute(
        self,
        action_id: str,
        params: dict,
        dry_run: bool = True,
    ) -> ExecutionResult:

        deployment = params.get("deployment")
        replicas = params.get("replicas")
        increment = params.get("increment")

        if not deployment:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="scaling",
                dry_run=dry_run,
                message="Missing deployment",
                error="deployment is required",
            )

        # Cas 1 : nombre exact de replicas
        if replicas is not None:
            command = [
                "kubectl",
                "scale",
                "deployment",
                deployment,
                f"--replicas={replicas}",
            ]

        # Cas 2 : augmenter/diminuer par rapport au nombre actuel
        elif increment is not None:

            try:
                current = run_kubectl(
                    [
                        "kubectl",
                        "get",
                        "deployment",
                        deployment,
                        "-o",
                        "jsonpath={.spec.replicas}",
                    ],
                    timeout=30,
                )

                if current.returncode != 0:
                    return ExecutionResult(
                        success=False,
                        action_id=action_id,
                        executor="scaling",
                        dry_run=dry_run,
                        message="Failed to get current replicas",
                        error=current.stderr.strip(),
                    )

                current_replicas = int(current.stdout.strip() or "0")
                target_replicas = current_replicas + int(increment)

                if target_replicas < 0:
                    target_replicas = 0

                command = [
                    "kubectl",
                    "scale",
                    "deployment",
                    deployment,
                    f"--replicas={target_replicas}",
                ]

            except (ValueError, TypeError) as exc:
                return ExecutionResult(
                    success=False,
                    action_id=action_id,
                    executor="scaling",
                    dry_run=dry_run,
                    message="Invalid increment",
                    error=str(exc),
                )

        else:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="scaling",
                dry_run=dry_run,
                message="Missing replicas/increment",
                error="replicas or increment is required",
            )

        # DRY-RUN : aucune commande réelle
        if dry_run:
            return ExecutionResult(
                success=True,
                action_id=action_id,
                executor="scaling",
                dry_run=True,
                message=f"DRY-RUN: would scale '{deployment}'",
                output=" ".join(command),
                metadata={
                    "deployment": deployment,
                    "replicas": replicas,
                    "increment": increment,
                },
            )

        # EXECUTION REELLE
        try:
            result = run_kubectl(command, timeout=60)

            success = result.returncode == 0

            return ExecutionResult(
                success=success,
                action_id=action_id,
                executor="scaling",
                dry_run=False,
                message=(
                    "Scaling completed"
                    if success
                    else "Scaling failed"
                ),
                output=result.stdout.strip(),
                error=result.stderr.strip() if not success else None,
                metadata={
                    "deployment": deployment,
                    "replicas": replicas,
                    "increment": increment,
                },
            )

        except Exception as exc:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="scaling",
                dry_run=False,
                message="Scaling execution failed",
                error=str(exc),
            )
