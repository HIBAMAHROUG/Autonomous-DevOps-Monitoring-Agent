import os
from unittest.mock import patch

import pytest

os.environ.setdefault("API_KEY", "test-key")

from app import create_app  # noqa: E402
from executor.service import execution_service  # noqa: E402
from remediation.approvals import approval_store  # noqa: E402
from remediation.models import Action  # noqa: E402


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True

    # reset l'état partagé entre tests
    approval_store._requests.clear()
    execution_service.safety.state.audit_log.clear()
    execution_service.safety.state.action_times.clear()
    execution_service.safety.state.pod_action_times.clear()
    execution_service.safety.state.circuit_open = False
    execution_service.safety.state.consecutive_failures = 0

    with app.test_client() as c:
        yield c


HEADERS = {"X-API-Key": "test-key"}


def test_dashboard_page_loads(client):
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert b"Tableau de bord" in res.data


def test_summary_requires_api_key(client):
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 401


@patch("executor.service.notify_approval_required")
def test_critical_action_creates_pending_approval_and_notifies(
    mock_notify,
    client,
):
    action = Action(
        action_id="rollback-42",
        name="rollback",
        type="rollback",
        executor="rollback",
    )

    result = execution_service.execute(
        action,
        params={"deployment": "checkout"},
        dry_run=True,
        severity="CRITICAL",
        approved=False,
    )

    assert result.success is False
    assert "approval" in result.error.lower()
    mock_notify.assert_called_once()

    res = client.get(
        "/api/approvals/pending",
        headers=HEADERS,
    )

    data = res.get_json()

    assert data["count"] == 1
    assert data["approvals"][0]["action_id"] == "rollback-42"


@patch("executor.service.notify_approval_required")
def test_approve_endpoint_marks_approved_and_returns_execution_result(
    mock_notify,
    client,
):
    action = Action(
        action_id="rollback-43",
        name="rollback",
        type="rollback",
        executor="rollback",
    )

    execution_service.execute(
        action,
        params={"deployment": "checkout"},
        dry_run=True,
        severity="CRITICAL",
        approved=False,
    )

    res = client.post(
        "/api/approvals/rollback-43/approve",
        headers=HEADERS,
    )

    data = res.get_json()

    assert res.status_code == 200
    assert data["approval"]["status"] == "APPROVED"

    # dry_run=False dans execute_approved -> exécution réelle tentée
    # (échouera proprement sans kubectl/cluster réel, mais le workflow
    # d'approbation lui-même doit passer)
    assert "execution_result" in data


@patch("executor.service.notify_approval_required")
def test_reject_endpoint_marks_rejected(mock_notify, client):
    action = Action(
        action_id="rollback-44",
        name="rollback",
        type="rollback",
        executor="rollback",
    )

    execution_service.execute(
        action,
        params={"deployment": "checkout"},
        dry_run=True,
        severity="CRITICAL",
        approved=False,
    )

    res = client.post(
        "/api/approvals/rollback-44/reject",
        headers=HEADERS,
    )

    data = res.get_json()

    assert res.status_code == 200
    assert data["approval"]["status"] == "REJECTED"

    # une deuxième décision sur la même demande doit être refusée
    res2 = client.post(
        "/api/approvals/rollback-44/approve",
        headers=HEADERS,
    )

    assert res2.status_code == 404


def test_approve_unknown_action_returns_404(client):
    res = client.post(
        "/api/approvals/does-not-exist/approve",
        headers=HEADERS,
    )

    assert res.status_code == 404


@patch("executor.service.notify_approval_required")
def test_dashboard_summary_counts_escalated_action(
    mock_notify,
    client,
):
    action = Action(
        action_id="rollback-45",
        name="rollback",
        type="rollback",
        executor="rollback",
    )

    execution_service.execute(
        action,
        params={"deployment": "checkout"},
        dry_run=True,
        severity="CRITICAL",
        approved=False,
    )

    res = client.get(
        "/api/dashboard/summary",
        headers=HEADERS,
    )

    data = res.get_json()

    assert data["escalated"] == 1
    assert data["pending_approval"] == 1


def test_dashboard_history_reflects_audit_log(client):
    action = Action(
        action_id="scale-1",
        name="scale",
        type="scaling",
        executor="scaling",
    )

    execution_service.execute(
        action,
        params={
            "deployment": "web",
            "replicas": 3,
        },
        dry_run=True,
    )

    res = client.get(
        "/api/dashboard/history",
        headers=HEADERS,
    )

    data = res.get_json()

    assert data["count"] >= 1
    assert data["history"][0]["action_id"] == "scale-1"
