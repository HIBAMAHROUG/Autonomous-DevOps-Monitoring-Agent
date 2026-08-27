"""
Métriques Prometheus natives de l'agent (décisions + self-healing).

Avant ce module, `prometheus.yml` scrape déjà `api:5000/metrics`, mais
rien ne servait ce endpoint : Prometheus/Grafana ne voyaient que les
métriques d'infrastructure (node-exporter), jamais ce que l'agent
décide ou répare lui-même. Ce module comble ce trou en exposant, au
format texte Prometheus, les compteurs et jauges alimentés par
`orchestrator.handle_alert` à chaque étape de la boucle
détection -> diagnostic -> décision -> exécution -> vérification.

Toutes les fonctions sont volontairement no-op-safe : si prometheus_client
n'est pas installé, l'import échoue proprement et l'appelant (l'API)
peut choisir de désactiver l'endpoint plutôt que de planter l'app.
"""
from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry()

# --- Décisions (remediation.process_anomaly / orchestrator) ---------------

decisions_total = Counter(
    "agent_decisions_total",
    "Nombre de décisions prises par le moteur de remédiation, par mode.",
    ["mode"],  # AUTO_EXECUTE | SUGGEST_TO_HUMAN | ESCALATE
    registry=REGISTRY,
)

decision_confidence = Histogram(
    "agent_decision_confidence",
    "Distribution du score de confiance des décisions (0-1).",
    buckets=(0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 1.0),
    registry=REGISTRY,
)

# --- Self-healing / incidents (remediation.mttr) ---------------------------

incidents_total = Counter(
    "agent_incidents_total",
    "Incidents traités par l'agent, par issue finale.",
    ["outcome"],  # resolved | escalated | pending | failed
    registry=REGISTRY,
)

mttr_seconds = Histogram(
    "agent_mttr_seconds",
    "Temps de résolution (détection -> résolution/escalade) en secondes.",
    buckets=(5, 15, 30, 60, 120, 300, 600, 1200, 3600),
    registry=REGISTRY,
)

self_healing_success_ratio = Gauge(
    "agent_self_healing_success_ratio",
    "Part des incidents résolus automatiquement sans intervention humaine "
    "(fenêtre glissante depuis le démarrage du process).",
    registry=REGISTRY,
)

# --- Exécution des actions de remédiation ----------------------------------

remediation_actions_total = Counter(
    "agent_remediation_actions_total",
    "Actions de remédiation exécutées, par type d'action et résultat.",
    ["action_type", "result"],  # result: success | failure
    registry=REGISTRY,
)

# --- Garde-fous de sécurité (remediation.safety.SafetyPolicy) --------------

safety_circuit_breaker_state = Gauge(
    "agent_safety_circuit_breaker_open",
    "1 si le disjoncteur de sécurité est ouvert (exécutions bloquées), 0 sinon.",
    registry=REGISTRY,
)

safety_kill_switch_state = Gauge(
    "agent_safety_kill_switch_enabled",
    "1 si le kill switch est activé (toute exécution automatique stoppée).",
    registry=REGISTRY,
)

pending_approvals_gauge = Gauge(
    "agent_pending_approvals",
    "Nombre de demandes d'approbation humaine actuellement en attente.",
    registry=REGISTRY,
)


def record_decision(mode: str, confidence: float | None) -> None:
    decisions_total.labels(mode=mode).inc()
    if confidence is not None:
        decision_confidence.observe(confidence)


def record_incident_outcome(
    outcome: str, mttr_seconds_value: float | None = None
) -> None:
    incidents_total.labels(outcome=outcome).inc()
    if mttr_seconds_value is not None:
        mttr_seconds.observe(mttr_seconds_value)


def record_remediation_action(action_type: str, success: bool) -> None:
    remediation_actions_total.labels(
        action_type=action_type, result="success" if success else "failure"
    ).inc()


def sync_from_mttr_stats(stats: dict) -> None:
    """Met à jour la jauge de taux de résolution auto depuis
    remediation.mttr.get_stats() (appelé côté /metrics, en lecture)."""
    if stats.get("total_incidents"):
        self_healing_success_ratio.set(
            stats["auto_resolution_rate"] or 0.0
        )


def sync_safety_state(*, circuit_open: bool, kill_switch: bool, pending: int) -> None:
    safety_circuit_breaker_state.set(1 if circuit_open else 0)
    safety_kill_switch_state.set(1 if kill_switch else 0)
    pending_approvals_gauge.set(pending)


def render_latest() -> tuple[bytes, str]:
    """Retourne (payload, content_type) prêt à être servi par Flask."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
