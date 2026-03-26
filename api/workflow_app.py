"""
FastAPI app: authoritative workflow HTTP API.

Authentication:
  - User endpoints: ``Authorization: Bearer <session_token>`` (see ``auth.validate_session``).
  - Internal worker endpoints: header ``X-Workflow-Internal-Key`` or
    ``Authorization: Bearer <WORKFLOW_INTERNAL_API_SECRET>``.

Environment:
  - ``DATABASE_URL`` — Postgres (default when set). If unset in non-production, workflow storage uses SQLite (see below).
  - ``DB_BACKEND`` — ``auto`` (default), ``postgres``, or ``sqlite``. Production-like hosts never use SQLite.
  - ``WORKFLOW_SQLITE_PATH`` — SQLite file for local workflow + Mission Control (default: ``lab_truth/dev_workflow.sqlite``).
  - ``WORKFLOW_INTERNAL_API_SECRET`` — workers / reminder delivery batch (non-admin internal routes).
  - ``WORKFLOW_ADMIN_API_SECRET`` — required for ``/internal/admin/...`` routes.
  - ``WORKFLOW_REMINDER_FALLBACK_STUB=1`` — after email failure, mark sent with channel ``stub`` (logged).

Public clients cannot complete or fail steps over HTTP; use ``/internal/.../service-*``
with the internal secret from trusted workers.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.workflow_deps import (
    get_owned_workflow,
    get_session_user,
    require_admin_service,
    require_internal_service,
)
from services.workflow import admin_override_service as admin_svc
from services.workflow import recovery_execution_service as rec_exec
from services.workflow.engine import WorkflowEngine
from services.workflow.home_summary_service import build_home_summary
from services.workflow import mission_control_service as mcc_svc
from services.workflow import reminder_service as rem_svc
from services.workflow.response_intake_service import intake_bureau_response

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def _workflow_api_lifespan(_app: FastAPI):
    """
    Align with Streamlit's ``database.init_database()`` so workflow DDL exists.
    Uvicorn-only processes previously skipped this; Mission Control SQL then
    failed with undefined-table errors (HTTP 500).
    """
    try:
        import database as db

        db.init_database()
    except Exception:
        _logger.exception(
            "workflow API: init_database() failed — DB unavailable or misconfigured"
        )
    yield


app = FastAPI(
    title="850 Lab Workflow API",
    version="0.2.0",
    lifespan=_workflow_api_lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine = WorkflowEngine()


class InitBody(BaseModel):
    workflow_type: Optional[str] = Field(
        default=None,
        description="Defaults to dispute_linear_v1",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResponseIntakeBody(BaseModel):
    """Structured summary of a bureau/furnisher response (no client-supplied user id)."""

    source_type: str = Field(
        default="unknown",
        max_length=40,
        description="bureau | furnisher | creditor | collection_agency | unknown",
    )
    response_channel: str = Field(
        default="upload",
        max_length=40,
        description="upload | manual_entry | mail_scan_placeholder | admin",
    )
    parsed_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Safe structured hints, e.g. summary_safe, outcome_keywords",
    )
    storage_ref: Optional[str] = Field(default=None, description="Blob path or file id")
    linked_mailing_id: Optional[int] = Field(default=None)
    linked_letter_id: Optional[int] = Field(default=None)


class InternalServiceCompleteBody(BaseModel):
    completion_payload_summary: Optional[Dict[str, Any]] = Field(default=None)
    audit_source: str = Field(default="worker", max_length=64)


class InternalServiceFailBody(BaseModel):
    error_code: str = Field(..., min_length=1, max_length=64)
    message_safe: str = Field(..., min_length=1)
    audit_source: str = Field(default="worker", max_length=64)


class InternalAsyncStateBody(BaseModel):
    state: Dict[str, Any] = Field(default_factory=dict)
    audit_source: str = Field(default="worker", max_length=64)


class StubBatchBody(BaseModel):
    limit: int = Field(default=20, ge=1, le=500)


class ReminderFailedBody(BaseModel):
    message_safe: str = Field(default="Reminder delivery failed", max_length=500)


class AdminActorReasonBody(BaseModel):
    actor_source: str = Field(..., max_length=128)
    reason_safe: str = Field(..., max_length=4000)


class OverrideClassificationBody(AdminActorReasonBody):
    response_id: str = Field(..., min_length=1)
    new_classification: str = Field(..., max_length=64)
    reasoning_safe: str = Field(default="", max_length=2000)


class OverrideEscalationBody(AdminActorReasonBody):
    response_id: str = Field(..., min_length=1)
    escalation_recommendation: Dict[str, Any] = Field(default_factory=dict)


class ReopenStepBody(AdminActorReasonBody):
    step_id: str = Field(..., max_length=64)


class RecoveryRecordBody(AdminActorReasonBody):
    action_type: str = Field(..., max_length=64)
    detail_safe: str = Field(default="", max_length=2000)


class RecoveryExecutionBody(AdminActorReasonBody):
    """``user_id`` must match the workflow session owner."""

    user_id: int = Field(..., ge=1)


class RecoveryRetryStepBody(RecoveryExecutionBody):
    step_id: str = Field(..., max_length=64)


@app.post("/api/workflows/init")
def post_init(
    body: InitBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Create a new workflow for the authenticated user."""
    return _engine.init_workflow(
        user_id=int(user["user_id"]),
        workflow_type=body.workflow_type,
        metadata=body.metadata or None,
    )


