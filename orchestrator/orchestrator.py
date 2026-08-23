"""
Orchestrateur end-to-end.

Avant ce module, chaque brique (collector, detector, diagonisis,
remediation, executor, storage) était fonctionnelle et testée en
isolation, mais rien ne les enchaînait automatiquement après une
détection réelle. `handle_alert()` est le point d'entrée unique qui
relie :

    détection confirmée (detector.pipeline.check_and_confirm)
        -> diagnostic Loki (diagonisis.log_collector + diagonisis.root_cause)
        -> confiance du diagnostic >= 80% ? sinon escalade (US 2.2)
        -> décision (remediation.process_anomaly)
        -> garde-fous + exécution + vérification (executor.service)
        -> mesure MTTR (remediation.mttr)
        -> notification d'escalade si nécessaire

Limitation connue et assumée : le collector actuel (collector/collector.py)
récupère des métriques au niveau du nœud/service, pas par pod
Kubernetes. Ce module accepte donc un identifiant de "pod" fourni par
l'appelant (par défaut le nom du service de l'alerte) -- une vraie
collecte par pod nécessiterait d'interroger l'API Kubernetes en plus de
Prometheus, ce qui est hors du périmètre de cette passe de correction.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from diagonisis.log_collector import LogCollectionError, get_pod_logs
from diagonisis.root_cause import diagnose
from executor.service import APPROVAL_REQUIRED_REASON, execution_service
from logger import logger
import remediation.mttr as mttr
from remediation.catalog import ActionCatalog, JsonActionCatalog
from remediation.knowledge_base import JsonKnowledgeBase, KnowledgeBase
from remediation.models import AnomalyEvent, DecisionMode, Severity
from remediation.notifications import notify_escalation

CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config"
)

# Backend par défaut : JSON (pas de dépendance Postgres). Le dépôt ne
# déploie de toute façon pas Postgres dans docker-compose.yml -- passer
# REMEDIATION_BACKEND=postgres si une base est réellement disponible.
_REMEDIATION_BACKEND = os.getenv("REMEDIATION_BACKEND", "json")

# Doit correspondre à `affected_component` dans config/known_problems.json.
DEFAULT_COMPONENT = "kubernetes-pod"

# Requêtes Prometheus utilisées pour la vérification post-remédiation :
# doivent correspondre aux métriques exposées par detector/detector.py
# (MONITORED_METRICS) et interrogées par collector/metrics.py.
METRIC_QUERIES = {
    "CPU": (
        '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
    ),
    "MEMORY": (
        "(1 - (node_memory_MemAvailable_bytes / "
        "node_memory_MemTotal_bytes)) * 100"
    ),
}

_kb: KnowledgeBase | None = None
_catalog: ActionCatalog | None = None


def _get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        if _REMEDIATION_BACKEND == "postgres":
            from remediation.knowledge_base import PostgresKnowledgeBase

            _kb = PostgresKnowledgeBase()
        else:
            _kb = JsonKnowledgeBase(
                os.path.join(CONFIG_DIR, "known_problems.json")
            )
    return _kb


def _get_catalog() -> ActionCatalog:
    global _catalog
    if _catalog is None:
        if _REMEDIATION_BACKEND == "postgres":
            from remediation.catalog import PostgresActionCatalog

            _catalog = PostgresActionCatalog()
        else:
            _catalog = JsonActionCatalog(
                os.path.join(CONFIG_DIR, "actions_catalog.json")
            )
    return _catalog


def reset_backends() -> None:
    """Force le rechargement du KB/catalogue -- utilitaire pour les tests."""
    global _kb, _catalog
    _kb = None
    _catalog = None


def _build_params(pod: str, alert: dict[str, Any]) -> dict[str, Any]:
    """
    Paramètres génériques transmis à l'exécuteur choisi. Chaque
    exécuteur (docker/scaling/cleanup/failover/rollback) ne lit que les
    clés qu'il connaît (voir executor/*.py) -- les autres sont ignorées.

    `target` (failover) et `path`/`older_than_days` (cleanup) sont des
    valeurs par défaut de démonstration ; une intégration réelle les
    dériverait de la topologie du cluster (ex: service mesh, inventaire).
    """
    return {
        "pod_id": pod,
        "container_name": pod,
        "service_name": pod,
        "deployment": pod,
        "service": pod,
        "target": f"{pod}-standby",
        "path": "/var/log",
        "older_than_days": 7,
        "increment": 1,
    }


def handle_alert(
    alert: dict[str, Any],
    pod: str | None = None,
    namespace: str = "default",
    dry_run: bool = True,
    verification_wait_seconds: int | None = None,
) -> dict[str, Any]:
    """
    Traite une alerte confirmée par le pipeline à deux étages
    (detector.pipeline.check_and_confirm) de bout en bout.

    `pod` : identifiant du pod concerné, pour interroger Loki et pour
    l'anti-boucle de SafetyPolicy. À défaut, on retombe sur le nom du
    service de l'alerte (voir limitation documentée en tête de module).

    Ne lève jamais d'exception : les erreurs (Loki indisponible, action
    inconnue, etc.) sont traitées comme des motifs d'escalade plutôt
    que de faire échouer la boucle de collecte appelante.
    """
    pod = pod or alert.get("service", "default")
    incident_id = str(uuid4())
    detected_at = datetime.now(timezone.utc)

    mttr.record_detected(incident_id, detected_at)

    logger.info(
        "Orchestrator: handling alert incident=%s pod=%s metric=%s value=%s",
        incident_id,
        pod,
        alert.get("metric"),
        alert.get("value"),
    )

    # 1) Diagnostic de cause racine via les logs Loki (US 2.2)
    try:
        log_result = get_pod_logs(pod, namespace=namespace)
        diagnosis = diagnose(log_result["logs"])
    except LogCollectionError as exc:
        logger.warning(
            "Orchestrator: Loki unavailable for incident=%s (%s) -- "
            "cannot diagnose root cause, escalating.",
            incident_id,
            exc,
        )
        mttr.record_outcome(incident_id, "escalated")
        notify_escalation(
            action_id=incident_id,
            component=pod,
            reason=f"Log collection failed, cannot diagnose: {exc}",
        )
        return {
            "incident_id": incident_id,
            "outcome": "escalated",
            "reason": "log_collection_failed",
        }

    # 2) Confiance du diagnostic < 80% -> escalade obligatoire, avant
    #    même d'envisager une remédiation automatique.
    if diagnosis.requires_human:
        logger.info(
            "Orchestrator: incident=%s root cause confidence %.2f < 80%% "
            "-- escalating.",
            incident_id,
            diagnosis.confidence,
        )
        mttr.record_outcome(incident_id, "escalated")
        notify_escalation(
            action_id=incident_id,
            component=pod,
            reason=(
                f"Root cause confidence too low "
                f"({diagnosis.confidence:.2f} < 0.80): "
                f"{diagnosis.category or 'unknown category'}"
            ),
        )
        return {
            "incident_id": incident_id,
            "outcome": "escalated",
            "reason": "low_root_cause_confidence",
            "diagnosis": diagnosis.to_dict(),
        }

    # 3) Décision (remediation.process_anomaly : mapping -> scoring -> decide)
    severity_value = str(alert.get("severity", "medium")).lower()

    anomaly = AnomalyEvent(
        anomaly_id=incident_id,
        metric=diagnosis.category,
        component=DEFAULT_COMPONENT,
        severity=Severity(severity_value),
        description=(
            f"{diagnosis.category} diagnosed on pod {pod} "
            f"({alert.get('metric')}={alert.get('value')}, "
            f"matched log: {diagnosis.matched_log!r})"
        ),
        detected_at=detected_at,
    )

    from remediation import process_anomaly

    decision = process_anomaly(anomaly, _get_kb(), _get_catalog())

    logger.info(
        "Orchestrator: incident=%s decision_mode=%s confidence=%s reason=%s",
        incident_id,
        decision.decision_mode,
        decision.confidence,
        decision.reason,
    )

    if decision.decision_mode == DecisionMode.ESCALATE:
        mttr.record_outcome(incident_id, "escalated")
        notify_escalation(
            action_id=incident_id,
            component=pod,
            reason=f"Decision engine escalated: {decision.reason}",
        )
        return {
            "incident_id": incident_id,
            "outcome": "escalated",
            "reason": decision.reason,
            "decision": decision,
        }

    # 4) AUTO_EXECUTE ou SUGGEST_TO_HUMAN : résoudre l'action choisie
    action = _get_catalog().get(decision.chosen_action_id)

    if action is None:
        logger.error(
            "Orchestrator: incident=%s decision chose unknown action_id=%s",
            incident_id,
            decision.chosen_action_id,
        )
        mttr.record_outcome(incident_id, "escalated")
        notify_escalation(
            action_id=incident_id,
            component=pod,
            reason=(
                f"Chosen action '{decision.chosen_action_id}' "
                "not found in catalog"
            ),
        )
        return {
            "incident_id": incident_id,
            "outcome": "escalated",
            "reason": "unknown_action_id",
        }

    params = _build_params(pod, alert)
    metric_query = METRIC_QUERIES.get(str(alert.get("metric", "")).upper())
    threshold = alert.get("threshold")
    can_verify = metric_query is not None and threshold is not None

    if decision.decision_mode == DecisionMode.AUTO_EXECUTE and can_verify:
        kwargs: dict[str, Any] = dict(
            action=action,
            params=params,
            metric_query=metric_query,
            threshold=float(threshold),
            component=pod,
            comparison="below",
            dry_run=dry_run,
            severity=severity_value.upper(),
        )
        if verification_wait_seconds is not None:
            kwargs["wait_seconds"] = verification_wait_seconds

        result, verification = execution_service.execute_and_verify(**kwargs)

        if not result.success:
            outcome = "escalated"
        elif dry_run:
            # Rien à vérifier en dry-run : ni résolu ni escaladé au sens
            # incident réel, mais on ne laisse pas l'incident "pending".
            outcome = "resolved"
        else:
            outcome = (
                "resolved"
                if verification and verification.resolved
                else "escalated"
            )

        mttr.record_outcome(incident_id, outcome)

        return {
            "incident_id": incident_id,
            "outcome": outcome,
            "decision": decision,
            "execution_result": result,
            "verification": verification,
        }

    # SUGGEST_TO_HUMAN, ou AUTO_EXECUTE sans requête Prometheus connue
    # pour vérifier (ex: métrique non mappée dans METRIC_QUERIES) :
    # on passe par execute() classique. S'il manque une approbation
    # (action critique), execute() crée déjà la demande + notifie
    # (US 4.2), et execute_approved() déclenchera la vérification une
    # fois approuvé (déjà branché dans executor/service.py).
    result = execution_service.execute(
        action=action,
        params=params,
        dry_run=dry_run,
        severity=severity_value.upper(),
        metric_query=metric_query,
        threshold=float(threshold) if threshold is not None else None,
        comparison="below",
        component=pod,
    )

    if result.error == APPROVAL_REQUIRED_REASON:
        outcome = "pending"
    elif result.success:
        outcome = "resolved"
    else:
        outcome = "escalated"

    if outcome != "pending":
        mttr.record_outcome(incident_id, outcome)

    return {
        "incident_id": incident_id,
        "outcome": outcome,
        "decision": decision,
        "execution_result": result,
    }
