from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from diagonisis.log_collector import (
    MAX_DURATION,
    MAX_LINES,
    LogCollectionError,
    get_pod_logs,
)


def _loki_response(messages):
    return {
        "data": {
            "result": [
                {
                    "values": [
                        [str(1_700_000_000_000_000_000 + i), msg]
                        for i, msg in enumerate(messages)
                    ]
                }
            ]
        }
    }


def test_acceptance_criteria_constants():
    # US 2.1 : 500 dernières lignes, temps de récupération <= 5 secondes.
    assert MAX_LINES == 500
    assert MAX_DURATION == 5


@patch("diagonisis.log_collector.requests.get")
def test_get_pod_logs_requests_up_to_500_lines(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: _loki_response(["INFO ok"]),
    )
    mock_get.return_value.raise_for_status = lambda: None

    get_pod_logs("checkout-service-abc123", namespace="prod")

    _, kwargs = mock_get.call_args
    assert kwargs["params"]["limit"] == 500
    assert kwargs["timeout"] == (1, 5)


@patch("diagonisis.log_collector.requests.get")
def test_get_pod_logs_filters_warn_error_fatal(mock_get):
    messages = [
        "INFO service started",
        "WARN cache miss rate high",
        "ERROR failed to connect to db",
        "DEBUG heartbeat",
        "FATAL unrecoverable state",
    ]
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: _loki_response(messages),
    )
    mock_get.return_value.raise_for_status = lambda: None

    result = get_pod_logs("pod-1")

    filtered_messages = [log["message"] for log in result["logs"]]

    assert filtered_messages == [
        "WARN cache miss rate high",
        "ERROR failed to connect to db",
        "FATAL unrecoverable state",
    ]
    assert result["count"] == 3


@patch("diagonisis.log_collector.requests.get")
def test_get_pod_logs_caps_at_max_lines(mock_get):
    messages = [f"ERROR line {i}" for i in range(600)]
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: _loki_response(messages),
    )
    mock_get.return_value.raise_for_status = lambda: None

    result = get_pod_logs("pod-1")

    assert result["count"] <= MAX_LINES


@patch("diagonisis.log_collector.requests.get")
def test_get_pod_logs_raises_on_connection_error(mock_get):
    mock_get.side_effect = requests.ConnectionError("boom")

    with pytest.raises(LogCollectionError):
        get_pod_logs("pod-1")


@patch("diagonisis.log_collector.time.perf_counter")
@patch("diagonisis.log_collector.requests.get")
def test_get_pod_logs_raises_if_slower_than_max_duration(
    mock_get, mock_perf_counter
):
    # Simule une récupération qui dépasse le budget de 5 secondes.
    mock_perf_counter.side_effect = [0.0, MAX_DURATION + 1]

    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: _loki_response(["ERROR slow"]),
    )
    mock_get.return_value.raise_for_status = lambda: None

    with pytest.raises(LogCollectionError):
        get_pod_logs("pod-1")