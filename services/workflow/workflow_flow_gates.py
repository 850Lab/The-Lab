"""
Central flow-control gates for customer, internal service, and operator paths.

Single source: ``compute_authoritative_step`` + ``StepDefinition.allowed_entry_statuses``.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional

from services.workflow.engine import compute_authoritative_step
from services.workflow import registry as reg
from services.workflow import lifecycle_rules as lr_mod
from services.workflow.repository import fetch_session, fetch_steps

# --- Trust levels --------------------------------------------------------------
TRUST_CUSTOMER = "customer"
TRUST_INTERNAL = "internal"
TRUST_OPERATOR = "operator"

# --- Customer action keys ------------------------------------------------------
ACTION_REPORT_PDF_UPLOAD = "report_pdf_upload"
ACTION_INTAKE_SUMMARY_VIEW = "intake_summary_view"
ACTION_REVIEW_CLAIMS_ACK = "review_claims_ack"
ACTION_DISPUTES_STRATEGY_VIEW = "disputes_strategy_view"
ACTION_DISPUTES_SELECTION_DRAFT = "disputes_selection_draft"
ACTION_DISPUTES_SELECTION_CONFIRM = "disputes_selection_confirm"
ACTION_PAYMENT_CONTEXT = "payment_context"
ACTION_PAYMENT_CHECKOUT = "payment_checkout"
ACTION_PAYMENT_RECONCILE = "payment_reconcile"
ACTION_PAYMENT_CONTINUE_CREDITS = "payment_continue_credits"
ACTION_LETTERS_CONTEXT_VIEW = "letters_context_view"
ACTION_LETTER_GENERATION_RUN = "letter_generation_run"
ACTION_CREDIT_COMMAND_PLAN_VIEW = "credit_command_plan_view"
ACTION_LETTER_BODY_READ = "letter_body_read"
ACTION_LETTERS_BUNDLE_READ = "letters_bundle_read"
ACTION_PROOF_CONTEXT = "proof_context"
ACTION_PROOF_UPLOAD = "proof_upload"
ACTION_PROOF_SIGNATURE = "proof_signature"
ACTION_MAIL_CONTEXT = "mail_context"
ACTION_MAIL_SEND_BUREAU = "mail_send_bureau"
ACTION_TRACKING_CONTEXT = "tracking_context"
ACTION_RESPONSES_METRICS = "responses_metrics"
ACTION_RESPONSES_LIST = "responses_list"
ACTION_RESPONSES_INTAKE = "responses_intake"
ACTION_DISPUTES_BEGIN_NEXT_ROUND = "disputes_begin_next_round"
ACTION_ESCALATION_LAYER_VIEW = "escalation_layer_view"
ACTION_ESCALATION_UX_UPDATE = "escalation_ux_update"
ACTION_CUSTOMER_UX_EVENT = "customer_ux_event"
ACTION_WORKFLOW_JOBS_LIST = "workflow_jobs_list"
ACTION_WORKFLOW_JOB_GET = "workflow_job_get"
ACTION_HOME_SUMMARY_VIEW = "home_summary_view"
ACTION_INTEGRITY_HINTS_VIEW = "integrity_hints_view"

# Internal (trusted HTTP + shared secret)
INTERNAL_SERVICE_COMPLETE = "internal_service_complete"
INTERNAL_SERVICE_FAIL = "internal_service_fail"
INTERNAL_ASYNC_STATE = "internal_async_state"
INTERNAL_REMINDER_CANDIDATES = "internal_reminder_candidates"

# Operator (admin secret)
OPERATOR_CLEAR_STALLED = "operator_clear_stalled"
OPERATOR_REOPEN_STEP = "operator_reopen_step"
OPERATOR_PAYMENT_WAIVED = "operator_payment_waived"
OPERATOR_RECOVERY_RECORD = "operator_recovery_record"
OPERATOR_RECOVERY_RETRY_STEP = "operator_recovery_retry_step"
OPERATOR_RECOVERY_RESUME = "operator_recovery_resume"
OPERATOR_RECOVERY_MAIL_RETRY = "operator_recovery_mail_retry"
OPERATOR_MC_REMINDER_CANDIDATES = "operator_mc_reminder_candidates"


class FlowEnforcementError(Exception):
    def __init__(
        self,
        code: str,
        message_safe: str,
        *,
        current_step: Optional[str] = None,
        expected_step: Optional[str] = None,
    ) -> None:
        super().__init__(message_safe)
        self.code = code
        self.message_safe = message_safe
        self.current_step = current_step
        self.expected_step = expected_step


def flow_violation_detail(exc: FlowEnforcementError) -> Dict[str, Any]:
    """Standard 409 body: code, messageSafe, currentStep, expectedStep."""
    out: Dict[str, Any] = {
        "code": exc.code,
        "messageSafe": exc.message_safe,
    }
    if exc.current_step is not None:
        out["currentStep"] = exc.current_step
    if exc.expected_step is not None:
        out["expectedStep"] = exc.expected_step
    return out


def _steps_map(workflow_id: str) -> Dict[str, Dict[str, Any]]:
    rows = fetch_steps(workflow_id)
    return {r["step_id"]: r for r in rows}


def _check_parse_done(_s: Dict[str, Any], smap: Dict[str, Dict[str, Any]]) -> Optional[str]:
    row = smap.get("parse_analyze")
    if not row or row.get("status") != "completed":
        return "Report parsing must finish before this action."
    return None


def _check_review_done(_s: Dict[str, Any], smap: Dict[str, Dict[str, Any]]) -> Optional[str]:
    row = smap.get("review_claims")
    if not row or row.get("status") != "completed":
        return "Finish reviewing claims before this step."
    return None


def _check_select_done(_s: Dict[str, Any], smap: Dict[str, Dict[str, Any]]) -> Optional[str]:
    row = smap.get("select_disputes")
    if not row or row.get("status") != "completed":
        return "Confirm dispute selection before this action."
    return None


def _check_payment_done(_s: Dict[str, Any], smap: Dict[str, Dict[str, Any]]) -> Optional[str]:
    row = smap.get("payment")
    if not row or row.get("status") != "completed":
        return "Complete payment before this action."
    return None


def _check_letter_gen_done(_s: Dict[str, Any], smap: Dict[str, Dict[str, Any]]) -> Optional[str]:
    row = smap.get("letter_generation")
    if not row or row.get("status") != "completed":
        return "Generate letters before this action."
    return None


def _check_disputes_strategy_view(
    _s: Dict[str, Any], smap: Dict[str, Dict[str, Any]]
) -> Optional[str]:
    return _check_parse_done(_s, smap) or _check_review_done(_s, smap)


def _check_customer_ux_ok(session: Dict[str, Any], _smap: Dict[str, Dict[str, Any]]) -> Optional[str]:
    if str(session.get("overall_status") or "active") != "active":
        return "Workflow is not active."
    return None


def _check_readiness_views(session: Dict[str, Any], _smap: Dict[str, Dict[str, Any]]) -> Optional[str]:
    o = str(session.get("overall_status") or "active")
    if o not in ("active", "failed", "completed"):
        return "Workflow is not readable."
    return None


def _check_jobs_read(session: Dict[str, Any], _smap: Dict[str, Dict[str, Any]]) -> Optional[str]:
    o = str(session.get("overall_status") or "active")
    if o not in ("active", "failed", "completed"):
        return "Workflow jobs are not available."
    return None


def _check_escalation_ux_update_allowed(
    session: Dict[str, Any], smap: Dict[str, Dict[str, Any]]
) -> Optional[str]:
    """Allow on ``select_disputes`` (e.g. round 2+ strategy) or post-track toolkit surface."""
    msg_early = _check_disputes_strategy_view(session, smap)
    if msg_early is None:
        order = reg.linear_order_for(str(session.get("workflow_type") or reg.WORKFLOW_TYPE_DEFAULT))
        head, phase = compute_authoritative_step(smap, order)
        if phase != "done" and head == "select_disputes":
            return None
    return _check_post_track_customer_surface_allowed(session, smap)


def _check_post_track_customer_surface_allowed(
    session: Dict[str, Any], smap: Dict[str, Dict[str, Any]]
) -> Optional[str]:
    msg = _check_parse_done(session, smap) or _check_review_done(session, smap)
    if msg:
        return msg
    tr = smap.get("track")
    if tr and tr.get("status") == "completed":
        return None
    overall = str(session.get("overall_status") or "active")
    if overall == "completed":
        return None
    meta = session.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    if not isinstance(meta, dict):
        meta = {}
    ds = meta.get("dispute_selection") or {}
    if isinstance(ds, dict):
        try:
            if int(ds.get("dispute_round_number") or 1) > 1:
                return None
        except (TypeError, ValueError):
            pass
    return "Finish certified mail and tracking before using this part of your program."


def _check_begin_next_dispute_round_allowed(
    session: Dict[str, Any], smap: Dict[str, Dict[str, Any]]
) -> Optional[str]:
    if str(session.get("overall_status") or "active") != "completed":
        return "Finish the full dispute cycle (through tracking) before starting another round."
    tr = smap.get("track")
    if not tr or tr.get("status") != "completed":
        return "Tracking must complete before another dispute round."
    return None


_PREDICATE_ONLY: Dict[str, Callable[[Dict[str, Any], Dict[str, Dict[str, Any]]], Optional[str]]] = {
    ACTION_INTAKE_SUMMARY_VIEW: _check_parse_done,
    ACTION_DISPUTES_STRATEGY_VIEW: _check_disputes_strategy_view,
    ACTION_ESCALATION_UX_UPDATE: _check_escalation_ux_update_allowed,
    ACTION_CREDIT_COMMAND_PLAN_VIEW: _check_select_done,
    ACTION_CUSTOMER_UX_EVENT: _check_customer_ux_ok,
    ACTION_HOME_SUMMARY_VIEW: _check_readiness_views,
    ACTION_INTEGRITY_HINTS_VIEW: _check_readiness_views,
    ACTION_WORKFLOW_JOBS_LIST: _check_jobs_read,
    ACTION_WORKFLOW_JOB_GET: _check_jobs_read,
    ACTION_LETTER_BODY_READ: lambda s, m: _check_payment_done(s, m) or _check_letter_gen_done(s, m),
    ACTION_LETTERS_BUNDLE_READ: lambda s, m: _check_payment_done(s, m) or _check_letter_gen_done(s, m),
}

_HEAD_CUSTOMER: Dict[str, str] = {
    ACTION_REPORT_PDF_UPLOAD: "upload",
    ACTION_REVIEW_CLAIMS_ACK: "review_claims",
    ACTION_DISPUTES_SELECTION_DRAFT: "select_disputes",
    ACTION_DISPUTES_SELECTION_CONFIRM: "select_disputes",
    ACTION_PAYMENT_CONTEXT: "payment",
    ACTION_PAYMENT_CHECKOUT: "payment",
    ACTION_PAYMENT_RECONCILE: "payment",
    ACTION_PAYMENT_CONTINUE_CREDITS: "payment",
    ACTION_LETTERS_CONTEXT_VIEW: "letter_generation",
    ACTION_LETTER_GENERATION_RUN: "letter_generation",
    ACTION_PROOF_CONTEXT: "proof_attachment",
    ACTION_PROOF_UPLOAD: "proof_attachment",
    ACTION_PROOF_SIGNATURE: "proof_attachment",
    ACTION_MAIL_CONTEXT: "mail",
    ACTION_MAIL_SEND_BUREAU: "mail",
}

# Tracking + responses after certified mail: valid when linear head is past track or workflow completed.
_POST_TRACK_COMPLETED_CUSTOMER_ACTIONS = frozenset(
    {
        ACTION_TRACKING_CONTEXT,
        ACTION_RESPONSES_METRICS,
        ACTION_RESPONSES_LIST,
        ACTION_RESPONSES_INTAKE,
        ACTION_ESCALATION_LAYER_VIEW,
    }
)


def _require_head_match(
    head: Optional[str],
    phase: str,
    expected: str,
    *,
    defn: reg.StepDefinition,
    smap: Dict[str, Dict[str, Any]],
) -> None:
    if phase == "done":
        raise FlowEnforcementError(
            "FLOW_ORDER_VIOLATION",
            "This workflow has finished linear progression for this path.",
            current_step=None,
            expected_step=expected,
        )
    if head != expected:
        raise FlowEnforcementError(
            "FLOW_ORDER_VIOLATION",
            f"This action is for a different step. Current step: {head!r}.",
            current_step=head,
            expected_step=expected,
        )
    row = smap.get(expected)
    st = row.get("status") if row else None
    if st not in frozenset(defn.allowed_entry_statuses):
        raise FlowEnforcementError(
            "FLOW_ORDER_VIOLATION",
            f"Step is not ready for this action (status: {st!r}).",
            current_step=head,
            expected_step=expected,
        )


def enforce_step_start(workflow_id: str, step_id: str) -> None:
    """POST .../steps/{step_id}/start — head must equal requested step."""
    enforce_flow_action(
        workflow_id,
        "__step_start__",
        trust=TRUST_CUSTOMER,
        step_id_arg=(step_id or "").strip()[:64],
    )


def enforce_flow_action(
    workflow_id: str,
    action_key: str,
    *,
    trust: str = TRUST_CUSTOMER,
    step_id_arg: Optional[str] = None,
    operator_target_step_id: Optional[str] = None,
) -> None:
    wf = (workflow_id or "").strip()
    if not wf:
        raise FlowEnforcementError("INVALID_WORKFLOW", "Workflow id is required.")

    session = fetch_session(wf)
    if not session:
        raise FlowEnforcementError("NOT_FOUND", "Workflow not found.")

    smap = _steps_map(wf)
    order = reg.linear_order_for(str(session.get("workflow_type") or reg.WORKFLOW_TYPE_DEFAULT))
    head, phase = compute_authoritative_step(smap, order)
    overall = str(session.get("overall_status") or "active")

    if trust == TRUST_CUSTOMER:
        if action_key in _POST_TRACK_COMPLETED_CUSTOMER_ACTIONS:
            msg = _check_post_track_customer_surface_allowed(session, smap)
            if msg:
                raise FlowEnforcementError(
                    "FLOW_ORDER_VIOLATION",
                    msg,
                    current_step=head,
                    expected_step=None,
                )
            return

        if action_key == ACTION_DISPUTES_BEGIN_NEXT_ROUND:
            msg = _check_begin_next_dispute_round_allowed(session, smap)
            if msg:
                raise FlowEnforcementError(
                    "FLOW_ORDER_VIOLATION",
                    msg,
                    current_step=head,
                    expected_step=None,
                )
            return

        if overall != "active":
            raise FlowEnforcementError(
                "WORKFLOW_NOT_ACTIVE",
                "This workflow is not active.",
                current_step=head,
                expected_step=None,
            )

        if action_key == "__step_start__":
            sid = step_id_arg or ""
            if sid not in reg.STEP_REGISTRY:
                raise FlowEnforcementError("INVALID_STEP", "Unknown step.", current_step=head, expected_step=sid)
            defn = reg.STEP_REGISTRY[sid]
            _require_head_match(head, phase, sid, defn=defn, smap=smap)
            return

        if action_key in _PREDICATE_ONLY:
            msg = _PREDICATE_ONLY[action_key](session, smap)
            if msg:
                raise FlowEnforcementError(
                    "FLOW_ORDER_VIOLATION",
                    msg,
                    current_step=head,
                    expected_step=None,
                )
            return

        if action_key == ACTION_REPORT_PDF_UPLOAD:
            if phase == "done":
                raise FlowEnforcementError(
                    "FLOW_ORDER_VIOLATION",
                    "This workflow has finished linear progression for this path.",
                    current_step=head,
                    expected_step="upload",
                )
            defn_upload = reg.STEP_REGISTRY["upload"]
            defn_review = reg.STEP_REGISTRY["review_claims"]
            row_u = smap.get("upload")
            row_r = smap.get("review_claims")
            st_u = row_u.get("status") if row_u else None
            st_r = row_r.get("status") if row_r else None
            if head == "upload" and st_u in defn_upload.allowed_entry_statuses:
                return
            if (
                head == "review_claims"
                and st_r in defn_review.allowed_entry_statuses
                and st_r != "completed"
            ):
                return
            raise FlowEnforcementError(
                "FLOW_ORDER_VIOLATION",
                "Upload a report when upload is your current step, or add another bureau PDF while review is still open.",
                current_step=head,
                expected_step="upload",
            )

        if action_key in _HEAD_CUSTOMER:
            sid = _HEAD_CUSTOMER[action_key]
            defn = reg.STEP_REGISTRY[sid]
            _require_head_match(head, phase, sid, defn=defn, smap=smap)
            return

        raise FlowEnforcementError("UNKNOWN_ACTION", f"Unknown action: {action_key!r}.")

    if trust == TRUST_INTERNAL:
        if overall not in ("active", "failed"):
            raise FlowEnforcementError(
                "WORKFLOW_STATE_INVALID",
                "Workflow must be active or failed for internal mutation.",
                current_step=head,
                expected_step=step_id_arg,
            )
        tid = (step_id_arg or "").strip()[:64]
        if action_key == INTERNAL_REMINDER_CANDIDATES:
            if overall != "active":
                raise FlowEnforcementError(
                    "WORKFLOW_NOT_ACTIVE",
                    "Reminder candidates require an active workflow.",
                    current_step=head,
                    expected_step=None,
                )
            return

        if tid not in reg.STEP_REGISTRY:
            raise FlowEnforcementError("INVALID_STEP", "Unknown step.", current_step=head, expected_step=tid)

        if phase == "done" and action_key != INTERNAL_SERVICE_COMPLETE:
            raise FlowEnforcementError(
                "FLOW_ORDER_VIOLATION",
                "Linear workflow is complete.",
                current_step=head,
                expected_step=tid,
            )

        if head != tid:
            raise FlowEnforcementError(
                "INTERNAL_STEP_MISMATCH",
                "Internal call targets a step that is not the current head.",
                current_step=head,
                expected_step=tid,
            )

        row = smap.get(tid)
        st = row.get("status") if row else None

        if action_key == INTERNAL_SERVICE_COMPLETE:
            if st not in ("available", "in_progress", "failed"):
                raise FlowEnforcementError(
                    "INVALID_STEP_STATUS",
                    "Service-complete requires available, in_progress, or failed step row.",
                    current_step=head,
                    expected_step=tid,
                )
        elif action_key == INTERNAL_SERVICE_FAIL:
            # Match WorkflowEngine.service_fail_step: fail from available, in_progress, or idempotent failed.
            if st not in ("available", "in_progress", "failed"):
                raise FlowEnforcementError(
                    "INVALID_STEP_STATUS",
                    "Service-fail requires available, in_progress, or failed step row.",
                    current_step=head,
                    expected_step=tid,
                )
        elif action_key == INTERNAL_ASYNC_STATE:
            if st != "in_progress":
                raise FlowEnforcementError(
                    "INVALID_STEP_STATUS",
                    "Async-state updates require in_progress step row.",
                    current_step=head,
                    expected_step=tid,
                )
        return

    if trust == TRUST_OPERATOR:
        if action_key == OPERATOR_CLEAR_STALLED:
            if overall != "active":
                raise FlowEnforcementError(
                    "WORKFLOW_NOT_ACTIVE",
                    "Clear-stalled requires an active workflow.",
                    current_step=head,
                    expected_step=None,
                )
            return

        if action_key == OPERATOR_PAYMENT_WAIVED:
            if overall != "active":
                raise FlowEnforcementError(
                    "WORKFLOW_NOT_ACTIVE",
                    "Payment waiver requires an active workflow.",
                    current_step=head,
                    expected_step="payment",
                )
            _require_head_match(head, phase, "payment", defn=reg.STEP_REGISTRY["payment"], smap=smap)
            return

        if action_key == OPERATOR_REOPEN_STEP:
            if overall not in ("active", "failed"):
                raise FlowEnforcementError(
                    "WORKFLOW_STATE_INVALID",
                    "Reopen requires an active or failed workflow.",
                    current_step=head,
                    expected_step=operator_target_step_id,
                )
            tid = (operator_target_step_id or "").strip()[:64]
            if tid not in reg.STEP_REGISTRY:
                raise FlowEnforcementError("INVALID_STEP", "Unknown step.", current_step=head, expected_step=tid)
            row = smap.get(tid)
            if not row or row.get("status") != "failed":
                raise FlowEnforcementError(
                    "STEP_NOT_FAILED",
                    "Reopen applies only to a failed step row.",
                    current_step=head,
                    expected_step=tid,
                )
            if tid not in lr_mod.FAILED_RETRYABLE_STEPS:
                raise FlowEnforcementError(
                    "STEP_NOT_REOPEN_ELIGIBLE",
                    "This step is not eligible for operator reopen.",
                    current_step=head,
                    expected_step=tid,
                )
            return

        if action_key in (
            OPERATOR_RECOVERY_RECORD,
            OPERATOR_RECOVERY_RETRY_STEP,
            OPERATOR_RECOVERY_RESUME,
            OPERATOR_RECOVERY_MAIL_RETRY,
            OPERATOR_MC_REMINDER_CANDIDATES,
        ):
            if overall not in ("active", "failed"):
                raise FlowEnforcementError(
                    "WORKFLOW_STATE_INVALID",
                    "Recovery tools require an active or failed workflow.",
                    current_step=head,
                    expected_step=None,
                )
            return

        raise FlowEnforcementError("UNKNOWN_ACTION", f"Unknown operator action: {action_key!r}.")

    raise FlowEnforcementError("UNKNOWN_TRUST", f"Unknown trust level: {trust!r}.")


def enforce_customer_action(workflow_id: str, action_key: str) -> None:
    """Backward-compatible alias for customer-only enforcement."""
    enforce_flow_action(workflow_id, action_key, trust=TRUST_CUSTOMER)


def assert_internal_service_fail_allowed(workflow_id: str, step_id: str) -> bool:
    """
    Trusted hooks before ``service_fail_step`` — same head/step rules as
    ``POST .../service-fail`` (head must match; row available/in_progress/failed).
    """
    wid = (workflow_id or "").strip()
    if not wid:
        return False
    try:
        enforce_flow_action(
            wid,
            INTERNAL_SERVICE_FAIL,
            trust=TRUST_INTERNAL,
            step_id_arg=step_id,
        )
    except FlowEnforcementError:
        return False
    return True


def assert_internal_service_complete_allowed(workflow_id: str, step_id: str) -> bool:
    """
    Trusted server hooks (report pipeline, Streamlit, DB): same head/status rules as
    ``POST .../service-complete`` before mutating via WorkflowEngine.
    """
    wid = (workflow_id or "").strip()
    if not wid:
        return False
    try:
        enforce_flow_action(
            wid,
            INTERNAL_SERVICE_COMPLETE,
            trust=TRUST_INTERNAL,
            step_id_arg=step_id,
        )
    except FlowEnforcementError:
        return False
    return True


def assert_customer_payment_capture_allowed(workflow_id: str) -> bool:
    """
    Stripe webhook / ``ensure_payment_step_after_purchase`` / reconcile: same rule as
    customer ``POST .../payment/reconcile`` (head must be payment).
    """
    wid = (workflow_id or "").strip()
    if not wid:
        return False
    try:
        enforce_customer_action(wid, ACTION_PAYMENT_RECONCILE)
    except FlowEnforcementError:
        return False
    return True


def assert_customer_payment_continue_credits_allowed(workflow_id: str) -> bool:
    """``complete_payment_with_existing_letter_entitlements`` — matches continue-with-credits route."""
    wid = (workflow_id or "").strip()
    if not wid:
        return False
    try:
        enforce_customer_action(wid, ACTION_PAYMENT_CONTINUE_CREDITS)
    except FlowEnforcementError:
        return False
    return True


def job_type_to_customer_action(job_type: str) -> Optional[str]:
    """Map async job types to customer flow actions (preflight before execution)."""
    if job_type == "letter_generation":
        return ACTION_LETTER_GENERATION_RUN
    return None


def describe_action_requirements(action_key: str) -> Dict[str, Any]:
    if action_key in _HEAD_CUSTOMER:
        sid = _HEAD_CUSTOMER[action_key]
        d = reg.STEP_REGISTRY.get(sid)
        return {
            "action": action_key,
            "kind": "head_bound",
            "canonicalStepId": sid,
            "allowedEntryStatuses": list(d.allowed_entry_statuses) if d else [],
        }
    if action_key in _POST_TRACK_COMPLETED_CUSTOMER_ACTIONS:
        return {
            "action": action_key,
            "kind": "post_track_surface",
        }
    if action_key == ACTION_DISPUTES_BEGIN_NEXT_ROUND:
        return {"action": action_key, "kind": "begin_next_dispute_round"}
    if action_key in _PREDICATE_ONLY:
        return {"action": action_key, "kind": "predicate"}
    return {"action": action_key, "kind": "unknown"}
