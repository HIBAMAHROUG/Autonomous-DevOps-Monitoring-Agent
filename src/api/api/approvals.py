"""
API des approbations humaines (US 4.2).

Sécurisée par la même clé API que le reste du service (header X-API-Key),
cohérent avec api/routes.py.
"""
from __future__ import annotations

import os
import hashlib
import hmac
from html import escape

from flask import Blueprint, jsonify, request

from remediation.approvals import approval_store
from remediation.models import Action

approvals_api = Blueprint("approvals_api", __name__)


def _check_api_key() -> bool:
    api_key = request.headers.get("X-API-Key")
    return bool(api_key) and api_key == os.getenv("API_KEY")


def _approval_cookie(action_id: str) -> str:
    secret = os.getenv("API_KEY", "approval-link-secret").encode()
    return hmac.new(secret, action_id.encode(), hashlib.sha256).hexdigest()


def _check_action_access(action_id: str) -> bool:
    if _check_api_key():
        return True
    cookie = request.cookies.get("approval_action")
    return bool(cookie) and hmac.compare_digest(cookie, _approval_cookie(action_id))


def _action_options(approval) -> list[dict]:
    options = approval.params.get("_available_actions", [])
    return options or [{
        "executor": approval.executor,
        "label": approval.executor,
        "params": {},
    }]


@approvals_api.route("/api/approvals/pending", methods=["GET"])
def list_pending():
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    pending = approval_store.list_pending()

    return jsonify({
        "count": len(pending),
        "approvals": [r.to_dict() for r in pending],
    })


@approvals_api.route("/api/approvals", methods=["GET"])
def list_all():
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    requests_ = approval_store.list_all()

    return jsonify({
        "count": len(requests_),
        "approvals": [r.to_dict() for r in requests_],
    })


@approvals_api.route("/api/approvals/<action_id>/approve", methods=["GET", "POST"])
def approve(action_id: str):
    if request.method == "GET":
        if approval_store.get(action_id) is None:
            return jsonify({"error": "Approval request not found"}), 404
        approval = approval_store.get(action_id)
        safe_id = escape(action_id)
        safe_reason = escape(approval.reason)
        safe_severity = escape(approval.severity)
        options = "".join(
            f"<label style='display:block;margin:12px 0'><input type='radio' "
            f"name='action' value='{escape(option['executor'])}' "
            f"{'checked' if index == 0 else ''}> {escape(option.get('label', option['executor']))}</label>"
            for index, option in enumerate(_action_options(approval))
        )
        response = (
            "<!doctype html><title>Confirm approval</title>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<style>body{font:16px system-ui;max-width:680px;margin:48px auto;"
            "padding:0 20px;color:#211b2b;background:#f7f5fa}main{background:#fff;"
            "padding:28px;border:1px solid #ddd5e8;border-radius:14px}"
            "button{padding:10px 16px;margin:8px 8px 0 0;cursor:pointer;"
            "border:1px solid #6d3fd0;border-radius:7px;background:#6d3fd0;"
            "color:#fff;font-weight:600}h1{font-size:24px}"
            ".severity{color:#b4233d;font-weight:700}.reason{padding:14px;"
            "background:#f3eff8;border-radius:8px;line-height:1.5}</style>"
            "<main>"
            f"<h1>Confirm critical action</h1><p>Approve action "
            f"<strong>{safe_id}</strong>?</p><p class='severity'>Severity: "
            f"{safe_severity}</p><p class='reason'>{safe_reason}</p>"
            "<p>Check the incident, logs, impact, then select one remediation:</p>"
            f"<form method='post' action='/api/approvals/{safe_id}/approve'>"
            f"{options}<input type='hidden' name='approved_by' value='email-review'>"
            "<button type='submit'>Approve and execute</button></form>"
            f"<form method='post' action='/api/approvals/{safe_id}/reject'>"
            "<button type='submit'>Reject</button></form></main>"
        )
        return response, 200, {
            "Content-Type": "text/html; charset=utf-8",
            "Set-Cookie": f"approval_action={_approval_cookie(action_id)}; HttpOnly; SameSite=Lax; Max-Age=900",
        }

    if not _check_action_access(action_id):
        return jsonify({"error": "Unauthorized"}), 401

    decided_by = request.headers.get("X-Approved-By", "unknown")

    approval = approval_store.get(action_id)
    if approval is None:
        return jsonify({
            "error": "Approval request not found or already decided"
        }), 404
    selected_executor = request.form.get("action")
    selected = next(
        (option for option in _action_options(approval)
         if option["executor"] == selected_executor),
        None,
    ) if selected_executor else _action_options(approval)[0]
    if selected is None:
        return jsonify({"error": "Invalid remediation option"}), 400
    approval.params.update(selected.get("params", {}))

    decision = approval_store.decide(
        action_id,
        approve=True,
        decided_by=decided_by,
    )

    if decision is None:
        return jsonify({
            "error": "Approval request not found or already decided"
        }), 404

    # Import différé pour éviter un cycle d'import.
    from executor.service import execution_service

    action = Action(
        action_id=decision.action_id,
        name=decision.action_id,
        type=decision.executor,
        executor=selected["executor"],
    )

    result = execution_service.execute_approved(
        action,
        dry_run=False,
    )

    return jsonify({
        "approval": decision.to_dict(),
        "execution_result": {
            "success": result.success,
            "message": result.message,
            "error": result.error,
        },
    })


@approvals_api.route("/api/approvals/<action_id>/reject", methods=["GET", "POST"])
def reject(action_id: str):
    if request.method == "GET":
        if approval_store.get(action_id) is None:
            return jsonify({"error": "Approval request not found"}), 404
        safe_id = escape(action_id)
        response = (
            "<!doctype html><title>Confirm rejection</title>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<style>body{font:16px system-ui;max-width:620px;margin:48px auto;"
            "padding:0 20px;color:#211b2b}button{padding:10px 16px;"
            "cursor:pointer}h1{font-size:24px}</style>"
            f"<h1>Confirm rejection</h1><p>Reject action "
            f"<strong>{safe_id}</strong>?</p>"
            f"<form method='post' action='/api/approvals/{safe_id}/reject'>"
            "<input type='hidden' name='approved_by' value='email-review'>"
            "<button type='submit'>Reject action</button></form>"
        )
        return response, 200, {
            "Content-Type": "text/html; charset=utf-8",
            "Set-Cookie": f"approval_action={_approval_cookie(action_id)}; HttpOnly; SameSite=Lax; Max-Age=900",
        }

    if not _check_action_access(action_id):
        return jsonify({"error": "Unauthorized"}), 401

    decided_by = request.headers.get("X-Approved-By", "unknown")

    decision = approval_store.decide(
        action_id,
        approve=False,
        decided_by=decided_by,
    )

    if decision is None:
        return jsonify({
            "error": "Approval request not found or already decided"
        }), 404

    return jsonify({
        "approval": decision.to_dict()
    })
