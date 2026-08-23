"""Tests de l'orchestrateur end-to-end."""

from orchestrator.orchestrator import handle_alert, reset_backends


def test_orchestrator_import():
    """Vérifie que l'orchestrateur est correctement importable."""
    assert callable(handle_alert)


def test_reset_backends():
    """Vérifie que les backends peuvent être réinitialisés."""
    reset_backends()