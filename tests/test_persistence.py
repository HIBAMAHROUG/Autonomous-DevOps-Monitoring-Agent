import os
import tempfile

os.environ["AUDIT_DB_PATH"] = os.path.join(
    tempfile.mkdtemp(),
    "test_persistence.sqlite3",
)

from remediation.approvals import ApprovalStore
from remediation.safety import SafetyPolicy
from storage import audit_store


def setup_function():
    audit_store.init_db()
    audit_store.reset_db()


def test_audit_log_survives_new_safety_policy_instance():
    policy_a = SafetyPolicy(persist=True)

    policy_a.audit(
        "action-1",
        True,
        "Scaling completed",
    )

    policy_a.audit(
        "action-2",
        False,
        "BLOCKED: kill switch",
    )

    # Simule un redémarrage du service.
    policy_b = SafetyPolicy(persist=True)

    assert len(policy_b.state.audit_log) == 2
    assert policy_b.state.audit_log[0]["action_id"] == "action-1"
    assert policy_b.state.audit_log[1]["success"] is False


def test_non_persistent_safety_policy_does_not_touch_db():
    audit_store.reset_db()

    policy = SafetyPolicy(persist=False)

    policy.audit(
        "action-x",
        True,
        "should not be persisted",
    )

    reloaded = SafetyPolicy(persist=True)

    assert reloaded.state.audit_log == []


def test_approval_request_survives_new_store_instance():
    store_a = ApprovalStore(persist=True)

    store_a.create(
        action_id="rollback-99",
        executor="rollback",
        params={"deployment": "checkout"},
        severity="critical",
        reason="Human approval required for critical action",
    )

    # Simule un redémarrage.
    store_b = ApprovalStore(persist=True)

    pending = store_b.list_pending()

    assert len(pending) == 1
    assert pending[0].action_id == "rollback-99"
    assert pending[0].params == {"deployment": "checkout"}


def test_approval_decision_is_persisted():
    store_a = ApprovalStore(persist=True)

    store_a.create(
        action_id="rollback-100",
        executor="rollback",
        params={},
        severity="critical",
        reason="Human approval required for critical action",
    )

    store_a.decide(
        "rollback-100",
        approve=True,
        decided_by="alice",
    )

    store_b = ApprovalStore(persist=True)

    request = store_b.get("rollback-100")

    assert request.status.value == "APPROVED"
    assert request.decided_by == "alice"
    assert store_b.list_pending() == []
