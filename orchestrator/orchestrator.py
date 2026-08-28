from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from diagonisis.log_collector import LogCollectionError, get_pod_logs
from diagonisis.root_cause import RootCauseDiagnosis, diagnose
from executor.service import APPROVAL_REQUIRED_REASON, execution_service
from logger import logger
import remediation.mttr as mttr
from remediation.catalog import ActionCatalog, JsonActionCatalog
from remediation.knowledge_base import JsonKnowledgeBase, KnowledgeBase
from remediation.models import AnomalyEvent, DecisionMode, Severity
from remediation.notifications import notify_escalation
from monitoring import agent_metrics
from remediation.decision_log import decision_log

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
_REMEDIATION_BACKEND = os.getenv("REMEDIATION_BACKEND", "json")
DEFAULT_COMPONENT = "kubernetes-pod"

METRIC_QUERIES = {
    "CPU": '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
    "MEMORY": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
}

_kb: KnowledgeBase | None = None
_catalog: ActionCatalog | None = None


def _get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = JsonKnowledgeBase(
            os.path.join(CONFIG_DIR, "known_problems.json")
        )
    return _kb


def _get_catalog() -> ActionCatalog:
    global _catalog
    if _catalog is None:
        _catalog = JsonActionCatalog(
            os.path.join(CONFIG_DIR, "actions_catalog.json")
        )
    return _catalog


def reset_backends() -> None:
    global _kb, _catalog
    _kb = None
    _catalog = None


def _build_params(pod: str, namespace: str, alert: dict[str, Any]) -> dict[str, Any]:
    return {
        "pod_id": pod,
        "pod_name": pod,
        "namespace": namespace,
        "container_name": pod,
        "service_name": pod,
        "deployment": pod,
        "service": pod,
        "target": f"{pod}-standby",
        "path": "/var/log",
        "older_than_days": 7,
        "increment": 1,
    }


def _metric_fallback(alert: dict[str, Any]) -> RootCauseDiagnosis:
    metric = str(alert.get("metric", "")).upper()
    if metric == "CPU":
        return RootCauseDiagnosis(
            category="HighCPU",
            confidence=0.85,
            matched_pattern="metric-threshold",
            matched_log=None,
        )
    if metric == "MEMORY":
        return RootCauseDiagnosis(
            category="HighMemory",
            confidence=0.85,
            matched_pattern="metric-threshold",
            matched_log=None,
        )
    return RootCauseDiagnosis(
        category=None,
        confidence=0.0,
        matched_pattern=None,
        matched_log=None,
    )


