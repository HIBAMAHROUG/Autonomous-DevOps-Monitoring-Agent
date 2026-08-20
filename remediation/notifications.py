"""
Notifications Slack/Email pour les actions critiques nécessitant une
approbation humaine (US 4.2).
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any

import requests

logger = logging.getLogger("remediation.notifications")

API_BASE_URL = os.getenv("AGENT_API_BASE_URL", "http://localhost:5000")


def _approve_reject_urls(action_id: str) -> tuple[str, str]:
    return (
        f"{API_BASE_URL}/api/approvals/{action_id}/approve",
        f"{API_BASE_URL}/api/approvals/{action_id}/reject",
    )


def _send_slack(
    action_id: str,
    executor: str,
    severity: str,
    reason: str,
) -> bool:
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not webhook_url:
        return False

    approve_url, reject_url = _approve_reject_urls(action_id)

    payload = {
        "text": (
            f":rotating_light: *Approbation requise* — action `{action_id}` "
            f"({executor}, sévérité {severity})\n"
            f"Raison : {reason}\n"
            f"✅ Approuver : `curl -X POST {approve_url}`\n"
            f"❌ Rejeter : `curl -X POST {reject_url}`\n"
            f"Ou via le dashboard : {API_BASE_URL}/dashboard"
        )
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=5,
        )
        response.raise_for_status()
        return True

    except requests.RequestException:
        logger.exception(
            "Échec de l'envoi de la notification Slack pour %s",
            action_id,
        )
        return False


def _send_email(
    action_id: str,
    executor: str,
    severity: str,
    reason: str,
) -> bool:
    smtp_host = os.getenv("SMTP_HOST")
    to_addr = os.getenv("APPROVAL_EMAIL_TO")

    if not smtp_host or not to_addr:
        return False

    approve_url, reject_url = _approve_reject_urls(action_id)

    from_addr = os.getenv(
        "APPROVAL_EMAIL_FROM",
        "devops-agent@localhost",
    )

    message = EmailMessage()

    message["Subject"] = (
        f"[Agent DevOps] Approbation requise: "
        f"{action_id} ({severity})"
    )

    message["From"] = from_addr
    message["To"] = to_addr

    message.set_content(
        "Une action critique nécessite une approbation humaine.\n\n"
        f"Action      : {action_id}\n"
        f"Exécuteur   : {executor}\n"
        f"Sévérité    : {severity}\n"
        f"Raison      : {reason}\n\n"
        f"Approuver : {approve_url}\n"
        f"Rejeter   : {reject_url}\n"
        f"Dashboard : {API_BASE_URL}/dashboard\n"
    )

    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))

        with smtplib.SMTP(
            smtp_host,
            smtp_port,
            timeout=10,
        ) as smtp:

            if os.getenv(
                "SMTP_USE_TLS",
                "true",
            ).lower() == "true":
                smtp.starttls()

            smtp_user = os.getenv("SMTP_USER")
            smtp_password = os.getenv("SMTP_PASSWORD")

            if smtp_user and smtp_password:
                smtp.login(
                    smtp_user,
                    smtp_password,
                )

            smtp.send_message(message)

        return True

    except Exception:
        logger.exception(
            "Échec de l'envoi de l'email d'approbation pour %s",
            action_id,
        )
        return False


def notify_approval_required(
    action_id: str,
    executor: str,
    severity: str,
    reason: str,
) -> dict[str, Any]:
    """
    Envoie une notification sur tous les canaux configurés.

    Retourne :
        {
            "slack": bool,
            "email": bool
        }
    """

    results = {
        "slack": _send_slack(
            action_id,
            executor,
            severity,
            reason,
        ),
        "email": _send_email(
            action_id,
            executor,
            severity,
            reason,
        ),
    }

    if not any(results.values()):
        logger.warning(
            "Aucun canal de notification configuré "
            "(SLACK_WEBHOOK_URL / SMTP_HOST+APPROVAL_EMAIL_TO) "
            "— approbation requise pour %s mais personne n'a "
            "été notifié en dehors du dashboard.",
            action_id,
        )

    return results
