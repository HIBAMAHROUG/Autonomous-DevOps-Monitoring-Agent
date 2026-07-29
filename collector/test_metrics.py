import os
import importlib
from unittest.mock import patch, MagicMock


def test_headers_without_token():
    with patch.dict(os.environ, {}, clear=True):
        from collector import metrics
        importlib.reload(metrics)
        assert metrics._get_headers() == {}


def test_headers_with_token():
    with patch.dict(os.environ, {"PROMETHEUS_TOKEN": "abc123"}):
        from collector import metrics
        importlib.reload(metrics)
        assert metrics._get_headers() == {"Authorization": "Bearer abc123"}


@patch("collector.metrics.requests.get")
def test_query_prometheus_success(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": {"result": [{"value": [0, "42.5"]}]}
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    from collector import metrics
    importlib.reload(metrics)
    result = metrics.query_prometheus("up")
    assert result == 42.5


@patch("collector.metrics.requests.get")
def test_query_prometheus_empty_result_raises(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": {"result": []}}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    from collector import metrics
    importlib.reload(metrics)

    try:
        metrics.query_prometheus("up")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass