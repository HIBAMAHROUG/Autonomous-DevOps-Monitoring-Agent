"""
Base de connaissances des problèmes connus.

Deux implémentations :
- JsonKnowledgeBase : lecture depuis config/known_problems.json, pratique
  pour les tests et le dev local.
- PostgresKnowledgeBase : requêtes sur les tables `problems` /
  `problem_actions` (voir storage/schema_remediation.sql), utilisée en
  prod. Le matching sémantique y est encore un fallback texte simple
  (ILIKE) — à remplacer par pgvector si besoin de vraie recherche
  vectorielle, sans changer l'interface `search_by_text`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from remediation.db_connector import get_dict_cursor
from remediation.models import Problem, Severity


class KnowledgeBase(Protocol):
    def find_by_signature(self, metric: str, component: str) -> list[Problem]: ...
    def search_by_text(self, text: str, top_k: int = 3) -> list[Problem]: ...


def _row_to_problem(row: dict, action_ids: list[str]) -> Problem:
    return Problem(
        problem_id=row["problem_id"],
        title=row["title"],
        category=row["category"],
        metric=row["metric"],
        condition=row["condition"],
        affected_component=row["affected_component"],
        duration_s=row["duration_s"] or 0,
        known_causes=row["known_causes"] or [],
        corrective_actions=action_ids,
        severity_default=Severity(row["severity_default"]),
        tags=row["tags"] or [],
        occurrences=row["occurrences"] or 0,
        last_updated=row["last_updated"],
    )


class PostgresKnowledgeBase:
    """Implémentation prod, backée par les tables `problems` / `problem_actions`."""

    def _actions_for(self, cur, problem_id: str) -> list[str]:
        cur.execute(
            "SELECT action_id FROM problem_actions WHERE problem_id = %s",
            (problem_id,),
        )
        return [r["action_id"] for r in cur.fetchall()]

    def find_by_signature(self, metric: str, component: str) -> list[Problem]:
        with get_dict_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM problems
                WHERE metric = %s AND affected_component = %s
                ORDER BY occurrences DESC
                """,
                (metric, component),
            )
            rows = cur.fetchall()
            return [_row_to_problem(r, self._actions_for(cur, r["problem_id"])) for r in rows]

    def search_by_text(self, text: str, top_k: int = 3) -> list[Problem]:
        with get_dict_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM problems
                WHERE title ILIKE %(pattern)s
                   OR category ILIKE %(pattern)s
                   OR tags::text ILIKE %(pattern)s
                ORDER BY occurrences DESC
                LIMIT %(top_k)s
                """,
                {"pattern": f"%{text}%", "top_k": top_k},
            )
            rows = cur.fetchall()
            return [_row_to_problem(r, self._actions_for(cur, r["problem_id"])) for r in rows]

    def record_occurrence(self, problem_id: str) -> None:
        """À appeler à chaque fois qu'un problème est effectivement matché,
        pour que `occurrences` (utilisé dans le scoring de fraîcheur) reste à jour."""
        with get_dict_cursor() as cur:
            cur.execute(
                """
                UPDATE problems
                SET occurrences = occurrences + 1, last_updated = now()
                WHERE problem_id = %s
                """,
                (problem_id,),
            )


class JsonKnowledgeBase:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._problems: list[Problem] = []
        self._load()

    def _load(self) -> None:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._problems = [
            Problem(
                problem_id=item["problem_id"],
                title=item["title"],
                category=item["category"],
                metric=item["metric"],
                condition=item["condition"],
                affected_component=item["affected_component"],
                duration_s=item.get("duration_s", 0),
                known_causes=item.get("known_causes", []),
                corrective_actions=item.get("corrective_actions", []),
                severity_default=Severity(item["severity_default"]),
                tags=item.get("tags", []),
                occurrences=item.get("occurrences", 0),
                last_updated=None,
            )
            for item in raw
        ]

    def find_by_signature(self, metric: str, component: str) -> list[Problem]:
        """
        Matching exact (rule-based) : même métrique + même composant.
        C'est la voie prioritaire du mapping engine (rapide, explicable).
        """
        return [
            p for p in self._problems
            if p.metric == metric and p.affected_component == component
        ]

    def search_by_text(self, text: str, top_k: int = 3) -> list[Problem]:
        """
        Fallback simple par mots-clés (sans dépendance ML), utilisé quand
        aucun match exact n'est trouvé. Remplace ceci par une recherche
        vectorielle (pgvector / OpenSearch kNN) quand tu veux du matching
        sémantique plus robuste — l'interface `search_by_text` reste la même.
        """
        text_lower = text.lower()
        scored: list[tuple[float, Problem]] = []
        for p in self._problems:
            haystack = " ".join([p.title, p.category, *p.tags, *p.known_causes]).lower()
            overlap = sum(1 for word in text_lower.split() if word in haystack)
            if overlap > 0:
                score = overlap / max(len(text_lower.split()), 1)
                scored.append((score, p))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [p for _, p in scored[:top_k]]

    def reload(self) -> None:
        self._problems.clear()
        self._load()