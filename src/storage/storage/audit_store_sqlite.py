from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


def _db_path() -> Path:
    """
    Lit AUDIT_DB_PATH à chaque appel (et non au moment de l'import) afin que
    l'isolation des tests mise en place par conftest.py fonctionne réellement,
    et que la valeur par défaut reste data/audit.sqlite3 en usage normal.
    """
    return Path(os.getenv("AUDIT_DB_PATH", "data/audit.sqlite3"))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action_id TEXT NOT NULL,
                success INTEGER NOT NULL,
                message TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_requests (
                action_id TEXT PRIMARY KEY,
                executor TEXT NOT NULL,
                params TEXT NOT NULL DEFAULT '{}',
                severity TEXT NOT NULL,
                reason TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                status TEXT NOT NULL,
                decided_at TEXT,
                decided_by TEXT
            )
            """
        )

        conn.commit()


def reset_db() -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM audit_log")
        conn.execute("DELETE FROM approval_requests")
        conn.commit()


def append_audit_entry(
    timestamp: str,
    action_id: str,
    success: bool,
    message: str,
) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_log
                (timestamp, action_id, success, message)
            VALUES
                (?, ?, ?, ?)
            """,
            (
                timestamp,
                action_id,
                int(success),
                message,
            ),
        )
        conn.commit()


def load_audit_log() -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, action_id, success, message
            FROM audit_log
            ORDER BY id
            """
        ).fetchall()

    return [
        {
            "timestamp": row["timestamp"],
            "action_id": row["action_id"],
            "success": bool(row["success"]),
            "message": row["message"],
        }
        for row in rows
    ]


def upsert_approval(
    request: dict[str, Any],
) -> None:
    init_db()
    params = json.dumps(
        request.get("params", {}),
        default=str,
    )

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO approval_requests
                (
                    action_id,
                    executor,
                    params,
                    severity,
                    reason,
                    requested_at,
                    status,
                    decided_at,
                    decided_by
                )
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(action_id)
            DO UPDATE SET
                executor = excluded.executor,
                params = excluded.params,
                severity = excluded.severity,
                reason = excluded.reason,
                requested_at = excluded.requested_at,
                status = excluded.status,
                decided_at = excluded.decided_at,
                decided_by = excluded.decided_by
            """,
            (
                request["action_id"],
                request["executor"],
                params,
                request["severity"],
                request["reason"],
                request["requested_at"],
                request["status"],
                request.get("decided_at"),
                request.get("decided_by"),
            ),
        )
        conn.commit()


def load_approvals() -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM approval_requests
            ORDER BY requested_at
            """
        ).fetchall()

    results = []
    for row in rows:
        results.append(
            {
                "action_id": row["action_id"],
                "executor": row["executor"],
                "params": json.loads(row["params"]),
                "severity": row["severity"],
                "reason": row["reason"],
                "requested_at": row["requested_at"],
                "status": row["status"],
                "decided_at": row["decided_at"],
                "decided_by": row["decided_by"],
            }
        )

    return results
