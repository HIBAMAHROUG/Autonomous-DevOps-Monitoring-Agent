from __future__ import annotations

import os
import platform
import subprocess
from datetime import datetime, timedelta

from .base import BaseExecutor, ExecutionResult


class CleanupExecutor(BaseExecutor):

    def execute(
        self,
        action_id: str,
        params: dict,
        dry_run: bool = True,
    ) -> ExecutionResult:

        path = params.get("path", "/var/log")
        older_than = params.get("older_than_days", 7)

        if dry_run:
            if platform.system() == "Windows":
                command = (
                    f"PowerShell: remove files older than {older_than} days "
                    f"from '{path}'"
                )
            else:
                command = (
                    f"find {path} -type f -mtime +{older_than} -delete"
                )

            return ExecutionResult(
                success=True,
                action_id=action_id,
                executor="cleanup",
                dry_run=True,
                message=f"DRY-RUN: would clean logs in {path}",
                output=command,
                metadata={
                    "path": path,
                    "older_than_days": older_than,
                },
            )

        try:
            if not os.path.isdir(path):
                return ExecutionResult(
                    success=False,
                    action_id=action_id,
                    executor="cleanup",
                    dry_run=False,
                    message="Log cleanup failed",
                    error=f"Directory does not exist: {path}",
                )

            cutoff = datetime.now() - timedelta(days=int(older_than))
            deleted = []

            for root, _, files in os.walk(path):
                for filename in files:
                    filepath = os.path.join(root, filename)

                    try:
                        modified = datetime.fromtimestamp(
                            os.path.getmtime(filepath)
                        )

                        if modified < cutoff:
                            os.remove(filepath)
                            deleted.append(filepath)

                    except OSError as exc:
                        return ExecutionResult(
                            success=False,
                            action_id=action_id,
                            executor="cleanup",
                            dry_run=False,
                            message="Log cleanup failed",
                            error=str(exc),
                            metadata={
                                "path": path,
                                "deleted_files": deleted,
                            },
                        )

            return ExecutionResult(
                success=True,
                action_id=action_id,
                executor="cleanup",
                dry_run=False,
                message="Log cleanup completed",
                output="\n".join(deleted),
                metadata={
                    "path": path,
                    "older_than_days": older_than,
                    "deleted_count": len(deleted),
                    "deleted_files": deleted,
                },
            )

        except Exception as exc:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="cleanup",
                dry_run=False,
                message="Cleanup execution failed",
                error=str(exc),
            )
