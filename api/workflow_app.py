"""
FastAPI app: authoritative workflow HTTP API.

**Product surface:** This module is the forward build target for customer and operator
HTTP contracts. Streamlit (`app.py`) is legacy reference/fallback until
``docs/STREAMLIT_RETIREMENT.md`` parity criteria are met — new endpoints and workflow
rules belong here (or in ``services/``), not in Streamlit session state.

Authentication:
  - User endpoints: ``Authorization: Bearer <session_token>`` (see ``auth.validate_session``).
  - Customer session creation: ``POST /api/auth/login``, ``POST /api/auth/signup`` (same ``sessions`` table as Streamlit).
  - Internal worker endpoints: header ``X-Workflow-Internal-Key`` or
    ``Authorization: Bearer <WORKFLOW_INTERNAL_API_SECRET>``.

Environment:
  - ``DATABASE_URL`` — Postgres connection string for **all** app data (auth, org, reports, workflow).
    Required whenever ``REPLIT_DEPLOYMENT=1`` or ``ENVIRONMENT=production``; startup fails if missing.
  - ``DB_BACKEND`` — ``auto`` (default) or ``postgres`` → workflow uses the same Postgres pool as ``database.get_db``.
    ``sqlite`` is **dev/tests only** (``DB_BACKEND=sqlite`` + ``WORKFLOW_SQLITE_PATH``); **forbidden** in production-like env.
  - ``WORKFLOW_SQLITE_PATH`` — optional SQLite file when ``DB_BACKEND=sqlite`` only (never used when deployed as production).
  - ``WORKFLOW_INTERNAL_API_SECRET`` — workers / reminder delivery batch (non-admin internal routes).
  - ``WORKFLOW_ADMIN_API_SECRET`` — required for ``/internal/admin/...`` routes.
  - ``WORKFLOW_REMINDER_FALLBACK_STUB=1`` — dev only: after email failure, mark sent with channel ``stub``.
    Ignored when ``REPLIT_DEPLOYMENT=1`` or ``ENVIRONMENT=production`` (reminders stay ``failed`` with audit).
  - ``RESEND_API_KEY`` + ``RESEND_FROM_EMAIL`` — verification and password emails (local: add to ``.env``).
  - ``WORKFLOW_DEV_EMAIL_HINTS=1`` — append Resend exception text to 503 ``messageSafe`` (local debug only).
  - Repo-root ``.env`` — loaded automatically when this module starts (before routes run). Gitignored.

Public clients cannot complete or fail steps over HTTP; use ``/internal/.../service-*``
with the internal secret from trusted workers.
"""

from __future__ import annotations


def _load_repo_dotenv() -> None:
    """Load permanent local secrets from repo-root ``.env`` (see ``.env.example``)."""
    import logging as _logging

    _env_log = _logging.getLogger(__name__)
    try:
        from pathlib import Path

        from dotenv import load_dotenv

        root = Path(__file__).resolve().parent.parent
        path = root / ".env"
        loaded_file = load_dotenv(path, override=True)
        _env_log.info(
            "Repo .env load: path=%s file_exists=%s load_dotenv_returned=%s",
            path,
            path.is_file(),
            loaded_file,
        )
    except ImportError:
        _env_log.warning("python-dotenv not installed; .env will not be auto-loaded")


_load_repo_dotenv()

import logging
import os
import re
import tempfile
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
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
    require_platform_admin,
)
from services.workflow.workflow_db_config import is_production_like
from services.workflow import admin_override_service as admin_svc
from services.workflow import recovery_execution_service as rec_exec
from services.workflow.engine import WorkflowEngine
from services.workflow.home_summary_service import build_home_summary
from services import architect_access_service as architect_access_svc
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
from services.workflow.repository import fetch_resume_workflow_id_for_user, fetch_session
from services.workflow.workflow_event_service import list_workflow_events
from services.workflow.integrity_hints_service import build_integrity_hints
from services.workflow import hooks as workflow_hooks
import auth
import database as db
from services.customer_intake_summary import build_customer_intake_summary
from services.customer_letter_service import (
    build_credit_command_plan_for_workflow,
    get_letter_body_for_user,
    letter_generation_head_state,
    list_letters_for_workflow_customer,
    run_letter_generation,
    selected_review_claim_ids_from_workflow,
)
from services.workflow.workflow_job_service import (
    JOB_TYPE_LETTER_GENERATION,
    JOB_TYPE_REPORT_UPLOAD_PARSE,
    create_job,
    get_job as wf_get_job,
    list_jobs as wf_list_jobs,
    public_job_view as wf_public_job_view,
)
from services.workflow.workflow_flow_gates import (
    ACTION_CREDIT_COMMAND_PLAN_VIEW,
    ACTION_CUSTOMER_UX_EVENT,
    ACTION_DISPUTES_SELECTION_CONFIRM,
    ACTION_DISPUTES_SELECTION_DRAFT,
    ACTION_DISPUTES_STRATEGY_VIEW,
    ACTION_HOME_SUMMARY_VIEW,
    ACTION_INTEGRITY_HINTS_VIEW,
    ACTION_INTAKE_SUMMARY_VIEW,
    ACTION_LETTER_BODY_READ,
    ACTION_LETTER_GENERATION_RUN,
    ACTION_LETTERS_BUNDLE_READ,
    ACTION_LETTERS_CONTEXT_VIEW,
    ACTION_MAIL_CONTEXT,
    ACTION_MAIL_SEND_BUREAU,
    ACTION_PAYMENT_CHECKOUT,
    ACTION_PAYMENT_CONTEXT,
    ACTION_PAYMENT_CONTINUE_CREDITS,
    ACTION_PAYMENT_RECONCILE,
    ACTION_PROOF_CONTEXT,
    ACTION_PROOF_SIGNATURE,
    ACTION_PROOF_UPLOAD,
    ACTION_REPORT_PDF_UPLOAD,
    ACTION_DISPUTES_BEGIN_NEXT_ROUND,
    ACTION_ESCALATION_LAYER_VIEW,
    ACTION_ESCALATION_UX_UPDATE,
    ACTION_RESPONSES_INTAKE,
    ACTION_RESPONSES_LIST,
    ACTION_RESPONSES_METRICS,
    ACTION_REVIEW_CLAIMS_ACK,
    ACTION_TRACKING_CONTEXT,
    ACTION_WORKFLOW_JOB_GET,
    ACTION_WORKFLOW_JOBS_LIST,
    FlowEnforcementError,
    INTERNAL_ASYNC_STATE,
    INTERNAL_REMINDER_CANDIDATES,
    INTERNAL_SERVICE_COMPLETE,
    INTERNAL_SERVICE_FAIL,
    OPERATOR_CLEAR_STALLED,
    OPERATOR_MC_REMINDER_CANDIDATES,
    OPERATOR_PAYMENT_WAIVED,
    OPERATOR_RECOVERY_MAIL_RETRY,
    OPERATOR_RECOVERY_RECORD,
    OPERATOR_RECOVERY_RESUME,
    OPERATOR_RECOVERY_RETRY_STEP,
    OPERATOR_REOPEN_STEP,
    TRUST_INTERNAL,
    TRUST_OPERATOR,
    enforce_customer_action,
    enforce_flow_action,
    enforce_step_start,
    flow_violation_detail,
)
from services.customer_proof_service import build_proof_context_payload
from services.customer_mail_service import (
    build_mail_context_payload,
    send_certified_letter_for_bureau,
)
from services.customer_tracking_service import build_tracking_context_payload
from services.workflow.escalation_layer_service import build_escalation_layer_payload
from services.workflow.escalation_ux_payload import persist_escalation_ux_state
from services.workflow_payment_service import (
    build_payment_context,
    complete_payment_with_existing_letter_entitlements,
    needed_letters_from_workflow_session,
    reconcile_checkout_session_for_user,
    start_checkout_for_workflow,
)
from services.demo_org_bridge_service import convert_demo_lead_to_org
from services.org_program_session_service import (
    create_program_session,
    list_program_sessions,
    patch_enrollment_workshop,
    set_enrollment_session,
    update_program_session,
)
from services.org_workshop_desk_service import build_workshop_desk
from services.org_program_workflow_service import (
    advance_org_program_steps,
    ensure_org_program_workflow,
)
from services.org_commerce_service import (
    build_org_program_billing_snapshot,
    reconcile_org_program_activation_checkout,
    start_org_program_activation_checkout,
)
from services.org_service import (
    add_organization_member,
    create_organization,
    get_organization,
    list_organization_members,
    org_allows_participant_program_access,
    update_organization,
    user_is_active_instructor_for_org,
    user_is_active_org_admin_for_org,
)
from services.org_program_visibility_service import (
    build_org_outcomes_aggregate,
    build_org_progress_aggregate,
    get_org_program_participant_detail,
    list_org_program_participants,
)
from services.program_enrollment_service import (
    build_me_org_program_payload,
    create_program_enrollment,
    get_enrollment,
    get_program_workflow_id_for_enrollment,
    list_enrollments_for_org,
)
from services.report_upload_object_storage import ReportUploadStorageError
from services.report_upload_session_service import (
    ReportUploadFinalizeError,
    create_report_upload_session,
    finalize_direct_storage_report_upload,
)
from services.report_upload_staging import (
    MAX_MERGED_REPORT_MB,
    MAX_REPORT_PARTS,
    MAX_REPORT_UPLOAD_MB,
    MAX_SINGLE_REPORT_UPLOAD_MB,
    ReportUploadStagingError,
    stream_upload_part_to_temp_file,
)
from services.program_progress_service import (
    apply_instructor_program_override,
    build_me_program_progress_payload,
    effective_findings_ready,
    effective_selections_saved,
    effective_upload_done,
    participant_forward_paused,
)
from services.public_demo_service import (
    list_demo_scenarios_public,
    public_demo_config_error,
    run_public_fixture_demo,
)
from services.me_org_report_service import (
    build_findings_payload,
    get_enrolled_org_participant_context,
)
from services.me_org_dispute_service import (
    build_program_dispute_options,
    get_dispute_selections_response,
    resolve_report_id_for_participant,
    run_program_letter_generation,
    save_program_dispute_selections,
)
from services.customer_dispute_strategy import (
    build_dispute_strategy_payload,
    dispute_selection_context_from_meta,
    estimate_unique_bureaus_for_claims,
    filter_eligible_dispute_items,
    free_mode_bureau_cap_violation,
    load_compressed_review_claims_for_user,
    parse_workflow_metadata_value,
    save_dispute_selection_draft,
    validate_selected_against_eligible,
)

_logger = logging.getLogger(__name__)