@app.get("/api/workflows/{workflow_id}/state")
def get_state(
    workflow_id: str,
    _session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    return _engine.get_state(workflow_id)


@app.get("/api/workflows/{workflow_id}/resume")
def get_resume(
    workflow_id: str,
    _session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    return _engine.resume(workflow_id)


@app.get("/api/workflows/{workflow_id}/home-summary")
def get_home_summary(
    workflow_id: str,
    _session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    return build_home_summary(workflow_id)


@app.post("/api/workflows/{workflow_id}/responses/intake")
def post_response_intake(
    workflow_id: str,
    body: ResponseIntakeBody,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    return intake_bureau_response(
        workflow_id=workflow_id,
        user_id=int(session["user_id"]),
        source_type=body.source_type,
        response_channel=body.response_channel,
        parsed_summary=body.parsed_summary,
        storage_ref=body.storage_ref,
        linked_mailing_id=body.linked_mailing_id,
        linked_letter_id=body.linked_letter_id,
    )


@app.post("/api/workflows/{workflow_id}/steps/{step_id}/start")
def post_step_start(
    workflow_id: str,
    step_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    return _engine.start_step(
        workflow_id,
        step_id,
        audit_source="api",
        audit_user_id=int(session["user_id"]),
    )


@app.post("/internal/workflows/{workflow_id}/steps/{step_id}/service-complete")
def internal_service_complete(
    workflow_id: str,
    step_id: str,
    body: InternalServiceCompleteBody,
    _: None = Depends(require_internal_service),
) -> Dict[str, Any]:
    ok = _engine.service_complete_step(
        workflow_id,
        step_id,
        body.completion_payload_summary,
        audit_source=body.audit_source or "internal_http",
    )
    return {"ok": ok}


@app.post("/internal/workflows/{workflow_id}/steps/{step_id}/service-fail")
def internal_service_fail(
    workflow_id: str,
    step_id: str,
    body: InternalServiceFailBody,
    _: None = Depends(require_internal_service),
) -> Dict[str, Any]:
    ok = _engine.service_fail_step(
        workflow_id,
        step_id,
        body.error_code,
        body.message_safe,
        audit_source=body.audit_source or "internal_http",
    )
    return {"ok": ok}


@app.post("/internal/workflows/{workflow_id}/steps/{step_id}/async-state")
def internal_async_state(
    workflow_id: str,
    step_id: str,
    body: InternalAsyncStateBody,
    _: None = Depends(require_internal_service),
) -> Dict[str, Any]:
    ok = _engine.service_set_async_task_state(
        workflow_id,
        step_id,
        body.state,
        audit_source=body.audit_source or "internal_http",
    )
    return {"ok": ok}


# --- Internal reminder execution (worker / ops; not for browsers) -----------------


@app.post("/internal/reminders/workflows/{workflow_id}/candidates")
def internal_reminder_candidates(
    workflow_id: str,
    _: None = Depends(require_internal_service),
) -> Dict[str, Any]:
    return rem_svc.create_reminder_candidates_for_workflow(workflow_id)


@app.post("/internal/reminders/process-stub-batch")
def internal_reminder_stub_batch(
    body: StubBatchBody,
    _: None = Depends(require_internal_service),
) -> Dict[str, Any]:
    """Deprecated name; runs real delivery (Resend when configured)."""
    return rem_svc.process_delivery_batch(limit=body.limit)


@app.post("/internal/reminders/process-delivery-batch")
def internal_reminder_delivery_batch(
    body: StubBatchBody,
    _: None = Depends(require_internal_service),
) -> Dict[str, Any]:
    return rem_svc.process_delivery_batch(limit=body.limit)


@app.post("/internal/reminders/{reminder_id}/deliver")
def internal_reminder_deliver(
    reminder_id: str,
    _: None = Depends(require_internal_service),
) -> Dict[str, Any]:
    return rem_svc.deliver_reminder(reminder_id)


@app.post("/internal/reminders/{reminder_id}/queue")
def internal_reminder_queue(
    reminder_id: str,
    _: None = Depends(require_internal_service),
) -> Dict[str, Any]:
    return {"ok": rem_svc.queue_reminder(reminder_id)}


@app.post("/internal/reminders/{reminder_id}/mark-sent-stub")
def internal_reminder_sent_stub(
    reminder_id: str,
    _: None = Depends(require_internal_service),
) -> Dict[str, Any]:
    return {"ok": rem_svc.mark_reminder_sent_stub(reminder_id)}


@app.post("/internal/reminders/{reminder_id}/mark-failed")
def internal_reminder_failed(
    reminder_id: str,
    body: ReminderFailedBody,
    _: None = Depends(require_internal_service),
) -> Dict[str, Any]:
    return {"ok": rem_svc.mark_reminder_failed(reminder_id, body.message_safe)}


# --- Internal admin overrides (WORKFLOW_ADMIN_API_SECRET only) --------------------


@app.post("/internal/admin/responses/override-classification")
def internal_admin_override_classification(
    body: OverrideClassificationBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    return admin_svc.override_response_classification(
        response_id=body.response_id,
        new_classification=body.new_classification,
        reasoning_safe=body.reasoning_safe,
        actor_source=body.actor_source,
        reason_safe=body.reason_safe,
    )


@app.post("/internal/admin/responses/override-escalation")
def internal_admin_override_escalation(
    body: OverrideEscalationBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    return admin_svc.override_escalation_recommendation(
        response_id=body.response_id,
        escalation_recommendation=body.escalation_recommendation,
        actor_source=body.actor_source,
        reason_safe=body.reason_safe,
    )


@app.post("/internal/admin/reminders/{reminder_id}/skip")
def internal_admin_skip_reminder(
    reminder_id: str,
    body: AdminActorReasonBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    return admin_svc.mark_reminder_skipped(
        reminder_id=reminder_id,
        actor_source=body.actor_source,
        reason_safe=body.reason_safe,
    )


@app.post("/internal/admin/workflows/{workflow_id}/clear-stalled-flag")
def internal_admin_clear_stalled(
    workflow_id: str,
    body: AdminActorReasonBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    return admin_svc.clear_stalled_flag(
        workflow_id=workflow_id,
        actor_source=body.actor_source,
        reason_safe=body.reason_safe,
    )


@app.post("/internal/admin/workflows/{workflow_id}/reopen-step")
def internal_admin_reopen_step(
    workflow_id: str,
    body: ReopenStepBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    return admin_svc.reopen_failed_step(
        workflow_id=workflow_id,
        step_id=body.step_id,
        actor_source=body.actor_source,
        reason_safe=body.reason_safe,
    )


@app.post("/internal/admin/workflows/{workflow_id}/payment-waived")
def internal_admin_payment_waived(
    workflow_id: str,
    body: AdminActorReasonBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    from services.workflow.repository import fetch_session

    row = fetch_session(workflow_id)
    if not row:
        return {"ok": False, "error": {"code": "NOT_FOUND"}}
    return admin_svc.apply_payment_waived(
        workflow_id=workflow_id,
        user_id=int(row["user_id"]),
        actor_source=body.actor_source,
        reason_safe=body.reason_safe,
    )


@app.post("/internal/admin/workflows/{workflow_id}/recovery-record")
def internal_admin_recovery_record(
    workflow_id: str,
    body: RecoveryRecordBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    return admin_svc.trigger_recovery_action_record(
        workflow_id=workflow_id,
        action_type=body.action_type,
        actor_source=body.actor_source,
        detail_safe=body.detail_safe or body.reason_safe,
    )


@app.post("/internal/admin/workflows/{workflow_id}/recovery/retry-step")
def internal_admin_recovery_retry_step(
    workflow_id: str,
    body: RecoveryRetryStepBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    return rec_exec.execute_retry_step(
        workflow_id=workflow_id,
        user_id=body.user_id,
        step_id=body.step_id,
        actor_source=body.actor_source,
        reason_safe=body.reason_safe,
    )


@app.post("/internal/admin/workflows/{workflow_id}/recovery/resume-current-step")
def internal_admin_recovery_resume_current(
    workflow_id: str,
    body: RecoveryExecutionBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    return rec_exec.execute_resume_current_step(
        workflow_id=workflow_id,
        user_id=body.user_id,
        actor_source=body.actor_source,
        reason_safe=body.reason_safe,
    )


@app.post("/internal/admin/workflows/{workflow_id}/recovery/re-run-mail-attempt")
def internal_admin_recovery_mail_retry(
    workflow_id: str,
    body: RecoveryExecutionBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    return rec_exec.execute_re_run_mail_attempt(
        workflow_id=workflow_id,
        user_id=body.user_id,
        actor_source=body.actor_source,
        reason_safe=body.reason_safe,
    )


# --- Mission Control (admin secret): aggregates + thin operator POST wrappers ----


@app.get("/internal/admin/mission-control/overview")
def mcc_overview(_: None = Depends(require_admin_service)) -> Dict[str, Any]:
    return mcc_svc.get_overview()


@app.get("/internal/admin/mission-control/workflows")
def mcc_workflows(
    _: None = Depends(require_admin_service),
    overall_status: Optional[str] = Query(None, max_length=24),
    current_step: Optional[str] = Query(None, max_length=64),
    has_failed_step: Optional[bool] = Query(None),
    stalled: Optional[bool] = Query(None),
    waiting_on: Optional[str] = Query(None, max_length=32),
    escalation_available: Optional[bool] = Query(None),
    limit: int = Query(75, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10_000),
) -> Dict[str, Any]:
    return mcc_svc.list_workflows(
        overall_status=overall_status,
        current_step=current_step,
        has_failed_step=has_failed_step,
        stalled=stalled,
        waiting_on=waiting_on,
        escalation_available=escalation_available,
        limit=limit,
        offset=offset,
    )


@app.get("/internal/admin/mission-control/workflows/{workflow_id}")
def mcc_workflow_detail(
    workflow_id: str,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    return mcc_svc.get_workflow_detail(workflow_id)


@app.get("/internal/admin/mission-control/exceptions")
def mcc_exceptions(
    _: None = Depends(require_admin_service),
    limit: int = Query(100, ge=1, le=300),
) -> Dict[str, Any]:
    return mcc_svc.list_exceptions(limit=limit)


@app.get("/internal/admin/mission-control/responses")
def mcc_responses(
    _: None = Depends(require_admin_service),
    needs_review_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0, le=10_000),
) -> Dict[str, Any]:
    return mcc_svc.list_responses_queue(
        limit=limit,
        offset=offset,
        needs_review_only=needs_review_only,
    )


@app.get("/internal/admin/mission-control/reminders")
def mcc_reminders(
    _: None = Depends(require_admin_service),
    status: Optional[str] = Query(
        None,
        description="Comma-separated: eligible,queued,sent,failed,skipped",
    ),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0, le=10_000),
) -> Dict[str, Any]:
    statuses = None
    if status:
        statuses = [s.strip()[:24] for s in status.split(",") if s.strip()]
    return mcc_svc.list_reminders_queue(statuses=statuses, limit=limit, offset=offset)


@app.get("/internal/admin/mission-control/audit")
def mcc_audit(
    _: None = Depends(require_admin_service),
    workflow_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0, le=10_000),
) -> Dict[str, Any]:
    return mcc_svc.list_admin_audit_global(
        workflow_id=workflow_id,
        limit=limit,
        offset=offset,
    )


@app.post("/internal/admin/mission-control/reminders/{reminder_id}/queue")
def mcc_admin_mc_reminder_queue(
    reminder_id: str,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    ok = rem_svc.queue_reminder(reminder_id)
    if not ok:
        return {
            "ok": False,
            "error": {
                "code": "QUEUE_FAILED",
                "messageSafe": "Reminder must be in eligible status to queue.",
            },
        }
    return {"ok": True, "reminderId": reminder_id}


@app.post("/internal/admin/mission-control/reminders/{reminder_id}/deliver")
def mcc_admin_mc_reminder_deliver(
    reminder_id: str,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    return rem_svc.deliver_reminder(reminder_id)


@app.post("/internal/admin/mission-control/workflows/{workflow_id}/reminder-candidates")
def mcc_admin_mc_reminder_candidates(
    workflow_id: str,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    return rem_svc.create_reminder_candidates_for_workflow(workflow_id)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "workflow-api"}
