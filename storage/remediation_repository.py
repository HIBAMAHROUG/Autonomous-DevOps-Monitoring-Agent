"""
Repository pour l'historique des décisions de l'agent de remédiation
(table `decisions`, voir storage/schema_remediation.sql).

Sépare volontairement la persistance (ici) de la logique de décision
(remediation/decision.py) : decision.py ne sait pas que Postgres existe,
il retourne juste un objet Decision. C'est ce module qui l'écrit.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from remediation.db_connector import get_dict_cursor
from remediation.models import Decision, DecisionMode


def save_decision(decision: Decision) -> None:
    """À appeler juste après remediation.process_anomaly(), avant toute exécution."""
    with get_dict_cursor() as cur:
        cur.execute(
            """
            INSERT INTO decisions (
                decision_id, anomaly_id, matched_problem_id, candidate_actions,
                chosen_action_id, decision_mode, confidence, reason,
                execution_status, human_override, created_at
            ) VALUES (
                %(decision_id)s, %(anomaly_id)s, %(matched_problem_id)s,
                %(candidate_actions)s, %(chosen_action_id)s, %(decision_mode)s,
                %(confidence)s, %(reason)s, 'pending', false, %(created_at)s
            )
            """,
            {
                "decision_id": decision.decision_id,
                "anomaly_id": decision.anomaly_id,
                "matched_problem_id": decision.matched_problem_id,
                "candidate_actions": json.dumps(decision.candidate_actions),
                "chosen_action_id": decision.chosen_action_id,
                "decision_mode": decision.decision_mode.value,
                "confidence": decision.confidence,
                "reason": decision.reason,
                "created_at": decision.created_at,
            },
        )


def mark_executed(
    decision_id: str,
    status: str,
    resolution_time_s: Optional[int] = None,
) -> None:
    """status: 'success' | 'failed' | 'skipped'."""
    with get_dict_cursor() as cur:
        cur.execute(
            """
            UPDATE decisions
            SET execution_status = %(status)s,
                resolution_time_s = %(resolution_time_s)s,
                executed_at = now(),
                resolved_at = CASE WHEN %(status)s IN ('success','failed')
                                    THEN now() ELSE resolved_at END
            WHERE decision_id = %(decision_id)s
            """,
            {"status": status, "resolution_time_s": resolution_time_s, "decision_id": decision_id},
        )


def record_human_override(decision_id: str, feedback: str | None = None) -> None:
    """
    À appeler quand un humain rejette ou modifie une suggestion
    (SUGGEST_TO_HUMAN). Alimente la boucle de feedback pour recalibrer
    le success_rate_historical des actions (voir catalog.update_success_rate).
    """
    with get_dict_cursor() as cur:
        cur.execute(
            """
            UPDATE decisions
            SET human_override = true,
                feedback = %(feedback)s,
                execution_status = 'overridden'
            WHERE decision_id = %(decision_id)s
            """,
            {"feedback": feedback, "decision_id": decision_id},
        )


def get_decision(decision_id: str) -> Optional[dict[str, Any]]:
    with get_dict_cursor() as cur:
        cur.execute("SELECT * FROM decisions WHERE decision_id = %s", (decision_id,))
        return cur.fetchone()


def list_recent_decisions(
    limit: int = 50,
    decision_mode: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Utilisé par l'API (api/) pour afficher l'historique récent."""
    with get_dict_cursor() as cur:
        if decision_mode:
            cur.execute(
                """
                SELECT * FROM decisions
                WHERE decision_mode = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (decision_mode, limit),
            )
        else:
            cur.execute(
                "SELECT * FROM decisions ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
        return cur.fetchall()


def get_stats(since: datetime) -> dict[str, Any]:
    """
    Stats simples pour un dashboard opérationnel : taux d'auto-résolution,
    taux d'escalade, temps de résolution moyen. Cf. design doc section 6.
    """
    with get_dict_cursor() as cur:
        cur.execute(
            """
            SELECT
                decision_mode,
                COUNT(*) AS count,
                AVG(resolution_time_s) AS avg_resolution_time_s,
                AVG(confidence) AS avg_confidence
            FROM decisions
            WHERE created_at >= %s
            GROUP BY decision_mode
            """,
            (since,),
        )
        rows = cur.fetchall()
        return {row["decision_mode"]: row for row in rows}