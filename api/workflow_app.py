"""
FastAPI app: authoritative workflow HTTP API.

Authentication:
  - User endpoints: ``Authorization: Bearer <session_token>`` (see ``auth.validate_session``).
  - Customer session creation: ``POST /api/auth/login``, ``POST /api/auth/signup`` (same ``sessions`` table as Streamlit).
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
import os
import re
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.customer_web_static import (
    install_strip_workflow_api_prefix_middleware,
    mount_customer_web_dist_if_present,
    register_customer_web_status_route,
)
from api.workflow_deps import (
    get_owned_workflow,
    get_session_bearer_token,
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
from services.customer_response_service import (
    build_customer_response_metrics_payload,
    build_customer_responses_list_payload,
)
from services.workflow.response_flow_events import (
    RESPONSE_FLOW_STEP_ID,
    emit_response_flow_event,
)
from services.workflow.response_intake_service import intake_bureau_response
from services.workflow.repository import fetch_latest_active_workflow_id
from services.workflow.integrity_hints_service import build_integrity_hints
from services.workflow import hooks as workflow_hooks
import auth
import database as db
from services.customer_intake_summary import build_customer_intake_summary
from services.customer_letter_service import (
    get_letter_body_for_user,
    letter_generation_head_state,
    list_letters_for_workflow_customer,
    run_letter_generation,
    selected_review_claim_ids_from_workflow,
)
from services.customer_proof_service import (
    build_proof_context_payload,
    on_proof_attachment_step,
)
from services.customer_mail_service import (
    build_mail_context_payload,
    send_certified_letter_for_bureau,
)
from services.customer_tracking_service import build_tracking_context_payload
from services.workflow_payment_service import (
    build_payment_context,
    complete_payment_with_existing_letter_entitlements,
    needed_letters_from_workflow_session,
    reconcile_checkout_session_for_user,
    start_checkout_for_workflow,
    workflow_payment_head_state,
)
from services.customer_dispute_strategy import (
    build_dispute_strategy_payload,
    estimate_unique_bureaus_for_claims,
    filter_eligible_dispute_items,
    free_mode_bureau_cap_violation,
    load_compressed_review_claims_for_user,
    parse_workflow_metadata_value,
    previously_disputed_claim_ids_from_meta,
    save_dispute_selection_draft,
    validate_selected_against_eligible,
    workflow_head_step_id,
)

_logger = logging.getLogger(__name__)

_MAX_REPORT_UPLOAD_MB = 25


def _run_one_time_data_fixes():
    try:
        import database as _db
        with _db.get_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                "SELECT id FROM proof_uploads WHERE id IN (6, 7) AND user_id IS NULL"
            )
            orphaned = [r["id"] for r in cur.fetchall()]
            if orphaned:
                cur.execute(
                    "UPDATE proof_uploads SET user_id = 11 WHERE id IN (6, 7) AND user_id IS NULL"
                )
                conn.commit()
                _logger.info("Startup fix: reassigned %d orphaned proof uploads to user 11", len(orphaned))
            else:
                conn.rollback()

            cur.execute("SELECT mailings FROM entitlements WHERE user_id = 11")
            row = cur.fetchone()
            if row and (row["mailings"] or 0) == 0:
                cur.execute(
                    "UPDATE entitlements SET mailings = mailings + 3, updated_at = NOW() WHERE user_id = 11"
                )
                cur.execute(
                    "INSERT INTO entitlement_transactions "
                    "(user_id, transaction_type, ai_rounds, letters, mailings, source, note, created_at) "
                    "VALUES (11, 'credit', 0, 0, 3, 'admin_grant', "
                    "'Startup fix: mailing credits for restart-storm affected customer', NOW())"
                )
                conn.commit()
                _logger.info("Startup fix: granted 3 mailing credits to user 11")
            else:
                conn.rollback()
    except Exception:
        _logger.debug("Startup data fixes skipped or failed", exc_info=True)


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
    _run_one_time_data_fixes()
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
install_strip_workflow_api_prefix_middleware(app)
register_customer_web_status_route(app)

_engine = WorkflowEngine()


class InitBody(BaseModel):
    workflow_type: Optional[str] = Field(
        default=None,
        description="Defaults to dispute_linear_v1",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CustomerUxEventBody(BaseModel):
    """Trusted UX signals from React (user/workflow from session; no raw response text)."""

    event_name: str = Field(..., min_length=8, max_length=64)
    step_id: str = Field(default=RESPONSE_FLOW_STEP_ID, max_length=64)
    status: str = Field(default="ok", max_length=32)
    metadata: Dict[str, Any] = Field(default_factory=dict)


_CUSTOMER_UX_RESPONSE_EVENTS = frozenset(
    {
        "response_intake_page_viewed",
        "response_history_viewed",
        "response_intake_submit_attempted",
        "response_list_fetch_failed",
    }
)

_CUSTOMER_UX_REPORT_ACQUISITION_EVENTS = frozenset(
    {
        "report_acquisition_page_viewed",
        "idiq_option_selected",
        "free_report_option_selected",
        "upload_existing_report_selected",
        "idiq_bridge_viewed",
        "idiq_redirect_clicked",
    }
)

_CUSTOMER_UX_WHITELIST = _CUSTOMER_UX_RESPONSE_EVENTS | _CUSTOMER_UX_REPORT_ACQUISITION_EVENTS


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


class IntakeAcknowledgeReviewBody(BaseModel):
    """Optional echo of how many claims the user acknowledged (audit only)."""

    item_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional count for workflow completion summary",
    )


class DisputeSelectionDraftBody(BaseModel):
    draft_selected_review_claim_ids: List[str] = Field(default_factory=list, max_length=500)


class DisputeSelectionConfirmBody(BaseModel):
    selected_review_claim_ids: List[str] = Field(default_factory=list, max_length=500)


class PaymentCheckoutBody(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=80)


class PaymentReconcileBody(BaseModel):
    stripe_checkout_session_id: str = Field(..., min_length=8, max_length=255)


class MailFromAddressBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    address_line1: str = Field(..., min_length=1, max_length=200)
    address_line2: str = Field("", max_length=200)
    address_city: str = Field(..., min_length=1, max_length=120)
    address_state: str = Field(..., min_length=2, max_length=2)
    address_zip: str = Field(..., min_length=3, max_length=15)


class MailSendBureauBody(BaseModel):
    bureau: str = Field(..., min_length=2, max_length=40)
    from_address: MailFromAddressBody
    return_receipt: bool = True


def _payment_public_origin() -> str:
    return (
        (os.environ.get("WORKFLOW_CUSTOMER_APP_ORIGIN") or os.environ.get("PUBLIC_APP_ORIGIN") or "")
        .strip()
        .rstrip("/")
    )


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


@app.get("/api/workflows/active")
def get_active_workflow(
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Most recent active or failed workflow for the session user (for React resume)."""
    wid = fetch_latest_active_workflow_id(int(user["user_id"]))
    return {"workflowId": wid}


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