def _log_resend_env_at_startup() -> None:
    """Log whether Resend-related env is visible in this process (no API key material)."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    key_set = bool((os.environ.get("RESEND_API_KEY") or "").strip())
    from_email = (os.environ.get("RESEND_FROM_EMAIL") or "").strip()
    _logger.info(
        "Resend env in process: RESEND_API_KEY set=%s | RESEND_FROM_EMAIL=%s | repo .env exists=%s",
        key_set,
        repr(from_email) if from_email else "unset",
        env_path.is_file(),
    )


_public_demo_hit_times: Dict[str, List[float]] = {}
_public_demo_lead_hit_times: Dict[str, List[float]] = {}


def _public_demo_client_ip(request: Request) -> str:
    xf = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if xf:
        return xf[:128]
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _public_demo_lead_rate_ok(request: Request) -> bool:
    raw = (os.environ.get("PUBLIC_DEMO_LEAD_RATE_PER_MINUTE") or "8").strip()
    try:
        limit = max(1, min(30, int(raw)))
    except ValueError:
        limit = 8
    ip = _public_demo_client_ip(request)
    now = time.time()
    window = 60.0
    arr = _public_demo_lead_hit_times.setdefault(ip, [])
    arr[:] = [t for t in arr if t > now - window]
    if len(arr) >= limit:
        return False
    arr.append(now)
    return True


def _public_demo_rate_ok(request: Request) -> bool:
    raw = (os.environ.get("PUBLIC_DEMO_RATE_PER_MINUTE") or "12").strip()
    try:
        limit = max(1, min(60, int(raw)))
    except ValueError:
        limit = 12
    ip = _public_demo_client_ip(request)
    now = time.time()
    window = 60.0
    arr = _public_demo_hit_times.setdefault(ip, [])
    arr[:] = [t for t in arr if t > now - window]
    if len(arr) >= limit:
        return False
    arr.append(now)
    return True


def _enforce_public_demo_secret(x_public_demo_secret: Optional[str]) -> None:
    expected = (os.environ.get("PUBLIC_DEMO_SECRET") or "").strip()
    if not expected:
        return
    got = (x_public_demo_secret or "").strip()
    if got != expected:
        raise HTTPException(
            status_code=403,
            detail=_http_detail(
                "DEMO_SECRET_INVALID",
                "Demo access is restricted.",
            ),
        )


def _demo_email_looks_valid(email: str) -> bool:
    s = (email or "").strip().lower()
    if len(s) < 5 or "@" not in s:
        return False
    local, _, domain = s.partition("@")
    if not local or not domain or "." not in domain:
        return False
    return True


def _demo_phone_has_digits(phone: str) -> bool:
    return sum(1 for c in (phone or "") if c.isdigit()) >= 7


@asynccontextmanager
async def _workflow_api_lifespan(_app: FastAPI):
    """
    Align with Streamlit's ``database.init_database()`` so workflow DDL exists.
    Uvicorn-only processes previously skipped this; Mission Control SQL then
    failed with undefined-table errors (HTTP 500).

    If the database is unreachable (e.g. ``DATABASE_URL`` points at localhost but Postgres is not running),
    we fail here so operators see a startup error instead of HTTP 500 on the first auth request.
    """
    _log_resend_env_at_startup()
    import database as db

    db.init_database()
    if is_production_like():
        _stub = (os.environ.get("WORKFLOW_REMINDER_FALLBACK_STUB") or "").strip().lower()
        if _stub in ("1", "true", "yes", "on"):
            _logger.warning(
                "WORKFLOW_REMINDER_FALLBACK_STUB is enabled in a production-like environment; "
                "reminder delivery still records failures (stub success is not applied). "
                "Unset the flag to avoid misleading configuration."
            )
    _w = (os.environ.get("WORKFLOW_JOB_WORKER_ENABLED") or "1").strip().lower()
    if _w not in ("0", "false", "no", "off"):
        from services.workflow.workflow_job_worker import start_job_worker

        start_job_worker()
    yield
    try:
        from services.workflow.workflow_job_worker import stop_job_worker

        stop_job_worker()
    except Exception:
        _logger.debug("job worker stop skipped", exc_info=True)


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


def _envelope_with_progression(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attach reader-facing progression slices to a workflow resume envelope.

    **Contract:** ``canonicalProgression`` is the authoritative progression JSON for clients;
    ``progression`` is the slim mirror. Do not return bare envelopes for routes that expose
    step state to the customer app.
    """
    from services.workflow.progression_api import (
        build_canonical_progression_envelope_from_resume,
        unified_progression_from_workflow_envelope,
    )

    return {
        **envelope,
        "progression": unified_progression_from_workflow_envelope(envelope),
        "canonicalProgression": build_canonical_progression_envelope_from_resume(envelope),
    }


def _workflow_payload_with_progression(workflow_id: str) -> Dict[str, Any]:
    """Resume once; attach ``workflow`` + ``progression`` + ``canonicalProgression`` (authoritative: latter)."""
    env = _engine.resume(workflow_id)
    from services.workflow.progression_api import (
        build_canonical_progression_envelope_from_resume,
        unified_progression_from_workflow_envelope,
    )

    return {
        "workflow": env,
        "progression": unified_progression_from_workflow_envelope(env),
        "canonicalProgression": build_canonical_progression_envelope_from_resume(env),
    }


def _me_org_engine_bundle(ctx: Dict[str, Any], uid: int) -> Optional[Dict[str, Any]]:
    """One resume read → slim progression + full canonical envelope for org participant."""
    from services.program_enrollment_service import get_program_workflow_id_for_enrollment
    from services.workflow.progression_api import (
        build_canonical_progression_envelope_from_resume,
        unified_progression_from_workflow_envelope,
    )

    eid = ctx.get("organization_program_enrollment_id")
    if eid is None:
        return None
    wid = get_program_workflow_id_for_enrollment(int(eid))
    if not wid:
        return None
    env = _engine.resume(wid)
    return {
        "progression": unified_progression_from_workflow_envelope(env),
        "canonicalProgression": build_canonical_progression_envelope_from_resume(
            env, surface_override="org_program"
        ),
    }


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


class EscalationUxStateBody(BaseModel):
    """Mark escalation toolkit steps reviewed / proceeded (metadata only)."""

    action_id: str = Field(..., min_length=4, max_length=80, alias="actionId")
    reviewed: bool = False
    proceeded: bool = False

    model_config = {"populate_by_name": True}


class ReportUploadFinalizeBody(BaseModel):
    """Finalize direct-to-object-storage upload → ``report_upload_parse`` job."""

    upload_id: str = Field(..., alias="uploadId", min_length=32, max_length=40)
    byte_size: int = Field(..., alias="byteSize", gt=0)
    sha256_hex: str = Field(..., alias="sha256Hex", min_length=64, max_length=64)

    model_config = {"populate_by_name": True}


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
        description=(
            "Safe structured hints: summary_safe, outcome_keywords, claim_outcomes, "
            "item_outcomes[{reviewClaimId,bureauOutcome}] with bureauOutcome in "
            "deleted|updated|verified|no_response"
        ),
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


class PublicDemoRunBody(BaseModel):
    """Guest demo: run fixture PDF through the real pipeline (dedicated demo DB user)."""

    scenario_id: str = Field(..., alias="scenarioId", min_length=2, max_length=64)

    model_config = {"populate_by_name": True}


class PublicDemoLeadBody(BaseModel):
    """Post-demo lead capture (workshops / follow-up). Stored in ``demo_leads``."""

    name: str = Field(..., min_length=2, max_length=200)
    email: str = Field(..., min_length=5, max_length=255)
    phone: str = Field(..., min_length=7, max_length=40)
    scenario_id: Optional[str] = Field(None, alias="scenarioId", max_length=64)
    workflow_id: Optional[str] = Field(None, alias="workflowId", max_length=80)
    intent: Optional[str] = Field(None, max_length=64)
    organization_name: Optional[str] = Field(None, alias="organizationName", max_length=200)
    audience_note: Optional[str] = Field(None, alias="audienceNote", max_length=500)
    referrer_name: Optional[str] = Field(None, alias="referrerName", max_length=200)

    model_config = {"populate_by_name": True}


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


class ArchitectAccessApplyBody(BaseModel):
    """Admin-only: seed real state and return a normal session token for the fixture user."""

    model_config = {"populate_by_name": True}

    scenario_id: str = Field(..., alias="scenarioId", min_length=4, max_length=80)
    reset_consumer_workflow: bool = Field(default=True, alias="resetConsumerWorkflow")


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


class OrgProgramBillingReconcileBody(BaseModel):
    stripe_checkout_session_id: str = Field(
        ...,
        min_length=8,
        max_length=255,
        alias="stripeCheckoutSessionId",
    )

    model_config = {"populate_by_name": True}


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
    env = _engine.init_workflow(
        user_id=int(user["user_id"]),
        workflow_type=body.workflow_type,
        metadata=body.metadata or None,
    )
    return _envelope_with_progression(env)


@app.get("/api/workflows/active")
def get_active_workflow(
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Workflow id for React resume: prefers active/failed, else latest completed (same program family)
    so tracking, responses, and follow-on dispute rounds stay addressable.
    """
    wid = fetch_resume_workflow_id_for_user(int(user["user_id"]))
    return {"workflowId": wid}


@app.get("/api/workflows/{workflow_id}/state")
def get_state(
    workflow_id: str,
    _session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    return _envelope_with_progression(_engine.get_state(workflow_id))


@app.get("/api/workflows/{workflow_id}/resume")
def get_resume(
    workflow_id: str,
    _session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    return _envelope_with_progression(_engine.resume(workflow_id))


@app.get("/api/workflows/{workflow_id}/integrity-hints")
def get_integrity_hints(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    """
    Deterministic drift hints from DB + entitlements + proof + Lob + mail ledger.
    Used for recovery banners and next-action copy; not inferred on the client.
    """
    try:
        enforce_customer_action(workflow_id, ACTION_INTEGRITY_HINTS_VIEW)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    return build_integrity_hints(uid, workflow_id)


@app.get("/api/workflows/{workflow_id}/home-summary")
def get_home_summary(
    workflow_id: str,
    _session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    try:
        enforce_customer_action(workflow_id, ACTION_HOME_SUMMARY_VIEW)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    try:
        enforce_customer_action(workflow_id, ACTION_INTAKE_SUMMARY_VIEW)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    return {
        **_workflow_payload_with_progression(workflow_id),
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
    try:
        enforce_customer_action(workflow_id, ACTION_REVIEW_CLAIMS_ACK)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    workflow_hooks.notify_review_claims_completed(
        uid,
        workflow_id=workflow_id,
        item_count=body.item_count,
        audit_source="api",
    )
    return _workflow_payload_with_progression(workflow_id)


def _http_detail(code: str, message_safe: str) -> Dict[str, Any]:
    return {"code": code, "messageSafe": message_safe}


def _raise_finalize_error(e: ReportUploadFinalizeError) -> None:
    raise HTTPException(
        status_code=e.http_status,
        detail=_http_detail(e.code, e.message_safe),
    ) from None


def _report_upload_session_api_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Shared shape for direct-to-storage session creation (retail + org)."""
    return {
        "ok": True,
        "uploadId": payload["uploadId"],
        "uploadUrl": payload["uploadUrl"],
        "objectKey": payload["objectKey"],
        "constraints": {
            "contentType": "application/pdf",
            "maxSingleFileBytes": MAX_SINGLE_REPORT_UPLOAD_MB * 1024 * 1024,
            "maxMergedBytes": MAX_MERGED_REPORT_MB * 1024 * 1024,
            "maxPartBytes": MAX_REPORT_UPLOAD_MB * 1024 * 1024,
            "maxParts": MAX_REPORT_PARTS,
        },
        "presignedExpiresIn": payload.get("presignedExpiresIn"),
        "sessionExpiresAt": payload.get("expiresAt"),
    }


async def _stage_report_upload_parts_to_temp(
    *,
    file: Optional[UploadFile],
    files: Optional[List[UploadFile]],
) -> tuple[List[str], List[str], List[int], List[str]]:
    """
    Stream each uploaded part to a temp file with incremental SHA-256, ``fsync``, and
    on-disk size verification. PDF merge/split runs in the worker after
    ``partByteSizes`` / ``partSha256Hex`` checks (see ``workflow_job_worker``).
    """
    uploads: List[UploadFile] = []
    if files:
        uploads = [u for u in files if u is not None][:MAX_REPORT_PARTS]
    elif file is not None:
        uploads = [file]
    if not uploads:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("NO_FILE", "A PDF file is required."),
        )
    if len(uploads) > MAX_REPORT_PARTS:
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "TOO_MANY_PARTS",
                f"At most {MAX_REPORT_PARTS} PDF parts per upload.",
            ),
        )

    chunk_max = MAX_REPORT_UPLOAD_MB * 1024 * 1024
    max_single = MAX_SINGLE_REPORT_UPLOAD_MB * 1024 * 1024
    multi = len(uploads) > 1
    paths: List[str] = []
    names: List[str] = []
    sizes: List[int] = []
    hashes: List[str] = []
    try:
        for uf in uploads:
            fname = (uf.filename or "part.pdf").replace("\\", "/").split("/")[-1]
            if not fname.lower().endswith(".pdf"):
                raise HTTPException(
                    status_code=400,
                    detail=_http_detail("NOT_PDF", "A PDF file is required."),
                )
            max_b = chunk_max if multi else max_single
            too_large = (
                f"Each PDF part must be at most {MAX_REPORT_UPLOAD_MB} MB when uploading multiple parts."
                if multi
                else f"Maximum upload size is {MAX_SINGLE_REPORT_UPLOAD_MB} MB."
            )
            try:
                pth, sz, hx = await stream_upload_part_to_temp_file(
                    uf,
                    max_bytes=max_b,
                    too_large_message=too_large,
                )
            except ReportUploadStagingError as e:
                raise HTTPException(
                    status_code=e.http_status,
                    detail=_http_detail(e.code, e.message_safe),
                ) from e
            paths.append(pth)
            names.append(fname)
            sizes.append(sz)
            hashes.append(hx)
    except HTTPException:
        for p in paths:
            try:
                os.unlink(p)
            except OSError:
                pass
        raise
    except Exception:
        for p in paths:
            try:
                os.unlink(p)
            except OSError:
                pass
        raise
    return paths, names, sizes, hashes


