"""API du tableau de bord de l'agent DevOps."""

from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta, timezone

import requests
from flask import Blueprint, jsonify, render_template, request

import detector.pipeline as pipeline_module
import remediation.mttr as mttr

from anomaly_agent.severity import classify_severity
from detector.detector import _default_detector
from detector.pipeline import check_and_confirm, _get_ml_detector
from executor.service import execution_service
from orchestrator.orchestrator import handle_alert
from remediation.approvals import approval_store
from remediation.decision_log import decision_log

# Configuration du logger
logger = logging.getLogger(__name__)

dashboard_api = Blueprint(
    "dashboard_api",
    __name__,
)


PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://prometheus:9090/api/v1/query",
)


# ============================================================
# PROMETHEUS - REQUÊTES CORRIGÉES AVEC FILTRES job
# ============================================================

INFRA_QUERIES = {
    # ✅ CPU : filtre job="node-exporter" + avg by instance
    "cpu_percent": (
        '100 - (avg by (instance) (rate('
        'node_cpu_seconds_total{job="node-exporter",mode="idle"}[5m]'
        ')) * 100)'
    ),

    # ✅ Memory : filtre job="node-exporter"
    "memory_percent": (
        '100 - (node_memory_MemAvailable_bytes{job="node-exporter"} / '
        'node_memory_MemTotal_bytes{job="node-exporter"} * 100)'
    ),

    # ✅ Network Receive : filtre job="node-exporter"
    "network_receive": (
        'sum(rate('
        'node_network_receive_bytes_total{job="node-exporter",device!="lo"}[5m]'
        '))'
    ),

    # ✅ Network Transmit : filtre job="node-exporter"
    "network_transmit": (
        'sum(rate('
        'node_network_transmit_bytes_total{job="node-exporter",device!="lo"}[5m]'
        '))'
    ),

    # ✅ Node Exporter UP
    "node_exporter_up": (
        'up{job="node-exporter"}'
    ),

    # ✅ Prometheus UP
    "prometheus_up": (
        'up{job="prometheus"}'
    ),
}


def _query_prometheus(expr: str) -> float | None:
    """Exécute une requête instantanée Prometheus."""
    try:
        logger.debug(f"Querying Prometheus: {expr}")
        
        response = requests.get(
            PROMETHEUS_URL,
            params={"query": expr},
            timeout=10,
        )

        response.raise_for_status()

        payload = response.json()

        if payload.get("status") != "success":
            logger.error(f"Prometheus status not success: {payload}")
            return None

        result = payload.get("data", {}).get("result", [])

        if not result:
            logger.warning(f"No results for query: {expr}")
            return None

        # Extraction sécurisée de la valeur
        value = result[0].get("value", [None, None])[1]
        if value is None:
            logger.warning(f"Value is None for query: {expr}")
            return None

        logger.debug(f"Query result: {value}")
        return float(value)

    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return None
    except (ValueError, KeyError, TypeError, IndexError) as e:
        logger.error(f"Parsing error: {e}")
        return None


# ============================================================
# AUTHENTICATION
# ============================================================

def _check_api_key() -> bool:
    provided_key = request.headers.get("X-API-Key")
    expected_key = os.getenv("API_KEY")
    return bool(provided_key and expected_key and provided_key == expected_key)


# ============================================================
# CLASSIFICATION
# ============================================================

def _classify_entry(entry: dict) -> str:
    message = entry.get("message", "")
    success = entry.get("success", False)
    if message == "Human approval required for critical action":
        return "escalated"
    return "resolved" if success else "failed"


# ============================================================
# DASHBOARD PAGE
# ============================================================

@dashboard_api.route("/dashboard", methods=["GET"])
def dashboard_page():
    return render_template("dashboard.html")


# ============================================================
# SUMMARY
# ============================================================

@dashboard_api.route("/api/dashboard/summary", methods=["GET"])
def summary():
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    audit_log = execution_service.safety.get_audit_log()

    detected = len(audit_log)
    resolved = 0
    failed = 0
    escalated = 0

    for entry in audit_log:
        status = _classify_entry(entry)
        if status == "resolved":
            resolved += 1
        elif status == "failed":
            failed += 1
        elif status == "escalated":
            escalated += 1

    pending = len(approval_store.list_pending())
    mttr_stats = mttr.get_stats()

    return jsonify({
        "detected": detected,
        "resolved": resolved,
        "failed": failed,
        "escalated": escalated,
        "pending_approval": pending,
        "total_incidents": mttr_stats.get("total_incidents", 0),
        "auto_resolution_rate": mttr_stats.get("auto_resolution_rate") or 0,
        "mttr_seconds_avg": mttr_stats.get("mttr_seconds_avg") or 0,
    })


# ============================================================
# INFRASTRUCTURE - ENDPOINT CORRIGÉ
# ============================================================

@dashboard_api.route("/api/dashboard/infra", methods=["GET"])
def infra():
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    metrics = {
        key: _query_prometheus(expression)
        for key, expression in INFRA_QUERIES.items()
    }

    # Log pour debug
    logger.info(f"Infra metrics: {metrics}")

    return jsonify({
        "source": "prometheus",
        "prometheus_url": PROMETHEUS_URL,
        "metrics": metrics,
        "cpu_percent": metrics.get("cpu_percent"),
        "memory_percent": metrics.get("memory_percent"),
        "network_receive_bytes_per_second": metrics.get("network_receive"),
        "network_transmit_bytes_per_second": metrics.get("network_transmit"),
        "node_exporter_up": metrics.get("node_exporter_up"),
        "prometheus_up": metrics.get("prometheus_up"),
    })


# ============================================================
# AI DECISIONS
# ============================================================

