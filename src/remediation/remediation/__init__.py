"""
Package remediation — agent de proposition d'actions correctives.

Expose les points d'entrée principaux pour que le reste du projet
(api/, app.py) puisse faire :

    from remediation import process_anomaly

sans connaître le détail interne (mapping, scoring, decision).
"""

from __future__ import annotations

from remediation.catalog import PostgresActionCatalog
from remediation.decision import DEFAULT_THRESHOLDS, decide
from remediation.knowledge_base import PostgresKnowledgeBase
from remediation.mapping import map_anomaly_to_candidates
from remediation.models import (
    Action,
    AnomalyEvent,
    CandidateAction,
    Decision,
    DecisionMode,
    Problem,
    ScoredCandidate,
    Severity,
)
from remediation.scoring import ScoringWeights, score_candidates

__all__ = [
    "Action",
    "AnomalyEvent",
    "CandidateAction",
    "Decision",
    "DecisionMode",
    "Problem",
    "ScoredCandidate",
    "Severity",
    "ScoringWeights",
    "PostgresActionCatalog",
    "PostgresKnowledgeBase",
    "map_anomaly_to_candidates",
    "score_candidates",
    "decide",
    "DEFAULT_THRESHOLDS",
    "process_anomaly",
]


def process_anomaly(
    anomaly: AnomalyEvent,
    kb: PostgresKnowledgeBase,
    catalog: PostgresActionCatalog,
    shadow_mode: bool = False,
) -> Decision:
    """
    Pipeline complet : anomalie -> candidates -> scoring -> décision.
    C'est LA fonction à appeler depuis app.py / api/ pour traiter une
    anomalie reçue depuis detector/diagonisis.
    """
    candidates = map_anomaly_to_candidates(anomaly, kb, catalog)
    scored = score_candidates(candidates, anomaly)
    return decide(anomaly, scored, shadow_mode=shadow_mode)