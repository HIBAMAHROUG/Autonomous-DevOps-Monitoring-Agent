"""
Vérification post-remédiation (US 3.2).

Après l'exécution d'une action de remédiation, l'agent doit s'assurer que
la panne est réellement résolue avant de clore l'incident :

- attendre un délai configurable (par défaut 60 secondes) ;
- interroger à nouveau Prometheus pour vérifier que la métrique concernée
  est revenue sous le seuil normal ;
- si le problème persiste, escalader l'incident à l'équipe de garde via
  Slack/Email (remediation.notifications.notify_remediation_failed).

Critères d'acceptation couverts :
- délai d'attente configurable après l'exécution du script ;
- re-vérification via Prometheus ;
- escalade en cas de persistance du problème.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from collector.metrics import query_prometheus
from remediation.notifications import notify_remediation_failed

logger = logging.getLogger("remediation.verification")

DEFAULT_WAIT_SECONDS = 60


@dataclass
class VerificationResult:
    action_id: str
    component: str
    metric_query: str
    value: float | None
    threshold: float
    resolved: bool
    escalated: bool
    message: str


def verify_remediation(
    action_id: str,
    component: str,
    metric_query: str,
    threshold: float,
    comparison: str = "below",
    wait_seconds: int = DEFAULT_WAIT_SECONDS,
    sleep_fn=time.sleep,
) -> VerificationResult:
    """
    Vérifie qu'une remédiation a bien résolu l'incident.

    Args:
        action_id: identifiant de l'action de remédiation exécutée.
        component: service/pod concerné (pour les logs et l'escalade).
        metric_query: requête PromQL à réévaluer après l'action.
        threshold: valeur seuil attendue après remédiation.
        comparison: "below" si la métrique doit repasser sous le seuil,
            "above" si elle doit repasser au-dessus (ex: espace disque
            disponible après nettoyage).
        wait_seconds: délai d'observation avant de revérifier (US 3.2).
        sleep_fn: injectable pour les tests (évite d'attendre réellement).

    Returns:
        VerificationResult décrivant si l'incident est résolu, et si une
        escalade a été déclenchée.
    """
    if comparison not in ("below", "above"):
        raise ValueError("comparison must be 'below' or 'above'")

    logger.info(
        "Vérification post-remédiation pour %s sur %s : "
        "attente de %ss avant re-contrôle Prometheus",
        action_id,
        component,
        wait_seconds,
    )

    sleep_fn(wait_seconds)

    try:
        value = query_prometheus(metric_query)
    except Exception:
        logger.exception(
            "Impossible de revérifier la métrique pour %s (%s) après "
            "remédiation ; incident escaladé par précaution.",
            action_id,
            component,
        )
        notify_remediation_failed(
            action_id=action_id,
            component=component,
            metric=metric_query,
            value=float("nan"),
            threshold=threshold,
        )
        return VerificationResult(
            action_id=action_id,
            component=component,
            metric_query=metric_query,
            value=None,
            threshold=threshold,
            resolved=False,
            escalated=True,
            message="Prometheus query failed after remediation",
        )

    if comparison == "below":
        resolved = value <= threshold
    else:
        resolved = value >= threshold

    if resolved:
        logger.info(
            "Remédiation confirmée pour %s sur %s : %s=%.2f (seuil %.2f)",
            action_id,
            component,
            metric_query,
            value,
            threshold,
        )
        return VerificationResult(
            action_id=action_id,
            component=component,
            metric_query=metric_query,
            value=value,
            threshold=threshold,
            resolved=True,
            escalated=False,
            message="Metric back to normal after remediation",
        )

    logger.warning(
        "Le problème persiste après remédiation pour %s sur %s : "
        "%s=%.2f (seuil %.2f) — escalade à l'équipe de garde",
        action_id,
        component,
        metric_query,
        value,
        threshold,
    )

    notify_remediation_failed(
        action_id=action_id,
        component=component,
        metric=metric_query,
        value=value,
        threshold=threshold,
    )

    return VerificationResult(
        action_id=action_id,
        component=component,
        metric_query=metric_query,
        value=value,
        threshold=threshold,
        resolved=False,
        escalated=True,
        message="Problem persists after remediation, escalated",
    )