@app.get("/api/workflows/{workflow_id}/integrity-hints")
def get_integrity_hints(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    """
    Deterministic drift hints from DB + entitlements + proof + Lob + mail ledger.
    Used for recovery banners and next-action copy; not inferred on the client.
    """
    uid = int(session["user_id"])
    return build_integrity_hints(uid, workflow_id)


@app.get("/api/workflows/{workflow_id}/home-summary")
def get_home_summary(
    workflow_id: str,
    _session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    return build_home_summary(workflow_id)


@app.get("/api/workflows/{workflow_id}/intake/summary")
def get_intake_summary(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    """
    Parsed report + claims summary for the authenticated user (same pipeline as Streamlit).
    Bundled with current workflow resume envelope for React analyze/review.
    """
    uid = int(session["user_id"])
    return {
        "workflow": _engine.resume(workflow_id),
        "intake": build_customer_intake_summary(uid),
    }


@app.post("/api/workflows/{workflow_id}/intake/acknowledge-review")
def post_intake_acknowledge_review(
    workflow_id: str,
    body: IntakeAcknowledgeReviewBody,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    """
    Customer finished reviewing parsed claims; completes workflow step ``review_claims``
    (same hook as Streamlit battle plan).
    """
    uid = int(session["user_id"])
    workflow_hooks.notify_review_claims_completed(
        uid,
        workflow_id=workflow_id,
        item_count=body.item_count,
        audit_source="api",
    )
    return {"workflow": _engine.resume(workflow_id)}


def _http_detail(code: str, message_safe: str) -> Dict[str, Any]:
    return {"code": code, "messageSafe": message_safe}


def _auth_public_user_from_db_row(u: Dict[str, Any]) -> Dict[str, Any]:
    uid = u.get("id")
    if uid is None:
        uid = u.get("user_id")
    return {
        "id": int(uid),
        "email": str(u.get("email") or ""),
        "displayName": u.get("display_name"),
        "role": str(u.get("role") or "consumer"),
        "tier": str(u.get("tier") or "free"),
        "emailVerified": bool(u.get("email_verified")),
    }


def _signup_password_errors(password: str) -> Optional[str]:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isupper() for c in password):
        return "Password must include at least one uppercase letter."
    if not any(c.islower() for c in password):
        return "Password must include at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must include at least one number."
    return None


class AuthLoginBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=256)


class AuthSignupBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=256)
    display_name: str = Field(..., min_length=1, max_length=255)


class AuthVerifyEmailBody(BaseModel):
    code: str = Field(..., min_length=4, max_length=12)


@app.post("/api/auth/login")
def post_auth_login(body: AuthLoginBody) -> Dict[str, Any]:
    """Email/password sign-in; returns the same session token shape Streamlit stores (``sessions`` table)."""
    row = auth.authenticate_user(body.email.strip(), body.password)
    if row.get("error"):
        raise HTTPException(
            status_code=401,
            detail=_http_detail("LOGIN_FAILED", str(row["error"])),
        )
    uid = int(row["id"])
    token = auth.create_session(uid)
    try:
        db.log_activity(uid, "login", row.get("email", ""))
    except Exception:
        _logger.debug("log_activity login skipped", exc_info=True)
    row["email_verified"] = bool(row.get("email_verified"))
    return {"token": token, "user": _auth_public_user_from_db_row(row)}


@app.post("/api/auth/signup")
def post_auth_signup(body: AuthSignupBody) -> Dict[str, Any]:
    email = body.email.strip()
    if not re.match(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        email,
    ):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("INVALID_EMAIL", "Please enter a valid email address."),
        )
    pw_err = _signup_password_errors(body.password)
    if pw_err:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("INVALID_PASSWORD", pw_err),
        )
    row = auth.create_user(
        email,
        body.password,
        body.display_name.strip(),
    )
    if row.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("SIGNUP_FAILED", str(row["error"])),
        )
    uid = int(row["id"])
    token = auth.create_session(uid)
    try:
        db.log_activity(uid, "signup", row.get("email", ""))
    except Exception:
        _logger.debug("log_activity signup skipped", exc_info=True)
    row["email_verified"] = False
    return {"token": token, "user": _auth_public_user_from_db_row(row)}


