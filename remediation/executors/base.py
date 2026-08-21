from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionResult:
    """Résultat d'exécution d'un executor."""
    
    success: bool
    action_id: str
    executor: str
    dry_run: bool = False
    message: str = ""
    output: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseExecutor:
    """Classe de base pour tous les executors."""
    
    def execute(
        self,
        action_id: str,
        params: dict[str, Any],
        dry_run: bool = True,
    ) -> ExecutionResult:
        """
        Exécute une action de remediation.
        
        Args:
            action_id: Identifiant unique de l'action
            params: Paramètres de l'action
            dry_run: Si True, simule l'exécution sans effectuer de changements
            
        Returns:
            ExecutionResult: Résultat de l'exécution
        """
        raise NotImplementedError("Subclasses must implement execute()")
    
    def validate_params(self, params: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Valide les paramètres de l'action.
        
        Returns:
            Tuple (is_valid, error_message)
        """
        return True, None
