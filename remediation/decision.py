"""
Logique de décision finale.

Les seuils sont chargés depuis :
config/remediation_thresholds.yaml
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

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


CONFIG_PATH = (
    Path(__file__).resolve().parent.parent
    / "config"
    / "remediation_thresholds.yaml"
)


def load_thresholds(
    config_path: Path = CONFIG_PATH,
) -> dict[Severity, SeverityThresholds]:
    """Charge les seuils depuis le fichier YAML."""

    if not config_path.exists():
        raise FileNotFoundError(
            f"Remediation thresholds configuration not found: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    raw_thresholds = data.get("thresholds", {})

    thresholds: dict[Severity, SeverityThresholds] = {}

    for severity in Severity:
        key = severity.value.lower()
        values = raw_thresholds.get(key)

        if values is None:
            raise ValueError(
                f"Missing remediation thresholds for severity: {key}"
            )

        thresholds[severity] = SeverityThresholds(
            auto_execute=float(values["auto_execute"]),
            suggest=float(values["suggest"]),
        )

    return thresholds


DEFAULT_THRESHOLDS = load_thresholds()


def decide(
    anomaly: AnomalyEvent,
    scored_candidates: list[ScoredCandidate],
    thresholds: dict[Severity, SeverityThresholds] = DEFAULT_THRESHOLDS,
    shadow_mode: bool = False,
) -> Decision:
    """
    Décide si l'agent :

    - auto-exécute ;
    - suggère une action humaine ;
    - escalade.

    shadow_mode=True force le mode SUGGEST_TO_HUMAN.
    """

    candidate_actions_payload = [
        {
            "action_id": sc.candidate.action.action_id,
            "confidence": sc.confidence,
        }
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
        chosen_action_id=(
            best.candidate.action.action_id
            if mode != DecisionMode.ESCALATE
            else None
        ),
        decision_mode=mode,
        confidence=best.confidence,
        reason=reason,
    )