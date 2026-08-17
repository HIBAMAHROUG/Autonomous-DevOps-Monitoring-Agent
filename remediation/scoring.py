"""
Score de confiance par action candidate.

Formule (pondération par défaut, ajustable via config) :
- 35% similarité du matching anomalie <-> problème connu
- 30% taux de succès historique de l'action
- 15% sévérité de l'anomalie (une anomalie critique pousse à agir)
- 10% fraîcheur de la donnée (problème vu récemment = plus fiable)
- pénalité de 15% si l'action n'est pas réversible
"""

from __future__ import annotations

from dataclasses import dataclass

from remediation.models import AnomalyEvent, CandidateAction, ScoredCandidate, Severity

SEVERITY_WEIGHTS: dict[Severity, float] = {
    Severity.CRITICAL: 1.0,
    Severity.HIGH: 0.85,
    Severity.MEDIUM: 0.65,
    Severity.LOW: 0.5,
}


@dataclass
class ScoringWeights:
    similarity: float = 0.35
    success_rate: float = 0.30
    severity: float = 0.15
    freshness: float = 0.10
    irreversible_penalty: float = 0.15


def freshness_score(occurrences: int) -> float:
    """
    Proxy simple de "fraîcheur" en l'absence de vraie donnée last_updated
    fiable : plus un problème a été rencontré souvent, plus on lui fait
    confiance. Plafonné à 1.0 à partir de 20 occurrences.
    """
    if occurrences <= 0:
        return 0.3  # nouveau problème, jamais confirmé -> prudence
    return min(1.0, 0.3 + occurrences / 20)


def compute_confidence(
    candidate: CandidateAction,
    anomaly: AnomalyEvent,
    weights: ScoringWeights = ScoringWeights(),
) -> float:
    similarity = candidate.match_score
    success_rate = candidate.action.success_rate_historical
    severity_factor = SEVERITY_WEIGHTS[anomaly.severity]
    freshness = freshness_score(candidate.source_problem.occurrences)
    penalty = weights.irreversible_penalty if not candidate.action.reversible else 0.0

    score = (
        weights.similarity * similarity
        + weights.success_rate * success_rate
        + weights.severity * severity_factor
        + weights.freshness * freshness
        - penalty
    )
    return round(max(0.0, min(1.0, score)), 3)


def score_candidates(
    candidates: list[CandidateAction],
    anomaly: AnomalyEvent,
    weights: ScoringWeights = ScoringWeights(),
) -> list[ScoredCandidate]:
    scored = [
        ScoredCandidate(candidate=c, confidence=compute_confidence(c, anomaly, weights))
        for c in candidates
    ]
    # Meilleure confiance en premier -> decision.py prend scored[0] par défaut
    scored.sort(key=lambda s: s.confidence, reverse=True)
    return scored