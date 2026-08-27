"""
Journal des décisions de l'agent (remediation.decision_log).

Ce module conserve un historique borné, en mémoire, des dernières
décisions prises par le moteur de remédiation (AUTO_EXECUTE,
SUGGEST_TO_HUMAN, ESCALATE). Il sert deux consommateurs :

- le dashboard (templates/dashboard.html), qui affiche le fil des
  décisions récentes sans avoir à interroger InfluxDB ;
- monitoring/agent_metrics.py, indirectement, puisque chaque décision
  journalisée ici incrémente aussi les compteurs Prometheus via
  record_decision (appelé par orchestrator.handle_alert).

Volontairement en mémoire (deque) et non persistant : au redémarrage
du process, l'historique redémarre à zéro, ce qui correspond au même
choix que remediation.mttr et remediation.approvals dans ce projet.
Si besoin de persistance, brancher ici un writer InfluxDB/SQLite plus
tard sans changer l'API publique du module.
"""
from __future__ import annotations

import threading
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Deque, Optional

_MAX_ENTRIES = 500


@dataclass
class DecisionEntry:
    id: str
    timestamp: str
    incident_id: Optional[str]
    mode: str  # AUTO_EXECUTE | SUGGEST_TO_HUMAN | ESCALATE
    confidence: Optional[float]
    action_type: Optional[str]
    reason: Optional[str]
    outcome: Optional[str] = None  # rempli plus tard par update_outcome()

    def to_dict(self) -> dict:
        return asdict(self)


class DecisionLogStore:
    def __init__(self, max_entries: int = _MAX_ENTRIES) -> None:
        self._entries: Deque[DecisionEntry] = deque(maxlen=max_entries)
        self._by_id: dict[str, DecisionEntry] = {}
        self._lock = threading.Lock()

    def add(
        self,
        *,
        mode: str,
        confidence: Optional[float] = None,
        incident_id: Optional[str] = None,
        action_type: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> DecisionEntry:
        entry = DecisionEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            incident_id=incident_id,
            mode=mode,
            confidence=confidence,
            action_type=action_type,
            reason=reason,
        )
        with self._lock:
            if len(self._entries) == self._entries.maxlen:
                oldest = self._entries[0]
                self._by_id.pop(oldest.id, None)
            self._entries.append(entry)
            self._by_id[entry.id] = entry
        return entry

    def update_outcome(self, decision_id: str, outcome: str) -> bool:
        with self._lock:
            entry = self._by_id.get(decision_id)
            if entry is None:
                return False
            entry.outcome = outcome
            return True

    def list_recent(self, limit: int = 50) -> list[dict]:
        with self._lock:
            snapshot = list(self._entries)[-limit:]
        snapshot.reverse()  # plus récent en premier
        return [e.to_dict() for e in snapshot]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._by_id.clear()


# Instance partagée, utilisée par orchestrator.py et api/routes.py
decision_log = DecisionLogStore()
