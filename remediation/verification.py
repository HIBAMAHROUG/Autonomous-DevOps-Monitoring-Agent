"""
Vérification post-remédiation (US 3.2).

Le succès d'une commande d'exécution (ex: `kubectl scale` renvoie 0) ne
prouve pas que l'incident est résolu -- un pod peut continuer à
redémarrer, ou la métrique qui a déclenché l'alerte peut rester en
dépassement. Ce module attend un délai d'observation, revérifie la
métrique concernée via Prometheus, et escalade explicitement (Slack/
email, voir remediation.notifications) si le problème persiste.

Flux attendu par le cahier des charges :
    exécution réussie -> attendre `wait_seconds` (60s par défaut,
    configurable) -> interroger Prometheus -> comparer au seuil ->
    RESOLVED ou ESCALATED.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from collector.metrics import query_prometheus
from logger import logger
from remediation.notifications import notify_escalation

DEFAULT_WAIT_SECONDS = 60

_SUPPORTED_COMPARISONS = ("below", "above")


@dataclass
class VerificationResult:
    action_id: str
    component: str
    metric_query: str
    threshold: float
    comparison: str
    value: float | None
    resolved: bool
    escalated: bool
    verified_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "component": self.component,
            "metric_query": self.metric_query,
            "threshold": self.threshold,
            "comparison": self.comparison,
            "value": self.value,
            "resolved": self.resolved,
            "escalated": self.escalated,
            "verified_at": self.verified_at.isoformat(),
            "error": self.error,
        }


def _is_within_threshold(value: float, threshold: float, comparison: str) -> bool:
    if comparison == "below":
        return value < threshold
    if comparison == "above":
        return value > threshold
    raise ValueError(
        f"Unsupported comparison '{comparison}'. "
        f"Expected one of: {_SUPPORTED_COMPARISONS}"
    )


def verify_remediation(
    action_id: str,
    component: str,
    metric_query: str,
    threshold: float,
    comparison: str = "below",
    wait_seconds: int = DEFAULT_WAIT_SECONDS,
) -> VerificationResult:
    """
    Attend `wait_seconds`, revérifie `metric_query` via Prometheus, et
    escalade si la métrique ne respecte pas `threshold` selon
    `comparison` ("below" ou "above").

    Ne lève jamais d'exception : un échec de la requête Prometheus elle-
    même est traité comme "impossible de confirmer la résolution" et
    entraîne une escalade prudente plutôt qu'un crash de l'appelant.
    """
    if wait_seconds > 0:
        logger.info(
            "Verification: waiting %ss before re-checking %s (%s)",
            wait_seconds,
            metric_query,
            component,
        )
        time.sleep(wait_seconds)

    try:
        value = query_prometheus(metric_query)
    except Exception as exc:
        logger.exception(
            "Verification failed to query Prometheus for action=%s component=%s",
            action_id,
            component,
        )
        notify_escalation(
            action_id=action_id,
            component=component,
            reason=f"Verification query failed: {exc}",
        )
        return VerificationResult(
            action_id=action_id,
            component=component,
            metric_query=metric_query,
            threshold=threshold,
            comparison=comparison,
            value=None,
            resolved=False,
            escalated=True,
            error=str(exc),
        )

    resolved = _is_within_threshold(value, threshold, comparison)

    if not resolved:
        logger.warning(
            "Remediation for action=%s component=%s did NOT resolve the "
            "incident: %s=%.2f (expected %s %.2f). Escalating.",
            action_id,
            component,
            metric_query,
            value,
            comparison,
            threshold,
        )
        notify_escalation(
            action_id=action_id,
            component=component,
            reason=(
                f"Incident persists after remediation: {metric_query}="
                f"{value:.2f} (expected {comparison} {threshold:.2f})"
            ),
        )
    else:
        logger.info(
            "Remediation for action=%s component=%s verified as resolved "
            "(%s=%.2f, expected %s %.2f).",
            action_id,
            component,
            metric_query,
            value,
            comparison,
            threshold,
        )

    return VerificationResult(
        action_id=action_id,
        component=component,
        metric_query=metric_query,
        threshold=threshold,
        comparison=comparison,
        value=value,
        resolved=resolved,
        escalated=not resolved,
    )