def _raise_flow_violation(e: FlowEnforcementError) -> None:
    """Flow gate failure: 404 when workflow missing, else 409 with structured detail."""
    status = 404 if e.code == "NOT_FOUND" else 409
    raise HTTPException(status_code=status, detail=flow_violation_detail(e)) from None


def _dev_email_error_hint(exc: Exception) -> str:
    """Optional short hint for local debugging (set WORKFLOW_DEV_EMAIL_HINTS=1)."""
    if (os.environ.get("WORKFLOW_DEV_EMAIL_HINTS") or "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        return ""
    msg = str(exc).strip().replace("\n", " ")
    return msg[:280] + ("..." if len(msg) > 280 else "")


def _public_organization_record(org: Dict[str, Any]) -> Dict[str, Any]:
    """CamelCase org payload for /api/orgs responses."""
    return {
        "id": int(org["id"]),
        "name": org.get("name"),
        "status": org.get("status"),
        "contactEmail": org.get("contact_email"),
        "contactPhone": org.get("contact_phone"),
        "programCode": org.get("program_code"),
        "onboardingStage": org.get("onboarding_stage"),
        "paymentAccess": org.get("payment_access"),
        "programAccessActivatedAt": org.get("program_access_activated_at"),
        "createdAt": org.get("created_at"),
        "updatedAt": org.get("updated_at"),
    }


def _public_org_membership_record(m: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": int(m["id"]),
        "organizationId": int(m["organization_id"]),
        "userId": int(m["user_id"]),
        "role": m.get("role"),
        "status": m.get("status"),
        "createdAt": m.get("created_at"),
        "updatedAt": m.get("updated_at"),
        "email": m.get("email"),
        "displayName": m.get("display_name"),
    }


def _public_org_enrollment_record(e: Dict[str, Any]) -> Dict[str, Any]:
    """CamelCase enrollment for list/create (instructor/admin; may include email)."""
    out: Dict[str, Any] = {
        "id": int(e["id"]),
        "organizationId": int(e["organization_id"]),
        "userId": int(e["user_id"]),
        "status": e.get("status"),
        "enrolledAt": e.get("enrolled_at"),
        "activatedAt": e.get("activated_at"),
        "completedAt": e.get("completed_at"),
        "createdAt": e.get("created_at"),
        "updatedAt": e.get("updated_at"),
    }
    if "session_id" in e:
        out["sessionId"] = e.get("session_id")
    if "session_checked_in_at" in e:
        out["sessionCheckedInAt"] = e.get("session_checked_in_at")
    if "session_workshop_complete_at" in e:
        out["sessionWorkshopCompleteAt"] = e.get("session_workshop_complete_at")
    if "email" in e:
        out["email"] = e.get("email")
    if "display_name" in e:
        out["displayName"] = e.get("display_name")
    return out


def _public_org_session_record(s: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": int(s["id"]),
        "organizationId": int(s["organization_id"]),
        "name": s.get("name"),
        "state": s.get("state"),
        "scheduledStartsAt": s.get("scheduled_starts_at"),
        "startedAt": s.get("started_at"),
        "endedAt": s.get("ended_at"),
        "createdAt": s.get("created_at"),
        "updatedAt": s.get("updated_at"),
    }


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
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        alias="displayName",
    )

    model_config = {"populate_by_name": True}


class AuthVerifyEmailBody(BaseModel):
    code: str = Field(..., min_length=4, max_length=12)


class AuthForgotPasswordBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)


class AuthResetPasswordBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    code: str = Field(..., min_length=4, max_length=12)
    password: str = Field(..., min_length=8, max_length=256)


class OrgCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class OrgMemberCreateBody(BaseModel):
    """Attach an existing account to the org. Provide ``userId`` or ``email`` (not both required; userId wins)."""

    user_id: Optional[int] = Field(default=None, gt=0, alias="userId")
    email: Optional[str] = Field(default=None, max_length=255)
    role: Literal["org_instructor", "org_user", "org_admin"]
    enroll_in_program: bool = Field(
        default=True,
        alias="enrollInProgram",
        description="For org_user: create program enrollment if missing (default true).",
    )

    model_config = {"populate_by_name": True}


class OrgPatchBody(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    contact_email: Optional[str] = Field(default=None, max_length=255, alias="contactEmail")
    contact_phone: Optional[str] = Field(default=None, max_length=80, alias="contactPhone")
    program_code: Optional[str] = Field(default=None, max_length=64, alias="programCode")
    onboarding_stage: Optional[str] = Field(default=None, max_length=32, alias="onboardingStage")
    payment_access: Optional[Literal["full", "locked", "trial"]] = Field(
        default=None, alias="paymentAccess"
    )
    status: Optional[str] = Field(default=None, max_length=32)

    model_config = {"populate_by_name": True}


class OrgProgramSessionCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class OrgProgramSessionPatchBody(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    state: Optional[Literal["draft", "scheduled", "active", "completed"]] = None


class OrgEnrollmentSessionBody(BaseModel):
    session_id: Optional[int] = Field(default=None, alias="sessionId")

    model_config = {"populate_by_name": True}


class OrgEnrollmentWorkshopBody(BaseModel):
    checked_in: Optional[bool] = Field(default=None, alias="checkedIn")
    workshop_complete: Optional[bool] = Field(default=None, alias="workshopComplete")

    model_config = {"populate_by_name": True}


class DemoLeadConvertToOrgBody(BaseModel):
    organization_name: str = Field(..., min_length=1, max_length=255, alias="organizationName")


class OrgProgramEnrollmentCreateBody(BaseModel):
    user_id: int = Field(..., gt=0, alias="userId")
    status: Literal[
        "enrolled", "active", "paused", "completed", "withdrawn"
    ] = Field(default="enrolled")

    model_config = {"populate_by_name": True}


class MeDisputeSelectionsBody(BaseModel):
    report_id: int = Field(..., gt=0, alias="reportId")
    selected_review_claim_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=500,
        alias="selectedReviewClaimIds",
    )

    model_config = {"populate_by_name": True}


class MeGenerateLettersBody(BaseModel):
    report_id: Optional[int] = Field(default=None, gt=0, alias="reportId")

    model_config = {"populate_by_name": True}


class InstructorProgramOverrideBody(BaseModel):
    action: Literal["pause", "resume", "advance", "reset"] = Field(
        ...,
        description="pause | resume | advance | reset (advance/reset require targetStep).",
    )
    target_step: Optional[str] = Field(
        default=None,
        alias="targetStep",
        description="One of enrollment, upload, findings_ready, selections_saved, letters_generated.",
    )
    reason_safe: Optional[str] = Field(
        default=None,
        max_length=500,
        alias="reasonSafe",
    )

    model_config = {"populate_by_name": True}


def _require_org_read_access(user: Dict[str, Any], org_id: int) -> None:
    """platform_admin, org_instructor, or org_admin (buyer visibility) for this org."""
    if (user.get("role") or "").strip() == "admin":
        return
    uid = int(user["user_id"])
    if user_is_active_instructor_for_org(uid, org_id):
        return
    if user_is_active_org_admin_for_org(uid, org_id):
        return
    raise HTTPException(
        status_code=403,
        detail=_http_detail(
            "ORG_ACCESS_DENIED",
            "You do not have access to this organization.",
        ),
    )


def _require_org_program_operator(user: Dict[str, Any], org_id: int) -> None:
    """Platform admin, org instructor, or org admin (rosters, sessions, assignments)."""
    if (user.get("role") or "").strip() == "admin":
        return
    uid = int(user["user_id"])
    if user_is_active_instructor_for_org(uid, org_id):
        return
    if user_is_active_org_admin_for_org(uid, org_id):
        return
    raise HTTPException(
        status_code=403,
        detail=_http_detail(
            "ORG_INSTRUCTOR_REQUIRED",
            "Active organization instructor or admin role is required.",
        ),
    )


def _require_org_billing_admin(user: Dict[str, Any], org_id: int) -> None:
    """Platform admin or org buyer (org_admin seat) for org Stripe activation checkout."""
    if (user.get("role") or "").strip() == "admin":
        return
    uid = int(user["user_id"])
    if user_is_active_org_admin_for_org(uid, org_id):
        return
    raise HTTPException(
        status_code=403,
        detail=_http_detail(
            "ORG_BILLING_ADMIN_REQUIRED",
            "Organization billing requires an organization admin seat (or platform admin).",
        ),
    )


def _require_org_program_payment_access(ctx: Dict[str, Any]) -> None:
    org = get_organization(int(ctx["organization_id"]))
    if not org_allows_participant_program_access(org):
        raise HTTPException(
            status_code=403,
            detail=_http_detail(
                "PROGRAM_ACCESS_LOCKED",
                "Organization program access is not active. Contact your organization.",
            ),
        )


def _require_enrolled_org_participant(user: Dict[str, Any]) -> Dict[str, Any]:
    """S3/S4: active org_user + program enrollment row."""
    ctx = get_enrolled_org_participant_context(int(user["user_id"]))
    if not ctx:
        raise HTTPException(
            status_code=403,
            detail=_http_detail(
                "ORG_PROGRAM_PARTICIPANT_REQUIRED",
                "Active program enrollment as an organization participant is required.",
            ),
        )
    uid = int(user["user_id"])
    ensure_org_program_workflow(
        uid,
        int(ctx["organization_id"]),
        int(ctx["organization_program_enrollment_id"]),
    )
    return ctx


def _require_org_program_upload_done(user: Dict[str, Any], ctx: Dict[str, Any]) -> None:
    uid = int(user["user_id"])
    eid = int(ctx["organization_program_enrollment_id"])
    if not effective_upload_done(uid, eid):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "PROGRAM_UPLOAD_REQUIRED",
                "Upload a credit report before running analyze.",
            ),
        )


