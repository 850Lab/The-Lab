"""
Trusted operator overrides — internal-only callers. Preserves prior values in audit rows
and session adminOverrideHistory.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.workflow.audit_log import log_workflow_event
from services.workflow.engine import WorkflowEngine, compute_authoritative_step
from services.workflow.repository import fetch_session, update_session_fields
from services.workflow import reminder_repository as rr
from services.workflow import response_repository as resp_rr
from services.workflow import reminder_service as rem_svc


def _session_meta_dict(session: Dict[str, Any]) -> Dict[str, Any]:
    meta = session.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def _snapshot_response(row: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "response_classification",
        "classification_status",
        "classification_reasoning_safe",
        "classification_confidence",
        "recommended_next_action",
        "escalation_recommendation",
    )
    out: Dict[str, Any] = {}
    for k in keys:
        out[k] = row.get(k)
    return out


def override_response_classification(
    *,
    response_id: str,
    new_classification: str,
    reasoning_safe: str,
    actor_source: str,
    reason_safe: str,
) -> Dict[str, Any]:
    row = resp_rr.fetch_response_by_id(response_id)
    if not row:
        return {"ok": False, "error": {"code": "NOT_FOUND"}}
    before = _snapshot_response(row)
    merged_reason = (
        f"[admin override {actor_source[:48]}] {reasoning_safe or ''}"[:3900]
    )
    esc = row.get("escalation_recommendation") or {}
    if not isinstance(esc, dict):
        esc = {}
    resp_rr.update_response_classification(
        response_id,
        classification_status="classified",
        response_classification=new_classification[:64],
        classification_reasoning_safe=merged_reason,
        classification_confidence=row.get("classification_confidence"),
        recommended_next_action=row.get("recommended_next_action") or "manual_review_required",
        escalation_recommendation=esc,
    )
    after = {**before, "response_classification": new_classification[:64], "classification_reasoning_safe": merged_reason}
    wid = str(row["workflow_id"])
    rr.insert_admin_audit(
        workflow_id=wid,
        user_id=int(row["user_id"]),
        actor_source=actor_source,
        action_type="override_response_classification",
        reason_safe=reason_safe,
        payload_before=before,
        payload_after=after,
        response_id=response_id,
    )
    rr.merge_session_admin_override_metadata(
        wid,
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "action": "override_response_classification",
            "actor": actor_source[:128],
            "reason": (reason_safe or "")[:500],
            "responseId": response_id,
            "priorClassification": before.get("response_classification"),
        },
    )
    log_workflow_event(
        "override_applied",
        workflow_id=wid,
        source=actor_source[:64],
        user_id=int(row["user_id"]),
        extra={"action": "override_response_classification", "responseId": response_id},
    )
    return {"ok": True, "responseId": response_id, "workflowId": wid}


def override_escalation_recommendation(
    *,
    response_id: str,
    escalation_recommendation: Dict[str, Any],
    actor_source: str,
    reason_safe: str,
) -> Dict[str, Any]:
    row = resp_rr.fetch_response_by_id(response_id)
    if not row:
        return {"ok": False, "error": {"code": "NOT_FOUND"}}
    before = _snapshot_response(row)
    esc = dict(escalation_recommendation or {})
    esc.setdefault("overriddenBy", actor_source[:64])
    esc.setdefault("overriddenAt", datetime.now(timezone.utc).isoformat())
    resp_rr.update_response_classification(
        response_id,
        classification_status=row.get("classification_status") or "classified",
        response_classification=row.get("response_classification"),
        classification_reasoning_safe=row.get("classification_reasoning_safe") or "",
        classification_confidence=row.get("classification_confidence"),
        recommended_next_action=row.get("recommended_next_action") or "manual_review_required",
        escalation_recommendation=esc,
    )
    after = {**before, "escalation_recommendation": esc}
    wid = str(row["workflow_id"])
    rr.insert_admin_audit(
        workflow_id=wid,
        user_id=int(row["user_id"]),
        actor_source=actor_source,
        action_type="override_escalation_recommendation",
        reason_safe=reason_safe,
        payload_before=before,
        payload_after=after,
        response_id=response_id,
    )
    rr.merge_session_admin_override_metadata(
        wid,
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "action": "override_escalation_recommendation",
            "actor": actor_source[:128],
            "reason": (reason_safe or "")[:500],
            "responseId": response_id,
        },
    )
    log_workflow_event(
        "override_applied",
        workflow_id=wid,
        source=actor_source[:64],
        user_id=int(row["user_id"]),
        extra={"action": "override_escalation", "responseId": response_id},
    )
    return {"ok": True, "responseId": response_id, "workflowId": wid}


def mark_reminder_skipped(
    *,
    reminder_id: str,
    actor_source: str,
    reason_safe: str,
) -> Dict[str, Any]:
    ok = rem_svc.mark_reminder_skipped_internal(reminder_id, reason_safe, actor_source)
    if not ok:
        return {"ok": False, "error": {"code": "SKIP_FAILED"}}
    row = rr.fetch_reminder(reminder_id)
    rr.insert_admin_audit(
        workflow_id=str(row["workflow_id"]) if row else None,
        user_id=int(row["user_id"]) if row else None,
        actor_source=actor_source,
        action_type="mark_reminder_skipped",
        reason_safe=reason_safe,
        payload_before={"status": row.get("status") if row else None},
        payload_after={"status": "skipped"},
        reminder_id=reminder_id,
    )
    log_workflow_event(
        "override_applied",
        workflow_id=str(row["workflow_id"]) if row else "",
        source=actor_source[:64],
        user_id=int(row["user_id"]) if row else None,
        extra={"action": "mark_reminder_skipped", "reminderId": reminder_id},
    )
    return {"ok": True, "reminderId": reminder_id}


def clear_stalled_flag(
    *,
    workflow_id: str,
    actor_source: str,
    reason_safe: str,
) -> Dict[str, Any]:
    session = fetch_session(workflow_id)
    if not session:
        return {"ok": False, "error": {"code": "NOT_FOUND"}}
    uid = int(session["user_id"])
    meta = _session_meta_dict(session)
    life = dict(meta.get("lifecycle") or {})
    life["stalledOverrideDismissedAt"] = datetime.now(timezone.utc).isoformat()
    life["stalledOverrideReason"] = (reason_safe or "")[:500]
    life["stalledOverrideActor"] = actor_source[:128]
    patch = {"lifecycle": life}
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db() as (conn, cur):
        update_session_fields(conn, cur, workflow_id, metadata_patch=patch)
        conn.commit()
    rr.insert_admin_audit(
        workflow_id=workflow_id,
        user_id=uid,
        actor_source=actor_source,
        action_type="clear_stalled_flag",
        reason_safe=reason_safe,
        payload_before={},
        payload_after=patch,
    )
    rr.merge_session_admin_override_metadata(
        workflow_id,
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "action": "clear_stalled_flag",
            "actor": actor_source[:128],
            "reason": (reason_safe or "")[:500],
        },
    )
    log_workflow_event(
        "override_applied",
        workflow_id=workflow_id,
        source=actor_source[:64],
        user_id=uid,
        extra={"action": "clear_stalled_flag"},
    )
    return {"ok": True, "workflowId": workflow_id}


def reopen_failed_step(
    *,
    workflow_id: str,
    step_id: str,
    actor_source: str,
    reason_safe: str,
) -> Dict[str, Any]:
    session = fetch_session(workflow_id)
    if not session:
        return {"ok": False, "error": {"code": "NOT_FOUND"}}
    eng = WorkflowEngine()
    uid = int(session["user_id"])
    core = eng.service_reopen_failed_step(
        workflow_id,
        step_id,
        audit_source=actor_source[:64] or "admin_reopen",
        audit_user_id=uid,
    )
    if not core.get("ok"):
        return core
    before = {"status": "failed", "stepId": step_id}
    rr.insert_admin_audit(
        workflow_id=workflow_id,
        user_id=uid,
        actor_source=actor_source,
        action_type="reopen_failed_step",
        reason_safe=reason_safe,
        payload_before=before,
        payload_after={"status": "available", "stepId": step_id},
    )
    rr.merge_session_admin_override_metadata(
        workflow_id,
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "action": "reopen_failed_step",
            "actor": actor_source[:128],
            "reason": (reason_safe or "")[:500],
            "stepId": step_id,
        },
    )
    log_workflow_event(
        "recovery_action_triggered",
        workflow_id=workflow_id,
        step_id=step_id,
        source=actor_source[:64],
        user_id=uid,
        extra={"action": "reopen_failed_step"},
    )
    return {"ok": True, "workflowId": workflow_id, "stepId": step_id}


def apply_payment_waived(
    *,
    workflow_id: str,
    user_id: int,
    actor_source: str,
    reason_safe: str,
) -> Dict[str, Any]:
    from services.workflow import hooks as wf_hooks

    ok = wf_hooks.notify_payment_waived(
        user_id,
        workflow_id=workflow_id,
        actor_source=actor_source,
        reason_safe=reason_safe,
    )
    if not ok:
        return {"ok": False, "error": {"code": "PAYMENT_WAIVE_NOT_APPLICABLE"}}
    rr.insert_admin_audit(
        workflow_id=workflow_id,
        user_id=user_id,
        actor_source=actor_source,
        action_type="payment_waived",
        reason_safe=reason_safe,
        payload_before={"paymentExpectation": "required"},
        payload_after={"paymentExpectation": "waived", "source": "admin"},
    )
    rr.merge_session_admin_override_metadata(
        workflow_id,
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "action": "payment_waived",
            "actor": actor_source[:128],
            "reason": (reason_safe or "")[:500],
        },
    )
    log_workflow_event(
        "override_applied",
        workflow_id=workflow_id,
        source=actor_source[:64],
        user_id=user_id,
        extra={"action": "payment_waived"},
    )
    return {"ok": True, "workflowId": workflow_id}


def trigger_recovery_action_record(
    *,
    workflow_id: str,
    action_type: str,
    actor_source: str,
    detail_safe: str,
) -> Dict[str, Any]:
    """Audit-only record that an operator acknowledged/triggered a recovery path (no duplicate engine effects)."""
    session = fetch_session(workflow_id)
    if not session:
        return {"ok": False, "error": {"code": "NOT_FOUND"}}
    uid = int(session["user_id"])
    rr.insert_admin_audit(
        workflow_id=workflow_id,
        user_id=uid,
        actor_source=actor_source,
        action_type="recovery_action_triggered",
        reason_safe=detail_safe,
        payload_before={},
        payload_after={"actionType": action_type},
    )
    log_workflow_event(
        "recovery_action_triggered",
        workflow_id=workflow_id,
        source=actor_source[:64],
        user_id=uid,
        extra={"recordedAction": action_type},
    )
    return {"ok": True, "workflowId": workflow_id, "recordedAction": action_type}
