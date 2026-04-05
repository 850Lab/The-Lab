"""
Reminder delivery: channel routing, Resend email, optional SMS stub, explicit stub fallback.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.workflow.workflow_db_config import is_production_like

_log = logging.getLogger(__name__)


@dataclass
class ReminderDeliveryResult:
    success: bool
    delivery_channel: str
    provider_response_summary: str
    error_safe: Optional[str] = None


def _allow_stub_fallback() -> bool:
    """
    Never treat a failed email send as “success” via stub in production-like deployments.
    ``WORKFLOW_REMINDER_FALLBACK_STUB=1`` is dev/test only.
    """
    if is_production_like():
        return False
    return (os.environ.get("WORKFLOW_REMINDER_FALLBACK_STUB") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def send_email_reminder(
    *,
    to_email: str,
    display_name: Optional[str],
    reminder_type: str,
    reason_plain: str,
) -> ReminderDeliveryResult:
    try:
        from resend_client import send_workflow_reminder_email

        summary = send_workflow_reminder_email(
            to_email,
            reminder_type=reminder_type,
            reason_plain=reason_plain,
            display_name=display_name,
        )
        mid = str(summary.get("message_id") or "")[:200]
        return ReminderDeliveryResult(
            success=True,
            delivery_channel="email",
            provider_response_summary=f"resend message_id={mid}"[:500],
        )
    except Exception as ex:
        msg = str(ex)[:300]
        return ReminderDeliveryResult(
            success=False,
            delivery_channel="email",
            provider_response_summary="resend_error",
            error_safe=msg,
        )


def send_sms_reminder(
    *,
    reminder_type: str,
) -> ReminderDeliveryResult:
    _ = reminder_type
    return ReminderDeliveryResult(
        success=False,
        delivery_channel="sms",
        provider_response_summary="sms_provider_not_configured",
        error_safe="sms_not_configured",
    )


def send_reminder(reminder_row: Dict[str, Any]) -> ReminderDeliveryResult:
    """
    Dispatch by preferred channel on payload_summary; default email.
    On email provider failure, optional stub when WORKFLOW_REMINDER_FALLBACK_STUB=1.
    """
    payload = reminder_row.get("payload_summary") or {}
    if not isinstance(payload, dict):
        payload = {}
    channel = (payload.get("preferred_channel") or "email").strip().lower()

    if channel == "sms":
        return send_sms_reminder(reminder_type=str(reminder_row.get("reminder_type") or ""))

    uid = int(reminder_row["user_id"])
    import auth

    user = auth.get_user_by_id(uid)
    if not user or not (user.get("email") or "").strip():
        return ReminderDeliveryResult(
            success=False,
            delivery_channel="email",
            provider_response_summary="no_recipient_email",
            error_safe="user_email_missing",
        )

    r = send_email_reminder(
        to_email=str(user["email"]).strip(),
        display_name=user.get("display_name"),
        reminder_type=str(reminder_row.get("reminder_type") or "reminder"),
        reason_plain=str(reminder_row.get("reason") or ""),
    )
    if r.success:
        return r

    if _allow_stub_fallback():
        _log.warning(
            "WORKFLOW_REMINDER_FALLBACK_STUB: marking reminder email as stub after Resend failure "
            "(non-production only): %s",
            (r.error_safe or "")[:200],
        )
        return ReminderDeliveryResult(
            success=True,
            delivery_channel="stub",
            provider_response_summary="fallback_stub_after_email_failure",
            error_safe=r.error_safe,
        )
    if is_production_like():
        _log.error(
            "Reminder email delivery failed (no stub in production): %s",
            (r.error_safe or "")[:300],
        )
    return r