def handle_alert(
    alert: dict[str, Any],
    pod: str | None = None,
    namespace: str = "default",
    dry_run: bool = False,
    verification_wait_seconds: int | None = None,
) -> dict[str, Any]:
    pod = pod or alert.get("pod") or alert.get("service", "default")
    incident_id = str(uuid4())
    detected_at = datetime.now(timezone.utc)

    mttr.record_detected(incident_id, detected_at)

    logger.info(
        "INCIDENT START id=%s pod=%s metric=%s value=%s severity=%s",
        incident_id,
        pod,
        alert.get("metric"),
        alert.get("value"),
        alert.get("severity"),
    )

    # 1. Loki diagnosis. Loki is mandatory as an evidence source, but an
    # empty/INFO-only log stream must not destroy a valid metric incident.
    try:
        log_result = get_pod_logs(pod, namespace=namespace)
        diagnosis = diagnose(log_result["logs"])
    except LogCollectionError as exc:
        logger.error("Loki unavailable: %s", exc)
        mttr.record_outcome(incident_id, "escalated")
        agent_metrics.record_decision("ESCALATE", None)
        agent_metrics.record_incident_outcome(
            "escalated",
            (datetime.now(timezone.utc) - detected_at).total_seconds(),
        )
        decision_log.add(
            mode="ESCALATE",
            confidence=None,
            incident_id=incident_id,
            reason=f"Loki unavailable: {exc}",
        )
        notify_escalation(
            action_id=incident_id,
            component=pod,
            reason=f"Loki unavailable: {exc}",
        )
        return {
            "incident_id": incident_id,
            "outcome": "escalated",
            "reason": "loki_unavailable",
        }

    if diagnosis.confidence < 0.80:
        fallback = _metric_fallback(alert)
        if fallback.category:
            diagnosis = fallback
            logger.info(
                "Loki had no matching root-cause pattern; "
                "using metric evidence category=%s confidence=%.2f",
                diagnosis.category,
                diagnosis.confidence,
            )

    if diagnosis.requires_human:
        mttr.record_outcome(incident_id, "escalated")
        agent_metrics.record_decision("ESCALATE", diagnosis.confidence)
        agent_metrics.record_incident_outcome(
            "escalated",
            (datetime.now(timezone.utc) - detected_at).total_seconds(),
        )
        decision_log.add(
            mode="ESCALATE",
            confidence=diagnosis.confidence,
            incident_id=incident_id,
            reason="root_cause_confidence_below_0.80",
        )
        notify_escalation(
            action_id=incident_id,
            component=pod,
            reason=f"Root cause confidence {diagnosis.confidence:.2f} < 0.80",
        )
        return {
            "incident_id": incident_id,
            "outcome": "escalated",
            "reason": "low_root_cause_confidence",
            "diagnosis": diagnosis.to_dict(),
        }

    severity_value = str(alert.get("severity", "medium")).lower()
    try:
        severity = Severity(severity_value)
    except ValueError:
        severity = Severity.MEDIUM
        severity_value = "medium"

    anomaly = AnomalyEvent(
        anomaly_id=incident_id,
        metric=diagnosis.category or str(alert.get("metric", "UNKNOWN")),
        component=DEFAULT_COMPONENT,
        severity=severity,
        description=(
            f"{diagnosis.category} on pod {pod}; "
            f"{alert.get('metric')}={alert.get('value')} "
            f"threshold={alert.get('threshold')}"
        ),
        detected_at=detected_at,
    )

    from remediation import process_anomaly
    decision = process_anomaly(anomaly, _get_kb(), _get_catalog())

    logger.info(
        "DECISION id=%s mode=%s confidence=%s action=%s reason=%s",
        incident_id,
        decision.decision_mode.value,
        decision.confidence,
        decision.chosen_action_id,
        decision.reason,
    )

    log_entry = decision_log.add(
        mode=decision.decision_mode.value,
        confidence=decision.confidence,
        incident_id=incident_id,
        action_type=decision.chosen_action_id,
        reason=decision.reason,
    )
    agent_metrics.record_decision(
        decision.decision_mode.value, decision.confidence
    )

    if decision.decision_mode == DecisionMode.ESCALATE:
        mttr.record_outcome(incident_id, "escalated")
        agent_metrics.record_incident_outcome(
            "escalated",
            (datetime.now(timezone.utc) - detected_at).total_seconds(),
        )
        decision_log.update_outcome(log_entry.id, "escalated")
        return {
            "incident_id": incident_id,
            "outcome": "escalated",
            "reason": decision.reason,
            "decision": decision,
        }

    action = _get_catalog().get(decision.chosen_action_id)
    if action is None:
        mttr.record_outcome(incident_id, "failed")
        return {
            "incident_id": incident_id,
            "outcome": "failed",
            "reason": "unknown_action_id",
        }

    params = _build_params(pod, namespace, alert)
    metric_query = METRIC_QUERIES.get(str(alert.get("metric", "")).upper())
    threshold = alert.get("threshold")
    can_verify = metric_query is not None and threshold is not None

    if decision.decision_mode == DecisionMode.AUTO_EXECUTE and can_verify:
        kwargs = dict(
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
            outcome = "pending" if result.error == APPROVAL_REQUIRED_REASON else "failed"
        elif dry_run:
            outcome = "resolved"
        else:
            outcome = "resolved" if verification and verification.resolved else "escalated"

        mttr.record_outcome(incident_id, outcome)
        agent_metrics.record_incident_outcome(
            outcome,
            (datetime.now(timezone.utc) - detected_at).total_seconds(),
        )
        agent_metrics.record_remediation_action(
            decision.chosen_action_id, result.success
        )
        decision_log.update_outcome(log_entry.id, outcome)

        logger.info(
            "REMEDIATION END id=%s outcome=%s success=%s",
            incident_id,
            outcome,
            result.success,
        )
        return {
            "incident_id": incident_id,
            "outcome": outcome,
            "decision": decision,
            "execution_result": result,
            "verification": verification,
        }

    # Human approval path, or action without a known verification query.
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
        outcome = "failed"

    if outcome != "pending":
        mttr.record_outcome(incident_id, outcome)
        agent_metrics.record_incident_outcome(
            outcome,
            (datetime.now(timezone.utc) - detected_at).total_seconds(),
        )
        agent_metrics.record_remediation_action(
            decision.chosen_action_id, result.success
        )
        decision_log.update_outcome(log_entry.id, outcome)

    return {
        "incident_id": incident_id,
        "outcome": outcome,
        "decision": decision,
        "execution_result": result,
    }
