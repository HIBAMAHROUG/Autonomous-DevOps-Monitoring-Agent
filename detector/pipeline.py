

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from detector.detector import check_metrics

logger = logging.getLogger(__name__)

try:
    from anomaly_agent.isolation_forest import IsolationForestDetector
except Exception:
    IsolationForestDetector = None


_ml_detector = None


def _get_ml_detector():
    """
    Lazily initialize the Isolation Forest detector.

    The project can still operate with threshold detection
    if the ML component is unavailable.
    """
    global _ml_detector

    if _ml_detector is not None:
        return _ml_detector

    if IsolationForestDetector is None:
        logger.warning(
            "Isolation Forest component is unavailable. "
            "Threshold confirmation will be used."
        )
        return None

    try:
        _ml_detector = IsolationForestDetector()
        return _ml_detector
    except Exception as exc:
        logger.warning(
            "Unable to initialize Isolation Forest: %s",
            exc,
        )
        return None


def _metric_value(metrics: Dict[str, Any], metric: str) -> Optional[float]:
    """
    Extract a numeric metric value from different possible
    metric dictionary formats.
    """
    value = metrics.get(metric)

    if value is None:
        value = metrics.get(metric.lower())

    if value is None:
        value = metrics.get(metric.upper())

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ml_confirm(
    metrics: Dict[str, Any],
    alert: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Try to confirm an alert with Isolation Forest.

    The function is intentionally defensive because the exact
    ML implementation can vary between project versions.
    """

    detector = _get_ml_detector()

    if detector is None:
        alert["ml_confirmed"] = True
        alert["ml_confidence"] = float(
            alert.get("confidence", 0.80)
        )
        return alert

    metric = alert.get("metric")

    value = _metric_value(metrics, metric)

    if value is None:
        alert["ml_confirmed"] = True
        alert["ml_confidence"] = float(
            alert.get("confidence", 0.80)
        )
        return alert

    try:
        # Support several common detector APIs.
        if hasattr(detector, "predict"):
            result = detector.predict([[value]])

        elif hasattr(detector, "detect"):
            result = detector.detect([value])

        elif hasattr(detector, "is_anomaly"):
            result = detector.is_anomaly(value)

        else:
            logger.warning(
                "Isolation Forest detector has no supported API."
            )
            result = True

        if isinstance(result, (list, tuple)):
            result = result[0]

        if isinstance(result, dict):
            confirmed = bool(
                result.get(
                    "is_anomaly",
                    result.get("anomaly", True),
                )
            )

            confidence = float(
                result.get(
                    "confidence",
                    result.get("score", 0.80),
                )
            )

        else:
            # sklearn commonly returns -1 for anomaly
            # and 1 for normal.
            if result == -1:
                confirmed = True
            elif result == 1:
                confirmed = False
            else:
                confirmed = bool(result)

            confidence = 0.85 if confirmed else 0.20

        alert["ml_confirmed"] = confirmed
        alert["ml_confidence"] = confidence

        return alert

    except Exception as exc:
        logger.warning(
            "ML confirmation failed: %s. "
            "Keeping threshold alert.",
            exc,
        )

        alert["ml_confirmed"] = True
        alert["ml_confidence"] = 0.80

        return alert


def check_and_confirm(
    metrics: Dict[str, Any],
    service: str = "infrastructure",
    pod: Optional[str] = None,
    baselines: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Main two-stage detection pipeline.

    Stage 1:
        Check thresholds.

    Stage 2:
        Confirm each threshold alert with ML.

    Returns:
        List of confirmed incidents.
    """

    try:
        threshold_alerts = check_metrics(
            metrics,
            service=service,
            pod=pod,
            baselines=baselines,
        )
    except TypeError:
        # Compatibility with older detector versions.
        threshold_alerts = check_metrics(
            metrics,
            service=service,
            pod=pod,
        )

    if not threshold_alerts:
        return []

    confirmed: List[Dict[str, Any]] = []

    for alert in threshold_alerts:

        alert = dict(alert)

        alert["service"] = alert.get(
            "service",
            service,
        )

        if pod:
            alert["pod"] = alert.get(
                "pod",
                pod,
            )

        alert = _ml_confirm(
            metrics,
            alert,
        )

        if alert.get("ml_confirmed", True):

            # Normalize confidence.
            confidence = alert.get(
                "ml_confidence",
                alert.get("confidence", 0.80),
            )

            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 0.80

            alert["confidence"] = confidence

            # Make sure downstream components have
            # the information they need.
            alert.setdefault(
                "status",
                "OPEN",
            )

            alert.setdefault(
                "source",
                "prometheus",
            )

            confirmed.append(alert)

            logger.warning(
                "Confirmed incident: metric=%s "
                "value=%s severity=%s confidence=%.2f",
                alert.get("metric"),
                alert.get("value"),
                alert.get("severity"),
                confidence,
            )

        else:
            logger.info(
                "Threshold alert rejected by ML: %s",
                alert,
            )

    return confirmed


# Backward compatibility.
def detect_and_confirm(
    metrics: Dict[str, Any],
    service: str = "infrastructure",
    pod: Optional[str] = None,
    baselines: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Backward-compatible alias.
    """
    return check_and_confirm(
        metrics=metrics,
        service=service,
        pod=pod,
        baselines=baselines,
    )