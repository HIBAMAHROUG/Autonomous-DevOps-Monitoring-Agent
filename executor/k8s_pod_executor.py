from __future__ import annotations

import os
import subprocess
from typing import Any

from .base import BaseExecutor, ExecutionResult


class K8sPodExecutor(BaseExecutor):
    """Restart a Kubernetes pod through kubectl."""

    def execute(
        self,
        action_id: str,
        params: dict[str, Any],
        dry_run: bool = True,
    ) -> ExecutionResult:
        pod = params.get("pod_name") or params.get("pod_id")
        namespace = params.get("namespace") or os.getenv("K8S_NAMESPACE", "default")

        if not pod:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="k8s_pod_restart",
                dry_run=dry_run,
                message="Missing pod_name",
                error="missing pod_name",
            )

        command = [
            "kubectl",
            "--kubeconfig",
            os.getenv("KUBECONFIG", ""),
            "-n",
            str(namespace),
            "delete",
            "pod",
            str(pod),
            "--wait=true",
            "--timeout=60s",
        ]
        if not command[2]:
            command = [
                "kubectl",
                "-n",
                str(namespace),
                "delete",
                "pod",
                str(pod),
                "--wait=true",
                "--timeout=60s",
            ]

        if dry_run:
            return ExecutionResult(
                success=True,
                action_id=action_id,
                executor="k8s_pod_restart",
                dry_run=True,
                message=f"DRY RUN: {' '.join(command)}",
            )

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=75,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="k8s_pod_restart",
                dry_run=False,
                message="kubectl execution failed",
                error=str(exc),
            )

        if completed.returncode != 0:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="k8s_pod_restart",
                dry_run=False,
                message=completed.stdout.strip(),
                error=completed.stderr.strip() or "kubectl returned non-zero status",
            )

        return ExecutionResult(
            success=True,
            action_id=action_id,
            executor="k8s_pod_restart",
            dry_run=False,
            message=completed.stdout.strip() or f"Pod {pod} restarted",
        )
