from __future__ import annotations

import json
from typing import Any

from remediation.db_connector import get_connection, get_dict_cursor


def init_db() -> None:
    return None


def reset_db() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM audit_log")
            cur.execute("DELETE FROM approval_requests")


def append_audit_entry(
    timestamp: str,
    action_id: str,
    success: bool,
    message: str,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log
                    (timestamp, action_id, success, message)
                VALUES
                    (%s, %s, %s, %s)
                """,
                (timestamp, action_id, success, message),
            )


def _as_iso(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return value.isoformat()


def load_audit_log() -> list[dict[str, Any]]:
    with get_dict_cursor() as cur:
        cur.execute(
            """
            SELECT timestamp, action_id, success, message
            FROM audit_log
            ORDER BY id
            """
        )

        rows = cur.fetchall()

        return [
            {
                "timestamp": _as_iso(row["timestamp"]),
                "action_id": row["action_id"],
                "success": bool(row["success"]),
                "message": row["message"],
            }
            for row in rows
        ]


def upsert_approval(request: dict[str, Any]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
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
                    (
                        %(action_id)s,
                        %(executor)s,
                        %(params)s,
                        %(severity)s,
                        %(reason)s,
                        %(requested_at)s,
                        %(status)s,
                        %(decided_at)s,
                        %(decided_by)s
                    )
                ON CONFLICT (action_id)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    decided_at = EXCLUDED.decided_at,
                    decided_by = EXCLUDED.decided_by
                """,
                {
                    **request,
                    "params": json.dumps(request["params"]),
                },
            )


def load_approvals() -> list[dict[str, Any]]:
    with get_dict_cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM approval_requests
            ORDER BY requested_at
            """
        )

        rows = cur.fetchall()
        results = []

        for row in rows:
            record = dict(row)

            params = record["params"]

            record["params"] = (
                json.loads(params)
                if isinstance(params, str)
                else params
            )

            record["requested_at"] = _as_iso(
                record["requested_at"]
            )

            record["decided_at"] = _as_iso(
                record["decided_at"]
            )

            results.append(record)

        return results
