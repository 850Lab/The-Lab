"""
Backend integration: connect domain events to WorkflowEngine.

Browser clients must not call these directly; use authenticated workflow HTTP routes
instead. Streamlit, webhooks, DB helpers, and pipelines call into this module as
trusted server code.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.workflow.engine import WorkflowEngine, compute_authoritative_step
from services.workflow.mail_gating import (
    apply_mail_progress_metadata,
    record_mail_attempt_failed,
    should_complete_mail_after_send,
)
from services.workflow.repository import (
    ensure_active_workflow_id,
    fetch_session,
    merge_into_workflow_metadata,
    update_session_fields,
)

_log = logging.getLogger(__name__)


def _engine() -> WorkflowEngine:
    return WorkflowEngine()


def _resolve_wid(user_id: int, workflow_id: Optional[str] = None) -> Optional[str]:
    if workflow_id:
        return workflow_id
    return ensure_active_workflow_id(user_id)


def _safe_call(fn, desc: str) -> None:
    try:
        fn()
    except Exception as exc:
        _log.warning("workflow hook %s: %s", desc, exc, exc_info=_log.isEnabledFor(logging.DEBUG))


# --- Upload / parse (report_pipeline) ---------------------------------------


def notify_upload_and_parse_success(
    user_id: int,
    report_id: Optional[int],
    bureau: str,
    filename: str,
    *,
    workflow_id: Optional[str] = None,
) -> None:
    """After PDF is parsed and structured data is stored (save_report succeeded)."""

    def _go() -> None:
        wid = _resolve_wid(user_id, workflow_id)
        if not wid:
            return
        eng = _engine()
        summary: Dict[str, Any] = {
            "bureau": bureau,
            "fileName": filename,
        }
        if report_id is not None:
            summary["reportId"] = report_id
        eng.service_complete_step(
            wid, "upload", summary, audit_source="report_pipeline", audit_user_id=user_id
        )
        eng.service_complete_step(
            wid,
            "parse_analyze",
            {"reportId": report_id, "bureau": bureau} if report_id else {"bureau": bureau},
            audit_source="report_pipeline",
            audit_user_id=user_id,
        )

    _safe_call(_go, "upload_and_parse_success")


def notify_upload_storage_failed(
    user_id: int,
    *,
    workflow_id: Optional[str] = None,
    message_safe: str = "Could not save your report. Try again.",
) -> None:
    def _go() -> None:
        wid = _resolve_wid(user_id, workflow_id)
        if not wid:
            return
        _engine().service_fail_step(
            wid,
            "upload",
            "UPLOAD_STORAGE_FAILED",
            message_safe,
            audit_source="report_pipeline",
            audit_user_id=user_id,
        )

    _safe_call(_go, "upload_storage_failed")


def notify_parse_failed(
    user_id: int,
    detail_safe: str,
    *,
    workflow_id: Optional[str] = None,
) -> None:
    """Parser or pipeline failed before a durable report row exists."""

    def _go() -> None:
        wid = _resolve_wid(user_id, workflow_id)
        if not wid:
            return
        msg = (detail_safe or "Parse failed.")[:500]
        _engine().service_fail_step(
            wid,
            "upload",
            "PARSE_FAILED",
            msg,
            audit_source="report_pipeline",
            audit_user_id=user_id,
        )

    _safe_call(_go, "parse_failed")


# --- Review / selection (Streamlit battle plan) -------------------------------


def notify_review_claims_completed(
    user_id: int,
    *,
    workflow_id: Optional[str] = None,
    item_count: Optional[int] = None,
    audit_source: str = "streamlit",
) -> None:
    def _go() -> None:
        wid = _resolve_wid(user_id, workflow_id)
        if not wid:
            return
        summary: Dict[str, Any] = {}
        if item_count is not None:
            summary["itemCount"] = item_count
        _engine().service_complete_step(
            wid,
            "review_claims",
            summary or {"confirmed": True},
            audit_source=audit_source,
            audit_user_id=user_id,
        )

    _safe_call(_go, "review_claims")


def complete_select_disputes_step(
    user_id: int,
    workflow_id: Optional[str],
    *,
    selected_count: int,
    bureaus: List[str],
    selected_review_claim_ids: Optional[List[str]] = None,
    audit_source: str = "api",
) -> bool:
    """
    Complete workflow step ``select_disputes`` and persist mail + optional dispute_selection ids.
    Returns False if the engine refused (wrong head / state).
    """
    wid = _resolve_wid(user_id, workflow_id)
    if not wid:
        return False
    summary: Dict[str, Any] = {"selectedCount": int(selected_count)}
    if bureaus:
        summary["bureaus"] = bureaus[:12]
    eng = _engine()
    ok = eng.service_complete_step(
        wid,
        "select_disputes",
        summary or {"confirmed": True},
        audit_source=audit_source,
        audit_user_id=user_id,
    )
    if not ok:
        return False

    uniq = len({(b or "").strip().lower() for b in (bureaus or []) if (b or "").strip()})
    expected = max(1, min(uniq if uniq else 1, 12))
    bureau_keys = sorted(
        {(b or "").strip().lower() for b in (bureaus or []) if (b or "").strip()}
    )[:12]
    mail_block = {
        "expected_unique_bureau_sends": expected,
        "selected_bureau_keys": bureau_keys,
        "confirmed_bureaus": [],
        "successful_send_count": 0,
        "failed_send_count": 0,
        "completed_all_sends": False,
    }

    def _mut(meta: Dict[str, Any]) -> None:
        meta["mail"] = mail_block
        if selected_review_claim_ids is not None:
            ids = [str(x) for x in selected_review_claim_ids[:500]]
            ds = meta.get("dispute_selection")
            if not isinstance(ds, dict):
                ds = {}
            else:
                ds = dict(ds)
            ds["selected_review_claim_ids"] = ids
            ds["draft_selected_review_claim_ids"] = ids
            meta["dispute_selection"] = ds

    merge_into_workflow_metadata(wid, _mut)
    return True


def notify_select_disputes_completed(
    user_id: int,
    *,
    workflow_id: Optional[str] = None,
    selected_count: Optional[int] = None,
    bureaus: Optional[List[str]] = None,
    audit_source: str = "streamlit",
    selected_review_claim_ids: Optional[List[str]] = None,
) -> None:
    def _go() -> None:
        sc = int(selected_count) if selected_count is not None else 0
        complete_select_disputes_step(
            user_id,
            workflow_id,
            selected_count=sc,
            bureaus=list(bureaus or []),
            selected_review_claim_ids=selected_review_claim_ids,
            audit_source=audit_source,
        )

    _safe_call(_go, "select_disputes")


# --- Payment (Stripe webhook) -------------------------------------------------


def notify_payment_completed(
    user_id: int,
    stripe_session_id: str,
    *,
    workflow_id: str,
    amount_cents: Optional[int] = None,
    audit_source: str = "webhook:stripe",
) -> None:
    """Completes workflow ``payment`` step with retries (same integrity as API reconcile)."""

    def _go() -> None:
        if not workflow_id or not str(workflow_id).strip():
            _log.warning("payment_completed skipped: missing workflow_id")
            return
        from services.workflow_payment_service import ensure_payment_step_after_purchase

        ok = ensure_payment_step_after_purchase(
            user_id=user_id,
            workflow_id=str(workflow_id).strip(),
            stripe_session_id=stripe_session_id,
            amount_cents=amount_cents,
            audit_source=audit_source or "webhook:stripe",
        )
        if not ok:
            _log.error(
                "notify_payment_completed: step not completed after retries (user=%s wf=%s)",
                user_id,
                workflow_id,
            )

    try:
        _go()
    except Exception as exc:
        _log.error("notify_payment_completed failed: %s", exc, exc_info=True)


def notify_payment_waived(
    user_id: int,
    *,
    workflow_id: str,
    actor_source: str,
    reason_safe: str,
) -> bool:
    """
    Trusted admin path: complete ``payment`` when product rules allow waiver.
    Head step must be ``payment`` in available/failed/in_progress.
    """

    def _go() -> bool:
        wid = str(workflow_id or "").strip()
        if not wid:
            return False
        session = fetch_session(wid)
        if not session or int(session["user_id"]) != int(user_id):
            return False
        eng = _engine()
        _, _, smap = eng.get_state_bundle(wid)
        head, _ = compute_authoritative_step(smap)
        if head != "payment":
            return False
        row = smap.get("payment")
        if not row or row.get("status") not in ("available", "failed", "in_progress"):
            return False
        summary: Dict[str, Any] = {
            "waived": True,
            "adminActor": (actor_source or "")[:64],
            "reason": (reason_safe or "")[:300],
        }
        src = f"admin:{(actor_source or 'operator')[:40]}"
        return eng.service_complete_step(
            wid,
            "payment",
            summary,
            audit_source=src,
            audit_user_id=user_id,
        )

    try:
        return bool(_go())
    except Exception:
        _log.warning("notify_payment_waived failed", exc_info=True)
        return False


# --- Letter generation --------------------------------------------------------


def complete_letter_generation_step(
    user_id: int,
    workflow_id: Optional[str],
    bureaus: List[str],
    *,
    audit_source: str = "api",
) -> bool:
    wid = _resolve_wid(user_id, workflow_id)
    if not wid:
        return False
    return _engine().service_complete_step(
        wid,
        "letter_generation",
        {"bureaus": [b.lower() for b in bureaus[:12]], "count": len(bureaus)},
        audit_source=(audit_source or "api")[:64],
        audit_user_id=user_id,
    )


def notify_letter_generation_completed(
    user_id: int,
    bureaus: List[str],
    *,
    workflow_id: Optional[str] = None,
    audit_source: str = "streamlit",
) -> None:
    def _go() -> None:
        complete_letter_generation_step(
            user_id,
            workflow_id,
            bureaus,
            audit_source=audit_source,
        )

    _safe_call(_go, "letter_generation")


# --- Proof bundle ------------------------------------------------------------


def maybe_notify_proof_attachment_completed(
    user_id: int,
    *,
    workflow_id: Optional[str] = None,
) -> None:
    """
    When government_id + address_proof uploads and signature exist, complete proof_attachment.
    Called from save_proof_upload after each insert.
    """

    def _go() -> None:
        import database as db

        id_docs = db.get_proof_docs_for_user(user_id, doc_types=["government_id"])
        addr_docs = db.get_proof_docs_for_user(user_id, doc_types=["address_proof"])
        sig = db.get_user_signature(user_id)
        if not id_docs or not addr_docs or not sig:
            return
        wid = _resolve_wid(user_id, workflow_id)
        if not wid:
            return
        _engine().service_complete_step(
            wid,
            "proof_attachment",
            {
                "hasGovernmentId": True,
                "hasAddressProof": True,
                "hasSignature": True,
            },
            audit_source="database",
            audit_user_id=user_id,
        )

    _safe_call(_go, "proof_attachment")


# --- Lob / mail + tracking ----------------------------------------------------


def notify_certified_mail_sent(
    user_id: int,
    bureau: str,
    tracking_number: str,
    *,
    lob_id: str = "",
    workflow_id: Optional[str] = None,
    report_id: Optional[int] = None,
) -> None:
    """
    After Lob accepted mail (DB row inserted). Completes `mail` then `track` only when
    all expected bureau sends (metadata.mail.expected_unique_bureau_sends) are satisfied.
    """

    def _go() -> None:
        wid = _resolve_wid(user_id, workflow_id)
        if not wid:
            return
        eng = _engine()
        mail_summary: Dict[str, Any] = {
            "bureau": bureau,
            "lobId": lob_id,
            "trackingNumber": (tracking_number or "")[:80],
        }
        if report_id is not None:
            mail_summary["reportId"] = report_id

        done, meta_patch = should_complete_mail_after_send(wid, bureau)
        apply_mail_progress_metadata(wid, meta_patch)

        if not done:
            _log.info(
                "mail gate: partial progress wf=%s bureau=%s patch=%s",
                wid,
                bureau,
                meta_patch,
            )
            return

        eng.service_complete_step(
            wid,
            "mail",
            mail_summary,
            audit_source="lob",
            audit_user_id=user_id,
        )
        eng.service_complete_step(
            wid,
            "track",
            {
                "bureau": bureau,
                "trackingNumber": (tracking_number or "")[:80],
                "mailGateComplete": True,
            },
            audit_source="lob",
            audit_user_id=user_id,
        )

    _safe_call(_go, "mail_and_track")


def notify_mail_send_failed(
    user_id: int,
    error_code: str,
    message_safe: str,
    *,
    workflow_id: Optional[str] = None,
) -> None:
    def _go() -> None:
        wid = _resolve_wid(user_id, workflow_id)
        if not wid:
            return
        try:
            record_mail_attempt_failed(
                wid,
                error_code=error_code,
                message_safe=message_safe,
            )
        except Exception:
            _log.debug("record_mail_attempt_failed skipped", exc_info=True)
        _engine().service_fail_step(
            wid,
            "mail",
            error_code[:64],
            (message_safe or "Mail send failed.")[:500],
            audit_source="lob",
            audit_user_id=user_id,
        )

    _safe_call(_go, "mail_failed")
