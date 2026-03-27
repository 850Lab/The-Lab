"""
Deterministic workflow integrity hints for customer recovery UI.

All flags are derived from DB workflow state, entitlements, proof uploads, Lob config,
and entitlement_transactions vs lob_sends — no guessing or client-side inference.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

import auth
import database as db
import lob_client
from services.workflow.engine import compute_authoritative_step
from services.workflow.repository import fetch_session, fetch_steps
from services.workflow_payment_service import (
    needed_letters_from_workflow_session,
)

NextRequiredAction = Literal["upload", "pay", "generate", "proof", "mail", "track"]


def next_required_action_from_head(
    head: Optional[str],
    phase: str,
) -> NextRequiredAction:
    if phase == "done" or not head:
        return "track"
    if head in ("upload", "parse_analyze", "review_claims", "select_disputes"):
        return "upload"
    if head == "payment":
        return "pay"
    if head == "letter_generation":
        return "generate"
    if head == "proof_attachment":
        return "proof"
    if head == "mail":
        return "mail"
    if head == "track":
        return "track"
    return "track"


def _last_mailings_debit_ts(user_id: int) -> Optional[datetime]:
    with db.get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT created_at
            FROM entitlement_transactions
            WHERE user_id = %s
              AND transaction_type = 'debit'
              AND COALESCE(mailings, 0) > 0
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (int(user_id),),
        )
        row = cur.fetchone()
    if not row:
        return None
    ts = row.get("created_at")
    return ts if isinstance(ts, datetime) else None


def _last_mailed_lob_ts(user_id: int) -> Optional[datetime]:
    with db.get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT created_at
            FROM lob_sends
            WHERE user_id = %s AND status = 'mailed'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (int(user_id),),
        )
        row = cur.fetchone()
    if not row:
        return None
    ts = row.get("created_at")
    return ts if isinstance(ts, datetime) else None


def _mailing_debit_without_mailed_send(user_id: int) -> bool:
    """
    True when the latest mailings entitlement debit is newer than any mailed Lob row.
    With spend-after-success this should be rare; indicates legacy paths or inconsistency.
    """
    d_ts = _last_mailings_debit_ts(user_id)
    if not d_ts:
        return False
    m_ts = _last_mailed_lob_ts(user_id)
    if not m_ts:
        return True
    return d_ts > m_ts


def build_integrity_hints(user_id: int, workflow_id: str) -> Dict[str, Any]:
    uid = int(user_id)
    wid = str(workflow_id).strip()
    steps: List[Dict[str, Any]] = fetch_steps(wid)
    smap = {s["step_id"]: s for s in steps}
    head, phase = compute_authoritative_step(smap)
    sess = fetch_session(wid)
    if not sess:
        # Owned-workflow routes should not hit this; keep deterministic defaults.
        return {
            "entitlementsButPaymentIncomplete": False,
            "paymentCompletedButWrongStep": False,
            "mailingDebitWithoutSend": False,
            "proofIncomplete": False,
            "mailBlocked": False,
            "workflowStepMismatch": False,
            "nextRequiredAction": "track",
        }

    pay_row = smap.get("payment")
    payment_completed = bool(pay_row and pay_row.get("status") == "completed")
    needed_letters = needed_letters_from_workflow_session(sess)
    has_letter_entitlement = auth.has_entitlement(uid, "letters", needed_letters)

    on_payment_head = phase == "active" and head == "payment"
    entitlements_but_payment_incomplete = bool(
        on_payment_head and not payment_completed and has_letter_entitlement
    )

    session_current = sess.get("current_step")
    sc = session_current if isinstance(session_current, str) else None
    payment_completed_wrong_step = bool(payment_completed and sc == "payment")

    overall = sess.get("overall_status")
    workflow_step_mismatch = False
    if overall == "active" and phase == "active" and head:
        if sc is None:
            workflow_step_mismatch = True
        elif sc != head:
            workflow_step_mismatch = True
    elif overall == "active" and phase == "done":
        # All step rows completed but session still marked active — any current_step is drift.
        if sc is not None:
            workflow_step_mismatch = True

    hp = db.has_proof_docs(uid)
    proof_both = bool(hp.get("both")) if isinstance(hp, dict) else False
    proof_incomplete = bool(
        phase == "active"
        and head in ("proof_attachment", "mail")
        and not proof_both
    )

    lob_block = lob_client.customer_mail_send_blocked_reason(is_admin=False)
    mail_blocked = bool(
        lob_block
        and phase == "active"
        and head in ("proof_attachment", "mail")
    )

    mailing_debit_without_send = _mailing_debit_without_mailed_send(uid)

    next_action = next_required_action_from_head(head, phase)
    if proof_incomplete:
        next_action = "proof"

    return {
        "entitlementsButPaymentIncomplete": entitlements_but_payment_incomplete,
        "paymentCompletedButWrongStep": payment_completed_wrong_step,
        "mailingDebitWithoutSend": mailing_debit_without_send,
        "proofIncomplete": proof_incomplete,
        "mailBlocked": mail_blocked,
        "workflowStepMismatch": workflow_step_mismatch,
        "nextRequiredAction": next_action,
    }
