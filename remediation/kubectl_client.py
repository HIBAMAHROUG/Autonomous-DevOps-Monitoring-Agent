"""
Client kubectl partagé par tous les executors Kubernetes
(scaling, rollback, failover).

Corrige le Bug 3 du cahier des charges : perte de connexion avec l'API
Kubernetes (réseau ou rotation de certificats).

Comportement :
- Retry avec backoff exponentiel sur les erreurs qui ressemblent à un
  problème de connectivité (timeout, "unable to connect", "connection
  refused", "dial tcp", etc.) plutôt que sur des erreurs applicatives
  (ex : ressource introuvable), qu'il ne sert à rien de retenter.
- Si la connectivité reste indisponible pendant plus de
  OFFLINE_THRESHOLD_SECONDS (5 minutes par défaut), déclenche une alerte
  "Agent Offline" via un canal secondaire (webhook externe), une seule
  fois par épisode de panne pour éviter le spam.
- Se réinitialise dès qu'une commande kubectl réussit à nouveau.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from remediation.notifications import notify_agent_offline

# Sous-chaînes typiques d'un problème de connectivité avec l'API Kubernetes,
# par opposition à une erreur applicative (ex: ressource introuvable).
_CONNECTIVITY_MARKERS = (
    "unable to connect to the server",
    "connection refused",
    "dial tcp",
    "i/o timeout",
    "no such host",
    "context deadline exceeded",
    "tls: failed to verify certificate",
    "certificate signed by unknown authority",
    "the server doesn't have a resource type",  # API server dégradé
)

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 2.0  # 2s, 4s, 8s...
OFFLINE_THRESHOLD_SECONDS = 5 * 60


@dataclass
class _OfflineTracker:
    """Suivi de l'état de connectivité, partagé par tous les executors."""

    first_failure_at: float | None = None
    alert_sent: bool = False

    def record_failure(self) -> None:
        now = time.monotonic()

        if self.first_failure_at is None:
            self.first_failure_at = now

        outage_duration = now - self.first_failure_at

        if (
            outage_duration >= OFFLINE_THRESHOLD_SECONDS
            and not self.alert_sent
        ):
            notify_agent_offline(
                reason=(
                    "Connexion à l'API Kubernetes indisponible depuis "
                    f"plus de {OFFLINE_THRESHOLD_SECONDS // 60} minutes."
                ),
                since=datetime.fromtimestamp(
                    self.first_failure_at,
                    tz=timezone.utc,
                ).isoformat(),
            )
            self.alert_sent = True

    def record_success(self) -> None:
        self.first_failure_at = None
        self.alert_sent = False


_tracker = _OfflineTracker()


def _looks_like_connectivity_issue(stderr: str) -> bool:
    lowered = stderr.lower()
    return any(marker in lowered for marker in _CONNECTIVITY_MARKERS)


def run_kubectl(
    command: list[str],
    timeout: int = 60,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
) -> subprocess.CompletedProcess:
    """
    Exécute une commande kubectl avec retry exponentiel sur les erreurs de
    connectivité. Ne retente jamais les erreurs applicatives (ex: kubectl
    répond correctement mais la ressource n'existe pas) : dans ce cas la
    commande échoue immédiatement, comme avant.

    Met à jour le suivi partagé de connectivité, qui déclenche une alerte
    "Agent Offline" si la panne dépasse 5 minutes.
    """
    last_result: subprocess.CompletedProcess | None = None

    for attempt in range(max_retries + 1):
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            # Un timeout de subprocess est en soi un signe de problème
            # réseau/connectivité avec l'API server.
            _tracker.record_failure()

            if attempt >= max_retries:
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=1,
                    stdout="",
                    stderr=f"kubectl timed out after {timeout}s: {exc}",
                )

            time.sleep(backoff_base_seconds * (2 ** attempt))
            continue

        last_result = result

        if result.returncode == 0:
            _tracker.record_success()
            return result

        if not _looks_like_connectivity_issue(result.stderr):
            # Erreur applicative : inutile de retenter, on remonte tel quel.
            return result

        _tracker.record_failure()

        if attempt >= max_retries:
            break

        time.sleep(backoff_base_seconds * (2 ** attempt))

    return last_result
