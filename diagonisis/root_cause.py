"""
Diagnostic de cause racine (US 2.2).

`diagonisis/patterns.yaml` déclare des catégories connues (OutOfMemory,
DiskFull, NetworkTimeout, CrashLoop, ConnectionRefused) avec un score de
confiance chacune, mais avant ce module aucun code ne les exploitait --
c'était un écart objectif entre le cahier des charges (qui exige un
score de confiance sur le diagnostic, avec escalade si < 80%) et
l'implémentation réelle.

Ce module fait correspondre les logs filtrés (WARN/ERROR/FATAL, voir
diagonisis.log_collector.get_pod_logs) aux patterns connus et retourne
un diagnostic explicite avec sa confiance.

Important : cette confiance (root_cause_confidence) est distincte de la
confiance de correspondance action<->anomalie calculée dans
remediation/scoring.py::compute_confidence(). Un score ML d'anomalie
élevé ne signifie pas que la cause racine est identifiée avec certitude
-- ce sont deux mesures différentes, gardées séparées ici.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

PATTERNS_PATH = os.getenv(
    "ROOT_CAUSE_PATTERNS_PATH",
    str(Path(__file__).resolve().parent / "patterns.yaml"),
)

# Cahier des charges : confiance de diagnostic < 80% => intervention
# humaine obligatoire, avant même d'envisager une remédiation automatique.
ROOT_CAUSE_CONFIDENCE_THRESHOLD = 0.80


@dataclass
class RootCauseDiagnosis:
    category: str | None
    confidence: float
    matched_pattern: str | None = None
    matched_log: str | None = None

    @property
    def requires_human(self) -> bool:
        return self.confidence < ROOT_CAUSE_CONFIDENCE_THRESHOLD

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "confidence": self.confidence,
            "matched_pattern": self.matched_pattern,
            "matched_log": self.matched_log,
            "requires_human": self.requires_human,
        }


def _load_categories(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return data.get("categories", {})


def diagnose(
    logs: list[dict],
    path: str = PATTERNS_PATH,
) -> RootCauseDiagnosis:
    """
    logs : liste de {"timestamp": ..., "message": ...}, typiquement le
    résultat de diagonisis.log_collector.get_pod_logs(...)["logs"]
    (donc déjà filtré sur WARN/ERROR/FATAL, du plus récent au plus
    ancien puisque Loki est interrogé avec direction="backward").

    Stratégie : premier pattern qui matche (log le plus récent en
    premier) l'emporte, avec la confiance déclarée pour sa catégorie
    dans patterns.yaml. Si aucun pattern ne matche sur aucun log,
    retourne confidence=0.0 -> requires_human=True (escalade).
    """
    categories = _load_categories(path)

    compiled: dict[str, list[tuple[re.Pattern, str]]] = {
        category: [
            (re.compile(p, re.IGNORECASE), p)
            for p in (info.get("patterns") or [])
        ]
        for category, info in categories.items()
    }

    for log in logs:
        message = log.get("message", "")

        for category, patterns in compiled.items():
            for compiled_pattern, raw_pattern in patterns:
                if compiled_pattern.search(message):
                    return RootCauseDiagnosis(
                        category=category,
                        confidence=float(categories[category]["confidence"]),
                        matched_pattern=raw_pattern,
                        matched_log=message,
                    )

    return RootCauseDiagnosis(category=None, confidence=0.0)