"""
Workflow engine: **authoritative** progression on ``workflow_sessions`` / ``workflow_steps``.

Trusted transitions use ``service_complete_step`` / internal ``mutate_step`` paths.
Do not mark steps completed from org projection tables or ad-hoc SQL — delegate here
(or ``advance_org_program_steps`` / ``services.workflow.hooks``), then mirror into
projections if needed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.workflow import registry as reg
from services.workflow.audit_log import log_workflow_event
from services.workflow.repository import (
    create_workflow_with_steps,
    fetch_session,
    fetch_steps,
    update_step_fields,
    utcnow,
)
from services.workflow import lifecycle_rules as lr_mod
from services.workflow import workflow_instance_service as wf_inst
from services.workflow.responses import safe_error, workflow_envelope

_log = logging.getLogger(__name__)


def _orion_after_commit(workflow_id: str) -> None:
    """Non-blocking O.R.I.O.N. refresh after durable workflow writes."""
    try:
        from services.guidance.orion_scheduler import schedule_guidance_evaluation

        schedule_guidance_evaluation(workflow_id)
    except Exception:
        pass


def _linear_order_from_session(session: Optional[Dict[str, Any]]) -> Tuple[str, ...]:
    if not session:
        return reg.LINEAR_STEP_ORDER
    return reg.linear_order_for(str(session.get("workflow_type") or reg.WORKFLOW_TYPE_DEFAULT))


def _steps_by_id(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {r["step_id"]: r for r in rows}


def _serialize_session(row: Dict[str, Any]) -> Dict[str, Any]:
    def ts(v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)

    return {
        "workflowId": str(row["workflow_id"]),
        "userId": row["user_id"],
        "workflowType": row["workflow_type"],
        "currentStep": row["current_step"],
        "overallStatus": row["overall_status"],
        "startedAt": ts(row.get("started_at")),
        "updatedAt": ts(row.get("updated_at")),
        "completedAt": ts(row.get("completed_at")),
        "lastErrorCode": row.get("last_error_code"),
        "lastErrorMessageSafe": row.get("last_error_message_safe"),
        "metadata": row.get("metadata") or {},
        "definitionVersion": row.get("definition_version"),
        "engineVersion": row.get("engine_version"),
    }


def _serialize_steps(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        out.append(
            {
                "workflowStepId": str(r["workflow_step_id"]),
                "stepId": r["step_id"],
                "status": r["status"],
                "attemptCount": r["attempt_count"],
                "startedAt": _ts(r.get("started_at")),
                "completedAt": _ts(r.get("completed_at")),
                "failedAt": _ts(r.get("failed_at")),
                "lastErrorCode": r.get("last_error_code"),
                "lastErrorMessageSafe": r.get("last_error_message_safe"),
                "completionPayloadSummary": r.get("completion_payload_summary"),
                "asyncTaskState": r.get("async_task_state"),
            }
        )
    return out


def _ts(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def repair_linear_availability_tx(
    conn,
    cur,
    workflow_id: str,
    smap: Dict[str, Dict[str, Any]],
    linear_order: Tuple[str, ...],
) -> bool:
    """Single-transaction repair: unlock `not_started` steps after a completed prefix."""
    changed = False
    prev_done = True
    for sid in linear_order:
        row = smap.get(sid)
        if not row:
            continue
        st = row["status"]
        if st == "completed":
            prev_done = True
            continue
        if prev_done and st == "not_started":
            wf_inst.mutate_step(
                conn,
                cur,
                workflow_id,
                sid,
                prior_step_status="not_started",
                status="available",
            )
            row["status"] = "available"
            changed = True
        prev_done = False
    return changed


def compute_authoritative_step(
    steps_map: Dict[str, Dict[str, Any]],
    linear_order: Optional[Tuple[str, ...]] = None,
) -> Tuple[Optional[str], str]:
    """
    First linear step that is not completed.
    Returns (step_id, phase) where phase is 'done' if all completed.
    """
    order = linear_order if linear_order is not None else reg.LINEAR_STEP_ORDER
    for sid in order:
        row = steps_map.get(sid)
        if not row:
            continue
        if row["status"] == "completed":
            continue
        return sid, "active"
    return None, "done"


def _first_open_step_after(
    completed_step_id: str,
    smap: Dict[str, Dict[str, Any]],
) -> Tuple[Optional[str], bool]:
    """
    After ``completed_step_id`` is (being) marked completed, find the next linear step
    whose row is not already ``completed``. If the chain ends, return (None, True).
    """
    cursor = completed_step_id
    while True:
        defn = reg.STEP_REGISTRY.get(cursor)
        if not defn or not defn.next_steps:
            return None, True
        nid = defn.next_steps[0]
        row = smap.get(nid) or {}
        st = str(row.get("status") or "not_started")
        if st != "completed":
            return nid, False
        cursor = nid


def build_next_actions(
    workflow_id: str,
    session_row: Dict[str, Any],
    steps_map: Dict[str, Dict[str, Any]],
    *,
    include_step_completion: bool = False,
) -> List[Dict[str, Any]]:
    """
    Public clients only receive `start` actions. Step completion/failure is never
    exposed over the public HTTP API (trusted services use internal endpoints).
    """
    actions: List[Dict[str, Any]] = []
    base = f"/api/workflows/{workflow_id}"

    if session_row["overall_status"] == "completed":
        return []

    order = _linear_order_from_session(session_row)
    head, phase = compute_authoritative_step(steps_map, order)
    if phase == "done":
        return []

    row = steps_map.get(head or "")
    if not row:
        return actions

    st = row["status"]
    if st == "available" or st == "failed":
        actions.append(
            {
                "action": "start",
                "stepId": head,
                "method": "POST",
                "path": f"{base}/steps/{head}/start",
            }
        )
    if include_step_completion and st == "in_progress":
        actions.append(
            {
                "action": "complete",
                "stepId": head,
                "method": "POST",
                "path": f"{base}/steps/{head}/complete",
            }
        )
        actions.append(
            {
                "action": "fail",
                "stepId": head,
                "method": "POST",
                "path": f"{base}/steps/{head}/fail",
            }
        )
    elif st == "in_progress":
        actions.append(
            {
                "action": "wait_for_server",
                "stepId": head,
                "method": None,
                "path": None,
                "hint": "This step is processed on the server; refresh state later.",
            }
        )
    return actions


class WorkflowEngine:
    """Single write authority for linear step completion (plus guarded engine internals)."""

    def get_state_bundle(self, workflow_id: str) -> Tuple[Optional[Dict], List[Dict], Dict[str, Any]]:
        from services.workflow.workflow_db import get_workflow_db

        session = fetch_session(workflow_id)
        if not session:
            return None, [], {}
        steps = fetch_steps(workflow_id)
        smap = _steps_by_id(steps)
        order = _linear_order_from_session(session)
        with get_workflow_db() as (conn, cur):
            if repair_linear_availability_tx(conn, cur, workflow_id, smap, order):
                wf_inst.touch_session_updated_at(conn, cur, workflow_id)
                conn.commit()
                _orion_after_commit(workflow_id)
                steps = fetch_steps(workflow_id)
                smap = _steps_by_id(steps)
            else:
                conn.rollback()
        return session, steps, smap

    def build_response(
        self,
        *,
        action_result: str,
        workflow_id: str,
        user_message: str,
        async_task_state: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session, steps, smap = self.get_state_bundle(workflow_id)
        if not session:
            return workflow_envelope(
                action_result="error",
                user_message="Workflow not found.",
                error=safe_error("NOT_FOUND", "Workflow not found."),
            )
        actions = build_next_actions(workflow_id, session, smap)
        return workflow_envelope(
            action_result=action_result,
            workflow_state=_serialize_session(session),
            step_status=_serialize_steps(steps),
            user_message=user_message,
            next_available_actions=actions,
            async_task_state=async_task_state,
            error=error,
        )

    def init_workflow(
        self,
        *,
        user_id: int,
        workflow_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        wtype = workflow_type or reg.WORKFLOW_TYPE_DEFAULT
        first = reg.linear_order_for(wtype)[0]
        wid = create_workflow_with_steps(
            user_id=user_id,
            workflow_type=wtype,
            metadata=metadata,
            first_step_id=first,
        )
        return self.build_response(
            action_result="ok",
            workflow_id=wid,
            user_message="Workflow started. Complete the upload step when you’re ready.",
        )

    def get_state(self, workflow_id: str) -> Dict[str, Any]:
        return self.build_response(
            action_result="ok",
            workflow_id=workflow_id,
            user_message="Current workflow state loaded.",
        )

    def resume(self, workflow_id: str) -> Dict[str, Any]:
        session, _, smap = self.get_state_bundle(workflow_id)
        if not session:
            return workflow_envelope(
                action_result="error",
                user_message="No workflow to resume.",
                error=safe_error("NOT_FOUND", "Workflow not found."),
            )
        head, phase = compute_authoritative_step(smap, _linear_order_from_session(session))
        msg = (
            "You’re all caught up — this workflow is complete."
            if phase == "done"
            else "Pick up where you left off using the actions below."
        )
        return self.build_response(
            action_result="ok",
            workflow_id=workflow_id,
            user_message=msg,
        )

    def service_complete_step(
        self,
        workflow_id: str,
        step_id: str,
        completion_payload_summary: Optional[Dict[str, Any]] = None,
        *,
        audit_source: str = "service",
        audit_user_id: Optional[int] = None,
    ) -> bool:
        """
        Trusted backend path: start-if-needed, then complete, in one transaction.
        Used by domain services (upload, webhooks, Lob, etc.), not the public HTTP API.
        """
        from services.workflow.workflow_db import get_workflow_db

        if step_id not in reg.STEP_REGISTRY:
            return False
        session, _, smap = self.get_state_bundle(workflow_id)
        if not session or session.get("overall_status") == "completed":
            return False
        order = _linear_order_from_session(session)
        head, phase = compute_authoritative_step(smap, order)
        if phase == "done" or head != step_id:
            _log.debug(
                "service_complete_step skipped: head=%s wanted=%s wf=%s",
                head,
                step_id,
                workflow_id,
            )
            return False
        row = smap[step_id]
        st = row["status"]
        if st == "completed":
            return True
        if st not in ("available", "failed", "in_progress"):
            return False

        now = utcnow()
        next_open, finish_session = _first_open_step_after(step_id, smap)
        summary = dict(completion_payload_summary or {})
        if step_id in reg.ASYNC_MANAGED_STEPS:
            summary.setdefault(
                "asyncTrustedResolution",
                {"source": audit_source[:64]},
            )
            summary["asyncLifecycle"] = {
                "finalPhase": "completed",
                "source": audit_source[:64],
                "resolvedAt": now.isoformat(),
            }

        prior_overall = str(session.get("overall_status") or "active")

        with get_workflow_db() as (conn, cur):
            if st in ("available", "failed"):
                mid_async: Any = False
                if step_id in reg.ASYNC_MANAGED_STEPS:
                    mid_async = {
                        "phase": "running",
                        "source": audit_source[:48],
                        "updatedAt": now.isoformat(),
                    }
                wf_inst.mutate_step(
                    conn,
                    cur,
                    workflow_id,
                    step_id,
                    prior_step_status=st,
                    status="in_progress",
                    attempt_count_delta=1,
                    started_at=now,
                    completed_at=None,
                    failed_at=None,
                    last_error_code=None,
                    last_error_message_safe=None,
                    async_task_state=mid_async,
                )
            wf_inst.mutate_step(
                conn,
                cur,
                workflow_id,
                step_id,
                prior_step_status="in_progress",
                status="completed",
                completed_at=now,
                failed_at=None,
                completion_payload_summary=summary,
                async_task_state=None,
                last_error_code=None,
                last_error_message_safe=None,
            )
            if not finish_session and next_open:
                next_row = smap.get(next_open) or {}
                next_prior = str(next_row.get("status") or "not_started")
                wf_inst.mutate_step(
                    conn,
                    cur,
                    workflow_id,
                    next_open,
                    prior_step_status=next_prior,
                    status="available",
                )
                wf_inst.mutate_session(
                    conn,
                    cur,
                    workflow_id,
                    prior_overall_status=prior_overall,
                    current_step=next_open,
                    overall_status="active",
                    last_error_code=None,
                    last_error_message_safe=None,
                )
            else:
                wf_inst.mutate_session(
                    conn,
                    cur,
                    workflow_id,
                    prior_overall_status=prior_overall,
                    current_step=None,
                    overall_status="completed",
                    completed_at=now,
                    last_error_code=None,
                    last_error_message_safe=None,
                )
            conn.commit()
            _orion_after_commit(workflow_id)
        log_workflow_event(
            "service_complete",
            workflow_id=workflow_id,
            step_id=step_id,
            source=audit_source,
            user_id=audit_user_id,
        )
        return True

    def service_begin_next_dispute_round(
        self,
        workflow_id: str,
        *,
        audit_source: str = "api:begin_next_dispute_round",
        audit_user_id: Optional[int] = None,
    ) -> bool:
        """
        After the linear workflow is ``completed`` (including ``track``), reopen
        ``select_disputes`` → … → ``track`` for another dispute cycle in the same session.
        """
        session, _, smap = self.get_state_bundle(workflow_id)
        if not session:
            return False
        if str(session.get("overall_status") or "") != "completed":
            return False
        tr = smap.get("track") or {}
        if tr.get("status") != "completed":
            return False

        from services.workflow.workflow_db import get_workflow_db

        reset_chain = (
            "select_disputes",
            "letter_generation",
            "proof_attachment",
            "mail",
            "track",
        )
        now = utcnow()
        prior_overall = "completed"

        with get_workflow_db() as (conn, cur):
            for sid in reset_chain:
                row = smap.get(sid) or {}
                if row.get("status") != "completed":
                    continue
                wf_inst.mutate_step(
                    conn,
                    cur,
                    workflow_id,
                    sid,
                    prior_step_status="completed",
                    status="available",
                )
                update_step_fields(
                    conn,
                    cur,
                    workflow_id,
                    sid,
                    completed_at=None,
                    failed_at=None,
                    async_task_state=None,
                )
            wf_inst.mutate_session(
                conn,
                cur,
                workflow_id,
                prior_overall_status=prior_overall,
                current_step="select_disputes",
                overall_status="active",
                completed_at=None,
                last_error_code=None,
                last_error_message_safe=None,
            )
            conn.commit()
            _orion_after_commit(workflow_id)

        from services.workflow.dispute_round_execution import snapshot_round_close_before_next
        from services.workflow.repository import merge_into_workflow_metadata

        snapshot_round_close_before_next(workflow_id)

        def _meta(meta: Dict[str, Any]) -> None:
            meta["mail"] = {
                "expected_unique_bureau_sends": 0,
                "selected_bureau_keys": [],
                "confirmed_bureaus": [],
                "successful_send_count": 0,
                "failed_send_count": 0,
                "completed_all_sends": False,
            }
            ds = meta.get("dispute_selection")
            if not isinstance(ds, dict):
                ds = {}
            else:
                ds = dict(ds)
            prev = int(ds.get("dispute_round_number") or 1)
            nxt = prev + 1
            ds["dispute_round_number"] = nxt
            hist = ds.get("dispute_round_history")
            if not isinstance(hist, list):
                hist = []
            hist = list(hist)
            hist.append(
                {
                    "beganAt": now.isoformat(),
                    "roundNumber": nxt,
                    "source": (audit_source or "")[:64],
                }
            )
            ds["dispute_round_history"] = hist[-24:]
            meta["dispute_selection"] = ds

        merge_into_workflow_metadata(workflow_id, _meta)
        log_workflow_event(
            "begin_next_dispute_round",
            workflow_id=workflow_id,
            step_id="select_disputes",
            source=audit_source,
            user_id=audit_user_id,
        )
        return True

    def service_fail_step(
        self,
        workflow_id: str,
        step_id: str,
        error_code: str,
        message_safe: str,
        *,
        audit_source: str = "service",
        audit_user_id: Optional[int] = None,
    ) -> bool:
        """Trusted path: mark head step failed when it is in_progress (or start then fail)."""
        from services.workflow.workflow_db import get_workflow_db

        if step_id not in reg.STEP_REGISTRY:
            return False
        session, _, smap = self.get_state_bundle(workflow_id)
        if not session or session.get("overall_status") == "completed":
            return False
        order = _linear_order_from_session(session)
        head, phase = compute_authoritative_step(smap, order)
        if phase == "done" or head != step_id:
            return False
        row = smap[step_id]
        st = row["status"]
        if st == "failed":
            return True
        now = utcnow()
        prior_overall = str(session.get("overall_status") or "active")
        with get_workflow_db() as (conn, cur):
            if st == "available":
                wf_inst.mutate_step(
                    conn,
                    cur,
                    workflow_id,
                    step_id,
                    prior_step_status="available",
                    status="in_progress",
                    attempt_count_delta=1,
                    started_at=now,
                    completed_at=None,
                    failed_at=None,
                )
            elif st != "in_progress":
                return False
            fail_async: Any = False
            if step_id in reg.ASYNC_MANAGED_STEPS:
                fail_async = {
                    "phase": "failed",
                    "errorCode": error_code[:64],
                    "messageSafe": (message_safe or "")[:300],
                    "source": (audit_source or "")[:48],
                    "updatedAt": now.isoformat(),
                }
            wf_inst.mutate_step(
                conn,
                cur,
                workflow_id,
                step_id,
                prior_step_status="in_progress",
                status="failed",
                failed_at=now,
                last_error_code=error_code,
                last_error_message_safe=message_safe,
                async_task_state=fail_async,
            )
            wf_inst.mutate_session(
                conn,
                cur,
                workflow_id,
                prior_overall_status=prior_overall,
                overall_status="failed",
                last_error_code=error_code,
                last_error_message_safe=message_safe,
            )
            conn.commit()
            _orion_after_commit(workflow_id)
        log_workflow_event(
            "service_fail",
            workflow_id=workflow_id,
            step_id=step_id,
            source=audit_source,
            user_id=audit_user_id,
            error_code=error_code,
            message_safe=message_safe,
        )
        return True

    def service_set_async_task_state(
        self,
        workflow_id: str,
        step_id: str,
        async_task_state: Dict[str, Any],
        *,
        audit_source: str = "worker",
        audit_user_id: Optional[int] = None,
    ) -> bool:
        """Trusted: set async_task_state for the current head step when it is in_progress."""
        from services.workflow.workflow_db import get_workflow_db

        if step_id not in reg.STEP_REGISTRY:
            return False
        session, _, smap = self.get_state_bundle(workflow_id)
        if not session or session.get("overall_status") == "completed":
            return False
        head, _ = compute_authoritative_step(smap, _linear_order_from_session(session))
        if head != step_id:
            return False
        row = smap[step_id]
        if row["status"] != "in_progress":
            return False
        with get_workflow_db() as (conn, cur):
            wf_inst.mutate_step(
                conn,
                cur,
                workflow_id,
                step_id,
                async_task_state=async_task_state,
            )
            wf_inst.touch_session_updated_at(conn, cur, workflow_id)
            conn.commit()
            _orion_after_commit(workflow_id)
        log_workflow_event(
            "async_state",
            workflow_id=workflow_id,
            step_id=step_id,
            source=audit_source,
            user_id=audit_user_id,
            extra={"state": async_task_state},
        )
        return True

    def service_reopen_failed_step(
        self,
        workflow_id: str,
        step_id: str,
        *,
        audit_source: str = "recovery_execution",
        audit_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Trusted transition: failed → available for retryable steps; clears session failure flags.
        """
        from services.workflow.workflow_db import get_workflow_db

        if step_id not in reg.STEP_REGISTRY:
            return {"ok": False, "error": {"code": "INVALID_STEP"}}
        session, _, smap = self.get_state_bundle(workflow_id)
        if not session:
            return {"ok": False, "error": {"code": "NOT_FOUND"}}
        row = smap.get(step_id)
        if not row or row.get("status") != "failed":
            return {"ok": False, "error": {"code": "STEP_NOT_FAILED"}}
        if step_id not in lr_mod.FAILED_RETRYABLE_STEPS:
            return {"ok": False, "error": {"code": "STEP_NOT_REOPEN_ELIGIBLE"}}
        uid = int(session["user_id"])
        prior_overall = str(session.get("overall_status") or "active")
        with get_workflow_db() as (conn, cur):
            wf_inst.mutate_step(
                conn,
                cur,
                workflow_id,
                step_id,
                prior_step_status="failed",
                status="available",
                failed_at=None,
                last_error_code=None,
                last_error_message_safe=None,
                async_task_state=None,
            )
            wf_inst.mutate_session(
                conn,
                cur,
                workflow_id,
                prior_overall_status=prior_overall,
                overall_status="active",
                last_error_code=None,
                last_error_message_safe=None,
            )
            conn.commit()
            _orion_after_commit(workflow_id)
        log_workflow_event(
            "service_reopen_failed",
            workflow_id=workflow_id,
            step_id=step_id,
            source=audit_source[:64],
            user_id=audit_user_id or uid,
        )
        return {"ok": True, "workflowId": workflow_id, "stepId": step_id}

    def service_mark_mail_recovery_retry(
        self,
        workflow_id: str,
        *,
        audit_source: str = "recovery_execution",
        audit_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Metadata-only execution for partial mail failures: pending bureau keys exclude
        already-confirmed sends; does not mutate successful counts or confirmed_bureaus.
        """
        from services.workflow.workflow_db import get_workflow_db

        session, _, smap = self.get_state_bundle(workflow_id)
        if not session:
            return {"ok": False, "error": {"code": "NOT_FOUND"}}
        head, _ = compute_authoritative_step(smap, _linear_order_from_session(session))
        if head != "mail":
            return {"ok": False, "error": {"code": "HEAD_NOT_MAIL"}}
        mail_row = smap.get("mail")
        if not mail_row or mail_row.get("status") not in ("available", "in_progress", "failed"):
            return {"ok": False, "error": {"code": "MAIL_STEP_INVALID_STATE"}}

        meta = session.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        if not isinstance(meta, dict):
            meta = {}
        mail = meta.get("mail") or {}
        if not isinstance(mail, dict):
            mail = {}

        exp = int(mail.get("expected_unique_bureau_sends") or 1)
        confirmed = mail.get("confirmed_bureaus") or []
        if not isinstance(confirmed, list):
            confirmed = []
        confirmed_norm = {str(x).strip().lower() for x in confirmed if str(x).strip()}
        ok_ct = len(confirmed_norm)
        failed_ct = int(mail.get("failed_send_count") or 0)

        if failed_ct <= 0:
            return {"ok": False, "error": {"code": "NO_FAILED_SENDS_TO_RETRY"}}
        if ok_ct >= exp:
            return {"ok": False, "error": {"code": "MAIL_ALREADY_COMPLETE"}}

        keys = mail.get("selected_bureau_keys") or []
        if isinstance(keys, list) and keys:
            pending = [k for k in keys if str(k).strip().lower() not in confirmed_norm]
        else:
            pending = []

        now = utcnow()
        now_iso = now.isoformat()

        patch_mail = {
            **mail,
            "recoveryRetryIssuedAt": now_iso,
            "recoveryRetryWave": int(mail.get("recoveryRetryWave") or 0) + 1,
            "pendingBureauKeysForRetry": pending
            if pending
            else None,
            "bureauSlotsRemainingAfterSuccess": max(0, exp - ok_ct),
        }
        # Drop None to avoid clutter
        patch_mail = {k: v for k, v in patch_mail.items() if v is not None}

        with get_workflow_db() as (conn, cur):
            wf_inst.patch_session_metadata(
                conn, cur, workflow_id, {"mail": patch_mail}
            )
            conn.commit()
            _orion_after_commit(workflow_id)

        log_workflow_event(
            "mail_recovery_retry_marked",
            workflow_id=workflow_id,
            step_id="mail",
            source=audit_source[:64],
            user_id=audit_user_id or int(session["user_id"]),
            extra={
                "pendingBureauCount": len(pending) if pending else max(0, exp - ok_ct),
                "failedSendCount": failed_ct,
            },
        )
        return {
            "ok": True,
            "workflowId": workflow_id,
            "pendingBureauKeysForRetry": pending,
            "bureauSlotsRemaining": max(0, exp - ok_ct),
            "failedSendCount": failed_ct,
        }

    def start_step(
        self,
        workflow_id: str,
        step_id: str,
        *,
        audit_source: str = "api",
        audit_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if step_id not in reg.STEP_REGISTRY:
            return workflow_envelope(
                action_result="rejected",
                user_message="Unknown step.",
                error=safe_error("INVALID_STEP", "This step is not part of the workflow."),
            )
        from services.workflow.workflow_db import get_workflow_db

        session, steps, smap = self.get_state_bundle(workflow_id)
        if not session:
            return workflow_envelope(
                action_result="error",
                user_message="Workflow not found.",
                error=safe_error("NOT_FOUND", "Workflow not found."),
            )
        if session["overall_status"] == "completed":
            return workflow_envelope(
                action_result="rejected",
                user_message="This workflow is already complete.",
                error=safe_error("WORKFLOW_COMPLETE", "No further steps."),
            )

        head, _ = compute_authoritative_step(smap, _linear_order_from_session(session))
        if head != step_id:
            exp_label = (
                reg.STEP_REGISTRY[head].name
                if head and head in reg.STEP_REGISTRY
                else None
            )
            return workflow_envelope(
                action_result="rejected",
                user_message=(
                    f"You can’t start this step yet. The active step is “{exp_label or head}”."
                    if head
                    else "You can’t start this step yet."
                ),
                error=safe_error(
                    "INVALID_PROGRESSION",
                    "That step is not the current workflow step.",
                    detail={
                        "expectedStepId": head,
                        "expectedStepName": exp_label,
                        "requestedStepId": step_id,
                    },
                ),
            )

        row = smap[step_id]
        if row["status"] not in ("available", "failed"):
            return workflow_envelope(
                action_result="rejected",
                user_message="This step can’t be started right now.",
                error=safe_error(
                    "INVALID_STATUS",
                    "Step is not available to start.",
                    detail={"status": row["status"], "stepId": step_id},
                ),
            )

        now = utcnow()
        async_payload: Optional[Dict[str, Any]] = None
        if step_id in reg.ASYNC_MANAGED_STEPS:
            async_payload = {
                "phase": "queued",
                "source": audit_source[:48],
                "updatedAt": now.isoformat(),
            }
        prior_overall = str(session.get("overall_status") or "active")
        row_status = str(row["status"])
        with get_workflow_db() as (conn, cur):
            wf_inst.mutate_step(
                conn,
                cur,
                workflow_id,
                step_id,
                prior_step_status=row_status,
                status="in_progress",
                attempt_count_delta=1,
                started_at=now,
                completed_at=None,
                failed_at=None,
                last_error_code=None,
                last_error_message_safe=None,
                async_task_state=async_payload if async_payload is not None else False,
            )
            wf_inst.mutate_session(
                conn,
                cur,
                workflow_id,
                prior_overall_status=prior_overall,
                current_step=step_id,
                overall_status="active",
                last_error_code=None,
                last_error_message_safe=None,
            )
            conn.commit()
            _orion_after_commit(workflow_id)

        log_workflow_event(
            "step_start",
            workflow_id=workflow_id,
            step_id=step_id,
            source=audit_source,
            user_id=audit_user_id,
        )
        return self.build_response(
            action_result="ok",
            workflow_id=workflow_id,
            user_message=f"“{reg.STEP_REGISTRY[step_id].name}” is in progress.",
        )

    def complete_step(
        self,
        workflow_id: str,
        step_id: str,
        completion_payload_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if step_id not in reg.STEP_REGISTRY:
            return workflow_envelope(
                action_result="rejected",
                user_message="Unknown step.",
                error=safe_error("INVALID_STEP", "This step is not part of the workflow."),
            )
        from services.workflow.workflow_db import get_workflow_db

        session, _, smap = self.get_state_bundle(workflow_id)
        if not session:
            return workflow_envelope(
                action_result="error",
                user_message="Workflow not found.",
                error=safe_error("NOT_FOUND", "Workflow not found."),
            )

        head, _ = compute_authoritative_step(smap, _linear_order_from_session(session))
        if head != step_id:
            return workflow_envelope(
                action_result="rejected",
                user_message="Only the active step can be completed.",
                error=safe_error(
                    "INVALID_PROGRESSION",
                    "Complete the current step first.",
                    detail={"expectedStepId": head},
                ),
            )

        row = smap[step_id]
        if row["status"] != "in_progress":
            return workflow_envelope(
                action_result="rejected",
                user_message="Start this step before completing it.",
                error=safe_error(
                    "INVALID_STATUS",
                    "Step is not in progress.",
                    detail={"status": row["status"]},
                ),
            )

        now = utcnow()
        next_open, finish_session = _first_open_step_after(step_id, smap)
        prior_overall = str(session.get("overall_status") or "active")

        with get_workflow_db() as (conn, cur):
            wf_inst.mutate_step(
                conn,
                cur,
                workflow_id,
                step_id,
                prior_step_status="in_progress",
                status="completed",
                completed_at=now,
                failed_at=None,
                completion_payload_summary=completion_payload_summary or {},
                async_task_state=None,
            )
            if not finish_session and next_open:
                next_row = smap.get(next_open) or {}
                next_prior = str(next_row.get("status") or "not_started")
                wf_inst.mutate_step(
                    conn,
                    cur,
                    workflow_id,
                    next_open,
                    prior_step_status=next_prior,
                    status="available",
                )
                wf_inst.mutate_session(
                    conn,
                    cur,
                    workflow_id,
                    prior_overall_status=prior_overall,
                    current_step=next_open,
                    overall_status="active",
                    last_error_code=None,
                    last_error_message_safe=None,
                )
            else:
                wf_inst.mutate_session(
                    conn,
                    cur,
                    workflow_id,
                    prior_overall_status=prior_overall,
                    current_step=None,
                    overall_status="completed",
                    completed_at=now,
                    last_error_code=None,
                    last_error_message_safe=None,
                )
            conn.commit()
            _orion_after_commit(workflow_id)

        # Refresh for response
        if not finish_session and next_open:
            msg = f"Step complete. Next: {reg.STEP_REGISTRY[next_open].name}."
        else:
            msg = "Workflow complete. Tracking and follow-ups can continue here."
        return self.build_response(
            action_result="ok",
            workflow_id=workflow_id,
            user_message=msg,
        )

    def fail_step(
        self,
        workflow_id: str,
        step_id: str,
        error_code: str,
        message_safe: str,
    ) -> Dict[str, Any]:
        from services.workflow.workflow_db import get_workflow_db

        session, _, smap = self.get_state_bundle(workflow_id)
        if not session:
            return workflow_envelope(
                action_result="error",
                user_message="Workflow not found.",
                error=safe_error("NOT_FOUND", "Workflow not found."),
            )

        head, _ = compute_authoritative_step(smap, _linear_order_from_session(session))
        if head != step_id:
            return workflow_envelope(
                action_result="rejected",
                user_message="Only the active step can be marked failed.",
                error=safe_error("INVALID_PROGRESSION", "Wrong step."),
            )

        row = smap[step_id]
        if row["status"] != "in_progress":
            return workflow_envelope(
                action_result="rejected",
                user_message="Only an in-progress step can fail.",
                error=safe_error("INVALID_STATUS", "Step is not in progress."),
            )

        now = utcnow()
        prior_overall = str(session.get("overall_status") or "active")
        with get_workflow_db() as (conn, cur):
            wf_inst.mutate_step(
                conn,
                cur,
                workflow_id,
                step_id,
                prior_step_status="in_progress",
                status="failed",
                failed_at=now,
                last_error_code=error_code,
                last_error_message_safe=message_safe,
            )
            wf_inst.mutate_session(
                conn,
                cur,
                workflow_id,
                prior_overall_status=prior_overall,
                overall_status="failed",
                last_error_code=error_code,
                last_error_message_safe=message_safe,
            )
            conn.commit()
            _orion_after_commit(workflow_id)

        return self.build_response(
            action_result="ok",
            workflow_id=workflow_id,
            user_message="We saved that issue. You can retry this step when ready.",
            error=safe_error(error_code, message_safe),
        )