@app.post("/api/auth/logout")
def post_auth_logout(token: str = Depends(get_session_bearer_token)) -> Dict[str, Any]:
    auth.delete_session(token)
    return {"ok": True}


@app.get("/api/auth/me")
def get_auth_me(user: Dict[str, Any] = Depends(get_session_user)) -> Dict[str, Any]:
    uid = int(user["user_id"])
    full = auth.get_user_by_id(uid)
    if not full:
        raise HTTPException(
            status_code=401,
            detail=_http_detail("INVALID_SESSION", "Session expired or invalid."),
        )
    full["email_verified"] = bool(user.get("email_verified"))
    return {"user": _auth_public_user_from_db_row(full)}


@app.post("/api/auth/verify-email")
def post_auth_verify_email(
    body: AuthVerifyEmailBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    uid = int(user["user_id"])
    result = auth.verify_email_code(uid, body.code)
    if result.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("VERIFY_FAILED", str(result["error"])),
        )
    return {"ok": True, "alreadyVerified": bool(result.get("already_verified"))}


@app.post("/api/auth/resend-verification")
def post_auth_resend_verification(
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    uid = int(user["user_id"])
    if auth.is_email_verified(uid):
        return {"ok": True, "alreadyVerified": True}
    code = auth.set_verification_code(uid)
    if not code:
        raise HTTPException(
            status_code=429,
            detail=_http_detail(
                "RESEND_LIMIT",
                "Please wait a few minutes before requesting another code.",
            ),
        )
    try:
        from resend_client import send_verification_email

        send_verification_email(
            user["email"],
            code,
            user.get("display_name"),
        )
    except Exception:
        _logger.exception("resend verification email failed")
        raise HTTPException(
            status_code=503,
            detail=_http_detail(
                "EMAIL_UNAVAILABLE",
                "Could not send verification email. Please try again later.",
            ),
        )
    return {"ok": True}


@app.get("/api/workflows/{workflow_id}/disputes/strategy")
def get_disputes_strategy(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Eligible dispute items grouped like Streamlit DISPUTES, plus entitlement hints and draft defaults.
    """
    uid = int(session["user_id"])
    payload = build_dispute_strategy_payload(uid, workflow_id, session_user=user)
    return {
        "workflow": _engine.resume(workflow_id),
        **payload,
    }


@app.put("/api/workflows/{workflow_id}/disputes/selection")
def put_dispute_selection_draft(
    workflow_id: str,
    body: DisputeSelectionDraftBody,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Persist checkbox draft under workflow metadata (does not advance the engine)."""
    head, phase = workflow_head_step_id(workflow_id)
    if phase == "done" or head != "select_disputes":
        raise HTTPException(
            status_code=409,
            detail=_http_detail(
                "WRONG_WORKFLOW_STEP",
                "Dispute selection is not open for this workflow.",
            ),
        )
    uid = int(session["user_id"])
    claims = load_compressed_review_claims_for_user(uid)
    meta = parse_workflow_metadata_value(session.get("metadata") if session else {})
    prev = previously_disputed_claim_ids_from_meta(meta)
    eligible = filter_eligible_dispute_items(
        claims, round_number=1, previously_disputed_ids=prev
    )
    eligible_ids = {rc.review_claim_id for rc in eligible}
    ok, err = validate_selected_against_eligible(
        list(body.draft_selected_review_claim_ids), eligible_ids
    )
    if not ok:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("INVALID_SELECTION", err),
        )
    save_dispute_selection_draft(workflow_id, list(body.draft_selected_review_claim_ids))
    return {"workflow": _engine.resume(workflow_id)}


@app.post("/api/workflows/{workflow_id}/disputes/selection/confirm")
def post_dispute_selection_confirm(
    workflow_id: str,
    body: DisputeSelectionConfirmBody,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Validate selection, persist ids on the session, complete ``select_disputes`` (same engine hook
    as Streamlit), and return the updated resume envelope.
    """
    head, phase = workflow_head_step_id(workflow_id)
    if phase == "done" or head != "select_disputes":
        raise HTTPException(
            status_code=409,
            detail=_http_detail(
                "WRONG_WORKFLOW_STEP",
                "Dispute selection is not open for this workflow.",
            ),
        )
    ids = [str(x).strip() for x in body.selected_review_claim_ids if str(x).strip()]
    if not ids:
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "SELECTION_REQUIRED",
                "Select at least one item to continue.",
            ),
        )
    uid = int(session["user_id"])
    claims = load_compressed_review_claims_for_user(uid)
    meta = parse_workflow_metadata_value(session.get("metadata") if session else {})
    prev = previously_disputed_claim_ids_from_meta(meta)
    eligible = filter_eligible_dispute_items(
        claims, round_number=1, previously_disputed_ids=prev
    )
    eligible_by_id = {rc.review_claim_id: rc for rc in eligible}
    eligible_ids = set(eligible_by_id.keys())
    ok, err = validate_selected_against_eligible(ids, eligible_ids)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("INVALID_SELECTION", err),
        )

    is_admin = auth.is_admin(user)
    ent = auth.get_entitlements(uid)
    letters_balance = int(ent.get("letters", 0) or 0)
    has_used_free = auth.has_used_free_letters(uid) if not is_admin else False
    using_free_mode = not is_admin and letters_balance == 0 and not has_used_free

    cap_msg = free_mode_bureau_cap_violation(
        eligible_by_id, ids, using_free_mode=using_free_mode
    )
    if cap_msg:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("FREE_PLAN_BUREAU_LIMIT", cap_msg),
        )

    bureaus = estimate_unique_bureaus_for_claims(eligible_by_id, ids)
    completed = workflow_hooks.complete_select_disputes_step(
        uid,
        workflow_id,
        selected_count=len(ids),
        bureaus=bureaus,
        selected_review_claim_ids=ids,
        audit_source="api",
    )
    if not completed:
        raise HTTPException(
            status_code=409,
            detail=_http_detail(
                "STEP_TRANSITION_FAILED",
                "Could not advance dispute selection. Refresh and try again.",
            ),
        )
    return {"workflow": _engine.resume(workflow_id)}


@app.get("/api/workflows/{workflow_id}/payment/context")
def get_payment_context(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Letter counts, catalog recommendation, entitlements, and payment step status for React."""
    uid = int(session["user_id"])
    ctx = build_payment_context(workflow_id, uid, is_admin=auth.is_admin(user))
    return {"workflow": _engine.resume(workflow_id), "payment": ctx}


@app.post("/api/workflows/{workflow_id}/payment/checkout")
def post_payment_checkout(
    workflow_id: str,
    body: PaymentCheckoutBody,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Create a Stripe Checkout session with ``workflow_id`` in metadata (same as Streamlit)."""
    head, phase, _ = workflow_payment_head_state(workflow_id)
    if phase == "done" or head != "payment":
        raise HTTPException(
            status_code=409,
            detail=_http_detail(
                "WRONG_WORKFLOW_STEP",
                "Payment is not the current step for this workflow.",
            ),
        )
    origin = _payment_public_origin()
    if not origin:
        raise HTTPException(
            status_code=503,
            detail=_http_detail(
                "CHECKOUT_RETURN_ORIGIN_MISSING",
                "Set WORKFLOW_CUSTOMER_APP_ORIGIN or PUBLIC_APP_ORIGIN to your customer app base URL (e.g. https://app.example.com).",
            ),
        )
    uid = int(session["user_id"])
    email = (user.get("email") or "").strip()
    if not email:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("EMAIL_REQUIRED", "Account email is required for checkout."),
        )
    success_url = f"{origin}/payment?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/payment?payment=cancelled"
    result = start_checkout_for_workflow(
        workflow_id=workflow_id,
        user_id=uid,
        user_email=email,
        product_id=body.product_id.strip(),
        success_url=success_url,
        cancel_url=cancel_url,
    )
    if result.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "CHECKOUT_FAILED",
                str(result.get("error", "checkout_error"))[:220],
            ),
        )
    return {
        "checkoutUrl": result.get("url"),
        "stripeCheckoutSessionId": result.get("session_id"),
        "workflow": _engine.resume(workflow_id),
    }


@app.post("/api/workflows/{workflow_id}/payment/reconcile")
def post_payment_reconcile(
    workflow_id: str,
    body: PaymentReconcileBody,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    After Stripe redirects back with ``session_id``, verify the session and apply entitlements +
    workflow payment completion (idempotent; same rules as Streamlit ``?payment=success``).
    """
    uid = int(session["user_id"])
    email = (user.get("email") or "").strip()
    out = reconcile_checkout_session_for_user(
        checkout_session_id=body.stripe_checkout_session_id.strip(),
        user_id=uid,
        user_email=email,
    )
    if not out.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "RECONCILE_FAILED",
                str(out.get("error", "reconcile_failed")),
            ),
        )
    wf_from_stripe = (out.get("workflowIdFromSession") or "").strip()
    if wf_from_stripe and wf_from_stripe != workflow_id:
        raise HTTPException(
            status_code=409,
            detail=_http_detail(
                "WORKFLOW_SESSION_MISMATCH",
                "This payment is tied to a different workflow.",
            ),
        )
    return {"workflow": _engine.resume(workflow_id), "reconcile": out}


@app.post("/api/workflows/{workflow_id}/payment/continue-with-credits")
def post_payment_continue_with_credits(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Complete the payment step without Stripe when letter balance already covers this round."""
    head, phase, _ = workflow_payment_head_state(workflow_id)
    if phase == "done" or head != "payment":
        raise HTTPException(
            status_code=409,
            detail=_http_detail(
                "WRONG_WORKFLOW_STEP",
                "Payment is not the current step for this workflow.",
            ),
        )
    uid = int(session["user_id"])
    needed = needed_letters_from_workflow_session(session)
    ok = complete_payment_with_existing_letter_entitlements(workflow_id, uid, needed)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "INSUFFICIENT_LETTERS",
                "Not enough letter credits to continue without purchasing.",
            ),
        )
    return {"workflow": _engine.resume(workflow_id)}


@app.get("/api/workflows/{workflow_id}/letters/context")
def get_letters_context(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Letter rows from DB + workflow step state for the React /letters step."""
    uid = int(session["user_id"])
    head, phase, lg_row = letter_generation_head_state(workflow_id)
    letters = list_letters_for_workflow_customer(uid)
    sel_ids = selected_review_claim_ids_from_workflow(session)
    return {
        "workflow": _engine.resume(workflow_id),
        "letters": letters,
        "lettersUi": {
            "workflowHeadStepId": head,
            "workflowPhase": phase,
            "letterGenerationStepStatus": lg_row.get("status") if lg_row else None,
            "letterGenerationCompleted": bool(lg_row and lg_row.get("status") == "completed"),
            "onLetterGenerationStep": head == "letter_generation" and phase == "active",
            "selectedReviewClaimCount": len(sel_ids),
        },
    }


@app.post("/api/workflows/{workflow_id}/letters/generate")
def post_letters_generate(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Run ``process_dispute_pipeline`` with DB-backed context (same engine as Streamlit GENERATING).
    Completes workflow step ``letter_generation`` on success.
    """
    uid = int(session["user_id"])
    result, err = run_letter_generation(
        uid,
        workflow_id,
        session_row=session,
        is_admin=auth.is_admin(user),
    )
    if err:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("LETTER_GENERATION_FAILED", err),
        )
    letters_out = result.get("letters") or {}
    readiness = result.get("readiness") or {}
    return {
        "workflow": _engine.resume(workflow_id),
        "generation": {
            "bureaus": [str(b).lower() for b in letters_out.keys() if b],
            "billing": result.get("billing"),
            "readinessSummary": {
                "includedDecisions": len(readiness.get("include_decisions") or []),
                "blockedDecisions": len(readiness.get("blocked_decisions") or []),
            },
        },
    }


@app.get("/api/workflows/{workflow_id}/letters/{letter_id}/content")
def get_letter_content(
    workflow_id: str,
    letter_id: int,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    """Full letter body for the signed-in owner (for preview modal)."""
    uid = int(session["user_id"])
    text = get_letter_body_for_user(uid, letter_id)
    if text is None:
        raise HTTPException(
            status_code=404,
            detail=_http_detail("LETTER_NOT_FOUND", "Letter not found."),
        )
    return {"letterText": text}


@app.get("/api/workflows/{workflow_id}/letters/bundle.txt")
def get_letters_bundle_txt(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Any:
    """Plain-text download of all current letters for the user (deduped per report+bureau)."""
    from fastapi.responses import PlainTextResponse

    uid = int(session["user_id"])
    rows = db.get_all_letters_for_user(uid)
    if not rows:
        return PlainTextResponse("No letters on file yet.\n", media_type="text/plain; charset=utf-8")
    dedup: Dict[Any, Dict[str, Any]] = {}
    for row in rows:
        key = (row.get("report_id"), (row.get("bureau") or "").lower())
        if key[1] and key not in dedup:
            dedup[key] = row
    parts: List[str] = []
    for row in sorted(dedup.values(), key=lambda r: (r.get("bureau") or "").lower()):
        lid = row.get("id")
        if lid is None:
            continue
        body = get_letter_body_for_user(uid, int(lid))
        if not body:
            continue
        title = (row.get("bureau") or "bureau").title()
        parts.append(f"{'=' * 12} {title} {'=' * 12}\n\n{body.strip()}\n")
    text = "\n\n".join(parts) if parts else "No letter bodies available.\n"
    return PlainTextResponse(text, media_type="text/plain; charset=utf-8")


@app.get("/api/workflows/{workflow_id}/proof/context")
def get_proof_context(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Proof document + signature flags and workflow step state (same DB rules as Streamlit proof page)."""
    uid = int(session["user_id"])
    return {
        "workflow": _engine.resume(workflow_id),
        "proof": build_proof_context_payload(uid, workflow_id),
    }


@app.post("/api/workflows/{workflow_id}/proof/upload")
async def post_proof_upload(
    workflow_id: str,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Upload government ID or address proof; runs ``doc_validator.validate_proof_document`` like Streamlit.
    Persists via ``database.save_proof_upload`` (triggers proof workflow hook when all requirements are met).
    """
    if not on_proof_attachment_step(workflow_id):
        raise HTTPException(
            status_code=409,
            detail=_http_detail(
                "WRONG_WORKFLOW_STEP",
                "Proof upload is not available for the current workflow step.",
            ),
        )
    raw = await file.read()
    max_size = 5 * 1024 * 1024
    if len(raw) > max_size:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("FILE_TOO_LARGE", "File must be under 5 MB."),
        )
    dt = (doc_type or "").strip().lower().replace("-", "_")
    if dt not in ("government_id", "address_proof"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "INVALID_DOC_TYPE",
                "doc_type must be government_id or address_proof.",
            ),
        )
    ctype = file.content_type or "application/octet-stream"
    from doc_validator import validate_proof_document

    val = validate_proof_document(raw, dt, ctype)
    if not val.get("valid"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "PROOF_VALIDATION_FAILED",
                str(val.get("reason") or "Document validation failed."),
            ),
        )
    uid = int(session["user_id"])
    fname = (file.filename or "upload").strip() or "upload"
    notes = (
        "Government-issued ID" if dt == "government_id" else "Proof of current address"
    )
    bureau = "government_id" if dt == "government_id" else "address_proof"
    db.save_proof_upload(
        uid,
        1,
        bureau,
        fname,
        ctype,
        notes=notes,
        file_data=raw,
        doc_type=dt,
        workflow_id=workflow_id,
    )
    return {
        "workflow": _engine.resume(workflow_id),
        "proof": build_proof_context_payload(uid, workflow_id),
    }


@app.post("/api/workflows/{workflow_id}/proof/signature")
async def post_proof_signature(
    workflow_id: str,
    file: UploadFile = File(...),
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Store a PNG signature (same ``user_signatures`` row as Streamlit); completes proof when ID+address+sig exist."""
    if not on_proof_attachment_step(workflow_id):
        raise HTTPException(
            status_code=409,
            detail=_http_detail(
                "WRONG_WORKFLOW_STEP",
                "Signature upload is not available for the current workflow step.",
            ),
        )
    raw = await file.read()
    max_sig = 2 * 1024 * 1024
    if len(raw) > max_sig:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("FILE_TOO_LARGE", "Signature image must be under 2 MB."),
        )
    ct = (file.content_type or "").lower()
    is_png_magic = len(raw) >= 8 and raw[:8] == b"\x89PNG\r\n\x1a\n"
    if not is_png_magic and "png" not in ct:
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "INVALID_SIGNATURE_FORMAT",
                "Signature must be a PNG image.",
            ),
        )
    uid = int(session["user_id"])
    db.save_user_signature(uid, raw, workflow_id=workflow_id)
    return {
        "workflow": _engine.resume(workflow_id),
        "proof": build_proof_context_payload(uid, workflow_id),
    }


@app.get("/api/workflows/{workflow_id}/mail/context")
def get_mail_context(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Mail readiness, Lob config, bureau send rows, and workflow mail-gate metadata (Streamlit send panel parity)."""
    uid = int(session["user_id"])
    return {
        "workflow": _engine.resume(workflow_id),
        "mail": build_mail_context_payload(
            uid,
            workflow_id,
            session_row=session,
            is_admin=auth.is_admin(user),
        ),
    }


@app.post("/api/workflows/{workflow_id}/mail/send-bureau")
def post_mail_send_bureau(
    workflow_id: str,
    body: MailSendBureauBody,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Send one certified letter via Lob (same stack as Streamlit ``send_mail``).
    Completes workflow ``mail``/``track`` when the mail gate is satisfied.
    """
    uid = int(session["user_id"])
    fa = body.from_address.model_dump()
    fa["address_state"] = str(fa.get("address_state") or "").strip().upper()[:2]
    result, err = send_certified_letter_for_bureau(
        uid,
        workflow_id,
        body.bureau.strip(),
        fa,
        body.return_receipt,
        session_row=session,
        is_admin=auth.is_admin(user),
    )
    if err:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("MAIL_SEND_BLOCKED", err),
        )
    if not result or not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "MAIL_SEND_FAILED",
                str((result or {}).get("error") or "Certified mail could not be sent."),
            ),
        )
    return {
        "workflow": _engine.resume(workflow_id),
        "lob": {
            "lobId": result.get("lob_id"),
            "trackingNumber": result.get("tracking_number"),
            "expectedDelivery": result.get("expected_delivery"),
            "isTest": result.get("is_test"),
        },
        "mail": build_mail_context_payload(
            uid,
            workflow_id,
            session_row=session,
            is_admin=auth.is_admin(user),
        ),
    }


