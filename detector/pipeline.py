"""Pipeline unifié de détection (Epic 1).

Avant cette version, `detector/` (seuils statiques) et `anomaly_agent/`
(isolation forest + sévérité calibrée par quantiles) étaient deux systèmes
de détection indépendants, non coordonnés. Ce module les assemble en un
seul pipeline à deux étages :

  1. Pré-filtre à seuils (`detector.py`) : peu coûteux, réagit vite, gère déjà
     le dépassement soutenu (`duration`), la tendance et les fenêtres de
     maintenance (Bug 2).
  2. Confirmation ML (`anomaly_agent`) : seulement déclenchée si l'étage 1
     réagit, elle évalue les 4 métriques ensemble (pas une seule à la fois)
     et calibre une sévérité (low/medium/high/critical). Si le modèle ne
     confirme pas l'anomalie, l'alerte est écartée -- un filtre
     supplémentaire contre les faux positifs, au-delà de Bug 2 seul.

`anomaly_agent/` reste utilisable indépendamment (son API FastAPI dédiée,
`anomaly_agent/api.py`, n'est pas affectée) ; ce module est le point
d'entrée à utiliser depuis `collector/collector.py`.
"""
from __future__ import annotations

from typing import Any

from anomaly_agent.model import AnomalyDetector as MLAnomalyDetector
from anomaly_agent.severity import classify_severity

from .detector import check_metrics as _threshold_check_metrics

_ml_detector: MLAnomalyDetector | None = None


def _get_ml_detector() -> MLAnomalyDetector:
    global _ml_detector

    if _ml_detector is None:
        # AnomalyDetector.load() amorce un modèle sur données simulées si
        # aucun artefact entraîné n'existe encore (voir anomaly_agent/model.py).
        _ml_detector = MLAnomalyDetector.load()

    return _ml_detector


def check_and_confirm(
    metrics: dict[str, float],
    service: str = "default",
    baselines: dict | None = None,
    ml_detector: MLAnomalyDetector | None = None,
) -> list[dict[str, Any]]:
    """
    Retourne une liste d'alertes confirmées par les deux étages, enrichies
    du score ML et de la sévérité calibrée.

    Liste vide si le pré-filtre ne déclenche pas, ou si le modèle ML ne
    confirme pas l'anomalie.

    `ml_detector` est injectable pour les tests ; sinon un modèle partagé
    est chargé paresseusement (voir `_get_ml_detector`).
    """
    threshold_alerts = _threshold_check_metrics(
        metrics,
        service=service,
        baselines=baselines,
    )

    if not threshold_alerts:
        return []

    detector = ml_detector or _get_ml_detector()

    score, z_scores = detector.score_sample(metrics)
    severity = classify_severity(
        score,
        detector.thresholds,
    )

    if severity is None:
        # Le pré-filtre a réagi à une seule métrique en dépassement, mais le
        # modèle multivarié juge l'ensemble des métriques normal -> pas d'alerte.
        return []

    return [
        {
            **alert,
            "ml_score": round(score, 4),
            "severity": severity,
            "z_scores": {
                k: round(v, 2)
                for k, v in z_scores.items()
            },
        }
        for alert in threshold_alerts
    ]