@dashboard_api.route("/api/dashboard/decisions", methods=["GET"])
def decisions():
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    limit = request.args.get("limit", 50, type=int)
    limit = max(1, min(limit, 200))

    stats = mttr.get_stats()
    recent = decision_log.list_recent(limit=limit)

    return jsonify({
        "recent": recent,
        "self_healing_ratio": stats.get("auto_resolution_rate") or 0.0,
        "total_incidents": stats.get("total_incidents", 0),
        "avg_mttr_seconds": stats.get("mttr_seconds_avg") or 0,
    })


# ============================================================
# PENDING APPROVALS
# ============================================================

@dashboard_api.route("/api/dashboard/approvals", methods=["GET"])
def approvals():
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    pending = approval_store.list_pending()

    return jsonify({
        "count": len(pending),
        "pending": pending,
    })


# ============================================================
# APPROVAL ACTIONS
# ============================================================

@dashboard_api.route("/api/approvals/<action_id>/<decision>", methods=["POST"])
def approval_decision(action_id: str, decision: str):
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    if decision not in {"approve", "reject"}:
        return jsonify({"error": "Invalid decision"}), 400

    try:
        if decision == "approve":
            result = approval_store.approve(action_id)
        else:
            result = approval_store.reject(action_id)

        return jsonify({
            "success": True,
            "decision": decision,
            "action_id": action_id,
            "result": result,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "action_id": action_id,
            "decision": decision,
        }), 500


# ============================================================
# HISTORY
# ============================================================

@dashboard_api.route("/api/dashboard/history", methods=["GET"])
def history():
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    limit = request.args.get("limit", 50, type=int)
    limit = max(1, min(limit, 200))

    audit_log = execution_service.safety.get_audit_log()
    entries = []

    for entry in reversed(audit_log[-limit:]):
        entries.append({
            "timestamp": entry.get("timestamp"),
            "action_id": entry.get("action_id"),
            "status": _classify_entry(entry),
            "message": entry.get("message"),
            "success": entry.get("success", False),
        })

    return jsonify({
        "count": len(entries),
        "history": entries,
    })


# ============================================================
# TEST INCIDENTS
# ============================================================

_test_incidents = []


@dashboard_api.route("/api/dashboard/test-critical", methods=["POST"])
def test_critical():
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    now = datetime.now(timezone.utc)
    incident = {
        "incident_id": f"TEST-CRITICAL-{int(now.timestamp())}",
        "timestamp": now.isoformat(),
        "service": "demo-service",
        "pod": "demo-pod",
        "metric": "CPU",
        "metric_key": "cpu",
        "value": 96.5,
        "threshold": 90,
        "severity": "CRITICAL",
        "status": "pending_approval",
        "decision": "Human approval required for critical action",
        "action": "restart_pod",
        "test": True,
    }

    _test_incidents.append(incident)

    return jsonify({
        "success": True,
        "incident": incident,
    })


# ============================================================
# SIMULATION D'INCIDENT RÉEL
# ============================================================

@dashboard_api.route("/api/dashboard/simulate-real-incident", methods=["POST"])
def simulate_real_incident():
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    scenario = body.get("scenario", "auto")

    default_cpu = 93.0 if scenario == "auto" else 99.9
    default_other = 40.0 if scenario == "auto" else 99.0

    try:
        cpu_value = float(body.get("cpu_usage", default_cpu))
        memory_value = float(body.get("memory_usage", default_other))
        network_value = float(body.get("network_usage", default_other))
        disk_value = float(body.get("disk_usage", default_other))
    except (TypeError, ValueError):
        return jsonify({
            "error": "Les valeurs des métriques doivent être numériques."
        }), 400

    service_name = f"demo-service-{scenario}"
    pod_name = f"demo-pod-{scenario}"
    now0 = datetime.now(timezone.utc)

    metrics = {
        "cpu_usage": cpu_value,
        "memory_usage": memory_value,
        "network_usage": network_value,
        "disk_usage": disk_value,
    }

    check_and_confirm(metrics, service=service_name)

    now1 = now0 + timedelta(seconds=301)

    threshold_alerts = _default_detector.check(
        metrics,
        service=service_name,
        pod=pod_name,
        now=now1,
    )

    if not threshold_alerts:
        return jsonify({
            "error": "Le pré-filtre n'a déclenché aucune alerte pour "
            f"cpu_usage={cpu_value}. Augmente cette valeur."
        }), 400

    pipeline_module._ml_detector = None
    ml_detector = _get_ml_detector()
    score, z_scores = ml_detector.score_sample(metrics)

    severity = classify_severity(score, ml_detector.thresholds)

    if severity is None:
        return jsonify({
            "error": f"Le modèle ML n'a pas confirmé l'anomalie (score={score:.4f}). "
            "Augmente les valeurs de métriques."
        }), 400

    alert = {
        **threshold_alerts[0],
        "ml_score": round(score, 4),
        "severity": severity,
        "z_scores": {
            key: round(value, 2)
            for key, value in z_scores.items()
        },
    }

    result = handle_alert(alert, pod=pod_name, dry_run=True)

    return jsonify({
        "scenario": scenario,
        "metrics": metrics,
        "ml_score": round(score, 4),
        "severity": severity,
        "orchestrator_result": result,
    })


# ============================================================
# TEST INCIDENTS
# ============================================================

@dashboard_api.route("/api/dashboard/test-incidents", methods=["GET"])
def test_incidents():
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify({
        "count": len(_test_incidents),
        "incidents": list(reversed(_test_incidents)),
    })


@dashboard_api.route("/api/dashboard/test-incidents", methods=["DELETE"])
def clear_test_incidents():
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    _test_incidents.clear()
    return jsonify({"success": True})