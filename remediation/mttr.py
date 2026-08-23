"""
Suivi du MTTR (Mean Time To Resolution).

Le cahier des charges annonce un objectif chiffré : réduction du MTTR de
40%. Avant ce module, rien dans le code ne mesurait de temps de
résolution -- impossible de défendre cet objectif avec des données
réellement produites par l'agent.

Stockage en mémoire (process-local), volontairement simple : suffisant
pour le dashboard et la démonstration end-to-end. À migrer vers
storage.remediation_repository (table `decisions`, dont le schéma
Postgres a déjà les colonnes resolution_time_s/resolved_at) si une
persistance multi-instance devient nécessaire en production.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Literal

Outcome = Literal["resolved", "escalated", "pending"]


@dataclass
class IncidentRecord:
    incident_id: str
    detected_at: datetime
    resolved_at: datetime | None = None
    outcome: Outcome = "pending"

    @property
    def mttr_seconds(self) -> float | None:
        if self.resolved_at is None:
            return None
        return (self.resolved_at - self.detected_at).total_seconds()


_incidents: dict[str, IncidentRecord] = {}


def record_detected(
    incident_id: str,
    detected_at: datetime | None = None,
) -> None:
    """À appeler dès qu'une anomalie confirmée démarre le pipeline de
    remédiation (voir orchestrator.handle_alert)."""
    _incidents[incident_id] = IncidentRecord(
        incident_id=incident_id,
        detected_at=detected_at or datetime.now(timezone.utc),
    )


def record_outcome(incident_id: str, outcome: Outcome) -> None:
    """outcome: 'resolved' (vérification Prometheus OK) ou 'escalated'
    (diagnostic <80%, aucune action trouvée, ou vérification échouée)."""
    record = _incidents.get(incident_id)

    if record is None:
        # Incident jamais suivi depuis sa détection (ex: approbation
        # traitée sans passer par l'orchestrateur) -- on le crée quand
        # même pour ne pas perdre la donnée, avec detected_at = now
        # (sous-estime le MTTR réel dans ce cas, mais évite un crash).
        record = IncidentRecord(
            incident_id=incident_id,
            detected_at=datetime.now(timezone.utc),
        )
        _incidents[incident_id] = record

    record.outcome = outcome

    if outcome in ("resolved", "escalated") and record.resolved_at is None:
        record.resolved_at = datetime.now(timezone.utc)


def get_stats() -> dict:
    records = list(_incidents.values())
    total = len(records)

    resolved = [r for r in records if r.outcome == "resolved"]
    escalated = [r for r in records if r.outcome == "escalated"]
    pending = [r for r in records if r.outcome == "pending"]

    resolution_times = [
        r.mttr_seconds for r in resolved if r.mttr_seconds is not None
    ]

    return {
        "total_incidents": total,
        "resolved": len(resolved),
        "escalated": len(escalated),
        "pending": len(pending),
        "auto_resolution_rate": (
            round(len(resolved) / total, 3) if total else None
        ),
        "escalation_rate": (
            round(len(escalated) / total, 3) if total else None
        ),
        "mttr_seconds_avg": (
            round(mean(resolution_times), 1) if resolution_times else None
        ),
    }


def reset() -> None:
    """Vide le suivi -- utilitaire pour les tests."""
    _incidents.clear()