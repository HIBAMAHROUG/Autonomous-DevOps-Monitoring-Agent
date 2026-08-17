"""
Logique de décision finale : à partir des candidates scorées, décide si
l'agent auto-exécute, suggère à un humain, ou escalade.

Les seuils sont chargés depuis config (voir config/remediation_thresholds.yaml)
et NE DOIVENT PAS être codés en dur ailleurs dans le projet.
"""

from __future__ import annotations

from dataclasses import dataclass

from remediation.models import (
    AnomalyEvent,
    Decision,
    DecisionMode,
    ScoredCandidate,
    Severity,
)


@dataclass
class SeverityThresholds:
    auto_execute: float
    suggest: float


DEFAULT_THRESHOLDS: dict[Severity, SeverityThresholds] = {
    Severity.CRITICAL: SeverityThresholds(auto_execute=0.90, suggest=0.60),
    Severity.HIGH: SeverityThresholds(auto_execute=0.85, suggest=0.50),
    Severity.MEDIUM: SeverityThresholds(auto_execute=0.80, suggest=0.40),
    Severity.LOW: SeverityThresholds(auto_execute=0.75, suggest=0.30),
}


def decide(
    anomaly: AnomalyEvent,
    scored_candidates: list[ScoredCandidate],
    thresholds: dict[Severity, SeverityThresholds] = DEFAULT_THRESHOLDS,
    shadow_mode: bool = False,
) -> Decision:
    """
    shadow_mode=True force le mode SUGGEST_TO_HUMAN même si la confiance
    dépasserait le seuil d'auto-exécution. À utiliser pendant la période
    probatoire avant d'activer l'auto-exécution en prod (voir design doc,
    étape "shadow mode").
    """
    candidate_actions_payload = [
        {"action_id": sc.candidate.action.action_id, "confidence": sc.confidence}
        for sc in scored_candidates
    ]

    if not scored_candidates:
        return Decision(
            decision_id=Decision.new_id(),
            anomaly_id=anomaly.anomaly_id,
            matched_problem_id=None,
            candidate_actions=[],
            chosen_action_id=None,
            decision_mode=DecisionMode.ESCALATE,
            confidence=None,
            reason="no_matching_problem_or_action_found",
        )

    best = scored_candidates[0]
    t = thresholds[anomaly.severity]

    if (
        not shadow_mode
        and best.confidence >= t.auto_execute
        and best.candidate.action.reversible
    ):
        mode = DecisionMode.AUTO_EXECUTE
        reason = "confidence_above_auto_execute_threshold"
    elif best.confidence >= t.suggest:
        mode = DecisionMode.SUGGEST_TO_HUMAN
        reason = (
            "shadow_mode_enabled"
            if shadow_mode and best.confidence >= t.auto_execute
            else "confidence_above_suggest_threshold_below_auto_execute"
        )
    else:
        mode = DecisionMode.ESCALATE
        reason = "confidence_below_suggest_threshold"

    return Decision(
        decision_id=Decision.new_id(),
        anomaly_id=anomaly.anomaly_id,
        matched_problem_id=best.candidate.source_problem.problem_id,
        candidate_actions=candidate_actions_payload,
        chosen_action_id=best.candidate.action.action_id if mode != DecisionMode.ESCALATE else None,
        decision_mode=mode,
        confidence=best.confidence,
        reason=reason,
    )