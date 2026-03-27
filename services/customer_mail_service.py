"""
Customer mail step: Lob certified send + workflow gate (same paths as Streamlit ``send_mail`` panel).

Uses ``lob_client.create_certified_letter``, ``database.save_lob_send``, and workflow hooks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import auth
import database as db
import lob_client
from services.customer_dispute_strategy import parse_workflow_metadata_value
from services.customer_letter_service import (
    get_letter_body_for_user,
    list_letters_for_workflow_customer,
)
from services.workflow.engine import compute_authoritative_step
from services.workflow.mail_gating import get_mail_gate_state
from services.workflow.repository import fetch_steps

_log = logging.getLogger(__name__)


def _norm_bureau(b: str) -> str:
    return (b or "").strip().lower()[:32]


def mail_step_head_state(workflow_id: str) -> Tuple[Optional[str], str, Optional[Dict[str, Any]]]:
    steps = fetch_steps(workflow_id)
    smap = {s["step_id"]: s for s in steps}
    head, phase = compute_authoritative_step(smap)
    return head, phase, smap.get("mail")


def selected_bureau_keys_from_session(session_row: Optional[Dict[str, Any]]) -> List[str]:
    if not session_row:
        return []
    meta = parse_workflow_metadata_value(session_row.get("metadata"))
    mail = meta.get("mail") or {}
    raw = mail.get("selected_bureau_keys") or []
    if not isinstance(raw, list):
        return []
    out = [_norm_bureau(str(x)) for x in raw if str(x).strip()]
    seen = set()
    uniq: List[str] = []
    for b in out:
        if b and b not in seen:
            seen.add(b)
            uniq.append(b)
    return uniq[:12]


def resolve_mail_targets(
    user_id: int,
    selected_keys: List[str],
) -> List[Dict[str, Any]]:
    letters = list_letters_for_workflow_customer(user_id)
    by_bureau: Dict[str, Dict[str, Any]] = {}
    for L in letters:
        b = _norm_bureau(str(L.get("bureau") or ""))
        if b and b not in by_bureau:
            by_bureau[b] = L
    keys = selected_keys if selected_keys else sorted(by_bureau.keys())
    return [by_bureau[k] for k in keys if k in by_bureau]


def _parse_lob_dt(dt: Any) -> Optional[datetime]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def latest_lob_row_for_target(user_id: int, bureau: str, report_id: Any) -> Optional[Dict[str, Any]]:
    """Latest ``lob_sends`` row for bureau+report (any status), by ``created_at``."""
    b = _norm_bureau(bureau)
    matches: List[Dict[str, Any]] = []
    for r in db.get_lob_sends_for_user(user_id):
        if (r.get("bureau") or "").lower() != b:
            continue
        if r.get("report_id") != report_id:
            continue
        matches.append(dict(r))
    if not matches:
        return None
    matches.sort(
        key=lambda x: _parse_lob_dt(x.get("created_at"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return matches[0]


def _per_bureau_mail_state(lob_r: Optional[Dict[str, Any]]) -> Tuple[str, bool, bool]:
    """
    Returns (customer_state, is_test_send, has_tracking_url).
    customer_state: pending | processing | sending_failed | sent_test | sent_live | tracking_available
    """
    if not lob_r:
        return "pending", False, False
    st = str(lob_r.get("status") or "").lower()
    if st == "error":
        return "sending_failed", False, False
    if st == "mailed":
        is_test = bool(lob_r.get("is_test"))
        tn = str(lob_r.get("tracking_number") or "")
        trk_url = lob_client.get_tracking_url(tn) if tn else ""
        has_trk = bool(trk_url)
        if is_test:
            return ("sent_test", True, has_trk)
        if has_trk:
            return ("tracking_available", False, True)
        return ("sent_live", False, False)
    return "processing", False, False


def _build_mail_status(
    *,
    mail_step_failed: bool,
    has_letters: bool,
    proof_both: bool,
    lob_configured: bool,
    lob_test_mode: bool,
    requires_live_for_customer: bool,
    customer_block_reason: Optional[str],
    has_credits: bool,
    is_admin: bool,
    pending_ct: int,
    mailed_ct: int,
    target_count: int,
    per_bureau: List[Dict[str, Any]],
    mail_gate_last_failure: str,
) -> Dict[str, Any]:
    has_tracking_any = any(bool(b.get("trackingUrl")) for b in per_bureau)
    is_blocked = bool(customer_block_reason) or not lob_configured
    credits_block = not is_admin and not has_credits and has_letters and proof_both

    primary = "ready_to_send"
    title = "Certified mail"
    message = ""
    block_detail = (customer_block_reason or "").strip() if customer_block_reason else ""

    if mail_step_failed:
        primary = "sending_failed"
        title = "Send step needs attention"
        message = (
            "A previous send attempt failed for this workflow."
            + (
                f" Last detail: {mail_gate_last_failure[:320]}"
                if mail_gate_last_failure
                else " Retry from this page or contact support if it keeps failing."
            )
        )
    elif is_blocked:
        primary = "send_blocked"
        title = "Sending is blocked"
        if not lob_configured:
            message = (
                "Certified mail is not configured on the server (Lob API key missing). "
                "Nothing can be submitted until this is fixed."
            )
        else:
            message = block_detail or "Sending is not available right now."
    elif not has_letters:
        primary = "no_letters"
        title = "Letters not ready for mail"
        message = (
            "Dispute letters are not on file for your selected bureaus yet. "
            "Finish letter generation first — generating does not send mail."
        )
    elif not proof_both:
        primary = "proof_required"
        title = "Proof required before sending"
        message = (
            "Government ID and proof of address must be on file before certified mail can go out. "
            "Complete the proof step first."
        )
    elif credits_block:
        primary = "send_blocked"
        title = "No mailing credits"
        message = (
            "You need at least one mailing credit to send. "
            "Purchase mailings or upgrade your pack in the main app."
        )
    elif target_count > 0 and mailed_ct >= target_count and pending_ct == 0:
        all_test = all(b.get("isTest") for b in per_bureau)
        all_live = all(not b.get("isTest") for b in per_bureau)
        if all_test:
            primary = "sent_test"
            title = "Test sends only (no USPS mail)"
            message = (
                "Every recorded send used Lob test mode. "
                "No physical letters were mailed through USPS."
            )
        elif all_live:
            primary = "tracking_available" if has_tracking_any else "sent_live"
            title = (
                "Letters submitted for mailing"
                if primary == "sent_live"
                else "Tracking available"
            )
            message = (
                "Live sends were accepted by the mail processor. "
                "USPS tracking shows handoff and transit — it is not a guarantee of delivery."
                if primary == "tracking_available"
                else (
                    "Live sends were accepted by the mail processor. "
                    "Open each bureau below for tracking when a USPS number is on file."
                )
            )
        else:
            primary = "sent_mixed"
            title = "Mix of test and live sends"
            message = (
                "Some bureaus were sent in Lob test mode (no USPS mail); "
                "others used live mail. Check each bureau row for details."
            )
    elif mailed_ct > 0 and pending_ct > 0:
        primary = "partially_sent"
        title = "Some letters sent, some waiting"
        message = (
            "One or more bureaus are already on file with the mail processor; "
            "finish the rest from this page when you are ready."
        )
    else:
        primary = "ready_to_send"
        title = "Ready to send your letters"
        if lob_test_mode:
            message = (
                "Your letters are generated and proof is on file. "
                "The server is using a Lob test key — if you send now, Lob may accept the request "
                "but USPS will not receive a real letter."
            )
        else:
            message = (
                "Your letters are generated and proof is on file. "
                "Each bureau send uses one mailing credit after the processor accepts the request."
            )

    if (
        primary == "ready_to_send"
        and requires_live_for_customer
        and lob_test_mode
        and not is_blocked
    ):
        primary = "send_blocked"
        title = "Live mail required"
        message = (
            "This server requires a live Lob key for customer sends. "
            "Test keys cannot be used to submit real certified mail here."
        )

    done_all = (
        target_count > 0
        and mailed_ct >= target_count
        and pending_ct == 0
    )
    if done_all:
        is_send_blocked = False
    else:
        is_send_blocked = bool(
            mail_step_failed
            or not lob_configured
            or bool(customer_block_reason)
            or credits_block
            or not proof_both
            or not has_letters
            or (requires_live_for_customer and lob_test_mode)
        )

    return {
        "primaryState": primary,
        "title": title,
        "message": message,
        "isBlocked": is_send_blocked,
        "isTestMode": bool(lob_test_mode),
        "requiresLiveForCustomerSend": bool(requires_live_for_customer),
        "hasTracking": bool(has_tracking_any),
        "lettersGenerated": bool(has_letters),
        "proofComplete": bool(proof_both),
        "mailingCreditsAvailable": bool(is_admin or has_credits),
        "pendingBureauCount": int(pending_ct),
        "mailedBureauCount": int(mailed_ct),
        "perBureau": per_bureau,
    }


def _proof_attachments(user_id: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    hp = db.has_proof_docs(user_id)
    if not hp.get("both"):
        return [], "Upload government ID and proof of address before sending."
    attachments: List[Dict[str, Any]] = []
    id_docs = db.get_proof_docs_for_user(user_id, doc_types=["government_id"])
    if id_docs:
        f = db.get_proof_doc_file(id_docs[0]["id"], user_id)
        if f and f.get("file_data"):
            attachments.append(
                {
                    "name": "Government-Issued ID",
                    "data": bytes(f["file_data"]),
                    "type": f.get("file_type") or "image/png",
                }
            )
    addr_docs = db.get_proof_docs_for_user(user_id, doc_types=["address_proof"])
    if addr_docs:
        f = db.get_proof_doc_file(addr_docs[0]["id"], user_id)
        if f and f.get("file_data"):
            attachments.append(
                {
                    "name": "Proof of Address",
                    "data": bytes(f["file_data"]),
                    "type": f.get("file_type") or "image/png",
                }
            )
    if len(attachments) < 2:
        return [], "Could not load saved proof documents. Re-upload on the proof step."
    return attachments, None


def build_mail_context_payload(
    user_id: int,
    workflow_id: str,
    *,
    session_row: Optional[Dict[str, Any]],
    is_admin: bool,
) -> Dict[str, Any]:
    head, phase, mail_row = mail_step_head_state(workflow_id)
    meta = parse_workflow_metadata_value((session_row or {}).get("metadata"))
    expected, confirmed, failed_ct = get_mail_gate_state(meta)
    mail_meta = meta.get("mail") if isinstance(meta.get("mail"), dict) else {}
    last_fail = ""
    if isinstance(mail_meta, dict):
        last_fail = str(mail_meta.get("last_failure_message_safe") or "")[:400]

    selected = selected_bureau_keys_from_session(session_row)
    targets = resolve_mail_targets(user_id, selected)

    bureau_payload: List[Dict[str, Any]] = []
    for t in targets:
        b = _norm_bureau(str(t.get("bureau") or ""))
        rid = t.get("reportId")
        lid = t.get("id")
        lob_r = latest_lob_row_for_target(user_id, b, rid)
        mailed = bool(lob_r and str(lob_r.get("status") or "").lower() == "mailed")
        mail_row_state, is_test_send, _has_trk_flag = _per_bureau_mail_state(lob_r)
        tn = ""
        trk_url = ""
        exp_del = ""
        lob_id_str = ""
        if lob_r:
            lob_id_str = str(lob_r.get("lob_id") or "")
            tn = str(lob_r.get("tracking_number") or "")
            trk_url = lob_client.get_tracking_url(tn) if tn else ""
            exp_del = str(lob_r.get("expected_delivery") or "")
        err_msg = ""
        if lob_r and str(lob_r.get("status") or "").lower() == "error":
            err_msg = str(lob_r.get("error_message") or "")[:400]
        bureau_payload.append(
            {
                "bureau": b,
                "bureauDisplay": (t.get("bureauDisplay") or b.title()),
                "letterId": lid,
                "reportId": rid,
                "sendStatus": "mailed" if mailed else "pending",
                "mailRowState": mail_row_state,
                "lobId": lob_id_str,
                "isTestSend": bool(is_test_send) if mailed else False,
                "lobErrorMessageSafe": err_msg,
                "trackingNumber": tn,
                "trackingUrl": trk_url,
                "expectedDelivery": exp_del,
            }
        )

    hp = db.has_proof_docs(user_id)
    ent = auth.get_entitlements(user_id)
    try:
        mail_bal = int(ent.get("mailings", 0) or 0)
    except (TypeError, ValueError):
        mail_bal = 0

    cost = lob_client.estimate_cost(return_receipt=True)
    mail_row_status = (mail_row or {}).get("status")

    cust_mail_block = lob_client.customer_mail_send_blocked_reason(is_admin=is_admin)

    done_row_states = ("sent_test", "sent_live", "tracking_available")
    mailed_ct = sum(1 for x in bureau_payload if x.get("mailRowState") in done_row_states)
    pending_ct = len(bureau_payload) - mailed_ct

    per_bureau_status: List[Dict[str, Any]] = [
        {
            "bureauKey": str(x.get("bureau") or ""),
            "state": str(x.get("mailRowState") or "pending"),
            "trackingUrl": str(x.get("trackingUrl") or ""),
            "lobId": str(x.get("lobId") or ""),
            "isTest": bool(x.get("isTestSend")),
            "trackingNumber": str(x.get("trackingNumber") or ""),
            "expectedDelivery": str(x.get("expectedDelivery") or ""),
            "errorMessageSafe": str(x.get("lobErrorMessageSafe") or "")[:400],
        }
        for x in bureau_payload
    ]

    mail_status_block = _build_mail_status(
        mail_step_failed=mail_row_status == "failed",
        has_letters=len(bureau_payload) > 0,
        proof_both=bool(hp.get("both")),
        lob_configured=lob_client.is_configured(),
        lob_test_mode=lob_client.is_test_mode(),
        requires_live_for_customer=lob_client.require_live_lob_for_customer_send(),
        customer_block_reason=cust_mail_block,
        has_credits=bool(is_admin or auth.has_entitlement(user_id, "mailings", 1)),
        is_admin=is_admin,
        pending_ct=pending_ct,
        mailed_ct=mailed_ct,
        target_count=len(bureau_payload),
        per_bureau=per_bureau_status,
        mail_gate_last_failure=last_fail,
    )

    return {
        "workflowHeadStepId": head,
        "workflowPhase": phase,
        "mailStepStatus": mail_row_status,
        "mailStepFailed": mail_row_status == "failed",
        "onMailStep": head == "mail" and phase == "active",
        "mailGateExpected": expected,
        "mailGateConfirmedBureaus": confirmed,
        "mailGateFailedSendCount": failed_ct,
        "mailGateLastFailureMessageSafe": last_fail,
        "bureauTargets": bureau_payload,
        "pendingSendCount": pending_ct,
        "mailedCount": mailed_ct,
        "hasLetters": len(bureau_payload) > 0,
        "proofBothOnFile": bool(hp.get("both")),
        "lobConfigured": lob_client.is_configured(),
        "lobTestMode": lob_client.is_test_mode(),
        "requiresLiveLobForCustomerSend": lob_client.require_live_lob_for_customer_send(),
        "customerMailSendBlocked": bool(cust_mail_block),
        "customerMailSendBlockedReason": (cust_mail_block or "")[:400],
        "hasMailingsEntitlement": is_admin or auth.has_entitlement(user_id, "mailings", 1),
        "mailingsBalance": mail_bal,
        "costEstimate": {
            "totalCents": cost.get("total_cents"),
            "totalDisplay": cost.get("total_display"),
            "breakdown": cost.get("breakdown"),
        },
        "usStateOptions": list(lob_client.US_STATES),
        "mailStatus": mail_status_block,
    }


def send_certified_letter_for_bureau(
    user_id: int,
    workflow_id: str,
    bureau_raw: str,
    from_address: Dict[str, str],
    return_receipt: bool,
    *,
    session_row: Optional[Dict[str, Any]],
    is_admin: bool,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    One Lob send for a bureau letter. Deducts mailing entitlement (non-admin).
    On Lob API failure, calls ``notify_mail_send_failed`` (matches Streamlit).
    """
    bureau = _norm_bureau(bureau_raw)
    if not bureau:
        return None, "Missing bureau."

    head, phase, _ = mail_step_head_state(workflow_id)
    if phase == "done" or head != "mail":
        return None, "Certified mail is not the current workflow step."

    selected = selected_bureau_keys_from_session(session_row)
    targets = resolve_mail_targets(user_id, selected)
    target = next((t for t in targets if _norm_bureau(str(t.get("bureau") or "")) == bureau), None)
    if not target:
        return None, "No saved letter found for that bureau."

    rid = target.get("reportId")
    lid = target.get("id")
    if lid is None:
        return None, "Letter id missing for this bureau."
    if db.has_been_sent_via_lob(user_id, bureau, report_id=rid):
        return None, "This bureau letter was already mailed."

    attachments, att_err = _proof_attachments(user_id)
    if att_err:
        return None, att_err

    lob_block = lob_client.customer_mail_send_blocked_reason(is_admin=is_admin)
    if lob_block:
        return None, lob_block

    if not is_admin and not auth.has_entitlement(user_id, "mailings", 1):
        return None, "No mailing credits remaining."

    v = lob_client.validate_address(from_address)
    if not v.get("valid"):
        return None, str(v.get("error") or "Invalid return address.")

    letter_text = get_letter_body_for_user(user_id, int(lid))
    if not letter_text:
        return None, "Letter text not found for this bureau."

    result = lob_client.create_certified_letter(
        from_address=from_address,
        to_bureau=bureau,
        letter_text=letter_text,
        return_receipt=return_receipt,
        description=f"850 Lab dispute - {bureau.title()}",
        attachments=attachments,
    )

    cost = lob_client.estimate_cost(return_receipt=return_receipt)

    if result.get("success"):
        if not is_admin:
            if not auth.spend_entitlement(user_id, "mailings", 1):
                _log.critical(
                    "Lob reported success but mailing credit could not be debited (user=%s bureau=%s); "
                    "letter was still sent via Lob.",
                    user_id,
                    bureau,
                )
        try:
            db.log_activity(user_id, "mail_sent", f"Certified mail to {bureau}", "DONE")
        except Exception:
            pass
        db.save_lob_send(
            user_id=user_id,
            report_id=rid,
            bureau=bureau,
            lob_id=str(result.get("lob_id") or ""),
            tracking_number=str(result.get("tracking_number") or ""),
            status="mailed",
            from_address=from_address,
            to_address=lob_client.get_bureau_address(bureau) or {},
            cost_cents=int(cost.get("total_cents") or 0),
            return_receipt=return_receipt,
            is_test=bool(result.get("is_test", False)),
            expected_delivery=str(result.get("expected_delivery") or ""),
            workflow_id=workflow_id,
        )
        return result, None

    err_msg = str(result.get("error") or "Certified mail could not be sent.")[:500]
    try:
        from services.workflow import hooks as workflow_hooks

        workflow_hooks.notify_mail_send_failed(
            user_id,
            str(result.get("error") or "MAIL_SEND_FAILED")[:64],
            err_msg,
            workflow_id=workflow_id,
        )
    except Exception:
        _log.debug("notify_mail_send_failed skipped", exc_info=True)
    return result, None
