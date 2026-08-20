"""Détecteur d'anomalies à seuils.

Corrige les limites de la version initiale :
- le seuil doit maintenant être dépassé pendant `duration` secondes
  consécutives avant de déclencher une alerte (évite les pics ponctuels) ;
- le service concerné est dynamique (n'est plus codé en dur) ;
- Bug 2 (faux positifs sur pics légitimes) : une alerte n'est levée que si
  la valeur dépasse aussi `trend_multiplier` fois une valeur de référence
  (baseline), et les alertes sont suspendues pendant les fenêtres de
  maintenance déclarées dans rules.yaml.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import yaml

RULES_PATH = os.getenv("DETECTOR_RULES_PATH", "detector/rules.yaml")

# (clé de règle, champ dans les métriques, libellé pour l'alerte)
MONITORED_METRICS = (
    ("cpu", "cpu_usage", "CPU"),
    ("memory", "memory_usage", "MEMORY"),
)


def _load_rules(path: str = RULES_PATH) -> dict:
    with open(path, "r") as file:
        return yaml.safe_load(file) or {}


@dataclass
class AnomalyDetector:
    rules: dict = field(default_factory=_load_rules)
    # dernier instant où chaque (service, métrique) a commencé à dépasser le seuil
    _breach_since: dict[tuple[str, str], datetime] = field(default_factory=dict)

    def _in_maintenance_window(self, service: str, now: datetime) -> tuple[bool, str | None]:
        for window in self.rules.get("maintenance_windows") or []:
            if service not in window.get("services", []):
                continue
            start = datetime.fromisoformat(window["start"])
            end = datetime.fromisoformat(window["end"])
            if start <= now <= end:
                return True, window.get("name", "unnamed")
        return False, None

    def _passes_trend_check(self, metric_key: str, value: float, baseline: float | None) -> bool:
        multiplier = self.rules.get(metric_key, {}).get("trend_multiplier")
        if multiplier is None or baseline is None or baseline <= 0:
            # pas de baseline dispo -> on ne bloque pas l'alerte sur ce critère
            return True
        return value >= baseline * multiplier

    def check(
        self,
        metrics: dict,
        service: str = "default",
        baselines: dict | None = None,
        now: datetime | None = None,
    ) -> list[dict]:
        """
        baselines : ex. {"cpu": valeur_moyenne_semaine_derniere_meme_heure}
        now : injectable pour les tests, sinon horloge système (UTC)
        """
        now = now or datetime.now(timezone.utc)
        baselines = baselines or {}
        alerts: list[dict] = []

        in_maintenance, window_name = self._in_maintenance_window(service, now)

        for rule_key, field_name, label in MONITORED_METRICS:
            rule = self.rules.get(rule_key)
            if not rule or field_name not in metrics:
                continue

            value = metrics[field_name]
            threshold = rule["threshold"]
            duration = rule.get("duration", 0)
            state_key = (service, rule_key)

            if value <= threshold:
                # retour sous le seuil : on réinitialise le chrono de dépassement
                self._breach_since.pop(state_key, None)
                continue

            breach_start = self._breach_since.setdefault(state_key, now)
            sustained_for = (now - breach_start).total_seconds()

            if sustained_for < duration:
                continue  # dépassement encore trop court

            if in_maintenance:
                continue  # pic attendu, agent mis en pause pour ce service

            if not self._passes_trend_check(rule_key, value, baselines.get(rule_key)):
                continue  # cohérent avec la tendance habituelle -> pas anormal

            alerts.append(
                {
                    "service": service,
                    "metric": label,
                    "value": value,
                    "threshold": threshold,
                    "sustained_seconds": round(sustained_for, 1),
                    "severity": "CRITICAL",
                }
            )

        if alerts:
            os.makedirs("events", exist_ok=True)
            with open("events/alerts.json", "w") as file:
                json.dump(alerts, file, indent=4)

        return alerts


# Instance par défaut partagée entre les appels du process de collecte,
# nécessaire pour que le suivi de `duration` (dépassement soutenu) fonctionne
# d'un cycle de collecte (30s) à l'autre.
_default_detector = AnomalyDetector()


def check_metrics(metrics: dict, service: str = "default", baselines: dict | None = None) -> list[dict]:
    """Wrapper de compatibilité avec l'ancienne signature utilisée par collector.py."""
    return _default_detector.check(metrics, service=service, baselines=baselines)