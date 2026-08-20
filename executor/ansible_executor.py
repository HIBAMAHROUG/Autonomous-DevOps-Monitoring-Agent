from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .base import BaseExecutor, ExecutionResult


PLAYBOOKS_DIR = (
    Path(__file__).resolve().parent.parent
    / "ansible"
    / "playbooks"
)

DEFAULT_INVENTORY = os.getenv(
    "ANSIBLE_INVENTORY",
    str(
        Path(__file__).resolve().parent.parent
        / "ansible"
        / "inventory"
        / "hosts.ini"
    ),
)


# Playbooks autorises explicitement.
# Cela empeche l'execution d'un playbook arbitraire.
ALLOWED_PLAYBOOKS = {
    "cleanup_disk_space": PLAYBOOKS_DIR / "cleanup_disk_space.yml",
    "restart_service": PLAYBOOKS_DIR / "restart_service.yml",
}


class AnsibleExecutor(BaseExecutor):
    """
    Execute les playbooks Ansible de remediation OS.

    Le mode dry_run utilise le --check natif d'Ansible.
    """

    def execute(
        self,
        action_id: str,
        params: dict,
        dry_run: bool = True,
    ) -> ExecutionResult:

        playbook_key = params.get("playbook")
        playbook_path = ALLOWED_PLAYBOOKS.get(playbook_key)

        # Verifier que le playbook est autorise.
        if playbook_path is None:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="ansible",
                dry_run=dry_run,
                message="Playbook inconnu ou non autorise",
                error=(
                    f"'{playbook_key}' n'est pas dans "
                    f"ALLOWED_PLAYBOOKS: {list(ALLOWED_PLAYBOOKS)}"
                ),
            )

        # Verifier que le fichier existe.
        if not playbook_path.exists():
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="ansible",
                dry_run=dry_run,
                message="Playbook introuvable",
                error=f"Fichier absent: {playbook_path}",
            )

        target_host = params.get("target_host")

        # Tous les parametres sauf ceux internes a l'executor
        # sont transmis a Ansible comme extra-vars.
        extra_vars = {
            k: v
            for k, v in params.items()
            if k not in ("playbook", "target_host")
        }

        command = [
            "ansible-playbook",
            str(playbook_path),
            "-i",
            DEFAULT_INVENTORY,
            "--extra-vars",
            json.dumps(extra_vars),
        ]

        if target_host:
            command += ["--limit", target_host]

        # Dry-run = simulation native Ansible.
        if dry_run:
            command.append("--check")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )

            success = result.returncode == 0

            return ExecutionResult(
                success=success,
                action_id=action_id,
                executor="ansible",
                dry_run=dry_run,
                message=(
                    f"Playbook '{playbook_key}' "
                    f"{'simule' if dry_run else 'execute'} avec succes"
                    if success
                    else f"Echec du playbook '{playbook_key}'"
                ),
                output=result.stdout.strip(),
                error=(
                    result.stderr.strip()
                    if not success
                    else None
                ),
                metadata={
                    "playbook": playbook_key,
                    "target_host": target_host,
                },
            )

        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="ansible",
                dry_run=dry_run,
                message="ansible-playbook introuvable sur cet hote",
                error=(
                    "La commande 'ansible-playbook' "
                    "n'est pas installee ou absente du PATH"
                ),
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="ansible",
                dry_run=dry_run,
                message="Timeout de l'execution du playbook",
                error="Delai de 120 secondes depasse",
            )

        except Exception as exc:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                executor="ansible",
                dry_run=dry_run,
                message="Execution Ansible echouee",
                error=str(exc),
            )
