"""
Boucle de surveillance autonome.

Contrairement à /api/dashboard/simulate-real-incident (qui déclenche le
pipeline manuellement, sur demande, en simulant l'écoulement du temps),
ce module tourne en fond de manière continue :

  - interroge Prometheus toutes les POLL_INTERVAL_SECONDS,
  - alimente le détecteur à seuil (qui a sa propre logique de durée
    minimale de dépassement, cf. config/rules.yaml -> duration: 300),
  - une fois qu'une alerte seuil est confirmée EN CONDITIONS RÉELLES
    (pas de faux "+301s"), calcule le score ML, classe la sévérité,
    et appelle handle_alert() -> le vrai pipeline de décision/exécution.

Démarrage : appeler start_background_monitor() une seule fois au
démarrage de l'app Flask (voir instructions d'intégration ci-dessous).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger("monitor_loop")

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

# Cadence de polling. 30s par défaut, aligné sur
# anomaly_agent.config.settings.collection_interval_seconds.
POLL_INTERVAL_SECONDS = int(os.getenv("MONITOR_POLL_INTERVAL_SECONDS", "30"))

# Nom logique du service/pod surveillé par cette boucle. À remplacer par
# un vrai nom de deployment Kubernetes si tu veux que ACT-SCALE-OUT /
# ACT-RESTART-POD agissent sur une charge de travail réelle.
MONITORED_SERVICE = os.getenv("MONITOR_SERVICE_NAME", "host-monitor")
MONITORED_POD = os.getenv("MONITOR_POD_NAME", "host-monitor")

# Anti-spam : une fois un incident déclenché, on laisse ce délai avant de
# pouvoir en déclencher un nouveau pour le même service, même si le
# dépassement de seuil continue (sinon un incident serait recréé à
# chaque cycle de poll tant que le CPU reste haut).
INCIDENT_COOLDOWN_SECONDS = int(
    os.getenv("MONITOR_INCIDENT_COOLDOWN_SECONDS", "600")
)

PROM_QUERIES = {
    "cpu_usage": (
        '100 - (avg(rate('
        'node_cpu_seconds_total{mode="idle"}[5m]'
        ')) * 100)'
    ),
    "memory_usage": (
        '(1 - (node_memory_MemAvailable_bytes / '
        'node_memory_MemTotal_bytes)) * 100'
    ),
    "network_usage": (
        'sum(rate('
        'node_network_receive_bytes_total{device!="lo"}[5m]'
        ')) + sum(rate('
        'node_network_transmit_bytes_total{device!="lo"}[5m]'
        '))'
    ),
    "disk_usage": (
        '100 - ((node_filesystem_avail_bytes{mountpoint="/rootfs"} / '
        'node_filesystem_size_bytes{mountpoint="/rootfs"}) * 100)'
    ),
}

_last_incident_at: float | None = None
_stop_event = threading.Event()


def _query_prometheus(expr: str) -> float | None:
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

        result = payload.get("data", {}).get("result", [])
        if not result:
            return None

        return float(result[0]["value"][1])

    except (
        requests.RequestException,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
    ) as exc:
        logger.warning("monitor_loop: échec requête Prometheus: %s", exc)
        return None


def _collect_metrics() -> dict[str, float] | None:
    metrics: dict[str, float] = {}

    for name, expr in PROM_QUERIES.items():
        value = _query_prometheus(expr)
        if value is None:
            logger.warning(
                "monitor_loop: métrique '%s' indisponible, cycle ignoré",
                name,
            )
            return None
        metrics[name] = value

    return metrics


def _in_cooldown() -> bool:
    if _last_incident_at is None:
        return False
    return (time.monotonic() - _last_incident_at) < INCIDENT_COOLDOWN_SECONDS


def _run_cycle() -> None:
    """Un cycle de surveillance : collecte, détection, décision."""
    global _last_incident_at

    # Imports différés : évite tout souci d'ordre d'import au chargement
    # du module (app.py doit avoir fini de configurer Flask/les
    # blueprints avant qu'on touche à detector/orchestrator).
    from detector.detector import _default_detector
    from detector.pipeline import check_and_confirm, _get_ml_detector
    from anomaly_agent.severity import classify_severity
    from orchestrator.orchestrator import handle_alert

    metrics = _collect_metrics()
    if metrics is None:
        return

    # Amorce/maintient le compteur de dépassement (_breach_since) du
    # détecteur à seuil. Contrairement à simulate_real_incident, on
    # n'avance PAS le temps artificiellement : la confirmation ne se
    # fait qu'après un vrai dépassement continu de duration_s secondes
    # (cf. config/rules.yaml), atteint au fil des cycles réels.
    check_and_confirm(metrics, service=MONITORED_SERVICE)

    now = datetime.now(timezone.utc)
    threshold_alerts = _default_detector.check(
        metrics,
        service=MONITORED_SERVICE,
        pod=MONITORED_POD,
        now=now,
    )

    if not threshold_alerts:
        return

    if _in_cooldown():
        logger.info(
            "monitor_loop: alerte seuil confirmée pour %s mais "
            "cooldown actif, incident non recréé",
            MONITORED_SERVICE,
        )
        return

    try:
        score, z_scores = _get_ml_detector().score_sample(metrics)
    except Exception as exc:  # modèle non chargé, etc.
        logger.exception("monitor_loop: échec du scoring ML: %s", exc)
        return

    severity = classify_severity(score, _get_ml_detector().thresholds)
    if severity is None:
        logger.info(
            "monitor_loop: seuil dépassé mais score ML non confirmé "
            "(score=%.4f), pas d'incident",
            score,
        )
        return

    alert = {
        **threshold_alerts[0],
        "ml_score": round(score, 4),
        "severity": severity,
        "z_scores": {k: round(v, 2) for k, v in z_scores.items()},
    }

    logger.info(
        "monitor_loop: incident réel détecté service=%s severity=%s "
        "score=%.4f -> déclenchement du pipeline",
        MONITORED_SERVICE,
        severity,
        score,
    )

    try:
        # dry_run=False : contrairement aux tests manuels vus jusqu'ici,
        # une détection automatique en continu doit pouvoir agir pour
        # de vrai. Mets à True si tu veux d'abord observer sans risque
        # avant d'activer l'exécution réelle.
        handle_alert(alert, pod=MONITORED_POD, dry_run=False)
    except Exception as exc:
        logger.exception("monitor_loop: échec handle_alert: %s", exc)
    finally:
        _last_incident_at = time.monotonic()


def _loop() -> None:
    logger.info(
        "monitor_loop: démarrage, poll toutes les %ss, service=%s",
        POLL_INTERVAL_SECONDS,
        MONITORED_SERVICE,
    )
    while not _stop_event.is_set():
        try:
            _run_cycle()
        except Exception as exc:  # ne jamais laisser le thread mourir
            logger.exception("monitor_loop: erreur inattendue: %s", exc)
        _stop_event.wait(POLL_INTERVAL_SECONDS)


def start_background_monitor() -> None:
    """
    Démarre la boucle de surveillance dans un thread daemon.
    Sans effet si déjà démarrée.
    """
    if getattr(start_background_monitor, "_started", False):
        return

    thread = threading.Thread(target=_loop, name="monitor-loop", daemon=True)
    thread.start()
    start_background_monitor._started = True  # type: ignore[attr-defined]


def stop_background_monitor() -> None:
    """Utilitaire pour les tests : arrête proprement la boucle."""
    _stop_event.set()