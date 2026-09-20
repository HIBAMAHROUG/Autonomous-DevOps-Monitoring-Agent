"""
Catalogue des actions correctives.

Deux implémentations :
- JsonActionCatalog : lecture depuis config/actions_catalog.json, pratique
  pour les tests unitaires et le développement local sans DB.
- PostgresActionCatalog : lecture/écriture dans la table `actions`
  (voir storage/schema_remediation.sql), utilisée en prod. C'est elle
  qui permet de mettre à jour success_rate_historical automatiquement
  à partir de l'historique réel des décisions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from remediation.db_connector import get_dict_cursor
from remediation.models import Action


class ActionCatalog(Protocol):
    def get(self, action_id: str) -> Action | None: ...
    def all(self) -> list[Action]: ...


def _row_to_action(row: dict) -> Action:
    return Action(
        action_id=row["action_id"],
        name=row["name"],
        type=row["type"],
        executor=row["executor"],
        params_schema=row["params_schema"] or {},
        risk_level=row["risk_level"],
        reversible=row["reversible"],
        avg_resolution_time_s=row["avg_resolution_time_s"] or 0,
        success_rate_historical=float(row["success_rate_historical"]),
    )


class PostgresActionCatalog:
    """Implémentation prod, backée par la table `actions`."""

    def get(self, action_id: str) -> Action | None:
        with get_dict_cursor() as cur:
            cur.execute("SELECT * FROM actions WHERE action_id = %s", (action_id,))
            row = cur.fetchone()
            return _row_to_action(row) if row else None

    def all(self) -> list[Action]:
        with get_dict_cursor() as cur:
            cur.execute("SELECT * FROM actions ORDER BY action_id")
            return [_row_to_action(r) for r in cur.fetchall()]

    def update_success_rate(self, action_id: str, success: bool) -> None:
        """
        Boucle de feedback : à appeler quand une action AUTO_EXECUTE ou
        SUGGEST_TO_HUMAN validée par un humain se termine, pour recalibrer
        le taux de succès historique (voir design doc, section 6).
        """
        with get_dict_cursor() as cur:
            cur.execute(
                """
                UPDATE actions
                SET executions_count = executions_count + 1,
                    successes_count = successes_count + %(inc)s,
                    success_rate_historical = ROUND(
                        (successes_count + %(inc)s)::numeric
                        / GREATEST(executions_count + 1, 1), 3
                    ),
                    updated_at = now()
                WHERE action_id = %(action_id)s
                """,
                {"inc": 1 if success else 0, "action_id": action_id},
            )


class JsonActionCatalog:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._actions: dict[str, Action] = {}
        self._load()

    def _load(self) -> None:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        for item in raw:
            action = Action(
                action_id=item["action_id"],
                name=item["name"],
                type=item["type"],
                executor=item["executor"],
                params_schema=item.get("params_schema", {}),
                risk_level=item["risk_level"],
                reversible=item["reversible"],
                avg_resolution_time_s=item.get("avg_resolution_time_s", 0),
                success_rate_historical=item.get("success_rate_historical", 0.5),
            )
            self._actions[action.action_id] = action

    def get(self, action_id: str) -> Action | None:
        return self._actions.get(action_id)

    def all(self) -> list[Action]:
        return list(self._actions.values())

    def reload(self) -> None:
        """À appeler si le fichier JSON a été modifié (hot-reload simple)."""
        self._actions.clear()
        self._load()