from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import remediation.executors.kubectl_client as kc


def setup_function():
    # Chaque test repart d'un suivi de connectivité vierge.
    kc._tracker = kc._OfflineTracker()


@patch("remediation.executors.kubectl_client.subprocess.run")
def test_success_on_first_try_does_not_retry(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="ok",
        stderr="",
    )

    result = kc.run_kubectl(["kubectl", "get", "pods"])

    assert result.returncode == 0
    assert mock_run.call_count == 1


@patch("remediation.executors.kubectl_client.time.sleep")
@patch("remediation.executors.kubectl_client.subprocess.run")
def test_connectivity_error_is_retried_with_backoff(mock_run, mock_sleep):
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="Unable to connect to the server: dial tcp: i/o timeout",
    )

    result = kc.run_kubectl(
        ["kubectl", "scale", "deployment/x", "--replicas=3"],
        max_retries=3,
    )

    # 1 tentative initiale + 3 retries = 4 appels au total.
    assert mock_run.call_count == 4
    assert result.returncode == 1

    # Backoff exponentiel : 2s, 4s, 8s.
    assert [call.args[0] for call in mock_sleep.call_args_list] == [
        2.0,
        4.0,
        8.0,
    ]


@patch("remediation.executors.kubectl_client.subprocess.run")
def test_application_error_is_not_retried(mock_run):
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr='Error from server (NotFound): deployments.apps "x" not found',
    )

    result = kc.run_kubectl(["kubectl", "rollout", "undo", "deployment/x"])

    assert mock_run.call_count == 1
    assert result.returncode == 1


@patch("remediation.executors.kubectl_client.notify_agent_offline")
@patch("remediation.executors.kubectl_client.time.sleep")
@patch("remediation.executors.kubectl_client.subprocess.run")
def test_prolonged_outage_triggers_agent_offline_alert(
    mock_run,
    mock_sleep,
    mock_notify,
):
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="connection refused",
    )

    # Simule que la première panne a débuté il y a plus de 5 minutes :
    # le prochain échec constaté doit donc déclencher l'alerte.
    kc._tracker.first_failure_at = (
        kc.time.monotonic() - kc.OFFLINE_THRESHOLD_SECONDS - 1
    )

    kc.run_kubectl(["kubectl", "get", "pods"], max_retries=0)

    mock_notify.assert_called_once()
    assert kc._tracker.alert_sent is True


@patch("remediation.executors.kubectl_client.notify_agent_offline")
@patch("remediation.executors.kubectl_client.subprocess.run")
def test_alert_is_sent_only_once_per_outage(mock_run, mock_notify):
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="connection refused",
    )

    kc._tracker.first_failure_at = (
        kc.time.monotonic() - kc.OFFLINE_THRESHOLD_SECONDS - 1
    )

    kc.run_kubectl(["kubectl", "get", "pods"], max_retries=0)
    kc.run_kubectl(["kubectl", "get", "pods"], max_retries=0)
    kc.run_kubectl(["kubectl", "get", "pods"], max_retries=0)

    mock_notify.assert_called_once()


@patch("remediation.executors.kubectl_client.notify_agent_offline")
@patch("remediation.executors.kubectl_client.subprocess.run")
def test_recovery_resets_tracker(mock_run, mock_notify):
    kc._tracker.first_failure_at = (
        kc.time.monotonic() - kc.OFFLINE_THRESHOLD_SECONDS - 1
    )
    kc._tracker.alert_sent = True

    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="ok",
        stderr="",
    )

    kc.run_kubectl(["kubectl", "get", "pods"])

    assert kc._tracker.first_failure_at is None
    assert kc._tracker.alert_sent is False


@patch("remediation.executors.kubectl_client.notify_agent_offline")
@patch("remediation.executors.kubectl_client.time.sleep")
@patch("remediation.executors.kubectl_client.subprocess.run")
def test_timeout_expired_is_treated_as_connectivity_failure(
    mock_run,
    mock_sleep,
    mock_notify,
):
    mock_run.side_effect = subprocess.TimeoutExpired(
        cmd=["kubectl", "get", "pods"],
        timeout=60,
    )

    result = kc.run_kubectl(["kubectl", "get", "pods"], max_retries=1)

    assert result.returncode == 1
    assert "timed out" in result.stderr
    assert mock_run.call_count == 2
