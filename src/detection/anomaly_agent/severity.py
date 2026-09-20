"""Classification de sévérité (low/medium/high/critical) — critère d'acceptation ML."""
from typing import Optional

from .model import Thresholds

SEVERITY_ORDER = ["low", "medium", "high", "critical"]


def classify_severity(score: float, thresholds: Thresholds) -> Optional[str]:
    """Retourne None si le point est considéré normal (pas d'alerte)."""
    if score < thresholds.anomaly:
        return None
    if score < thresholds.medium:
        return "low"
    if score < thresholds.high:
        return "medium"
    if score < thresholds.critical:
        return "high"
    return "critical"
