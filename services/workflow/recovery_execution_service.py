"""
Admin-only recovery execution (WorkflowEngine-backed). Requires caller-supplied user_id
matching workflow owner.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.workflow.audit_log import log_workflow_event
from services.workflow.engine import WorkflowEngine, compute_authoritative_step
from services.workflow.repository import fetch_session
from services.workflow import reminder_repository as rr


def _session_for_user(workflow_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    session = fetch_session(workflow_id)
    if not session or int(session["user_id"]) != int(user_id):
        return None
    return session


def execute_retry_step(
    *,
    workflow_id: str,
    user_id: int,
    step_id: str,
    actor_source: str,
    reason_safe: str,
) -> Dict[str, Any]:
    if not _session_for_user(workflow_id, user_id):
        return {"ok": False, "error": {"code": "NOT_FOUND_OR_OWNER_MISMATCH"}}
    eng = WorkflowEngine()
    core = eng.service_reopen_failed_step(
        workflow_id,
        step_id,
        audit_source=actor_source[:64] or "recovery_execution",
        audit_user_id=user_id,
    )
    if not core.get("ok"):
        return core
    rr.insert_admin_audit(
        workflow_id=workflow_id,
        user_id=user_id,
        actor_source=actor_source[:128],
        action_type="recovery_execute_retry_step",
        reason_safe=reason_safe,
        payload_before={"stepId": step_id, "priorStatus": "failed"},
        payload_after={"stepId": step_id, "status": "available"},
    )
    log_workflow_event(
        "recovery_execution_triggered",
        workflow_id=workflow_id,
        step_id=step_id,
        source=actor_source[:64],
        user_id=user_id,
        message_safe=(reason_safe or "")[:500],
        extra={"action": "retry_step", "actor_source": actor_source[:128]},
    )
    return {"ok": True, "workflowId": workflow_id, "stepId": step_id, "action": "retry_step"}


def execute_resume_current_step(
    *,
    workflow_id: str,
    user_id: int,
    actor_source: str,
    reason_safe: str,
) -> Dict[str, Any]:
    if not _session_for_user(workflow_id, user_id):
        return {"ok": False, "error": {"code": "NOT_FOUND_OR_OWNER_MISMATCH"}}
    eng = WorkflowEngine()
    _, _, smap = eng.get_state_bundle(workflow_id)
    head, _ = compute_authoritative_step(smap)
    if not head:
        return {"ok": False, "error": {"code": "NO_ACTIVE_STEP"}}
    row = smap.get(head)
    if not row or row.get("status") != "available":
        return {"ok": False, "error": {"code": "STEP_NOT_AVAILABLE_TO_START"}}
    env = eng.start_step(
        workflow_id,
        head,
        audit_source=actor_source[:64] or "recovery_execution",
        audit_user_id=user_id,
    )
    if env.get("actionResult") != "ok":
        return {
            "ok": False,
            "error": {"code": "START_STEP_REJECTED"},
            "engine": env,
        }
    rr.insert_admin_audit(
        workflow_id=workflow_id,
        user_id=user_id,
        actor_source=actor_source[:128],
        action_type="recovery_execute_resume_current_step",
        reason_safe=reason_safe,
        payload_before={"headStepId": head, "priorStatus": "available"},
        payload_after={"headStepId": head, "status": "in_progress"},
    )
    log_workflow_event(
        "recovery_execution_triggered",
        workflow_id=workflow_id,
        step_id=head,
        source=actor_source[:64],
        user_id=user_id,
        message_safe=(reason_safe or "")[:500],
        extra={"action": "resume_current_step", "actor_source": actor_source[:128]},
    )
    return {"ok": True, "workflowId": workflow_id, "stepId": head, "action": "resume_current_step"}


def execute_re_run_mail_attempt(
    *,
    workflow_id: str,
    user_id: int,
    actor_source: str,
    reason_safe: str,
) -> Dict[str, Any]:
    if not _session_for_user(workflow_id, user_id):
        return {"ok": False, "error": {"code": "NOT_FOUND_OR_OWNER_MISMATCH"}}
    eng = WorkflowEngine()
    core = eng.service_mark_mail_recovery_retry(
        workflow_id,
        audit_source=actor_source[:64] or "recovery_execution",
        audit_user_id=user_id,
    )
    if not core.get("ok"):
        return core
    rr.insert_admin_audit(
        workflow_id=workflow_id,
        user_id=user_id,
        actor_source=actor_source[:128],
        action_type="recovery_execute_re_run_mail_attempt",
        reason_safe=reason_safe,
        payload_before={},
        payload_after={
            "pendingBureauKeysForRetry": core.get("pendingBureauKeysForRetry"),
            "bureauSlotsRemaining": core.get("bureauSlotsRemaining"),
            "failedSendCount": core.get("failedSendCount"),
        },
    )
    log_workflow_event(
        "recovery_execution_triggered",
        workflow_id=workflow_id,
        step_id="mail",
        source=actor_source[:64],
        user_id=user_id,
        message_safe=(reason_safe or "")[:500],
        extra={"action": "re_run_mail_attempt", "actor_source": actor_source[:128]},
    )
    return {
        "ok": True,
        "workflowId": workflow_id,
        "action": "re_run_mail_attempt",
        "pendingBureauKeysForRetry": core.get("pendingBureauKeysForRetry"),
        "bureauSlotsRemaining": core.get("bureauSlotsRemaining"),
        "failedSendCount": core.get("failedSendCount"),
    }
