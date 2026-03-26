"""
Authoritative home / resume summary for a workflow (backend-computed).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.workflow import registry as reg
from services.workflow.engine import (
    WorkflowEngine,
    compute_authoritative_step,
)
from services.workflow import lifecycle_rules as lr
from services.workflow import reminder_repository as rem_repo
from services.workflow import response_repository as rr
from services.workflow.recovery_service import compute_recovery_actions

STEP_ROUTE_HINTS: Dict[str, str] = {
    "upload": "/upload",
    "parse_analyze": "/analyze",
    "review_claims": "/prepare",
    "select_disputes": "/strategy",
    "payment": "/payment",
    "letter_generation": "/letters",
    "proof_attachment": "/proof",
    "mail": "/send",
    "track": "/tracking",
}


def _next_best_action(
    head: Optional[str],
    head_status: Optional[str],
    phase: str,
    overall: str,
) -> str:
    if overall == "completed" or phase == "done":
        return "Workflow steps are complete; monitor bureau responses and credit reports."
    if overall == "failed":
        return "A step needs attention — retry or contact support from the failed step."
    if not head:
        return "Continue your dispute workflow."
    name = reg.STEP_REGISTRY.get(head, reg.STEP_REGISTRY.get("upload"))
    title = name.name if name else head
    if head_status == "available":
        return f"Start or complete: {title}."
    if head_status == "in_progress":
        return f"Finish: {title} (processing may be in progress)."
    if head_status == "failed":
        return f"Retry: {title}."
    return f"Continue: {title}."


def _escalation_available(
    track_done: bool,
    overall: str,
    latest: Optional[Dict[str, Any]],
) -> bool:
    if overall == "failed" or not track_done:
        return False
    if not latest:
        return True
    cls = latest.get("response_classification") or ""
    if cls in ("favorable_resolved",):
        return False
    return True


def build_home_summary(workflow_id: str) -> Dict[str, Any]:
    eng = WorkflowEngine()
    session, steps, smap = eng.get_state_bundle(workflow_id)
    if not session:
        return {
            "ok": False,
            "error": {"code": "NOT_FOUND", "messageSafe": "Workflow not found."},
        }

    head, phase = compute_authoritative_step(smap)
    head_row = smap.get(head) if head else None
    head_status = head_row["status"] if head_row else None
    overall = session.get("overall_status") or "active"

    waiting_on = lr.compute_waiting_attribution(head, head_status, smap)

    latest = rr.fetch_latest_response_for_workflow(workflow_id)
    latest_ts = latest.get("received_at") if latest else None
    if isinstance(latest_ts, datetime):
        latest_dt = latest_ts if latest_ts.tzinfo else latest_ts.replace(tzinfo=timezone.utc)
    else:
        latest_dt = None

    stalled, stalled_reasons = lr.compute_stalled(
        session=session,
        steps_map=smap,
        latest_response_received_at=latest_dt,
    )

    failed_id, re_entry = lr.failed_step_reentry_eligible(smap, overall)
    failed_payload = None
    if failed_id:
        fr = smap.get(failed_id) or {}
        failed_payload = {
            "stepId": failed_id,
            "messageSafe": fr.get("last_error_message_safe") or "",
            "reEntryEligible": re_entry,
        }

    reminder_flags = lr.compute_reminder_eligibility(
        waiting_on=waiting_on,
        stalled=stalled,
        failed_step_id=failed_id,
        head_status=head_status,
        head_step_id=head,
    )

    track_done = bool(smap.get("track") and smap["track"].get("status") == "completed")
    esc_on = _escalation_available(track_done, overall, latest)

    meta = session.get("metadata") or {}
    if isinstance(meta, str):
        try:
            import json

            meta = json.loads(meta)
        except Exception:
            meta = {}

    response_block = None
    if latest:
        response_block = {
            "latestResponseId": latest.get("response_id"),
            "classificationStatus": latest.get("classification_status"),
            "responseClassification": latest.get("response_classification"),
            "receivedAt": latest.get("received_at").isoformat()
            if isinstance(latest.get("received_at"), datetime)
            else latest.get("received_at"),
            "sourceType": latest.get("source_type"),
            "responseChannel": latest.get("response_channel"),
        }

    step_name = reg.STEP_REGISTRY[head].name if head and head in reg.STEP_REGISTRY else None

    recovery = compute_recovery_actions(workflow_id)
    active_reminders = rem_repo.list_reminders_for_workflow(
        workflow_id,
        statuses=["eligible", "queued"],
        limit=15,
    )

    return {
        "ok": True,
        "workflowId": str(session["workflow_id"]),
        "userId": session["user_id"],
        "overallStatus": overall,
        "currentStepId": head,
        "currentStepName": step_name,
        "linearPhase": "done" if phase == "done" else "active",
        "nextBestAction": _next_best_action(head, head_status, phase, overall),
        "waitingOn": waiting_on,
        "failedStep": failed_payload,
        "escalationAvailable": esc_on,
        "responseStatus": response_block,
        "safeRouteHint": STEP_ROUTE_HINTS.get(head or "", "/"),
        "reminderEligibility": reminder_flags,
        "stalled": stalled,
        "stalledReasons": stalled_reasons,
        "definitionVersion": session.get("definition_version"),
        "engineVersion": session.get("engine_version"),
        "lifecycleMetadata": (meta or {}).get("lifecycle"),
        "recentResponses": rr.list_responses_for_workflow(workflow_id, limit=5),
        "activeReminders": active_reminders,
        "recoveryActions": recovery.get("recoveryActions") or [],
        "adminOverridePresent": bool((meta or {}).get("adminOverridePresent")),
    }
