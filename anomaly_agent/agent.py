"""Agent temps réel — cœur de la story ML Engineer.

Boucle : toutes les `collection_interval_seconds` (30s par défaut, aligné
sur la story SRE), récupère le dernier point, le score, classe sa sévérité,
génère une explication si anomalie, et dispatch l'alerte.

Garantie de latence (< 60s) : chaque cycle ne fait qu'un appel réseau
(fetch_latest) + du calcul vectorisé en mémoire (µs-ms) -> la latence
dominante est l'écart entre l'horodatage de la donnée et l'instant de
traitement, mesurée et loggée dans chaque Alert.detection_latency_seconds.
"""
import asyncio
import logging
import time

from .alerting import Alert, dispatcher
from .config import settings
from .datasources import get_data_source
from .datasources.base import DataSource
from .explain import explain
from .model import AnomalyDetector
from .severity import classify_severity

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("anomaly_agent.agent")


class AnomalyAgent:
    def __init__(self, detector: AnomalyDetector, source: DataSource = None):
        self.detector = detector
        self.source = source or get_data_source(settings.data_source)
        self._running = False

    def process_once(self):
        sample = self.source.fetch_latest()
        t0 = time.monotonic()
        score, z_scores = self.detector.score_sample(sample.values)
        severity = classify_severity(score, self.detector.thresholds)
        compute_ms = (time.monotonic() - t0) * 1000

        logger.info(
            "point traité ts=%s score=%.3f severity=%s (calcul=%.1fms)",
            sample.timestamp.isoformat(), score, severity, compute_ms,
        )

        if severity is not None:
            explanation = explain(sample.values, z_scores, self.detector.feature_store)
            alert = Alert.create(
                severity=severity, score=score, sample=sample.values,
                explanation=explanation, sample_timestamp=sample.timestamp,
            )
            dispatcher.dispatch(alert)
            return alert
        return None

    async def run_forever(self):
        self._running = True
        interval = settings.collection_interval_seconds
        while self._running:
            cycle_start = time.monotonic()
            try:
                self.process_once()
            except Exception:
                logger.exception("Erreur dans le cycle de détection")
            elapsed = time.monotonic() - cycle_start
            await asyncio.sleep(max(0.0, interval - elapsed))

    def stop(self):
        self._running = False


def main():
    detector = AnomalyDetector.load()
    agent = AnomalyAgent(detector)
    asyncio.run(agent.run_forever())


if __name__ == "__main__":
    main()
