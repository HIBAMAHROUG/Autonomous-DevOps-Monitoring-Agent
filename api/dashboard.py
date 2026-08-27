"""API du tableau de bord de l'agent DevOps."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import requests
from flask import Blueprint, jsonify, render_template, request

from executor.service import execution_service
from remediation.approvals import approval_store
from remediation.decision_log import decision_log
import remediation.mttr as mttr


dashboard_api = Blueprint("dashboard_api", __name__)

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://prometheus:9090",
)


# ============================================================
# PROMETHEUS
# ============================================================

INFRA_QUERIES = {
    "cpu_percent": (
        '100 - (avg(rate('
        'node_cpu_seconds_total{mode="idle"}[5m]'
        ')) * 100)'
    ),

    "memory_percent": (
        '(1 - (node_memory_MemAvailable_bytes / '
        'node_memory_MemTotal_bytes)) * 100'
    ),

    "network_receive": (
        'sum(rate('
        'node_network_receive_bytes_total{device!="lo"}[5m]'
        '))'
    ),

    "network_transmit": (
        'sum(rate('
        'node_network_transmit_bytes_total{device!="lo"}[5m]'
        '))'
    ),

    "node_exporter_up": (
        'up{job="node-exporter"}'
    ),

    "prometheus_up": (
        'up{job="prometheus"}'
    ),
}


def _query_prometheus(expr: str) -> float | None:
    """Exécute une requête instantanée Prometheus."""

    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": expr},
            timeout=5,
        )

        response.raise_for_status()

        payload = response.json()

        if payload.get("status") != "success":
            return None

        result = payload.get(
            "data",
            {},
        ).get(
            "result",
            [],
        )

        if not result:
            return None

        return float(
            result[0]["value"][1]
        )

    except (
        requests.RequestException,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
    ):
        return None


# ============================================================
# AUTHENTICATION
# ============================================================

def _check_api_key() -> bool:
    api_key = request.headers.get(
        "X-API-Key"
    )

    expected_key = os.getenv(
        "API_KEY"
    )

    return bool(
        api_key
        and expected_key
        and api_key == expected_key
    )


# ============================================================
# CLASSIFICATION
# ============================================================

def _classify_entry(entry: dict) -> str:

    message = entry.get(
        "message",
        "",
    )

    success = entry.get(
        "success",
        False,
    )

    if message == (
        "Human approval required for critical action"
    ):
        return "escalated"

    return (
        "resolved"
        if success
        else "failed"
    )


# ============================================================
# DASHBOARD PAGE
# ============================================================

@dashboard_api.route(
    "/dashboard",
    methods=["GET"],
)
def dashboard_page():

    return render_template(
        "dashboard.html"
    )


# ============================================================
# SUMMARY
# ============================================================

@dashboard_api.route(
    "/api/dashboard/summary",
    methods=["GET"],
)
def summary():

    if not _check_api_key():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    audit_log = (
        execution_service
        .safety
        .get_audit_log()
    )

    detected = len(
        audit_log
    )

    resolved = 0
    failed = 0
    escalated = 0

    for entry in audit_log:

        status = _classify_entry(
            entry
        )

        if status == "resolved":
            resolved += 1

        elif status == "failed":
            failed += 1

        elif status == "escalated":
            escalated += 1

    pending = len(
        approval_store.list_pending()
    )

    mttr_stats = mttr.get_stats()

    return jsonify({
        "detected": detected,
        "resolved": resolved,
        "failed": failed,
        "escalated": escalated,
        "pending_approval": pending,

        "total_incidents": (
            mttr_stats.get(
                "total_incidents",
                0,
            )
        ),

        "auto_resolution_rate": (
            mttr_stats.get(
                "auto_resolution_rate"
            ) or 0
        ),

        "mttr_seconds_avg": (
            mttr_stats.get(
                "mttr_seconds_avg"
            ) or 0
        ),
    })


# ============================================================
# INFRASTRUCTURE
# ============================================================

@dashboard_api.route(
    "/api/dashboard/infra",
    methods=["GET"],
)
def infra():

    if not _check_api_key():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    metrics = {
        key: _query_prometheus(
            expression
        )
        for key, expression
        in INFRA_QUERIES.items()
    }

    return jsonify({

        "source": "prometheus",

        "prometheus_url": (
            PROMETHEUS_URL
        ),

        "metrics": metrics,

        "cpu_percent": (
            metrics.get(
                "cpu_percent"
            )
        ),

        "memory_percent": (
            metrics.get(
                "memory_percent"
            )
        ),

        "network_receive_bytes_per_second": (
            metrics.get(
                "network_receive"
            )
        ),

        "network_transmit_bytes_per_second": (
            metrics.get(
                "network_transmit"
            )
        ),

        "node_exporter_up": (
            metrics.get(
                "node_exporter_up"
            )
        ),

        "prometheus_up": (
            metrics.get(
                "prometheus_up"
            )
        ),
    })


# ============================================================
# AI DECISIONS
# ============================================================

@dashboard_api.route(
    "/api/dashboard/decisions",
    methods=["GET"],
)
def decisions():

    if not _check_api_key():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    limit = request.args.get(
        "limit",
        50,
        type=int,
    )

    limit = max(
        1,
        min(limit, 200),
    )

    stats = mttr.get_stats()

    recent = (
        decision_log
        .list_recent(
            limit=limit
        )
    )

    return jsonify({

        "recent": recent,

        "self_healing_ratio": (
            stats.get(
                "auto_resolution_rate"
            ) or 0.0
        ),

        "total_incidents": (
            stats.get(
                "total_incidents",
                0,
            )
        ),

        "avg_mttr_seconds": (
            stats.get(
                "mttr_seconds_avg"
            ) or 0
        ),
    })


# ============================================================
# PENDING APPROVALS
# ============================================================

@dashboard_api.route(
    "/api/dashboard/approvals",
    methods=["GET"],
)
def approvals():

    if not _check_api_key():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    pending = (
        approval_store
        .list_pending()
    )

    return jsonify({
        "count": len(pending),
        "pending": pending,
    })


# ============================================================
# HISTORY
# ============================================================

@dashboard_api.route(
    "/api/dashboard/history",
    methods=["GET"],
)
def history():

    if not _check_api_key():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    limit = request.args.get(
        "limit",
        50,
        type=int,
    )

    limit = max(
        1,
        min(limit, 200),
    )

    audit_log = (
        execution_service
        .safety
        .get_audit_log()
    )

    entries = []

    for entry in reversed(
        audit_log[-limit:]
    ):

        entries.append({
            "timestamp": entry.get(
                "timestamp"
            ),

            "action_id": entry.get(
                "action_id"
            ),

            "status": _classify_entry(
                entry
            ),

            "message": entry.get(
                "message"
            ),

            "success": entry.get(
                "success",
                False,
            ),
        })

    return jsonify({
        "count": len(entries),
        "history": entries,
    })


# ============================================================
# TEST CRITICAL INCIDENT
# ============================================================

_test_incidents = []


@dashboard_api.route(
    "/api/dashboard/test-critical",
    methods=["POST"],
)
def test_critical():

    if not _check_api_key():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    now = datetime.now(
        timezone.utc
    )

    incident = {
        "incident_id": (
            f"TEST-CRITICAL-"
            f"{int(now.timestamp())}"
        ),

        "timestamp": now.isoformat(),

        "service": "demo-service",

        "pod": "demo-pod",

        "metric": "CPU",

        "metric_key": "cpu",

        "value": 96.5,

        "threshold": 90,

        "severity": "CRITICAL",

        "status": "pending_approval",

        "decision": (
            "Human approval required "
            "for critical action"
        ),

        "action": "restart_pod",

        "test": True,
    }

    _test_incidents.append(
        incident
    )

    return jsonify({
        "success": True,
        "incident": incident,
    })


# ============================================================
# TEST INCIDENTS
# ============================================================

@dashboard_api.route(
    "/api/dashboard/test-incidents",
    methods=["GET"],
)
def test_incidents():

    if not _check_api_key():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    return jsonify({
        "count": len(
            _test_incidents
        ),

        "incidents": list(
            reversed(
                _test_incidents
            )
        ),
    })


@dashboard_api.route(
    "/api/dashboard/test-incidents",
    methods=["DELETE"],
)
def clear_test_incidents():

    if not _check_api_key():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    _test_incidents.clear()

    return jsonify({
        "success": True
    })