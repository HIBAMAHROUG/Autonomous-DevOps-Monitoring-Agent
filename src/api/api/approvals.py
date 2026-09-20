"""
API des approbations humaines (US 4.2).

Sécurisée par la même clé API que le reste du service (header X-API-Key),
cohérent avec api/routes.py.
"""
from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from remediation.approvals import approval_store
from remediation.models import Action

approvals_api = Blueprint("approvals_api", __name__)


def _check_api_key() -> bool:
    api_key = request.headers.get("X-API-Key")
    return bool(api_key) and api_key == os.getenv("API_KEY")


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


@approvals_api.route("/api/approvals/<action_id>/approve", methods=["POST"])
def approve(action_id: str):
    if not _check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    decided_by = request.headers.get("X-Approved-By", "unknown")

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
        executor=decision.executor,
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


@approvals_api.route("/api/approvals/<action_id>/reject", methods=["POST"])
def reject(action_id: str):
    if not _check_api_key():
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
