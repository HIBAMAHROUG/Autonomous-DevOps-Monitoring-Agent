"""
Endpoint /metrics au format Prometheus (US dashboard : "connecter avec
Prometheus/Grafana").

Distinct de `api/routes.py` (`/api/metrics`, JSON, écrit vers InfluxDB) :
ici on expose au format texte Prometheus les métriques *internes* de
l'agent -- décisions, incidents/self-healing, garde-fous -- pour que
`prometheus.yml` (job `api`) puisse les scraper et que Grafana les
affiche à côté des métriques d'infrastructure (node-exporter).
"""
from __future__ import annotations

from flask import Blueprint, Response

import remediation.mttr as mttr
from executor.service import execution_service
from monitoring import agent_metrics
from remediation.approvals import approval_store

prometheus_api = Blueprint("prometheus_api", __name__)


@prometheus_api.route("/metrics", methods=["GET"])
def metrics():
    # Rafraîchit les jauges "état actuel" juste avant de servir --
    # les compteurs/histogrammes, eux, sont alimentés en continu par
    # l'orchestrateur (voir orchestrator/orchestrator.py).
    agent_metrics.sync_from_mttr_stats(mttr.get_stats())

    safety = execution_service.safety
    agent_metrics.sync_safety_state(
        circuit_open=safety.state.circuit_open,
        kill_switch=safety.state.kill_switch,
        pending=len(approval_store.list_pending()),
    )

    payload, content_type = agent_metrics.render_latest()
    return Response(payload, mimetype=content_type)