def _require_org_program_findings_ready(user: Dict[str, Any], ctx: Dict[str, Any]) -> None:
    uid = int(user["user_id"])
    eid = int(ctx["organization_program_enrollment_id"])
    if not effective_findings_ready(uid, eid):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "PROGRAM_FINDINGS_NOT_READY",
                "Complete report upload and analysis before using dispute options.",
            ),
        )


def _require_org_program_selections_saved(user: Dict[str, Any], ctx: Dict[str, Any]) -> None:
    uid = int(user["user_id"])
    eid = int(ctx["organization_program_enrollment_id"])
    if not effective_selections_saved(uid, eid):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "PROGRAM_SELECTIONS_REQUIRED",
                "Save dispute selections before generating letters.",
            ),
        )


def _require_org_instructor_only(user: Dict[str, Any], org_id: int) -> None:
    """S5B: instructor endpoints — not platform admin unless also org instructor."""
    uid = int(user["user_id"])
    if not user_is_active_instructor_for_org(uid, org_id):
        raise HTTPException(
            status_code=403,
            detail=_http_detail(
                "ORG_INSTRUCTOR_REQUIRED",
                "Active organization instructor role is required.",
            ),
        )


def _require_org_program_not_paused(user: Dict[str, Any], ctx: Dict[str, Any]) -> None:
    uid = int(user["user_id"])
    eid = int(ctx["organization_program_enrollment_id"])
    if participant_forward_paused(uid, eid):
        raise HTTPException(
            status_code=403,
            detail=_http_detail(
                "PROGRAM_PAUSED_BY_INSTRUCTOR",
                "This program is paused by your instructor. Contact your organization.",
            ),
        )


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
    _logger.info(
        "signup verification path entered: user_id=%s email=%s",
        uid,
        row.get("email", email),
    )
    try:
        code = auth.set_verification_code(uid)
        if not code:
            _logger.warning(
                "signup verification email not sent: set_verification_code returned None "
                "(likely rate limit on action email_send for user_id=%s)",
                uid,
            )
        else:
            from resend_client import send_verification_email

            _logger.info(
                "signup verification: sending Resend email to=%s from_env=RESEND_FROM_EMAIL",
                row.get("email", email),
            )
            result = send_verification_email(
                row.get("email", email),
                code,
                body.display_name.strip() or None,
            )
            _logger.info(
                "signup verification email send finished: user_id=%s resend_result=%s",
                uid,
                result,
            )
    except Exception as exc:
        _logger.exception(
            "signup verification email failed: user_id=%s error=%s",
            uid,
            exc,
        )
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


@app.post("/api/orgs")
def post_api_orgs(
    body: OrgCreateBody,
    _admin: Dict[str, Any] = Depends(require_platform_admin),
) -> Dict[str, Any]:
    """Create an organization (platform admin session only)."""
    row = create_organization(body.name.strip())
    if row.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("ORG_CREATE_FAILED", str(row["error"])),
        )
    return {"organization": _public_organization_record(row)}


