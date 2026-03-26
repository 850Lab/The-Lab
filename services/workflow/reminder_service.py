"""
Reminder candidate creation and internal execution contract (no full messaging platform).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.workflow.audit_log import log_workflow_event
from services.workflow.home_summary_service import build_home_summary
from services.workflow import reminder_delivery
from services.workflow import reminder_repository as rr


def _reason_for_type(rtype: str, summary: Dict[str, Any]) -> str:
    reasons = {
        "nudge_upload": "Upload step is available; user action needed.",
        "nudge_retry_failed": "A retryable step failed; user or ops follow-up.",
        "nudge_bureau_clock": "Bureau response window; external clock / upload response.",
        "nudge_resume_payment": "Payment step is open; checkout not completed.",
        "nudge_response_upload": "Post-track phase; upload bureau/furnisher response.",
    }
    base = reasons.get(rtype, "Lifecycle reminder.")
    sr = summary.get("stalledReasons") or []
    if sr:
        return f"{base} Signals: {', '.join(sr[:5])}."
    return base


def create_reminder_candidates_for_workflow(workflow_id: str) -> Dict[str, Any]:
    """
    From home-summary eligibility flags, insert deduped reminder rows (status=eligible).
    """
    summary = build_home_summary(workflow_id)
    if not summary.get("ok"):
        return {"ok": False, "error": summary.get("error"), "created": []}

    flags = summary.get("reminderEligibility") or {}
    uid = int(summary["userId"])
    pairs = [
        ("nudge_upload", flags.get("nudge_upload")),
        ("nudge_retry_failed", flags.get("nudge_retry_failed")),
        ("nudge_bureau_clock", flags.get("nudge_bureau_clock")),
        ("nudge_resume_payment", flags.get("nudge_resume_payment")),
        ("nudge_response_upload", flags.get("nudge_response_upload")),
    ]
    created: List[Dict[str, Any]] = []
    for rtype, on in pairs:
        if not on:
            continue
        if rr.has_active_or_recent_reminder(workflow_id, rtype):
            continue
        payload = {
            "source": "reminder_service",
            "waitingOn": summary.get("waitingOn"),
            "stalled": summary.get("stalled"),
            "stalledReasons": summary.get("stalledReasons") or [],
            "currentStepId": summary.get("currentStepId"),
        }
        rid = rr.insert_reminder(
            workflow_id=workflow_id,
            user_id=uid,
            reminder_type=rtype,
            reason=_reason_for_type(rtype, summary),
            payload_summary=payload,
        )
        created.append({"reminderId": rid, "reminderType": rtype})
        log_workflow_event(
            "reminder_created",
            workflow_id=workflow_id,
            step_id=None,
            source="reminder_service",
            user_id=uid,
            extra={"reminderId": rid, "reminderType": rtype},
        )
    return {"ok": True, "created": created}


def list_eligible_for_scan(limit: int = 100) -> List[Dict[str, Any]]:
    return rr.list_eligible_reminders(limit=limit)


def queue_reminder(reminder_id: str) -> bool:
    row = rr.fetch_reminder(reminder_id)
    if not row or row.get("status") != "eligible":
        return False
    rr.update_reminder_status(reminder_id, status="queued")
    log_workflow_event(
        "reminder_queued",
        workflow_id=str(row["workflow_id"]),
        source="reminder_service",
        user_id=int(row["user_id"]),
        extra={"reminderId": reminder_id, "reminderType": row.get("reminder_type")},
    )
    return True


def mark_reminder_sent_stub(reminder_id: str) -> bool:
    """Explicit stub (no external I/O); use for tests or manual ops only."""
    row = rr.fetch_reminder(reminder_id)
    if not row or row.get("status") not in ("eligible", "queued"):
        return False
    now = datetime.now(timezone.utc)
    rr.update_reminder_status(
        reminder_id,
        status="sent",
        sent_at=now,
        delivery_channel="stub",
        payload_patch={
            "stubbedAt": now.isoformat(),
            "deliveryResult": {
                "success": True,
                "delivery_channel": "stub",
                "provider_response_summary": "explicit_stub_no_provider_io",
            },
        },
    )
    log_workflow_event(
        "reminder_delivery_success",
        workflow_id=str(row["workflow_id"]),
        source="reminder_stub_provider",
        user_id=int(row["user_id"]),
        extra={"reminderId": reminder_id, "reminderType": row.get("reminder_type"), "channel": "stub"},
    )
    return True


def deliver_reminder(reminder_id: str) -> Dict[str, Any]:
    """Send via reminder_delivery; queued → sent or failed (no silent success)."""
    row = rr.fetch_reminder(reminder_id)
    if not row or row.get("status") != "queued":
        return {"ok": False, "error": "not_queued", "reminderId": reminder_id}
    wid = str(row["workflow_id"])
    uid = int(row["user_id"])
    log_workflow_event(
        "reminder_delivery_attempted",
        workflow_id=wid,
        source="reminder_delivery",
        user_id=uid,
        extra={"reminderId": reminder_id, "reminderType": row.get("reminder_type")},
    )
    result = reminder_delivery.send_reminder(row)
    now = datetime.now(timezone.utc)
    dr = {
        "success": result.success,
        "delivery_channel": result.delivery_channel,
        "provider_response_summary": result.provider_response_summary[:500],
        "attemptedAt": now.isoformat(),
    }
    if result.error_safe:
        dr["error_safe"] = result.error_safe[:500]
    if result.success:
        rr.update_reminder_status(
            reminder_id,
            status="sent",
            sent_at=now,
            delivery_channel=result.delivery_channel[:32],
            payload_patch={"deliveryResult": dr},
        )
        log_workflow_event(
            "reminder_delivery_success",
            workflow_id=wid,
            source="reminder_delivery",
            user_id=uid,
            extra={"reminderId": reminder_id, **dr},
        )
        log_workflow_event(
            "reminder_sent",
            workflow_id=wid,
            source="reminder_delivery",
            user_id=uid,
            extra={"reminderId": reminder_id, "channel": result.delivery_channel},
        )
        return {"ok": True, "reminderId": reminder_id, "deliveryResult": dr}
    rr.update_reminder_status(
        reminder_id,
        status="failed",
        payload_patch={"deliveryResult": dr},
    )
    log_workflow_event(
        "reminder_delivery_failed",
        workflow_id=wid,
        source="reminder_delivery",
        user_id=uid,
        message_safe=result.error_safe,
        extra={"reminderId": reminder_id, **dr},
    )
    log_workflow_event(
        "reminder_failed",
        workflow_id=wid,
        source="reminder_delivery",
        user_id=uid,
        message_safe=result.error_safe,
        extra={"reminderId": reminder_id},
    )
    return {"ok": False, "reminderId": reminder_id, "deliveryResult": dr}


def mark_reminder_failed(reminder_id: str, message_safe: str) -> bool:
    row = rr.fetch_reminder(reminder_id)
    if not row:
        return False
    rr.update_reminder_status(
        reminder_id,
        status="failed",
        payload_patch={"failureMessageSafe": (message_safe or "")[:500]},
    )
    log_workflow_event(
        "reminder_failed",
        workflow_id=str(row["workflow_id"]),
        source="reminder_service",
        user_id=int(row["user_id"]),
        message_safe=message_safe,
        extra={"reminderId": reminder_id},
    )
    return True


def mark_reminder_skipped_internal(reminder_id: str, reason_safe: str, actor: str) -> bool:
    row = rr.fetch_reminder(reminder_id)
    if not row or row.get("status") in ("sent",):
        return False
    rr.update_reminder_status(
        reminder_id,
        status="skipped",
        payload_patch={"skippedBy": actor[:128], "skippedReason": (reason_safe or "")[:500]},
    )
    log_workflow_event(
        "reminder_skipped",
        workflow_id=str(row["workflow_id"]),
        source=actor[:64] or "admin",
        user_id=int(row["user_id"]),
        message_safe=reason_safe,
        extra={"reminderId": reminder_id},
    )
    return True


def process_delivery_batch(limit: int = 20) -> Dict[str, Any]:
    """Queue eligible reminders, deliver queued via email/SMS routing (or failed with audit)."""
    processed_ok: List[str] = []
    failures: List[str] = []
    attempts = 0

    def _try_deliver(rid: str) -> None:
        nonlocal attempts
        if attempts >= limit:
            return
        attempts += 1
        out = deliver_reminder(rid)
        if out.get("ok"):
            processed_ok.append(rid)
        else:
            failures.append(rid)

    for r in rr.list_queued_reminders(limit=limit):
        _try_deliver(r["reminder_id"])
        if attempts >= limit:
            break
    if attempts < limit:
        for r in list_eligible_for_scan(limit=max(1, limit - attempts)):
            if attempts >= limit:
                break
            rid = r["reminder_id"]
            if queue_reminder(rid):
                _try_deliver(rid)

    return {
        "ok": True,
        "processedReminderIds": processed_ok,
        "failedReminderIds": failures,
        "count": len(processed_ok),
    }


def process_next_stub_batch(limit: int = 20) -> Dict[str, Any]:
    """Backward-compatible name: uses real delivery (not implicit stub)."""
    return process_delivery_batch(limit=limit)
