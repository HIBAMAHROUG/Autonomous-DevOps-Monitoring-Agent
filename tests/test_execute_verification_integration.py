import remediation.verification as verification_module
from executor.base import ExecutionResult
from executor.service import ExecutionService
from remediation.approvals import approval_store
from remediation.models import Action


def _service():
    # Instance isolée (pas le singleton execution_service) pour ne pas
    # polluer le rate-limiting/circuit breaker partagé entre tests.
    return ExecutionService()


def _stub_success(executor_service, executor_name: str) -> None:
    """
    Remplace l'exécuteur réel (docker/kubectl...) par un stub qui renvoie
    toujours un succès, sans invoquer de binaire externe -- ces tests
    portent sur le branchement execute_and_verify/execute_approved ->
    verify_remediation, pas sur les exécuteurs eux-mêmes (déjà testés
    ailleurs).
    """

    class _StubExecutor:
        def execute(self, action_id, params, dry_run=True):
            return ExecutionResult(
                success=True,
                action_id=action_id,
                executor=executor_name,
                dry_run=dry_run,
                message="stubbed success",
            )

    executor_service.executors[executor_name] = _StubExecutor()


def test_execute_and_verify_runs_verification_on_success(monkeypatch):
    monkeypatch.setattr(verification_module, "query_prometheus", lambda q: 10.0)
    escalations = []
    monkeypatch.setattr(
        verification_module,
        "notify_escalation",
        lambda **kwargs: escalations.append(kwargs),
    )

    service = _service()
    _stub_success(service, "docker")
    action = Action(
        action_id="ACT-DOCKER-1",
        name="Restart container",
        type="remediation",
        executor="docker",
        reversible=True,
    )

    result, verification = service.execute_and_verify(
        action,
        params={"container_name": "web-1"},
        metric_query="cpu_usage",
        threshold=80.0,
        component="web-1",
        comparison="below",
        dry_run=False,
        severity="HIGH",
        wait_seconds=0,
    )

    assert result.success is True
    assert verification is not None
    assert verification.resolved is True
    assert escalations == []


def test_execute_and_verify_skips_verification_in_dry_run(monkeypatch):
    calls = []
    monkeypatch.setattr(
        verification_module, "query_prometheus", lambda q: calls.append(q) or 0.0
    )

    service = _service()
    action = Action(
        action_id="ACT-DOCKER-2",
        name="Restart container",
        type="remediation",
        executor="docker",
        reversible=True,
    )

    result, verification = service.execute_and_verify(
        action,
        params={"container_name": "web-2"},
        metric_query="cpu_usage",
        threshold=80.0,
        component="web-2",
        dry_run=True,
        wait_seconds=0,
    )

    assert result.dry_run is True
    assert verification is None
    assert calls == []  # Prometheus jamais interrogé en dry-run


def test_execute_approved_triggers_verification_when_info_present(monkeypatch):
    # execute_approved() n'expose pas wait_seconds (toujours
    # DEFAULT_WAIT_SECONDS=60) : on mocke time.sleep pour ne pas
    # ralentir la suite de tests de 60s réelles.
    monkeypatch.setattr(verification_module.time, "sleep", lambda s: None)
    monkeypatch.setattr(verification_module, "query_prometheus", lambda q: 5.0)
    verified = []
    monkeypatch.setattr(
        verification_module,
        "notify_escalation",
        lambda **kwargs: verified.append(kwargs),
    )

    service = _service()
    _stub_success(service, "rollback")
    action = Action(
        action_id="ACT-CRITICAL-1",
        name="Rollback deployment",
        type="remediation",
        executor="rollback",
        reversible=True,
    )

    # Simule ce que execute() fait quand une action critique est bloquée
    # faute d'approbation : une ApprovalRequest est créée avec les infos
    # de vérification attachées sous _verification.
    approval_store.create(
        action_id=action.action_id,
        executor="rollback",
        params={
            "deployment": "checkout-api",
            "_verification": {
                "metric_query": "error_rate",
                "threshold": 1.0,
                "comparison": "below",
                "component": "checkout-api",
            },
        },
        severity="CRITICAL",
        reason="Human approval required for critical action",
    )

    result = service.execute_approved(action, dry_run=False)

    assert result.success is True
    # La vérification a bien tourné automatiquement après l'approbation ;
    # error_rate=5.0 n'est pas < threshold=1.0 -> incident jugé persistant
    # -> escalade (c'est le comportement attendu de verify_remediation).
    assert len(verified) == 1
    assert verified[0]["action_id"] == "ACT-CRITICAL-1"


def test_execute_approved_without_verification_info_does_not_call_prometheus(
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        verification_module, "query_prometheus", lambda q: calls.append(q) or 0.0
    )

    service = _service()
    _stub_success(service, "docker")
    action = Action(
        action_id="ACT-NO-VERIF-1",
        name="Restart container",
        type="remediation",
        executor="docker",
        reversible=True,
    )

    approval_store.create(
        action_id=action.action_id,
        executor="docker",
        params={"container_name": "legacy-app"},
        severity="CRITICAL",
        reason="Human approval required for critical action",
    )

    result = service.execute_approved(action, dry_run=False)

    assert result.success is True
    assert calls == []  # pas d'info _verification -> pas de vérification