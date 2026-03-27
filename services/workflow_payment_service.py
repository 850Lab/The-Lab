"""
Workflow payment context + Stripe checkout reconcile for the customer HTTP API.

Mirrors Streamlit ``app.py`` payment return path and ``webhook_handler`` catalog rules.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import auth
import database as db
from database import get_db
from services.workflow.engine import WorkflowEngine, compute_authoritative_step
from services.workflow.repository import fetch_session, fetch_steps
from stripe_client import create_checkout_session, get_stripe_client, verify_checkout_session

_log = logging.getLogger(__name__)
_ENGINE = WorkflowEngine()

_PAYMENT_STEP_RETRY_ATTEMPTS = 5
_PAYMENT_STEP_RETRY_DELAY_SEC = 0.3


def _payment_step_row_completed(workflow_id: str) -> bool:
    steps = fetch_steps(workflow_id)
    for s in steps:
        if s.get("step_id") == "payment" and s.get("status") == "completed":
            return True
    return False


def _sync_payment_step_once(
    user_id: int,
    workflow_id: str,
    stripe_session_id: str,
    amount_cents: Optional[int],
    audit_source: str,
) -> bool:
    """Single attempt to complete the payment step; no retries."""
    wid = str(workflow_id).strip()
    if not wid:
        return True
    session = fetch_session(wid)
    if not session or int(session["user_id"]) != int(user_id):
        _log.warning(
            "payment step sync skipped: workflow %s missing or wrong owner for user %s",
            wid,
            user_id,
        )
        return False
    summary: Dict[str, Any] = {"stripeSessionId": stripe_session_id}
    if amount_cents is not None:
        summary["amountCents"] = int(amount_cents)
    ok = _ENGINE.service_complete_step(
        wid,
        "payment",
        summary,
        audit_source=(audit_source or "api:payment")[:64],
        audit_user_id=user_id,
    )
    return bool(ok)


def ensure_payment_step_after_purchase(
    *,
    user_id: int,
    workflow_id: Optional[str],
    stripe_session_id: str,
    amount_cents: Optional[int],
    audit_source: str,
) -> bool:
    """
    After entitlements are recorded for a Stripe session, advance the workflow ``payment`` step.

    Idempotent: safe if the step is already completed. Retries transient failures.
    Returns False only if the step is still not completed after retries (caller should surface recovery).
    """
    wid = (workflow_id or "").strip()
    if not wid:
        return True
    if _payment_step_row_completed(wid):
        return True
    sid = (stripe_session_id or "").strip()
    for attempt in range(_PAYMENT_STEP_RETRY_ATTEMPTS):
        if _payment_step_row_completed(wid):
            return True
        _sync_payment_step_once(user_id, wid, sid, amount_cents, audit_source)
        if _payment_step_row_completed(wid):
            return True
        if attempt + 1 < _PAYMENT_STEP_RETRY_ATTEMPTS:
            time.sleep(_PAYMENT_STEP_RETRY_DELAY_SEC)
    completed = _payment_step_row_completed(wid)
    if not completed:
        _log.error(
            "payment step still incomplete after %s attempts (user=%s workflow=%s session=%s)",
            _PAYMENT_STEP_RETRY_ATTEMPTS,
            user_id,
            wid,
            sid[:16] if sid else "",
        )
    return completed


def build_product_catalog() -> Dict[str, Dict[str, Any]]:
    catalog: Dict[str, Dict[str, Any]] = {}
    for pid, p in auth.PACKS.items():
        catalog[pid] = {
            "price_cents": p["price_cents"],
            "ai_rounds": p["ai_rounds"],
            "letters": p["letters"],
            "mailings": p["mailings"],
            "label": p["label"],
        }
    for pid, p in auth.ALA_CARTE.items():
        ent = {"ai_rounds": 0, "letters": 0, "mailings": 0}
        ent[p["type"]] = p["qty"]
        catalog[pid] = {
            "price_cents": p["price_cents"],
            "label": p["label"],
            **ent,
        }
    return catalog


def _parse_meta(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def needed_letters_from_workflow_session(session_row: Optional[Dict[str, Any]]) -> int:
    """
    Bureau letter count seeded at ``select_disputes`` completion (``metadata.mail``).
    """
    if not session_row:
        return 1
    meta = _parse_meta(session_row.get("metadata"))
    mail = meta.get("mail") or {}
    if not isinstance(mail, dict):
        return 1
    exp = mail.get("expected_unique_bureau_sends")
    if isinstance(exp, int) and exp > 0:
        return min(exp, 12)
    keys = mail.get("selected_bureau_keys")
    if isinstance(keys, list) and keys:
        return min(len(keys), 12)
    return 1


def workflow_payment_head_state(workflow_id: str) -> Tuple[Optional[str], str, Optional[Dict[str, Any]]]:
    steps = fetch_steps(workflow_id)
    smap = {s["step_id"]: s for s in steps}
    head, phase = compute_authoritative_step(smap)
    pay = smap.get("payment")
    return head, phase, pay


def user_is_founder(user_id: int) -> bool:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            "SELECT COALESCE(is_founder, FALSE) AS f FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    return bool(row and row.get("f"))


def recommend_pack_for_letters(
    needed_letters: int,
    *,
    needed_ai: int = 0,
    needed_mailings: int = 0,
    is_founder: bool = False,
) -> Optional[str]:
    recommended: Optional[str] = None
    if needed_ai > 0 or needed_letters > 0 or needed_mailings > 0:
        for pack_id, pack in auth.PACKS.items():
            if is_founder and pack_id == "deletion_sprint":
                continue
            if (
                pack["ai_rounds"] >= needed_ai
                and pack["letters"] >= needed_letters
                and pack["mailings"] >= needed_mailings
            ):
                recommended = pack_id
                break
    return recommended


def build_payment_context(
    workflow_id: str,
    user_id: int,
    *,
    is_admin: bool = False,
) -> Dict[str, Any]:
    sess = fetch_session(workflow_id)
    head, phase, pay_row = workflow_payment_head_state(workflow_id)
    needed_letters = needed_letters_from_workflow_session(sess)
    catalog = build_product_catalog()
    is_founder = user_is_founder(user_id)
    rec_id = recommend_pack_for_letters(
        needed_letters,
        needed_ai=0,
        needed_mailings=0,
        is_founder=is_founder,
    )
    rec_pack_id = rec_id or "digital_only"
    rec_pack = dict(auth.PACKS[rec_pack_id])
    rec_pack["id"] = rec_pack_id

    ent = auth.get_entitlements(user_id)
    has_letters = auth.has_entitlement(user_id, "letters", needed_letters)

    payment_completed = bool(pay_row and pay_row.get("status") == "completed")
    on_payment_step = head == "payment" and phase == "active"

    ds = _parse_meta(sess.get("metadata") if sess else {}).get("dispute_selection") or {}
    selected_ids = ds.get("selected_review_claim_ids") if isinstance(ds, dict) else None
    selected_count = len(selected_ids) if isinstance(selected_ids, list) else None

    other_packs: List[Dict[str, Any]] = []
    for pid, p in auth.PACKS.items():
        if pid == rec_pack_id:
            continue
        if is_founder and pid == "deletion_sprint":
            continue
        other_packs.append(
            {
                "id": pid,
                "label": p["label"],
                "price_cents": p["price_cents"],
                "ai_rounds": p["ai_rounds"],
                "letters": p["letters"],
                "mailings": p["mailings"],
            }
        )

    ala: List[Dict[str, Any]] = []
    for aid, item in auth.ALA_CARTE.items():
        if item["type"] != "letters":
            continue
        ala.append(
            {
                "id": aid,
                "label": item["label"],
                "price_cents": item["price_cents"],
                "letters": item["qty"],
                "ai_rounds": 0,
                "mailings": 0,
            }
        )

    stripe_ok = get_stripe_client() is not None
    origin = (os.environ.get("WORKFLOW_CUSTOMER_APP_ORIGIN") or os.environ.get("PUBLIC_APP_ORIGIN") or "").strip()

    return {
        "neededLetters": needed_letters,
        "selectedDisputeItemCount": selected_count,
        "recommendedPack": rec_pack,
        "otherPacks": other_packs,
        "alaCarteLetters": ala,
        "entitlements": {
            "letters": int(ent.get("letters", 0) or 0),
            "ai_rounds": int(ent.get("ai_rounds", 0) or 0),
            "mailings": int(ent.get("mailings", 0) or 0),
        },
        "hasSufficientLetterEntitlement": has_letters,
        "paymentStepStatus": pay_row.get("status") if pay_row else None,
        "paymentStepCompleted": payment_completed,
        "onPaymentStep": on_payment_step,
        "workflowHeadStepId": head,
        "workflowPhase": phase,
        "stripeCheckoutAvailable": stripe_ok,
        "checkoutReturnOriginConfigured": bool(origin),
        "catalogProductIds": list(catalog.keys()),
        "isAdmin": is_admin,
        "isFounder": is_founder,
    }


def reconcile_checkout_session_for_user(
    *,
    checkout_session_id: str,
    user_id: int,
    user_email: str,
) -> Dict[str, Any]:
    """
    Idempotent: credits entitlements once per Stripe session, then ensures the workflow
    ``payment`` step completes (retried). Reconcile may be called again after credits exist
    solely to finish the step.
    """
    sid = (checkout_session_id or "").strip()
    if not sid:
        return {"ok": False, "error": "missing_session_id"}

    result = verify_checkout_session(sid)
    if not result or result.get("payment_status") != "paid":
        return {"ok": False, "error": "session_not_paid_or_unverified"}

    meta = result.get("metadata") or {}
    meta_uid = meta.get("user_id")
    session_email = (result.get("customer_email") or "").lower().strip()
    current_email = (user_email or "").lower().strip()
    amount = int(result.get("amount_total") or 0)
    product_id = meta.get("product_id", "")

    owner_match = str(user_id) == str(meta_uid) and session_email == current_email

    catalog = build_product_catalog()
    catalog_entry = catalog.get(product_id)
    product_valid = catalog_entry is not None and int(catalog_entry["price_cents"]) == amount

    if not owner_match:
        return {"ok": False, "error": "account_mismatch"}
    if not product_valid:
        return {"ok": False, "error": "product_mismatch"}

    wf_meta = (meta.get("workflow_id") or "").strip()

    already = auth.entitlement_purchase_processed(sid)
    if already:
        step_ok = ensure_payment_step_after_purchase(
            user_id=user_id,
            workflow_id=wf_meta or None,
            stripe_session_id=sid,
            amount_cents=amount,
            audit_source="api:payment_reconcile_resume",
        )
        return {
            "ok": True,
            "alreadyProcessed": True,
            "paymentStepCompleted": step_ok,
            "workflowIdFromSession": wf_meta or None,
            "productId": product_id,
        }

    auth.add_entitlements(
        user_id,
        ai_rounds=int(catalog_entry["ai_rounds"]),
        letters=int(catalog_entry["letters"]),
        mailings=int(catalog_entry["mailings"]),
        source=f"stripe:{product_id}",
        stripe_session_id=sid,
        note=f'Purchased {catalog_entry["label"]} for ${amount / 100:.2f}',
    )
    auth.record_payment(user_id, amount, stripe_session_id=sid, status="completed")

    step_ok = ensure_payment_step_after_purchase(
        user_id=user_id,
        workflow_id=wf_meta or None,
        stripe_session_id=sid,
        amount_cents=amount,
        audit_source="api:payment_return",
    )

    if product_id == "deletion_sprint":
        try:
            db.create_sprint_guarantee(user_id, stripe_session_id=sid)
        except Exception as exc:
            _log.warning("create_sprint_guarantee failed: %s", exc)

    return {
        "ok": True,
        "alreadyProcessed": False,
        "paymentStepCompleted": step_ok,
        "workflowIdFromSession": wf_meta or None,
        "productId": product_id,
    }


def start_checkout_for_workflow(
    *,
    workflow_id: str,
    user_id: int,
    user_email: str,
    product_id: str,
    success_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    catalog = build_product_catalog()
    entry = catalog.get(product_id)
    if not entry:
        return {"error": "unknown_product", "messageSafe": "Unknown product."}

    label = str(entry["label"])
    price_cents = int(entry["price_cents"])
    ai_rounds = int(entry.get("ai_rounds", 0))
    letters = int(entry.get("letters", 0))
    mailings = int(entry.get("mailings", 0))

    return create_checkout_session(
        user_id,
        user_email,
        product_id,
        label,
        price_cents,
        ai_rounds=ai_rounds,
        letters=letters,
        mailings=mailings,
        success_url=success_url,
        cancel_url=cancel_url,
        workflow_id=workflow_id,
    )


def complete_payment_with_existing_letter_entitlements(
    workflow_id: str,
    user_id: int,
    needed_letters: int,
) -> bool:
    """Advance ``payment`` when the user already has enough letter credits (no Stripe)."""
    if needed_letters <= 0:
        needed_letters = 1
    if not auth.has_entitlement(user_id, "letters", needed_letters):
        return False
    return _ENGINE.service_complete_step(
        workflow_id,
        "payment",
        {
            "source": "existing_entitlements",
            "neededLetters": needed_letters,
        },
        audit_source="api:existing_letters",
        audit_user_id=user_id,
    )
