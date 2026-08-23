from contextlib import contextmanager
from unittest.mock import patch
import json

import storage.audit_store as dispatcher
import storage.audit_store_postgres as pg


class FakeCursor:
    def __init__(self, store):
        self.store = store
        self._last_query = None
        self._result = []

    def execute(self, query, params=None):
        self._last_query = (query, params)

        q = " ".join(query.strip().lower().split())

        if q.startswith("insert into audit_log"):
            if isinstance(params, dict):
                self.store["audit_log"].append(
                    {
                        "id": len(self.store["audit_log"]) + 1,
                        "timestamp": params.get("timestamp"),
                        "action_id": params.get("action_id"),
                        "success": params.get("success"),
                        "message": params.get("message"),
                    }
                )
            else:
                self.store["audit_log"].append(
                    {
                        "id": len(self.store["audit_log"]) + 1,
                        "timestamp": params[0],
                        "action_id": params[1],
                        "success": params[2],
                        "message": params[3],
                    }
                )

        elif q.startswith(
            "select timestamp, action_id, success, message from audit_log"
        ):
            self._result = list(self.store["audit_log"])

        elif q.startswith("insert into approval_requests"):
            if isinstance(params, dict):
                stored = dict(params)

                if isinstance(stored.get("params"), str):
                    stored["params"] = json.loads(stored["params"])

                self.store["approvals"][stored["action_id"]] = stored

            else:
                stored = {
                    "action_id": params[0],
                    "executor": params[1],
                    "params": (
                        json.loads(params[2])
                        if isinstance(params[2], str)
                        else params[2]
                    ),
                    "severity": params[3],
                    "reason": params[4],
                    "requested_at": params[5],
                    "status": params[6],
                    "decided_at": params[7],
                    "decided_by": params[8],
                }

                self.store["approvals"][stored["action_id"]] = stored

        elif q.startswith("select * from approval_requests"):
            self._result = list(self.store["approvals"].values())

        elif q.startswith("delete from audit_log"):
            self.store["audit_log"].clear()

        elif q.startswith("delete from approval_requests"):
            self.store["approvals"].clear()

    def fetchall(self):
        return self._result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self, store):
        self.store = store

    def cursor(self, cursor_factory=None):
        return FakeCursor(self.store)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def make_fake_backend():
    store = {
        "audit_log": [],
        "approvals": {},
    }

    @contextmanager
    def fake_get_connection():
        yield FakeConnection(store)

    @contextmanager
    def fake_get_dict_cursor():
        with FakeConnection(store).cursor() as cur:
            yield cur

    return store, fake_get_connection, fake_get_dict_cursor


def test_postgres_append_and_load_audit_entry():
    store, fake_conn, fake_cursor = make_fake_backend()

    with patch.object(pg, "get_connection", fake_conn), patch.object(
        pg, "get_dict_cursor", fake_cursor
    ):
        pg.append_audit_entry(
            "2026-01-01T00:00:00",
            "action-1",
            True,
            "Scaling completed",
        )

        log = pg.load_audit_log()

    assert len(log) == 1
    assert log[0]["action_id"] == "action-1"
    assert log[0]["success"] is True


def test_postgres_upsert_and_load_approval():
    store, fake_conn, fake_cursor = make_fake_backend()

    request = {
        "action_id": "rollback-1",
        "executor": "rollback",
        "params": {"deployment": "checkout"},
        "severity": "critical",
        "reason": "Human approval required for critical action",
        "requested_at": "2026-01-01T00:00:00",
        "status": "PENDING",
        "decided_at": None,
        "decided_by": None,
    }

    with patch.object(pg, "get_connection", fake_conn), patch.object(
        pg, "get_dict_cursor", fake_cursor
    ):
        pg.upsert_approval(request)

        approvals = pg.load_approvals()

    assert len(approvals) == 1
    assert approvals[0]["action_id"] == "rollback-1"
    assert approvals[0]["params"] == {"deployment": "checkout"}


def test_postgres_reset_clears_both_tables():
    store, fake_conn, fake_cursor = make_fake_backend()

    with patch.object(pg, "get_connection", fake_conn), patch.object(
        pg, "get_dict_cursor", fake_cursor
    ):
        pg.append_audit_entry(
            "2026-01-01T00:00:00",
            "a",
            True,
            "m",
        )

        pg.upsert_approval(
            {
                "action_id": "x",
                "executor": "e",
                "params": {},
                "severity": "low",
                "reason": "r",
                "requested_at": "2026-01-01T00:00:00",
                "status": "PENDING",
                "decided_at": None,
                "decided_by": None,
            }
        )

        pg.reset_db()

        assert pg.load_audit_log() == []
        assert pg.load_approvals() == []


def test_dispatcher_uses_sqlite_by_default(monkeypatch):
    monkeypatch.delenv("AUDIT_BACKEND", raising=False)

    assert dispatcher._backend() is dispatcher._sqlite


def test_dispatcher_switches_to_postgres_via_env_var(monkeypatch):
    monkeypatch.setenv("AUDIT_BACKEND", "postgres")

    assert dispatcher._backend() is dispatcher._postgres

    monkeypatch.delenv("AUDIT_BACKEND", raising=False)
