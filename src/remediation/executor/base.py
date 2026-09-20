from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionResult:
    success: bool
    action_id: str
    executor: str
    dry_run: bool
    message: str
    output: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseExecutor(ABC):
    """
    Interface commune de tous les exécuteurs.

    IMPORTANT :
    aucun executor ne doit exécuter une commande réelle
    lorsque dry_run=True.
    """

    @abstractmethod
    def execute(
        self,
        action_id: str,
        params: dict[str, Any],
        dry_run: bool = True,
    ) -> ExecutionResult:
        pass