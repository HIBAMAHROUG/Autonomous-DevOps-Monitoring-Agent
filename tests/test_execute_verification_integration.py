from __future__ import annotations

from unittest.mock import MagicMock, patch

from executor.service import ExecutionService
from remediation.approvals import approval_store
from remediation.models import Action
from remediation.safety import SafetyPolicy


def _make_service_with_forced_approval():
    """
    ExecutionService dont SafetyPolicy.check() force systématiquement le
    chemin "approbation requise", pour tester le branchement bout-en-bout
    execute() -> approval_store -> execute_approved() sans dépendre des
    règles réelles de criticité.
    """
    service = ExecutionService()
    service.safety = SafetyPolicy()
    service.safety.check = MagicMock(
        return_value=(False, "Human approval required for critical action")
    )
    service.safety.audit = MagicMock()
    service.safety.record_result = MagicMock()
    return service


@patch("executor.service.notify_approval_required")
def test_execute_attaches_verification_info_to_approval(mock_notify):
    service = _make_service_with_forced_approval()

    action = Action(
        action_id="ACT-VERIFY-1",
        name="restart service",
        type="docker",
        executor="docker",
    )

    service.execute(
        action,
        params={"container": "checkout"},
        dry_run=False,
        severity="CRITICAL",
        metric_query="cpu_usage",
        threshold=90.0,
        comparison="below",
        component="checkout-service",
    )

    request = approval_store.get("ACT-VERIFY-1")

    assert request is not None
    assert request.params["_verification"] == {
        "metric_query": "cpu_usage",
        "threshold": 90.0,
        "comparison": "below",
        "component": "checkout-service",
    }
    # Le conteneur cible doit rester dans les params passés à l'exécuteur.
    assert request.params["container"] == "checkout"


@patch("executor.service.notify_approval_required")
def test_execute_without_verification_info_creates_plain_approval(
    mock_notify,
):
    service = _make_service_with_forced_approval()

    action = Action(
        action_id="ACT-VERIFY-2",
        name="restart service",
        type="docker",
        executor="docker",
    )

    service.execute(
        action,
        params={"container": "checkout"},
        dry_run=False,
        severity="CRITICAL",
    )

    request = approval_store.get("ACT-VERIFY-2")

    assert request is not None
    assert "_verification" not in request.params


@patch("executor.service.verify_remediation")
@patch("executor.service.DockerExecutor.execute")
def test_execute_approved_triggers_verification_when_present(
    mock_docker_execute, mock_verify
):
    from executor.base import ExecutionResult

    service = ExecutionService()

    action = Action(
        action_id="ACT-VERIFY-3",
        name="restart service",
        type="docker",
        executor="docker",
    )

    approval_store.create(
        action_id="ACT-VERIFY-3",
        executor="docker",
        params={
            "container": "checkout",
            "_verification": {
                "metric_query": "cpu_usage",
                "threshold": 90.0,
                "comparison": "below",
                "component": "checkout-service",
            },
        },
        severity="CRITICAL",
        reason="Human approval required for critical action",
    )

    mock_docker_execute.return_value = ExecutionResult(
        success=True,
        action_id="ACT-VERIFY-3",
        executor="docker",
        dry_run=False,
        message="restarted",
    )

    service.execute_approved(action, dry_run=False)

    mock_verify.assert_called_once_with(
        action_id="ACT-VERIFY-3",
        component="checkout-service",
        metric_query="cpu_usage",
        threshold=90.0,
        comparison="below",
    )

    # Le conteneur doit avoir été transmis à l'exécuteur, sans la clé
    # réservée _verification.
    _, kwargs = mock_docker_execute.call_args
    assert kwargs["params"] == {"container": "checkout"}


@patch("executor.service.verify_remediation")
@patch("executor.service.DockerExecutor.execute")
def test_execute_approved_skips_verification_in_dry_run(
    mock_docker_execute, mock_verify
):
    from executor.base import ExecutionResult

    service = ExecutionService()

    action = Action(
        action_id="ACT-VERIFY-4",
        name="restart service",
        type="docker",
        executor="docker",
    )

    approval_store.create(
        action_id="ACT-VERIFY-4",
        executor="docker",
        params={
            "container": "checkout",
            "_verification": {
                "metric_query": "cpu_usage",
                "threshold": 90.0,
                "comparison": "below",
                "component": "checkout-service",
            },
        },
        severity="CRITICAL",
        reason="Human approval required for critical action",
    )

    mock_docker_execute.return_value = ExecutionResult(
        success=True,
        action_id="ACT-VERIFY-4",
        executor="docker",
        dry_run=True,
        message="dry-run ok",
    )

    service.execute_approved(action, dry_run=True)

    mock_verify.assert_not_called()


@patch("executor.service.verify_remediation")
@patch("executor.service.DockerExecutor.execute")
def test_execute_approved_skips_verification_when_execution_fails(
    mock_docker_execute, mock_verify
):
    from executor.base import ExecutionResult

    service = ExecutionService()

    action = Action(
        action_id="ACT-VERIFY-5",
        name="restart service",
        type="docker",
        executor="docker",
    )

    approval_store.create(
        action_id="ACT-VERIFY-5",
        executor="docker",
        params={
            "container": "checkout",
            "_verification": {
                "metric_query": "cpu_usage",
                "threshold": 90.0,
                "comparison": "below",
                "component": "checkout-service",
            },
        },
        severity="CRITICAL",
        reason="Human approval required for critical action",
    )

    mock_docker_execute.return_value = ExecutionResult(
        success=False,
        action_id="ACT-VERIFY-5",
        executor="docker",
        dry_run=False,
        message="failed",
        error="container not found",
    )

    service.execute_approved(action, dry_run=False)

    mock_verify.assert_not_called()