@app.get("/api/orgs/{org_id}")
def get_api_org(
    org_id: int,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    _require_org_read_access(user, org_id)
    org = get_organization(org_id)
    if not org:
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    return {"organization": _public_organization_record(org)}


@app.patch("/api/orgs/{org_id}")
def patch_api_org(
    org_id: int,
    body: OrgPatchBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Org profile / onboarding fields; billing fields (payment_access, status) are admin-only."""
    _require_org_read_access(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    is_admin = (user.get("role") or "").strip() == "admin"
    data = body.model_dump(exclude_unset=True, exclude_none=True, by_alias=False)
    if not is_admin:
        data.pop("payment_access", None)
        data.pop("status", None)
    if not data:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("NO_CHANGES", "No allowed fields to update."),
        )
    row = update_organization(org_id, **data)
    if row.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("ORG_UPDATE_FAILED", str(row["error"])),
        )
    return {"organization": _public_organization_record(row)}


@app.post("/api/orgs/{org_id}/members")
def post_api_org_members(
    org_id: int,
    body: OrgMemberCreateBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Attach an existing account to the org (participant, co-guide, or — platform admin only — buyer seat).

    Org instructors and org admins may add ``org_user`` and ``org_instructor`` by email or user id.
    Self-serve: no platform admin required for roster / co-guide setup.
    """
    is_platform = (user.get("role") or "").strip() == "admin"
    if not is_platform:
        _require_org_program_operator(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    if body.role == "org_admin" and not is_platform:
        raise HTTPException(
            status_code=403,
            detail=_http_detail(
                "ORG_ADMIN_SEAT_RESTRICTED",
                "Only a platform administrator can assign an organization billing-admin seat.",
            ),
        )
    target_uid: Optional[int] = body.user_id
    em = (body.email or "").strip().lower()
    if target_uid is None or target_uid <= 0:
        if not em:
            raise HTTPException(
                status_code=400,
                detail=_http_detail(
                    "ORG_MEMBER_IDENTIFIER_REQUIRED",
                    "Provide userId or email for an existing account.",
                ),
            )
        u = auth.get_user_by_email(em)
        if not u:
            raise HTTPException(
                status_code=404,
                detail=_http_detail(
                    "USER_NOT_FOUND",
                    "No account exists for that email. They need to sign up first, then you can add them.",
                ),
            )
        target_uid = int(u["id"])
    row = add_organization_member(
        org_id,
        int(target_uid),
        body.role,
        allow_org_admin_seat=is_platform,
    )
    if row.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("ORG_MEMBER_FAILED", str(row["error"])),
        )
    out: Dict[str, Any] = {"membership": _public_org_membership_record(row)}
    if str(body.role) == "org_user" and body.enroll_in_program:
        if not get_enrollment(org_id, int(target_uid)):
            en = create_program_enrollment(org_id, int(target_uid), "enrolled")
            if not en.get("error"):
                out["enrollment"] = _public_org_enrollment_record(en)
    return out


@app.get("/api/orgs/{org_id}/members")
def get_api_org_members(
    org_id: int,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    _require_org_read_access(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    members = list_organization_members(org_id)
    return {
        "members": [_public_org_membership_record(m) for m in members],
    }


@app.post("/api/orgs/{org_id}/enrollments")
def post_api_org_enrollments(
    org_id: int,
    body: OrgProgramEnrollmentCreateBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Create a program enrollment for an existing org_user (platform admin or org instructor).
    """
    _require_org_program_operator(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    row = create_program_enrollment(
        org_id, int(body.user_id), status=str(body.status)
    )
    if row.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("ENROLLMENT_CREATE_FAILED", str(row["error"])),
        )
    return {"enrollment": _public_org_enrollment_record(row)}


@app.get("/api/orgs/{org_id}/enrollments")
def get_api_org_enrollments(
    org_id: int,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """List program enrollments for an org (platform admin or org instructor)."""
    _require_org_read_access(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    rows = list_enrollments_for_org(org_id)
    return {
        "enrollments": [_public_org_enrollment_record(r) for r in rows],
    }


@app.get("/api/orgs/{org_id}/participants")
def get_org_program_participants(
    org_id: int,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """List enrolled participants with roster fields (instructor / org_admin read)."""
    _require_org_read_access(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    raw = list_org_program_participants(org_id)
    participants = []
    for r in raw:
        uid = int(r["user_id"])
        eid = int(r["enrollment_id"])
        name = (r.get("display_name") or "").strip() or None
        email = (r.get("email") or "").strip() or None
        participants.append(
            {
                "userId": uid,
                "enrollmentId": eid,
                "displayName": name,
                "email": email,
                "displayLabel": name or email or f"User #{uid}",
                "enrollmentStatus": r.get("status"),
                "enrolledAt": r.get("enrolled_at"),
                "activatedAt": r.get("activated_at"),
                "completedAt": r.get("completed_at"),
                "sessionId": r.get("session_id"),
                "sessionCheckedInAt": r.get("session_checked_in_at"),
                "sessionWorkshopCompleteAt": r.get("session_workshop_complete_at"),
                "programCurrentStep": r.get("program_current_step"),
            }
        )
    return {"participants": participants}


@app.get("/api/orgs/{org_id}/participants/{participant_user_id}")
def get_org_program_participant(
    org_id: int,
    participant_user_id: int,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Single participant progress (dual-state, non-PII). Instructor or org_admin (read-only)."""
    _require_org_read_access(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    detail = get_org_program_participant_detail(org_id, participant_user_id)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Participant enrollment not found."),
        )
    return detail


@app.post("/api/orgs/{org_id}/participants/{participant_user_id}/override")
def post_org_program_participant_override(
    org_id: int,
    participant_user_id: int,
    body: InstructorProgramOverrideBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """S5B: instructor pause / resume / advance / reset (minimal override row)."""
    _require_org_instructor_only(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    enr = get_enrollment(org_id, participant_user_id)
    if not enr:
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Participant enrollment not found."),
        )
    eid = int(enr["id"])
    row, err = apply_instructor_program_override(
        eid,
        participant_user_id,
        int(user["user_id"]),
        str(body.action),
        body.target_step,
        body.reason_safe,
    )
    if err:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("OVERRIDE_INVALID", str(err)),
        )
    from services.workflow.progression_api import build_org_participant_progression_bundle

    canon = build_org_participant_progression_bundle(participant_user_id, eid) or {}
    return {
        "ok": True,
        "enrollmentId": eid,
        "userId": participant_user_id,
        "instructorState": {
            "paused": bool(row.get("instructor_paused")),
            "overrideKind": row.get("instructor_override_kind"),
            "overrideStep": row.get("instructor_override_step"),
            "overrideAt": row.get("instructor_override_at"),
            "overrideByUserId": row.get("instructor_override_by_user_id"),
            "overrideReasonSafe": row.get("instructor_override_reason_safe"),
        },
        **canon,
    }


@app.get("/api/orgs/{org_id}/progress")
def get_org_program_progress_summary(
    org_id: int,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """S6: aggregate program step distribution (non-PII)."""
    _require_org_read_access(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    return build_org_progress_aggregate(org_id)


@app.get("/api/orgs/{org_id}/outcomes")
def get_org_program_outcomes_summary(
    org_id: int,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """S6: aggregate activity counts (non-PII)."""
    _require_org_read_access(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    return build_org_outcomes_aggregate(org_id)


@app.get("/api/orgs/{org_id}/sessions")
def get_org_program_sessions(
    org_id: int,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    _require_org_read_access(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    rows = list_program_sessions(org_id)
    return {"sessions": [_public_org_session_record(r) for r in rows]}


@app.post("/api/orgs/{org_id}/sessions")
def post_org_program_session(
    org_id: int,
    body: OrgProgramSessionCreateBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    _require_org_program_operator(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    row = create_program_session(org_id, body.name.strip())
    if row.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("SESSION_CREATE_FAILED", str(row["error"])),
        )
    return {"session": _public_org_session_record(row)}


@app.patch("/api/orgs/{org_id}/sessions/{session_id}")
def patch_org_program_session(
    org_id: int,
    session_id: int,
    body: OrgProgramSessionPatchBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    _require_org_program_operator(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    row = update_program_session(
        org_id,
        int(session_id),
        name=body.name,
        state=body.state,
    )
    if row.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("SESSION_UPDATE_FAILED", str(row["error"])),
        )
    return {"session": _public_org_session_record(row)}


@app.post("/api/orgs/{org_id}/enrollments/{enrollment_id}/session")
def post_org_enrollment_session(
    org_id: int,
    enrollment_id: int,
    body: OrgEnrollmentSessionBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    _require_org_program_operator(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    row = set_enrollment_session(org_id, int(enrollment_id), body.session_id)
    if row.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("ENROLLMENT_SESSION_FAILED", str(row["error"])),
        )
    return {"enrollment": _public_org_enrollment_record(row)}


@app.patch("/api/orgs/{org_id}/enrollments/{enrollment_id}/workshop")
def patch_org_enrollment_workshop(
    org_id: int,
    enrollment_id: int,
    body: OrgEnrollmentWorkshopBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    _require_org_program_operator(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    row = patch_enrollment_workshop(
        org_id,
        int(enrollment_id),
        checked_in=body.checked_in,
        workshop_complete=body.workshop_complete,
    )
    if row.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("ENROLLMENT_WORKSHOP_FAILED", str(row["error"])),
        )
    return {"enrollment": _public_org_enrollment_record(row)}


@app.get("/api/orgs/{org_id}/sessions/{session_id}/workshop-desk")
def get_org_session_workshop_desk(
    org_id: int,
    session_id: int,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    _require_org_read_access(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    payload = build_workshop_desk(org_id, int(session_id))
    if payload.get("error"):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", str(payload["error"])),
        )
    return payload


@app.get("/api/orgs/{org_id}/program/billing")
def get_org_program_billing(
    org_id: int,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Billing status, catalog price, and cohort usage for org admins and guides."""
    _require_org_read_access(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    snap = build_org_program_billing_snapshot(org_id)
    if snap.get("error"):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", str(snap["error"])),
        )
    return snap


@app.post("/api/orgs/{org_id}/program/checkout")
def post_org_program_checkout(
    org_id: int,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Stripe Checkout to unlock cohort program access (org admin or platform admin)."""
    _require_org_billing_admin(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    origin = _payment_public_origin()
    if not origin:
        raise HTTPException(
            status_code=503,
            detail=_http_detail(
                "CHECKOUT_RETURN_ORIGIN_MISSING",
                "Set WORKFLOW_CUSTOMER_APP_ORIGIN or PUBLIC_APP_ORIGIN to your customer app base URL.",
            ),
        )
    email = (user.get("email") or "").strip()
    if not email:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("EMAIL_REQUIRED", "Account email is required for checkout."),
        )
    uid = int(user["user_id"])
    success_url = f"{origin}/program/setup?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/program/setup?payment=cancelled"
    result = start_org_program_activation_checkout(
        user_id=uid,
        user_email=email,
        org_id=org_id,
        success_url=success_url,
        cancel_url=cancel_url,
    )
    err = result.get("error")
    if err:
        if err == "not_org_billing_admin":
            raise HTTPException(
                status_code=403,
                detail=_http_detail("ORG_BILLING_ADMIN_REQUIRED", str(err)),
            )
        raise HTTPException(
            status_code=400,
            detail=_http_detail("ORG_CHECKOUT_FAILED", str(err)[:220]),
        )
    return {
        "checkoutUrl": result.get("url"),
        "stripeCheckoutSessionId": result.get("session_id"),
    }


@app.post("/api/orgs/{org_id}/program/billing/reconcile")
def post_org_program_billing_reconcile(
    org_id: int,
    body: OrgProgramBillingReconcileBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """After Stripe redirect, verify session and unlock program access (idempotent)."""
    _require_org_billing_admin(user, org_id)
    if not get_organization(org_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Organization not found."),
        )
    uid = int(user["user_id"])
    email = (user.get("email") or "").strip()
    out = reconcile_org_program_activation_checkout(
        checkout_session_id=body.stripe_checkout_session_id.strip(),
        user_id=uid,
        user_email=email,
    )
    if not out.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "ORG_BILLING_RECONCILE_FAILED",
                str(out.get("error", "reconcile_failed")),
            ),
        )
    if int(out.get("organizationId") or 0) != int(org_id):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "ORG_MISMATCH",
                "That checkout session is not for this organization.",
            ),
        )
    org = get_organization(org_id)
    return {
        "ok": True,
        "reconcile": out,
        "programUnlockVerified": bool(out.get("programUnlockVerified")),
        "organization": _public_organization_record(org) if org else None,
    }


@app.get("/api/me/org-program")
def get_me_org_program(
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Org membership + enrollment; includes ``canonicalProgression`` when a program workflow exists."""
    uid = int(user["user_id"])
    return build_me_org_program_payload(uid)


@app.get("/api/me/progress")
def get_me_program_progress(
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Participant milestones (delivery / instructor overlay) plus **authoritative**
    ``canonicalProgression`` when a program workflow is bound. Prefer ``canonicalProgression``
    for engine head and next actions; see ``progressionReadContract`` on milestone fields.
    """
    ctx = _require_enrolled_org_participant(user)
    uid = int(user["user_id"])
    eid = int(ctx["organization_program_enrollment_id"])
    payload = build_me_program_progress_payload(uid, eid)
    org = get_organization(int(ctx["organization_id"]))
    payload["programAccess"] = {
        "allowed": org_allows_participant_program_access(org),
    }
    bundle = _me_org_engine_bundle(ctx, uid)
    if bundle:
        payload.update(bundle)
    return payload


@app.post("/api/me/report")
async def post_me_report(
    user: Dict[str, Any] = Depends(get_session_user),
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    privacy_consent: str = Form("false"),
) -> Dict[str, Any]:
    """
    Enrolled org participant: upload one bureau PDF (or multiple parts merged server-side);
    parse runs in a ``report_upload_parse`` background job (same as ``POST .../reports/upload``).
    Client polls ``GET /api/workflows/{programWorkflowId}/jobs/{jobId}`` until terminal.
    """
    ctx = _require_enrolled_org_participant(user)
    _require_org_program_payment_access(ctx)
    _require_org_program_not_paused(user, ctx)
    consent = (privacy_consent or "").strip().lower()
    if consent not in ("1", "true", "yes", "on"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "PRIVACY_CONSENT_REQUIRED",
                "Privacy consent is required before upload.",
            ),
        )

    part_paths, part_names, part_sizes, part_sha256 = await _stage_report_upload_parts_to_temp(
        file=file,
        files=files,
    )

    uid = int(user["user_id"])
    oid = int(ctx["organization_id"])
    eid = int(ctx["organization_program_enrollment_id"])
    wid = get_program_workflow_id_for_enrollment(eid)
    if not wid:
        wid = ensure_org_program_workflow(uid, oid, eid)
    total_bytes = sum(part_sizes)

    try:
        jid = create_job(
            wid,
            JOB_TYPE_REPORT_UPLOAD_PARSE,
            {
                "userId": uid,
                "staging": "parts_v1",
                "tempPartPaths": part_paths,
                "partFilenames": part_names,
                "partByteSizes": part_sizes,
                "partSha256Hex": part_sha256,
                "orgProgramFollowup": True,
                "organizationId": oid,
                "organizationProgramEnrollmentId": eid,
            },
            dedupe_pending=False,
        )
    except Exception:
        for p in part_paths:
            try:
                os.unlink(p)
            except OSError:
                pass
        raise

    _logger.info(
        "me_report_upload_queued user_id=%s enrollment_id=%s job_id=%s bytes=%s",
        uid,
        eid,
        jid,
        total_bytes,
    )

    out: Dict[str, Any] = {
        "ok": True,
        "processing": True,
        "jobId": jid,
        "programWorkflowId": wid,
        "processingStatus": "queued",
        "reportsProcessed": 0,
        "reportIds": [],
        "fileSkips": [],
    }
    bundle = _me_org_engine_bundle(ctx, uid)
    if bundle:
        out.update(bundle)
    return out


@app.post("/api/me/report-upload/session")
def post_me_report_upload_session(
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Org program: presigned PUT session for direct-to-object-storage upload (same flow gates as
    ``POST /api/me/report`` without multipart body). Legacy ``POST /api/me/report`` unchanged.
    """
    ctx = _require_enrolled_org_participant(user)
    _require_org_program_payment_access(ctx)
    _require_org_program_not_paused(user, ctx)

    uid = int(user["user_id"])
    oid = int(ctx["organization_id"])
    eid = int(ctx["organization_program_enrollment_id"])
    wid = get_program_workflow_id_for_enrollment(eid)
    if not wid:
        wid = ensure_org_program_workflow(uid, oid, eid)

    try:
        payload = create_report_upload_session(
            user_id=uid,
            workflow_id=wid,
            kind="org_program",
            organization_id=oid,
            organization_program_enrollment_id=eid,
        )
    except ReportUploadStorageError as e:
        raise HTTPException(
            status_code=503,
            detail=_http_detail(
                "REPORT_UPLOAD_STORAGE_UNAVAILABLE",
                (str(e) or "Object storage is not configured.")[:280],
            ),
        ) from e

    return _report_upload_session_api_response(payload)


@app.post("/api/me/report-upload/finalize")
def post_me_report_upload_finalize(
    body: ReportUploadFinalizeBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    After PUT to presigned URL, verify object + enqueue ``report_upload_parse`` (same job shape as
    ``POST /api/me/report``). Legacy multipart route unchanged.
    """
    ctx = _require_enrolled_org_participant(user)
    _require_org_program_payment_access(ctx)
    _require_org_program_not_paused(user, ctx)

    uid = int(user["user_id"])
    oid = int(ctx["organization_id"])
    eid = int(ctx["organization_program_enrollment_id"])
    wid = get_program_workflow_id_for_enrollment(eid)
    if not wid:
        wid = ensure_org_program_workflow(uid, oid, eid)

    try:
        jid, idem = finalize_direct_storage_report_upload(
            upload_id=body.upload_id,
            user_id=uid,
            workflow_id=wid,
            kind="org_program",
            byte_size=body.byte_size,
            sha256_hex=body.sha256_hex,
            organization_id=oid,
            organization_program_enrollment_id=eid,
        )
    except ReportUploadStorageError as e:
        raise HTTPException(
            status_code=503,
            detail=_http_detail(
                "REPORT_UPLOAD_STORAGE_UNAVAILABLE",
                (str(e) or "Object storage is not configured.")[:280],
            ),
        ) from e
    except ReportUploadFinalizeError as e:
        _raise_finalize_error(e)

    out: Dict[str, Any] = {
        "ok": True,
        "jobId": jid,
        "idempotent": idem,
        "processing": True,
        "programWorkflowId": wid,
        "processingStatus": "queued",
        "reportsProcessed": 0,
        "reportIds": [],
        "fileSkips": [],
    }
    bundle = _me_org_engine_bundle(ctx, uid)
    if bundle:
        out.update(bundle)
    return out


@app.post("/api/me/report/analyze")
def post_me_report_analyze(
    user: Dict[str, Any] = Depends(get_session_user),
    report_id: Optional[int] = Query(
        None,
        description="Specific report id; defaults to latest for this user.",
    ),
) -> Dict[str, Any]:
    """
    Rebuild findings from stored parse (extract_claims → compress_claims).
    Does not re-read the PDF; use after POST /api/me/report.
    """
    ctx = _require_enrolled_org_participant(user)
    _require_org_program_payment_access(ctx)
    _require_org_program_not_paused(user, ctx)
    _require_org_program_upload_done(user, ctx)
    uid = int(user["user_id"])
    payload = build_findings_payload(uid, report_id=report_id)
    if payload.get("processingStatus") == "no_report":
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "NO_REPORT",
                "No saved report found. Upload a report first.",
            ),
        )
    if payload.get("processingStatus") == "complete":
        advance_org_program_steps(
            uid,
            int(ctx["organization_id"]),
            int(ctx["organization_program_enrollment_id"]),
            ["orgprog_findings_ready"],
            audit_source="api:me_report_analyze",
        )
    bundle = _me_org_engine_bundle(ctx, uid)
    if bundle:
        payload = {**payload, **bundle}
    return payload


@app.get("/api/me/report/findings")
def get_me_report_findings(
    user: Dict[str, Any] = Depends(get_session_user),
    report_id: Optional[int] = Query(
        None,
        description="Specific report id; defaults to latest for this user.",
    ),
) -> Dict[str, Any]:
    """Participant findings: reviewClaims + DB violations + summary (latest report by default)."""
    ctx = _require_enrolled_org_participant(user)
    _require_org_program_payment_access(ctx)
    uid = int(user["user_id"])
    payload = build_findings_payload(uid, report_id=report_id)
    bundle = _me_org_engine_bundle(ctx, uid)
    if bundle:
        payload = {**payload, **bundle}
    return payload


@app.get("/api/me/dispute-options")
def get_me_dispute_options(
    user: Dict[str, Any] = Depends(get_session_user),
    report_id: Optional[int] = Query(
        None,
        alias="reportId",
        description="Target report; defaults to latest for this user.",
    ),
) -> Dict[str, Any]:
    """Round-1 eligible dispute items for one report (workflow-shaped ``disputeStrategy``)."""
    ctx = _require_enrolled_org_participant(user)
    _require_org_program_payment_access(ctx)
    _require_org_program_not_paused(user, ctx)
    _require_org_program_findings_ready(user, ctx)
    uid = int(user["user_id"])
    payload = build_program_dispute_options(uid, report_id, session_user=user)
    bundle = _me_org_engine_bundle(ctx, uid)
    if bundle:
        payload = {**payload, **bundle}
    return payload


@app.get("/api/me/dispute-selections")
def get_me_dispute_selections(
    user: Dict[str, Any] = Depends(get_session_user),
    report_id: Optional[int] = Query(
        None,
        alias="reportId",
        description="Defaults to latest report when omitted.",
    ),
) -> Dict[str, Any]:
    ctx = _require_enrolled_org_participant(user)
    _require_org_program_payment_access(ctx)
    _require_org_program_not_paused(user, ctx)
    _require_org_program_findings_ready(user, ctx)
    uid = int(user["user_id"])
    payload = get_dispute_selections_response(uid, report_id)
    bundle = _me_org_engine_bundle(ctx, uid)
    if bundle:
        payload = {**payload, **bundle}
    return payload


@app.post("/api/me/dispute-selections")
def post_me_dispute_selections(
    body: MeDisputeSelectionsBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    ctx = _require_enrolled_org_participant(user)
    _require_org_program_payment_access(ctx)
    _require_org_program_not_paused(user, ctx)
    _require_org_program_findings_ready(user, ctx)
    uid = int(user["user_id"])
    rid = int(body.report_id)
    row = db.get_report(rid, user_id=uid)
    if not row:
        raise HTTPException(
            status_code=404,
            detail=_http_detail("NOT_FOUND", "Report not found."),
        )
    out = save_program_dispute_selections(
        uid,
        rid,
        ctx.get("organization_program_enrollment_id"),
        list(body.selected_review_claim_ids),
    )
    if out.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("INVALID_SELECTION", str(out["error"])),
        )
    advance_org_program_steps(
        uid,
        int(ctx["organization_id"]),
        int(ctx["organization_program_enrollment_id"]),
        ["orgprog_selections_saved"],
        audit_source="api:me_dispute_selections",
    )
    sel_out = {
        "reportId": rid,
        "selectedReviewClaimIds": out.get("selectedReviewClaimIds") or [],
        "updatedAt": out.get("updated_at"),
    }
    bundle = _me_org_engine_bundle(ctx, uid)
    if bundle:
        sel_out.update(bundle)
    return sel_out


@app.post("/api/me/generate-letters")
def post_me_generate_letters(
    body: MeGenerateLettersBody,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Generate bureau letters from saved program dispute selections (same letter pipeline;
    completes ``orgprog_letters_generated`` on the enrollment ``org_program_v1`` workflow).
    """
    ctx = _require_enrolled_org_participant(user)
    _require_org_program_payment_access(ctx)
    _require_org_program_not_paused(user, ctx)
    _require_org_program_findings_ready(user, ctx)
    _require_org_program_selections_saved(user, ctx)
    uid = int(user["user_id"])
    rid = body.report_id
    if rid is None:
        rid = resolve_report_id_for_participant(uid, None)
        if rid is None:
            raise HTTPException(
                status_code=400,
                detail=_http_detail("NO_REPORT", "No report found."),
            )
        saved = get_dispute_selections_response(uid, rid)
        if not (saved.get("selectedReviewClaimIds") or []):
            raise HTTPException(
                status_code=400,
                detail=_http_detail(
                    "NO_SELECTION",
                    "Save dispute selections first or pass reportId.",
                ),
            )
    else:
        rid = int(rid)

    result, err_safe = run_program_letter_generation(
        uid, rid, is_admin=auth.is_admin(user), session_user=user
    )
    serialized = result.pop("_serialized_letters", []) if isinstance(result, dict) else []
    selected_n = (
        int(result.pop("_selected_item_count", 0)) if isinstance(result, dict) else 0
    )

    if err_safe:
        raise HTTPException(
            status_code=400,
            detail=_http_detail("LETTER_GENERATION_FAILED", err_safe),
        )

    billing = (result or {}).get("billing") or {}
    advance_org_program_steps(
        uid,
        int(ctx["organization_id"]),
        int(ctx["organization_program_enrollment_id"]),
        ["orgprog_letters_generated"],
        audit_source="api:me_generate_letters",
    )
    gen_out = {
        "generationStatus": "success",
        "reportId": rid,
        "selectedItemCount": selected_n,
        "billing": billing,
        "letters": serialized,
        "bureauKeys": list((result.get("letters") or {}).keys()),
    }
    bundle = _me_org_engine_bundle(ctx, uid)
    if bundle:
        gen_out.update(bundle)
    return gen_out


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
    except Exception as exc:
        _logger.exception("resend verification email failed")
        hint = _dev_email_error_hint(exc)
        msg = "Could not send verification email. Please try again later."
        if hint:
            msg = f"{msg} ({hint})"
        raise HTTPException(
            status_code=503,
            detail=_http_detail("EMAIL_UNAVAILABLE", msg),
        )
    return {"ok": True}


@app.post("/api/auth/forgot-password")
def post_auth_forgot_password(body: AuthForgotPasswordBody) -> Dict[str, Any]:
    """
    Request a password reset code by email. Response is generic so addresses cannot be enumerated.
    """
    email = body.email.strip()
    if not re.match(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        email,
    ):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("INVALID_EMAIL", "Please enter a valid email address."),
        )
    result = auth.send_password_reset_code(email)
    if not result.get("success"):
        return {"ok": True}
    uid = result.get("user_id")
    if uid is not None and result.get("code"):
        try:
            from resend_client import send_password_reset_email

            send_password_reset_email(
                email.lower().strip(),
                str(result["code"]),
                result.get("display_name"),
            )
        except Exception as exc:
            _logger.exception("password reset email send failed")
            hint = _dev_email_error_hint(exc)
            msg = "Could not send reset email. Please try again later."
            if hint:
                msg = f"{msg} ({hint})"
            raise HTTPException(
                status_code=503,
                detail=_http_detail("EMAIL_UNAVAILABLE", msg),
            )
    return {"ok": True}


@app.post("/api/auth/reset-password")
def post_auth_reset_password(body: AuthResetPasswordBody) -> Dict[str, Any]:
    """Verify emailed code and set a new password (invalidates existing sessions)."""
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
    out = auth.verify_reset_code_and_set_password(
        email,
        body.code.strip(),
        body.password,
    )
    if out.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("RESET_FAILED", str(out["error"])),
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
    try:
        enforce_customer_action(workflow_id, ACTION_DISPUTES_STRATEGY_VIEW)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    payload = build_dispute_strategy_payload(uid, workflow_id, session_user=user)
    return {
        **_workflow_payload_with_progression(workflow_id),
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
    try:
        enforce_customer_action(workflow_id, ACTION_DISPUTES_SELECTION_DRAFT)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    claims = load_compressed_review_claims_for_user(uid)
    meta = parse_workflow_metadata_value(session.get("metadata") if session else {})
    rnd, cumulative, outcomes = dispute_selection_context_from_meta(meta)
    eligible = filter_eligible_dispute_items(
        claims,
        round_number=rnd,
        cumulative_disputed_ids=cumulative,
        claim_outcomes=outcomes,
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
    return _workflow_payload_with_progression(workflow_id)


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
    try:
        enforce_customer_action(workflow_id, ACTION_DISPUTES_SELECTION_CONFIRM)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    rnd, cumulative, outcomes = dispute_selection_context_from_meta(meta)
    eligible = filter_eligible_dispute_items(
        claims,
        round_number=rnd,
        cumulative_disputed_ids=cumulative,
        claim_outcomes=outcomes,
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
    return _workflow_payload_with_progression(workflow_id)


@app.post("/api/workflows/{workflow_id}/disputes/begin-next-round")
def post_disputes_begin_next_round(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    After the linear workflow is complete, reopen dispute selection through tracking
    for another round in the same program (same uploads and account).
    """
    try:
        enforce_customer_action(workflow_id, ACTION_DISPUTES_BEGIN_NEXT_ROUND)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    ok = _engine.service_begin_next_dispute_round(
        workflow_id,
        audit_source="api:begin_next_dispute_round",
        audit_user_id=uid,
    )
    if not ok:
        raise HTTPException(
            status_code=409,
            detail=_http_detail(
                "BEGIN_NEXT_ROUND_FAILED",
                "Could not start another dispute round. Refresh and try again.",
            ),
        )
    return _workflow_payload_with_progression(workflow_id)


@app.get("/api/workflows/{workflow_id}/payment/context")
def get_payment_context(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Letter counts, catalog recommendation, entitlements, and payment step status for React."""
    try:
        enforce_customer_action(workflow_id, ACTION_PAYMENT_CONTEXT)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    ctx = build_payment_context(workflow_id, uid, is_admin=auth.is_admin(user))
    return {**_workflow_payload_with_progression(workflow_id), "payment": ctx}


@app.post("/api/workflows/{workflow_id}/payment/checkout")
def post_payment_checkout(
    workflow_id: str,
    body: PaymentCheckoutBody,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Create a Stripe Checkout session with ``workflow_id`` in metadata (same as Streamlit)."""
    try:
        enforce_customer_action(workflow_id, ACTION_PAYMENT_CHECKOUT)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
        **_workflow_payload_with_progression(workflow_id),
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
    try:
        enforce_customer_action(workflow_id, ACTION_PAYMENT_RECONCILE)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    return {**_workflow_payload_with_progression(workflow_id), "reconcile": out}


@app.post("/api/workflows/{workflow_id}/payment/continue-with-credits")
def post_payment_continue_with_credits(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Complete the payment step without Stripe when letter balance already covers this round."""
    try:
        enforce_customer_action(workflow_id, ACTION_PAYMENT_CONTINUE_CREDITS)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    return _workflow_payload_with_progression(workflow_id)


@app.get("/api/workflows/{workflow_id}/letters/context")
def get_letters_context(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Letter rows from DB + workflow step state for the React /letters step."""
    try:
        enforce_customer_action(workflow_id, ACTION_LETTERS_CONTEXT_VIEW)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    head, phase, lg_row = letter_generation_head_state(workflow_id)
    letters = list_letters_for_workflow_customer(uid)
    sel_ids = selected_review_claim_ids_from_workflow(session)
    return {
        **_workflow_payload_with_progression(workflow_id),
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


@app.get("/api/workflows/{workflow_id}/credit-command-plan")
def get_credit_command_plan(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Deterministic 72-hour tactical plan from dispute selection + parsed reports
    (same ``build_credit_command_plan`` as Streamlit). Always 200; null plan if context is missing.
    """
    try:
        enforce_customer_action(workflow_id, ACTION_CREDIT_COMMAND_PLAN_VIEW)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    plan, err = build_credit_command_plan_for_workflow(
        uid,
        workflow_id,
        session_row=session,
        is_admin=auth.is_admin(user),
    )
    return {
        **_workflow_payload_with_progression(workflow_id),
        "creditCommandPlan": plan,
        "unavailableReason": err,
    }


@app.get("/api/public/demo/scenarios")
def get_public_demo_scenarios() -> Dict[str, Any]:
    """
    List fixture-backed demo scenarios (PDFs under ``samples/``).
    No auth. Production-like deploys need ``PUBLIC_DEMO_ENABLED=1``. Demo runs use a
    dedicated DB user (auto-created unless ``PUBLIC_DEMO_USER_ID`` is set).
    """
    err = public_demo_config_error()
    if err:
        raise HTTPException(
            status_code=503,
            detail=_http_detail("PUBLIC_DEMO_UNAVAILABLE", err),
        )
    scenarios = list_demo_scenarios_public()
    if not scenarios:
        raise HTTPException(
            status_code=503,
            detail=_http_detail(
                "PUBLIC_DEMO_NO_FIXTURES",
                "No demo fixture PDFs found on the server.",
            ),
        )
    return {"scenarios": scenarios}


@app.post("/api/public/demo/run")
def post_public_demo_run(
    request: Request,
    body: PublicDemoRunBody,
    x_public_demo_secret: Optional[str] = Header(None, alias="X-Public-Demo-Secret"),
) -> Dict[str, Any]:
    """
    One-shot truthful demo: new workflow for the dedicated demo user (env id or auto-created
    system row), ingest fixture, deterministic strongest-path selection, payment waiver or
    existing credits, letter generation, 72-hour command plan. **Does not use the visitor's account.**

    Optional: set ``PUBLIC_DEMO_SECRET`` and send matching ``X-Public-Demo-Secret`` header.
    """
    err = public_demo_config_error()
    if err:
        raise HTTPException(
            status_code=503,
            detail=_http_detail("PUBLIC_DEMO_UNAVAILABLE", err),
        )
    _enforce_public_demo_secret(x_public_demo_secret)
    if not _public_demo_rate_ok(request):
        raise HTTPException(
            status_code=429,
            detail=_http_detail(
                "PUBLIC_DEMO_RATE_LIMIT",
                "Too many demo runs. Try again in a minute.",
            ),
        )
    try:
        out = run_public_fixture_demo(body.scenario_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=_http_detail("PUBLIC_DEMO_MISCONFIGURED", str(exc)),
        ) from None
    if not out.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "PUBLIC_DEMO_FAILED",
                str(out.get("error") or "Demo run failed."),
            ),
        )
    wid = str(out.get("workflowId") or "").strip()
    if wid:
        out = {**out, **_workflow_payload_with_progression(wid)}
    return out


@app.post("/api/public/demo/lead")
def post_public_demo_lead(
    request: Request,
    body: PublicDemoLeadBody,
    x_public_demo_secret: Optional[str] = Header(None, alias="X-Public-Demo-Secret"),
) -> Dict[str, Any]:
    """
    Lead capture after the guided demo. Stored in ``demo_leads`` with ``source=react_demo``.
    Does not require the visitor to be logged in. Rate-limited per IP.
    """
    _enforce_public_demo_secret(x_public_demo_secret)
    if not _public_demo_lead_rate_ok(request):
        raise HTTPException(
            status_code=429,
            detail=_http_detail(
                "DEMO_LEAD_RATE_LIMIT",
                "Too many submissions. Please try again shortly.",
            ),
        )
    if not _demo_email_looks_valid(body.email):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "INVALID_EMAIL",
                "Please enter a valid email address.",
            ),
        )
    phone = body.phone.strip()
    if not _demo_phone_has_digits(phone):
        raise HTTPException(
            status_code=400,
            detail=_http_detail(
                "INVALID_PHONE",
                "Please enter a phone number we can use to follow up.",
            ),
        )
    meta_lead: Dict[str, Any] = {"clientIp": _public_demo_client_ip(request)}
    if (body.intent or "").strip():
        meta_lead["intent"] = (body.intent or "").strip()[:64]
    if (body.organization_name or "").strip():
        meta_lead["organizationName"] = (body.organization_name or "").strip()[:200]
    if (body.audience_note or "").strip():
        meta_lead["audienceNote"] = (body.audience_note or "").strip()[:500]
    if (body.referrer_name or "").strip():
        meta_lead["referrerName"] = (body.referrer_name or "").strip()[:200]
    try:
        lead_id = db.insert_demo_lead(
            body.name.strip(),
            body.email.strip(),
            phone,
            source="react_demo",
            scenario_id=(body.scenario_id or "").strip() or None,
            workflow_id=(body.workflow_id or "").strip() or None,
            meta=meta_lead,
        )
    except Exception:
        _logger.exception("demo_lead insert failed")
        raise HTTPException(
            status_code=503,
            detail=_http_detail(
                "DEMO_LEAD_STORAGE_UNAVAILABLE",
                "We could not save your details. Please try again later.",
            ),
        ) from None

    if lead_id:
        try:
            from resend_client import send_demo_lead_operator_notification

            send_demo_lead_operator_notification(
                lead_id=lead_id,
                name=body.name.strip(),
                email=body.email.strip(),
                phone=phone,
                scenario_id=body.scenario_id,
                workflow_id=body.workflow_id,
            )
        except Exception:
            _logger.debug("demo lead notification skipped or failed", exc_info=True)

    return {"ok": True, "leadId": lead_id}


@app.get("/internal/admin/demo-leads")
def get_internal_demo_leads(
    limit: int = Query(50, ge=1, le=200),
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    """Operator-only: recent rows from ``demo_leads`` (Bearer ``WORKFLOW_ADMIN_API_SECRET``)."""
    return jsonable_encoder({"demoLeads": db.list_demo_leads(limit=limit)})


@app.post("/internal/admin/demo-leads/{lead_id}/convert-to-org")
def post_internal_demo_lead_convert_to_org(
    lead_id: int,
    body: DemoLeadConvertToOrgBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    """
    Create a new organization from a demo lead and link the row for continuity.
    Memberships and enrollments still use standard admin/instructor APIs.
    """
    out = convert_demo_lead_to_org(int(lead_id), body.organization_name.strip())
    if out.get("error"):
        raise HTTPException(
            status_code=400,
            detail=_http_detail("CONVERT_FAILED", str(out["error"])),
        )
    org = out["organization"]
    return {
        "ok": True,
        "leadId": out["leadId"],
        "organization": _public_organization_record(org),
    }


@app.get("/internal/admin/workflows/{workflow_id}/events")
def get_internal_workflow_events(
    workflow_id: str,
    limit: int = Query(500, ge=1, le=2000),
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    """Operator-only: append-only workflow event log (oldest first)."""
    if not fetch_session(workflow_id):
        return {"ok": False, "error": {"code": "NOT_FOUND"}}
    items = list_workflow_events(workflow_id, limit=limit, oldest_first=True)
    return {"ok": True, "order": "oldest_first", "items": items}


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
    try:
        enforce_customer_action(workflow_id, ACTION_LETTER_GENERATION_RUN)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
        **_workflow_payload_with_progression(workflow_id),
        "generation": {
            "bureaus": [str(b).lower() for b in letters_out.keys() if b],
            "billing": result.get("billing"),
            "readinessSummary": {
                "includedDecisions": len(readiness.get("include_decisions") or []),
                "blockedDecisions": len(readiness.get("blocked_decisions") or []),
            },
        },
    }


@app.post("/api/workflows/{workflow_id}/letters/generate-async")
def post_letters_generate_async(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Enqueue letter generation for background processing (same pipeline as sync generate).
    Returns immediately with ``jobId``; poll ``GET .../jobs/{jobId}`` for status.
    """
    try:
        enforce_customer_action(workflow_id, ACTION_LETTER_GENERATION_RUN)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    jid = create_job(
        workflow_id,
        JOB_TYPE_LETTER_GENERATION,
        {"userId": uid, "isAdmin": auth.is_admin(user)},
        dedupe_pending=True,
    )
    return {
        **_workflow_payload_with_progression(workflow_id),
        "ok": True,
        "jobId": jid,
        "status": "pending",
    }


@app.get("/api/workflows/{workflow_id}/jobs")
def get_workflow_jobs_list(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    limit: int = Query(25, ge=1, le=100),
) -> Dict[str, Any]:
    try:
        enforce_customer_action(workflow_id, ACTION_WORKFLOW_JOBS_LIST)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    rows = wf_list_jobs(workflow_id, limit=limit)
    return {
        "ok": True,
        "items": [wf_public_job_view(r) for r in rows],
    }


@app.get("/api/workflows/{workflow_id}/jobs/{job_id}")
def get_workflow_job_single(
    workflow_id: str,
    job_id: str,
    _session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    try:
        enforce_customer_action(workflow_id, ACTION_WORKFLOW_JOB_GET)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    row = wf_get_job(job_id)
    if not row or str(row.get("workflow_id")) != str(workflow_id):
        raise HTTPException(
            status_code=404,
            detail=_http_detail("JOB_NOT_FOUND", "Job not found for this workflow."),
        )
    return {"ok": True, "job": wf_public_job_view(row)}


@app.get("/api/workflows/{workflow_id}/letters/{letter_id}/content")
def get_letter_content(
    workflow_id: str,
    letter_id: int,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    """Full letter body for the signed-in owner (for preview modal)."""
    try:
        enforce_customer_action(workflow_id, ACTION_LETTER_BODY_READ)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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

    try:
        enforce_customer_action(workflow_id, ACTION_LETTERS_BUNDLE_READ)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    try:
        enforce_customer_action(workflow_id, ACTION_PROOF_CONTEXT)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    return {
        **_workflow_payload_with_progression(workflow_id),
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
    try:
        enforce_customer_action(workflow_id, ACTION_PROOF_UPLOAD)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
        **_workflow_payload_with_progression(workflow_id),
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
    try:
        enforce_customer_action(workflow_id, ACTION_PROOF_SIGNATURE)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
        **_workflow_payload_with_progression(workflow_id),
        "proof": build_proof_context_payload(uid, workflow_id),
    }


@app.get("/api/workflows/{workflow_id}/mail/context")
def get_mail_context(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Mail readiness, Lob config, bureau send rows, and workflow mail-gate metadata (Streamlit send panel parity)."""
    try:
        enforce_customer_action(workflow_id, ACTION_MAIL_CONTEXT)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    return {
        **_workflow_payload_with_progression(workflow_id),
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
    try:
        enforce_customer_action(workflow_id, ACTION_MAIL_SEND_BUREAU)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
        **_workflow_payload_with_progression(workflow_id),
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
    try:
        enforce_customer_action(workflow_id, ACTION_TRACKING_CONTEXT)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    return {
        **_workflow_payload_with_progression(workflow_id),
        "tracking": build_tracking_context_payload(
            uid,
            workflow_id,
            session_row=session,
        ),
    }


@app.get("/api/workflows/{workflow_id}/escalation/layer")
def get_escalation_layer(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """
    Deterministic escalation triggers (mail age, response classifications, per-claim outcomes)
    plus concrete leverage actions: furnisher disputes, follow-up letters, call scripts, CFPB path.
    """
    try:
        enforce_customer_action(workflow_id, ACTION_ESCALATION_LAYER_VIEW)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    uid = int(session["user_id"])
    layer = build_escalation_layer_payload(uid, workflow_id, session_row=session)
    return {
        **_workflow_payload_with_progression(workflow_id),
        "escalationLayer": layer,
    }


@app.post("/api/workflows/{workflow_id}/escalation/ux-state")
def post_escalation_ux_state(
    workflow_id: str,
    body: EscalationUxStateBody,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    """Persist per-action reviewed/proceeded flags under ``dispute_selection.escalation_ux``."""
    try:
        enforce_customer_action(workflow_id, ACTION_ESCALATION_UX_UPDATE)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    _ = int(user["user_id"])
    persist_escalation_ux_state(
        workflow_id,
        body.action_id,
        reviewed=bool(body.reviewed),
        proceeded=bool(body.proceeded),
    )
    return _workflow_payload_with_progression(workflow_id)


@app.get("/api/workflows/{workflow_id}/responses/metrics")
def get_workflow_response_metrics(
    workflow_id: str,
    _session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    """
    Compact aggregates from ``workflow_response_intake`` rows (same owner scope as list/intake).
    """
    try:
        enforce_customer_action(workflow_id, ACTION_RESPONSES_METRICS)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    payload = build_customer_response_metrics_payload(workflow_id)
    return {
        **_workflow_payload_with_progression(workflow_id),
        **payload,
    }


@app.get("/api/workflows/{workflow_id}/responses")
def get_workflow_responses(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    limit: int = Query(30, ge=1, le=50),
) -> Dict[str, Any]:
    """Recent ``workflow_response_intake`` rows for the owner (classification + escalation snapshot)."""
    try:
        enforce_customer_action(workflow_id, ACTION_RESPONSES_LIST)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
        **_workflow_payload_with_progression(workflow_id),
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
    try:
        enforce_customer_action(workflow_id, ACTION_CUSTOMER_UX_EVENT)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    try:
        enforce_customer_action(workflow_id, ACTION_RESPONSES_INTAKE)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    return {**out, **_workflow_payload_with_progression(workflow_id)}


@app.post("/api/workflows/{workflow_id}/steps/{step_id}/start")
def post_step_start(
    workflow_id: str,
    step_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    try:
        enforce_step_start(workflow_id, step_id)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    return _envelope_with_progression(
        _engine.start_step(
            workflow_id,
            step_id,
            audit_source="api",
            audit_user_id=int(session["user_id"]),
        )
    )


@app.post("/api/workflows/{workflow_id}/reports/upload")
async def post_workflow_report_upload(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    privacy_consent: str = Form("false"),
) -> Dict[str, Any]:
    """
    Upload one bureau credit-report PDF, or several parts (``files``) merged server-side into one
    document, then ``services.report_pipeline.process_uploaded_reports`` (same path as Streamlit).
    On success, workflow hooks complete ``upload`` and ``parse_analyze``.
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

    try:
        enforce_customer_action(workflow_id, ACTION_REPORT_PDF_UPLOAD)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)

    part_paths, part_names, part_sizes, part_sha256 = await _stage_report_upload_parts_to_temp(
        file=file,
        files=files,
    )

    uid = int(session["user_id"])
    total_bytes = sum(part_sizes)
    _logger.info(
        "workflow_report_upload_begin workflow_id=%s user_id=%s bytes=%s parts=%s",
        workflow_id,
        uid,
        total_bytes,
        len(part_paths),
    )

    try:
        jid = create_job(
            workflow_id,
            JOB_TYPE_REPORT_UPLOAD_PARSE,
            {
                "userId": uid,
                "staging": "parts_v1",
                "tempPartPaths": part_paths,
                "partFilenames": part_names,
                "partByteSizes": part_sizes,
                "partSha256Hex": part_sha256,
            },
            dedupe_pending=False,
        )
    except Exception:
        for p in part_paths:
            try:
                os.unlink(p)
            except OSError:
                pass
        raise

    _logger.info(
        "workflow_report_upload_queued workflow_id=%s user_id=%s job_id=%s bytes=%s",
        workflow_id,
        uid,
        jid,
        total_bytes,
    )

    return {
        "ok": True,
        "processing": True,
        "jobId": jid,
        "reportsProcessed": 0,
        "fileSkips": [],
        **_workflow_payload_with_progression(workflow_id),
    }


@app.post("/api/workflows/{workflow_id}/report-upload/session")
def post_workflow_report_upload_session(
    workflow_id: str,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    """
    Direct-to-object-storage: create an upload session and presigned PUT URL.
    Client uploads bytes to ``uploadUrl``, then calls finalize (separate route; not yet implemented).
    Legacy ``POST .../reports/upload`` is unchanged.
    """
    try:
        enforce_customer_action(workflow_id, ACTION_REPORT_PDF_UPLOAD)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)

    uid = int(session["user_id"])
    try:
        payload = create_report_upload_session(
            user_id=uid,
            workflow_id=workflow_id,
            kind="retail",
        )
    except ReportUploadStorageError as e:
        raise HTTPException(
            status_code=503,
            detail=_http_detail(
                "REPORT_UPLOAD_STORAGE_UNAVAILABLE",
                (str(e) or "Object storage is not configured.")[:280],
            ),
        ) from e

    return _report_upload_session_api_response(payload)


@app.post("/api/workflows/{workflow_id}/report-upload/finalize")
def post_workflow_report_upload_finalize(
    workflow_id: str,
    body: ReportUploadFinalizeBody,
    session: Dict[str, Any] = Depends(get_owned_workflow),
) -> Dict[str, Any]:
    """
    After PUT to presigned URL, verify object in storage and enqueue ``report_upload_parse``.
    Legacy ``POST .../reports/upload`` unchanged.
    """
    try:
        enforce_customer_action(workflow_id, ACTION_REPORT_PDF_UPLOAD)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)

    uid = int(session["user_id"])
    try:
        jid, idem = finalize_direct_storage_report_upload(
            upload_id=body.upload_id,
            user_id=uid,
            workflow_id=workflow_id,
            kind="retail",
            byte_size=body.byte_size,
            sha256_hex=body.sha256_hex,
        )
    except ReportUploadStorageError as e:
        raise HTTPException(
            status_code=503,
            detail=_http_detail(
                "REPORT_UPLOAD_STORAGE_UNAVAILABLE",
                (str(e) or "Object storage is not configured.")[:280],
            ),
        ) from e
    except ReportUploadFinalizeError as e:
        _raise_finalize_error(e)

    return {
        "ok": True,
        "jobId": jid,
        "idempotent": idem,
        "processing": True,
        "reportsProcessed": 0,
        "fileSkips": [],
        **_workflow_payload_with_progression(workflow_id),
    }


@app.post("/internal/workflows/{workflow_id}/steps/{step_id}/service-complete")
def internal_service_complete(
    workflow_id: str,
    step_id: str,
    body: InternalServiceCompleteBody,
    _: None = Depends(require_internal_service),
) -> Dict[str, Any]:
    try:
        enforce_flow_action(
            workflow_id,
            INTERNAL_SERVICE_COMPLETE,
            trust=TRUST_INTERNAL,
            step_id_arg=step_id,
        )
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    try:
        enforce_flow_action(
            workflow_id,
            INTERNAL_SERVICE_FAIL,
            trust=TRUST_INTERNAL,
            step_id_arg=step_id,
        )
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    try:
        enforce_flow_action(
            workflow_id,
            INTERNAL_ASYNC_STATE,
            trust=TRUST_INTERNAL,
            step_id_arg=step_id,
        )
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    try:
        enforce_flow_action(
            workflow_id,
            INTERNAL_REMINDER_CANDIDATES,
            trust=TRUST_INTERNAL,
        )
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    if is_production_like():
        raise HTTPException(
            status_code=403,
            detail=_http_detail(
                "REMINDER_STUB_FORBIDDEN",
                "Stub reminder delivery is disabled in production.",
            ),
        )
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
    try:
        enforce_flow_action(workflow_id, OPERATOR_CLEAR_STALLED, trust=TRUST_OPERATOR)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    try:
        enforce_flow_action(
            workflow_id,
            OPERATOR_REOPEN_STEP,
            trust=TRUST_OPERATOR,
            operator_target_step_id=body.step_id,
        )
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    try:
        enforce_flow_action(workflow_id, OPERATOR_PAYMENT_WAIVED, trust=TRUST_OPERATOR)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    try:
        enforce_flow_action(workflow_id, OPERATOR_RECOVERY_RECORD, trust=TRUST_OPERATOR)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    try:
        enforce_flow_action(workflow_id, OPERATOR_RECOVERY_RETRY_STEP, trust=TRUST_OPERATOR)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    try:
        enforce_flow_action(workflow_id, OPERATOR_RECOVERY_RESUME, trust=TRUST_OPERATOR)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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
    try:
        enforce_flow_action(workflow_id, OPERATOR_RECOVERY_MAIL_RETRY, trust=TRUST_OPERATOR)
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
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


@app.get("/internal/admin/architect-access/scenarios")
def architect_access_scenarios(_: None = Depends(require_admin_service)) -> Dict[str, Any]:
    return {"ok": True, "scenarios": architect_access_svc.list_scenarios()}


@app.post("/internal/admin/architect-access/apply")
def architect_access_apply(
    body: ArchitectAccessApplyBody,
    _: None = Depends(require_admin_service),
) -> Dict[str, Any]:
    try:
        out = architect_access_svc.apply_scenario(
            body.scenario_id,
            reset_consumer_workflow=body.reset_consumer_workflow,
        )
    except Exception as ex:
        _logger.exception("architect_access_apply failed: %s", body.scenario_id)
        raise HTTPException(
            status_code=500,
            detail={"messageSafe": str(ex)[:500], "code": "ARCHITECT_APPLY_FAILED"},
        ) from ex
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out.get("error") or {"messageSafe": "Apply failed."})
    return out


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
    try:
        enforce_flow_action(
            workflow_id,
            OPERATOR_MC_REMINDER_CANDIDATES,
            trust=TRUST_OPERATOR,
        )
    except FlowEnforcementError as e:
        _raise_flow_violation(e)
    return rem_svc.create_reminder_candidates_for_workflow(workflow_id)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "workflow-api"}


@app.api_route(
    "/api/{rest_of_path:path}",
    methods=["POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
def unknown_write_api_path(rest_of_path: str) -> Dict[str, Any]:
    """
    Fallback so POST/PUT/PATCH/DELETE under ``/api/`` never hit the SPA ``GET /{path}``
    catch-all (which would incorrectly return **405 Method Not Allowed**).
    """
    raise HTTPException(
        status_code=404,
        detail=_http_detail(
            "API_ROUTE_NOT_FOUND",
            "Unknown API path or your workflow server needs a restart after updating.",
        ),
    )


mount_customer_web_dist_if_present(app, _logger)
