"""Modèle d'alerte + dispatch (log structuré, webhook optionnel)."""
import json
import logging
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Optional

import requests

from .config import settings

logger = logging.getLogger("anomaly_agent.alerting")


@dataclass
class Alert:
    id: str
    timestamp: str
    severity: str
    score: float
    sample: Dict[str, float]
    explanation: dict
    detection_latency_seconds: float

    @staticmethod
    def create(severity: str, score: float, sample: Dict[str, float],
               explanation: dict, sample_timestamp: datetime) -> "Alert":
        now = datetime.now(timezone.utc)
        latency = (now - sample_timestamp).total_seconds()
        return Alert(
            id=str(uuid.uuid4()),
            timestamp=now.isoformat(),
            severity=severity,
            score=round(score, 4),
            sample=sample,
            explanation=explanation,
            detection_latency_seconds=round(latency, 3),
        )


class AlertDispatcher:
    """Stocke les alertes en mémoire (exposées via l'API) + log + webhook optionnel."""

    def __init__(self, max_history: int = 500):
        self._alerts = []
        self.max_history = max_history

    def dispatch(self, alert: Alert) -> None:
        self._alerts.insert(0, alert)
        self._alerts = self._alerts[: self.max_history]

        log_fn = {
            "low": logger.info,
            "medium": logger.warning,
            "high": logger.error,
            "critical": logger.critical,
        }.get(alert.severity, logger.info)
        log_fn(json.dumps(asdict(alert)))

        if alert.detection_latency_seconds > settings.max_detection_latency_seconds:
            logger.error(
                "SLA de détection dépassé: %.1fs > %.1fs pour alerte %s",
                alert.detection_latency_seconds, settings.max_detection_latency_seconds, alert.id,
            )

        if settings.alert_webhook_url:
            try:
                requests.post(settings.alert_webhook_url, json=asdict(alert), timeout=3)
            except Exception as exc:
                logger.warning("Échec envoi webhook: %s", exc)

    def latest(self, limit: int = 50):
        return self._alerts[:limit]

    def get(self, alert_id: str) -> Optional[Alert]:
        return next((a for a in self._alerts if a.id == alert_id), None)


dispatcher = AlertDispatcher()
