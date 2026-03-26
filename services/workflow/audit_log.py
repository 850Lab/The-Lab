"""
Lightweight structured audit for workflow progression (log aggregation friendly).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_log = logging.getLogger("workflow.audit")


def log_workflow_event(
    event: str,
    *,
    workflow_id: str,
    step_id: Optional[str] = None,
    source: str = "unknown",
    user_id: Optional[int] = None,
    error_code: Optional[str] = None,
    message_safe: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Structured audit line for aggregators. ``event`` is the primary type; ``eventType``
    mirrors it for consumers that expect that key.

    Common events: step_started, step_completed, step_failed, async_state_updated.
    """
    canonical = {
        "step_start": "step_started",
        "service_complete": "step_completed",
        "service_fail": "step_failed",
        "async_state": "async_state_updated",
        "reminder_created": "reminder_created",
        "reminder_queued": "reminder_queued",
        "reminder_sent": "reminder_sent",
        "reminder_failed": "reminder_failed",
        "reminder_skipped": "reminder_skipped",
        "reminder_delivery_attempted": "reminder_delivery_attempted",
        "reminder_delivery_success": "reminder_delivery_success",
        "reminder_delivery_failed": "reminder_delivery_failed",
        "override_applied": "override_applied",
        "recovery_action_triggered": "recovery_action_triggered",
        "recovery_execution_triggered": "recovery_execution_triggered",
        "service_reopen_failed": "service_reopen_failed",
        "mail_recovery_retry_marked": "mail_recovery_retry_marked",
    }.get(event, event)
    now_iso = datetime.now(timezone.utc).isoformat()
    payload: Dict[str, Any] = {
        "ts": now_iso,
        "timestamp": now_iso,
        "event": event,
        "eventType": canonical,
        "workflow_id": str(workflow_id),
        "step_id": step_id,
        "source": source[:64],
        "user_id": user_id,
    }
    if error_code:
        payload["error_code"] = str(error_code)[:64]
    if message_safe:
        payload["message_safe"] = str(message_safe)[:500]
    if extra:
        payload["extra"] = extra
    _log.info("workflow_audit %s", json.dumps(payload, default=str))