@app.get("/api/workflows/{workflow_id}/tracking/context")
def get_tracking_context(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Post-send Lob rows per bureau, mail-gate metadata, workflow step flags, and ``build_home_summary`` hints."""
    uid = int(session["user_id"])
    return {
        "workflow": _engine.resume(workflow_id),
        "tracking": build_tracking_context_payload(
            uid,
            workflow_id,
            session_row=session,
        ),
    }


@app.get("/api/workflows/{workflow_id}/responses/metrics")
def get_workflow_response_metrics(
    workflow_id: str,
    _session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    """
    Compact aggregates from ``workflow_response_intake`` rows (same owner scope as list/intake).
    """
    payload = build_customer_response_metrics_payload(workflow_id)
    return {
        "workflow": _engine.resume(workflow_id),
        **payload,
    }


@app.get("/api/workflows/{workflow_id}/responses")
def get_workflow_responses(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    limit: int = Query(30, ge=1, le=50),
) -> Dict[str, Any]:
    """Recent ``workflow_response_intake`` rows for the owner (classification + escalation snapshot)."""
    uid = int(session["user_id"])
    try:
        payload = build_customer_responses_list_payload(workflow_id, limit=limit)
    except Exception:
        emit_response_flow_event(
            "response_list_fetch_failed",
            workflow_id=workflow_id,
            user_id=uid,
            status="error",
            source="backend",
            error_code="LIST_FETCH_FAILED",
            message_safe="Response list query failed.",
        )
        raise
    emit_response_flow_event(
        "response_list_fetched",
        workflow_id=workflow_id,
        user_id=uid,
        status="ok",
        source="backend",
        metadata={"count": payload["count"], "limit": limit},
    )
    return {
        "workflow": _engine.resume(workflow_id),
        **payload,
    }


@app.post("/api/workflows/{workflow_id}/events/customer-ux")
def post_customer_ux_event(
    workflow_id: str,
    body: CustomerUxEventBody,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    """
    Persist lightweight UX milestones for observability (mirrors workflow audit pipeline).
    """
    if body.event_name not in _CUSTOMER_UX_WHITELIST:
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "UNKNOWN_UX_EVENT",
                "Unsupported customer UX event name.",
            ),
        )
    uid = int(session["user_id"])
    emit_response_flow_event(
        body.event_name,
        workflow_id=workflow_id,
        user_id=uid,
        step_id=body.step_id or RESPONSE_FLOW_STEP_ID,
        status=(body.status or "ok")[:32],
        source="frontend",
        metadata=body.metadata,
    )
    return {"ok": True}


@app.post("/api/workflows/{workflow_id}/responses/intake")
def post_response_intake(
    workflow_id: str,
    body: ResponseIntakeBody,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    out = intake_bureau_response(
        workflow_id=workflow_id,
        user_id=int(session["user_id"]),
        source_type=body.source_type,
        response_channel=body.response_channel,
        parsed_summary=body.parsed_summary,
        storage_ref=body.storage_ref,
        linked_mailing_id=body.linked_mailing_id,
        linked_letter_id=body.linked_letter_id,
    )
    if not out.get("ok"):
        err = out.get("error") or {}
        code = str(err.get("code") or "INTAKE_FAILED")
        msg = str(err.get("messageSafe") or "Could not record this response.")
        status = 404 if code == "NOT_FOUND" else 403
        raise HTTPException(
            status_code=status,
            detail=_http_detail(code, msg),
        )
    return {**out, "workflow": _engine.resume(workflow_id)}


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


@app.post("/api/workflows/{workflow_id}/reports/upload")
async def post_workflow_report_upload(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    file: UploadFile = File(...),
    privacy_consent: str = Form("false"),
) -> Dict[str, Any]:
    """
    Upload one bureau credit-report PDF; runs ``services.report_pipeline.process_uploaded_reports``
    (same path as Streamlit). On success, workflow hooks complete ``upload`` and ``parse_analyze``.
    """
    consent = (privacy_consent or "").strip().lower()
    if consent not in ("1", "true", "yes", "on"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PRIVACY_CONSENT_REQUIRED",
                "messageSafe": "Privacy consent is required before upload.",
            },
        )

    raw = await file.read()
    max_bytes = _MAX_REPORT_UPLOAD_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "FILE_TOO_LARGE",
                "messageSafe": f"Maximum file size is {_MAX_REPORT_UPLOAD_MB} MB.",
            },
        )
    if not raw:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_FILE", "messageSafe": "Empty file."},
        )

    fname = (file.filename or "report.pdf").replace("\\", "/").split("/")[-1]
    if not fname.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail={"code": "NOT_PDF", "messageSafe": "A PDF file is required."},
        )

    uid = int(session["user_id"])
    try:
        from services.report_pipeline import process_uploaded_reports

        result = process_uploaded_reports(
            [(fname, raw)],
            {"user_id": uid, "workflow_id": workflow_id},
        )
    except Exception:
        _logger.exception("report upload pipeline failed for workflow %s", workflow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "PARSE_PIPELINE_ERROR",
                "messageSafe": "Report processing failed. Try again or use a different PDF.",
            },
        ) from None

    envelope = _engine.resume(workflow_id)
    skips = result.get("file_skips") or []
    processed = int(result.get("reports_processed") or 0)

    return {
        "ok": processed > 0 and len(skips) == 0,
        "reportsProcessed": processed,
        "fileSkips": skips,
        "workflow": envelope,
    }


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


class MailApprovalBody(BaseModel):
    user_id: int = Field(..., ge=1)
    actor_source: str = "admin"
    reason_safe: str = ""


@app.post("/internal/admin/mail/approve")
def internal_admin_approve_mail(
    body: MailApprovalBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    db.approve_mail_for_user(
        body.user_id,
        approved_by=body.actor_source,
        reason=body.reason_safe or None,
    )
    _logger.info(
        "Admin approved mail for user %d (actor=%s reason=%s)",
        body.user_id, body.actor_source, body.reason_safe,
    )
    return {"ok": True, "userId": body.user_id, "approved": True}


@app.post("/internal/admin/mail/revoke")
def internal_admin_revoke_mail(
    body: MailApprovalBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    revoked = db.revoke_mail_approval(body.user_id)
    _logger.info(
        "Admin revoked mail approval for user %d (revoked=%s actor=%s)",
        body.user_id, revoked, body.actor_source,
    )
    return {"ok": True, "userId": body.user_id, "revoked": revoked}


@app.get("/internal/admin/mail/approval-status/{user_id}")
def internal_admin_mail_approval_status(
    user_id: int,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    approved = db.is_mail_approved(user_id)
    return {"userId": user_id, "approved": approved}


class ReassignProofBody(BaseModel):
    proof_ids: List[int] = Field(..., min_length=1, max_length=50)
    target_user_id: int = Field(..., ge=1)
    actor_source: str = "admin"
    reason_safe: str = ""


@app.post("/internal/admin/proof/reassign-orphaned")
def internal_admin_reassign_proof(
    body: ReassignProofBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    if any(pid < 1 for pid in body.proof_ids):
        return {"ok": False, "error": {"code": "INVALID_PROOF_IDS"}}
    target = db.get_user_by_id(body.target_user_id) if hasattr(db, "get_user_by_id") else True
    if not target:
        return {"ok": False, "error": {"code": "USER_NOT_FOUND"}}
    updated = db.reassign_orphaned_proof_uploads(body.proof_ids, body.target_user_id)
    _logger.info(
        "Admin reassigned %d orphaned proof uploads to user %d (actor=%s reason=%s)",
        updated, body.target_user_id, body.actor_source, body.reason_safe,
    )
    return {"ok": True, "updatedCount": updated}


class GrantEntitlementsBody(BaseModel):
    user_id: int = Field(..., ge=1)
    ai_rounds: int = Field(0, ge=0)
    letters: int = Field(0, ge=0)
    mailings: int = Field(0, ge=0)
    actor_source: str = "admin"
    reason_safe: str = ""


@app.post("/internal/admin/entitlements/grant")
def internal_admin_grant_entitlements(
    body: GrantEntitlementsBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    target = db.get_user_by_id(body.user_id) if hasattr(db, "get_user_by_id") else True
    if not target:
        return {"ok": False, "error": {"code": "USER_NOT_FOUND"}}
    auth.add_entitlements(
        body.user_id,
        ai_rounds=body.ai_rounds,
        letters=body.letters,
        mailings=body.mailings,
        source="admin_grant",
        note=f"Admin grant: {body.reason_safe or 'manual'} (actor={body.actor_source})",
    )
    ent = auth.get_entitlements(body.user_id)
    _logger.info(
        "Admin granted entitlements to user %d: +%d ai, +%d letters, +%d mailings (actor=%s)",
        body.user_id, body.ai_rounds, body.letters, body.mailings, body.actor_source,
    )
    return {
        "ok": True,
        "entitlements": {
            "ai_rounds": ent.get("ai_rounds", 0),
            "letters": ent.get("letters", 0),
            "mailings": ent.get("mailings", 0),
        },
    }


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


mount_customer_web_dist_if_present(app, _logger)
