from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from remediation.verification import DEFAULT_WAIT_SECONDS, verify_remediation


def _fake_sleep_recorder():
    calls = []

    def _sleep(seconds):
        calls.append(seconds)

    return _sleep, calls


@patch("remediation.verification.notify_remediation_failed")
@patch("remediation.verification.query_prometheus")
def test_verify_remediation_resolved_below(mock_query, mock_notify):
    mock_query.return_value = 40.0  # CPU redescendu sous le seuil

    sleep_fn, sleep_calls = _fake_sleep_recorder()

    result = verify_remediation(
        action_id="ACT-RESTART-SVC",
        component="checkout-service",
        metric_query="cpu_usage",
        threshold=90.0,
        comparison="below",
        sleep_fn=sleep_fn,
    )

    assert result.resolved is True
    assert result.escalated is False
    assert result.value == 40.0
    assert sleep_calls == [DEFAULT_WAIT_SECONDS]
    mock_notify.assert_not_called()


@patch("remediation.verification.notify_remediation_failed")
@patch("remediation.verification.query_prometheus")
def test_verify_remediation_persists_and_escalates(mock_query, mock_notify):
    mock_query.return_value = 95.0  # toujours au-dessus du seuil

    sleep_fn, _ = _fake_sleep_recorder()

    result = verify_remediation(
        action_id="ACT-RESTART-SVC",
        component="checkout-service",
        metric_query="cpu_usage",
        threshold=90.0,
        comparison="below",
        sleep_fn=sleep_fn,
    )

    assert result.resolved is False
    assert result.escalated is True
    mock_notify.assert_called_once_with(
        action_id="ACT-RESTART-SVC",
        component="checkout-service",
        metric="cpu_usage",
        value=95.0,
        threshold=90.0,
    )


@patch("remediation.verification.notify_remediation_failed")
@patch("remediation.verification.query_prometheus")
def test_verify_remediation_resolved_above(mock_query, mock_notify):
    # Cas espace disque disponible : on veut la valeur >= seuil après nettoyage
    mock_query.return_value = 30.0

    sleep_fn, _ = _fake_sleep_recorder()

    result = verify_remediation(
        action_id="ACT-CLEAR-DISK",
        component="worker-node",
        metric_query="disk_free_percent",
        threshold=20.0,
        comparison="above",
        sleep_fn=sleep_fn,
    )

    assert result.resolved is True
    mock_notify.assert_not_called()


@patch("remediation.verification.notify_remediation_failed")
@patch("remediation.verification.query_prometheus")
def test_verify_remediation_prometheus_failure_escalates(
    mock_query, mock_notify
):
    mock_query.side_effect = ValueError("No data returned")

    sleep_fn, _ = _fake_sleep_recorder()

    result = verify_remediation(
        action_id="ACT-RESTART-SVC",
        component="checkout-service",
        metric_query="cpu_usage",
        threshold=90.0,
        sleep_fn=sleep_fn,
    )

    assert result.resolved is False
    assert result.escalated is True
    assert result.value is None
    mock_notify.assert_called_once()


def test_verify_remediation_invalid_comparison_raises():
    with pytest.raises(ValueError):
        verify_remediation(
            action_id="ACT-X",
            component="svc",
            metric_query="cpu_usage",
            threshold=10.0,
            comparison="sideways",
            sleep_fn=lambda s: None,
        )


@patch("remediation.verification.notify_remediation_failed")
@patch("remediation.verification.query_prometheus")
def test_verify_remediation_respects_custom_wait_seconds(
    mock_query, mock_notify
):
    mock_query.return_value = 1.0

    sleep_fn, sleep_calls = _fake_sleep_recorder()

    verify_remediation(
        action_id="ACT-X",
        component="svc",
        metric_query="cpu_usage",
        threshold=90.0,
        wait_seconds=15,
        sleep_fn=sleep_fn,
    )

    assert sleep_calls == [15]