from __future__ import annotations

import os

from . import audit_store_sqlite as _sqlite
from . import audit_store_postgres as _postgres


def _backend():
    backend = os.getenv(
        "AUDIT_BACKEND",
        "sqlite",
    ).strip().lower()

    if backend == "postgres":
        return _postgres

    return _sqlite


def init_db() -> None:
    _backend().init_db()


def reset_db() -> None:
    _backend().reset_db()


def append_audit_entry(
    timestamp: str,
    action_id: str,
    success: bool,
    message: str,
) -> None:
    _backend().append_audit_entry(
        timestamp,
        action_id,
        success,
        message,
    )


def load_audit_log():
    return _backend().load_audit_log()


def upsert_approval(request):
    _backend().upsert_approval(request)


def load_approvals():
    return _backend().load_approvals()
