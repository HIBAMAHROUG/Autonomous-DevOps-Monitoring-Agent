"""CLI d'évaluation — vérifie les critères d'acceptation mesurables :
  - Taux de faux positifs < 5%
  - Latence de détection < 60s (simulée)

Usage:
  python -m anomaly_agent.evaluate --model artifacts/anomaly_model.joblib --days 7
"""
import argparse
import logging
import time

import numpy as np

from .config import settings
from .datasources.mock import MockDataSource
from .model import AnomalyDetector
from .severity import classify_severity

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("anomaly_agent.evaluate")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=settings.model_artifact_path)
    parser.add_argument("--days", type=int, default=7, help="jours de données de validation étiquetées")
    args = parser.parse_args()

    detector = AnomalyDetector.load(args.model)

    val_source = MockDataSource(anomaly_probability=0.05, seed=123)
    val_df = val_source.fetch_history(days=args.days)

    y_true, y_pred, latencies = [], [], []
    for _, row in val_df.sort_values("timestamp").iterrows():
        sample = {m: row[m] for m in detector.metric_names if m in row}
        t0 = time.monotonic()
        score, _ = detector.score_sample(sample)
        severity = classify_severity(score, detector.thresholds)
        latencies.append((time.monotonic() - t0) * 1000)

        y_true.append(bool(row["is_anomaly"]))
        y_pred.append(severity is not None)

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    tp = int(np.sum(y_true & y_pred))
    fp = int(np.sum(~y_true & y_pred))
    fn = int(np.sum(y_true & ~y_pred))
    tn = int(np.sum(~y_true & ~y_pred))

    fpr = fp / max(1, (fp + tn))
    recall = tp / max(1, (tp + fn))
    precision = tp / max(1, (tp + fp))

    logger.info("=== Rapport d'évaluation ===")
    logger.info("Points évalués      : %d", len(y_true))
    logger.info("Vrais positifs      : %d", tp)
    logger.info("Faux positifs       : %d", fp)
    logger.info("Faux négatifs       : %d", fn)
    logger.info("Vrais négatifs      : %d", tn)
    logger.info("Taux de faux positifs (FPR) : %.2f%%  (cible < %.0f%%)", fpr * 100, settings.target_false_positive_rate * 100)
    logger.info("Rappel (recall)     : %.2f%%", recall * 100)
    logger.info("Précision           : %.2f%%", precision * 100)
    logger.info("Latence calcul p95  : %.2fms (budget total < %.0fs)", np.percentile(latencies, 95), settings.max_detection_latency_seconds)

    ok = fpr < settings.target_false_positive_rate
    logger.info("Critère FPR < %.0f%% : %s", settings.target_false_positive_rate * 100, "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
