"""Entraînement du détecteur d'anomalies.

Usage:
  python -m anomaly_agent.train --days 30
"""
import argparse
import logging

from .config import settings
from .datasources import get_data_source
from .model import AnomalyDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("anomaly_agent.train")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="historique à utiliser pour l'entraînement")
    parser.add_argument("--source", default=settings.data_source)
    args = parser.parse_args()

    source = get_data_source(args.source)
    history_df = source.fetch_history(days=args.days)

    detector = AnomalyDetector()
    detector.fit(history_df)
    path = detector.save()

    logger.info("Modèle entraîné et sauvegardé dans %s", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
