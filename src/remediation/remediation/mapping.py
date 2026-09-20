"""
Moteur de mapping : transforme une AnomalyEvent en liste de CandidateAction.

Stratégie (dans l'ordre) :
1. Matching exact par signature (metric + component) -> match_type="exact", score=1.0
2. Si rien trouvé, matching sémantique simple par texte -> match_type="semantic"
3. Si toujours rien, liste vide -> le decision.py escaladera automatiquement
"""

from __future__ import annotations

from remediation.catalog import ActionCatalog
from remediation.knowledge_base import KnowledgeBase
from remediation.models import AnomalyEvent, CandidateAction


def map_anomaly_to_candidates(
    anomaly: AnomalyEvent,
    kb: KnowledgeBase,
    catalog: ActionCatalog,
) -> list[CandidateAction]:
    problems = kb.find_by_signature(anomaly.metric, anomaly.component)
    match_type = "exact"

    if not problems:
        query_text = anomaly.description or f"{anomaly.metric} {anomaly.component}"
        problems = kb.search_by_text(query_text, top_k=3)
        match_type = "semantic"

    if not problems:
        return []

    candidates: list[CandidateAction] = []
    for problem in problems:
        match_score = 1.0 if match_type == "exact" else _semantic_score_placeholder(problem)
        for action_id in problem.corrective_actions:
            action = catalog.get(action_id)
            if action is None:
                # Le problème référence une action absente du catalogue :
                # on l'ignore plutôt que de planter, mais ça vaut la peine
                # de logger cette incohérence côté appelant.
                continue
            candidates.append(
                CandidateAction(
                    action=action,
                    source_problem=problem,
                    match_score=match_score,
                    match_type=match_type,
                )
            )

    return candidates


def _semantic_score_placeholder(problem) -> float:
    """
    Le matching par mots-clés de JsonKnowledgeBase.search_by_text ne renvoie
    pas de score exploitable directement ici (il est déjà utilisé pour trier
    en interne). On applique un score prudent par défaut pour le matching
    sémantique tant que ce n'est pas remplacé par une vraie recherche
    vectorielle qui renvoie un score de similarité normalisé.
    """
    return 0.6