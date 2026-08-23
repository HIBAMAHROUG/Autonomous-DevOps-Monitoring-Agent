import remediation.verification as verification_module
from remediation.verification import verify_remediation


def test_verify_remediation_resolved_below_threshold(monkeypatch):
    monkeypatch.setattr(
        verification_module, "query_prometheus", lambda q: 42.0
    )

    escalated_calls = []
    monkeypatch.setattr(
        verification_module,
        "notify_escalation",
        lambda **kwargs: escalated_calls.append(kwargs),
    )

    result = verify_remediation(
        action_id="ACT-1",
        component="pod-a",
        metric_query="cpu_usage",
        threshold=80.0,
        comparison="below",
        wait_seconds=0,
    )

    assert result.resolved is True
    assert result.escalated is False
    assert result.value == 42.0
    assert escalated_calls == []


def test_verify_remediation_still_above_threshold_escalates(monkeypatch):
    monkeypatch.setattr(
        verification_module, "query_prometheus", lambda q: 95.0
    )

    escalated_calls = []
    monkeypatch.setattr(
        verification_module,
        "notify_escalation",
        lambda **kwargs: escalated_calls.append(kwargs),
    )

    result = verify_remediation(
        action_id="ACT-1",
        component="pod-a",
        metric_query="cpu_usage",
        threshold=80.0,
        comparison="below",
        wait_seconds=0,
    )

    assert result.resolved is False
    assert result.escalated is True
    assert len(escalated_calls) == 1
    assert escalated_calls[0]["action_id"] == "ACT-1"


def test_verify_remediation_prometheus_error_escalates(monkeypatch):
    def _raise(q):
        raise ValueError("no data")

    monkeypatch.setattr(verification_module, "query_prometheus", _raise)

    escalated_calls = []
    monkeypatch.setattr(
        verification_module,
        "notify_escalation",
        lambda **kwargs: escalated_calls.append(kwargs),
    )

    result = verify_remediation(
        action_id="ACT-2",
        component="pod-b",
        metric_query="memory_usage",
        threshold=10.0,
        comparison="above",
        wait_seconds=0,
    )

    assert result.resolved is False
    assert result.escalated is True
    assert result.value is None
    assert result.error == "no data"
    assert len(escalated_calls) == 1


def test_verify_remediation_waits_configured_seconds(monkeypatch):
    slept = []
    monkeypatch.setattr(verification_module.time, "sleep", slept.append)
    monkeypatch.setattr(
        verification_module, "query_prometheus", lambda q: 1.0
    )
    monkeypatch.setattr(
        verification_module, "notify_escalation", lambda **kwargs: None
    )

    verify_remediation(
        action_id="ACT-3",
        component="pod-c",
        metric_query="q",
        threshold=100.0,
        comparison="below",
        wait_seconds=60,
    )

    assert slept == [60]