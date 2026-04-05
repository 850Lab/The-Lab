"""
Org program monetization: Stripe Checkout for cohort activation, webhook/reconcile unlock.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import auth
from database import get_db
from services.org_program_visibility_service import (
    build_org_outcomes_aggregate,
    list_org_program_participants,
)
from services.org_service import (
    get_organization,
    org_allows_participant_program_access,
    user_is_active_org_admin_for_org,
)
from stripe_client import create_checkout_session, verify_checkout_session

_log = logging.getLogger(__name__)

ORG_PROGRAM_ACTIVATION_PRODUCT_ID = "org_program_activation"
PURCHASE_KIND_ORG_ACTIVATION = "org_program_activation"


def org_activation_price_cents() -> int:
    raw = (os.environ.get("ORG_PROGRAM_ACTIVATION_PRICE_CENTS") or "9900").strip()
    try:
        n = int(raw)
        return max(n, 100)
    except ValueError:
        return 9900


def org_activation_label() -> str:
    return (os.environ.get("ORG_PROGRAM_ACTIVATION_LABEL") or "Organization program access").strip()[
        :120
    ]


def org_activation_catalog_entry() -> Dict[str, Any]:
    return {
        "product_id": ORG_PROGRAM_ACTIVATION_PRODUCT_ID,
        "price_cents": org_activation_price_cents(),
        "label": org_activation_label(),
    }


def user_may_checkout_org_activation(user_id: int, org_id: int) -> bool:
    u = auth.get_user_by_id(user_id)
    if u and (u.get("role") or "").strip() == "admin":
        return True
    return user_is_active_org_admin_for_org(user_id, org_id)


def apply_org_program_activation_paid(
    *,
    org_id: int,
    stripe_session_id: str,
    amount_cents: int,
    payer_user_id: int,
) -> Dict[str, Any]:
    """Idempotent unlock: full program access + audit fields."""
    sid = (stripe_session_id or "").strip()
    if not sid:
        return {"ok": False, "error": "missing_session_id"}
    expected = org_activation_price_cents()
    if int(amount_cents) != int(expected):
        return {"ok": False, "error": "amount_mismatch"}

    org = get_organization(org_id)
    if not org:
        return {"ok": False, "error": "org_not_found"}

    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            UPDATE organizations
            SET payment_access = 'full',
                program_access_activated_at = COALESCE(
                    program_access_activated_at, CURRENT_TIMESTAMP
                ),
                program_access_last_stripe_session_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, payment_access, program_access_activated_at
            """,
            (sid, org_id),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return {"ok": False, "error": "org_not_found"}
        conn.commit()

    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            "SELECT payment_access FROM organizations WHERE id = %s",
            (org_id,),
        )
        verify = cur.fetchone()
    pa = (verify.get("payment_access") or "").strip().lower() if verify else ""
    unlock_verified = pa == "full"
    err_safe = ""
    if not unlock_verified:
        err_safe = (
            f"After paid activation UPDATE, payment_access is {pa!r} (expected full). "
            f"Verify DB migration and organizations row id={org_id}."
        )[:500]
        _log.error(
            "org_program_activation: org %s payment_access is %r after unlock (expected full); session=%s",
            org_id,
            pa,
            sid[:32],
        )
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                """
                UPDATE organizations
                SET program_access_unlock_error_safe = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (err_safe, org_id),
            )
            conn.commit()
    else:
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                """
                UPDATE organizations
                SET program_access_unlock_error_safe = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (org_id,),
            )
            conn.commit()

    if not auth.payment_already_processed(sid):
        auth.record_payment(
            payer_user_id,
            int(amount_cents),
            stripe_session_id=sid,
            status="completed",
        )

    return {
        "ok": True,
        "organizationId": int(row["id"]),
        "paymentAccess": row.get("payment_access"),
        "programAccessActivatedAt": row.get("program_access_activated_at"),
        "programUnlockVerified": unlock_verified,
    }


def process_org_activation_checkout_session(*, session: Dict[str, Any]) -> Dict[str, Any]:
    """Webhook-shaped session dict (Stripe ``checkout.session.completed`` object)."""
    session_id = (session.get("id") or "").strip()
    payment_status = (session.get("payment_status") or "").strip()
    if payment_status != "paid":
        return {"ok": True, "skipped": "not_paid"}

    metadata = session.get("metadata") or {}
    if (metadata.get("purchase_kind") or "").strip() != PURCHASE_KIND_ORG_ACTIVATION:
        return {"ok": False, "error": "not_org_purchase"}

    try:
        user_id = int(metadata.get("user_id") or 0)
        org_id = int(metadata.get("organization_id") or 0)
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid_ids"}

    product_id = (metadata.get("product_id") or "").strip()
    if product_id != ORG_PROGRAM_ACTIVATION_PRODUCT_ID:
        return {"ok": False, "error": "product_mismatch"}

    amount = int(session.get("amount_total") or 0)
    cat = org_activation_catalog_entry()
    if amount != int(cat["price_cents"]):
        return {"ok": False, "error": "amount_mismatch"}

    user = auth.get_user_by_id(user_id)
    if not user:
        return {"ok": False, "error": "user_not_found"}

    cd = session.get("customer_details")
    if isinstance(cd, dict):
        session_email = str(cd.get("email") or session.get("customer_email") or "").lower().strip()
    else:
        session_email = str(session.get("customer_email") or "").lower().strip()
    user_email = (user.get("email") or "").lower().strip()
    if session_email and session_email != user_email:
        return {"ok": False, "error": "email_mismatch"}

    if not user_may_checkout_org_activation(user_id, org_id):
        return {"ok": False, "error": "not_org_billing_admin"}

    return apply_org_program_activation_paid(
        org_id=org_id,
        stripe_session_id=session_id,
        amount_cents=amount,
        payer_user_id=user_id,
    )


def start_org_program_activation_checkout(
    *,
    user_id: int,
    user_email: str,
    org_id: int,
    success_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    if not user_may_checkout_org_activation(user_id, org_id):
        return {"error": "not_org_billing_admin"}
    if not get_organization(org_id):
        return {"error": "Organization not found."}
    cat = org_activation_catalog_entry()
    return create_checkout_session(
        user_id,
        user_email,
        cat["product_id"],
        cat["label"],
        int(cat["price_cents"]),
        ai_rounds=0,
        letters=0,
        mailings=0,
        success_url=success_url,
        cancel_url=cancel_url,
        workflow_id="",
        extra_metadata={
            "purchase_kind": PURCHASE_KIND_ORG_ACTIVATION,
            "organization_id": str(org_id),
        },
    )


def reconcile_org_program_activation_checkout(
    *,
    checkout_session_id: str,
    user_id: int,
    user_email: str,
) -> Dict[str, Any]:
    sid = (checkout_session_id or "").strip()
    if not sid:
        return {"ok": False, "error": "missing_session_id"}

    result = verify_checkout_session(sid)
    if not result or result.get("payment_status") != "paid":
        return {"ok": False, "error": "session_not_paid_or_unverified"}

    meta = result.get("metadata") or {}
    if (meta.get("purchase_kind") or "").strip() != PURCHASE_KIND_ORG_ACTIVATION:
        return {"ok": False, "error": "not_org_purchase"}

    meta_uid = meta.get("user_id")
    session_email = (result.get("customer_email") or "").lower().strip()
    current_email = (user_email or "").lower().strip()
    if str(user_id) != str(meta_uid) or session_email != current_email:
        return {"ok": False, "error": "account_mismatch"}

    try:
        org_id = int(meta.get("organization_id") or 0)
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid_org"}

    product_id = (meta.get("product_id") or "").strip()
    if product_id != ORG_PROGRAM_ACTIVATION_PRODUCT_ID:
        return {"ok": False, "error": "product_mismatch"}

    amount = int(result.get("amount_total") or 0)
    if amount != org_activation_price_cents():
        return {"ok": False, "error": "product_mismatch"}

    if not user_may_checkout_org_activation(user_id, org_id):
        return {"ok": False, "error": "not_org_billing_admin"}

    out = apply_org_program_activation_paid(
        org_id=org_id,
        stripe_session_id=sid,
        amount_cents=amount,
        payer_user_id=user_id,
    )
    if not out.get("ok"):
        return {"ok": False, "error": out.get("error", "activation_failed")}
    return {
        "ok": True,
        "organizationId": org_id,
        "programAccessActivatedAt": out.get("programAccessActivatedAt"),
        "programUnlockVerified": out.get("programUnlockVerified"),
        "programAccessUnlockErrorSafe": out.get("programAccessUnlockErrorSafe"),
    }


def build_org_program_billing_snapshot(org_id: int) -> Dict[str, Any]:
    org = get_organization(org_id)
    if not org:
        return {"error": "Organization not found."}
    parts = list_org_program_participants(org_id)
    outcomes = build_org_outcomes_aggregate(org_id)
    allowed = org_allows_participant_program_access(org)
    pa = (org.get("payment_access") or "full").strip().lower()
    cat = org_activation_catalog_entry()
    return {
        "organizationId": org_id,
        "paymentAccess": pa,
        "programAccessAllowed": allowed,
        "programAccessActivatedAt": org.get("program_access_activated_at"),
        "programAccessUnlockErrorSafe": org.get("program_access_unlock_error_safe"),
        "onboardingStage": org.get("onboarding_stage"),
        "organizationStatus": org.get("status"),
        "usage": {
            "participantSeatsActive": len(parts),
            "programEnrollments": outcomes.get("programEnrollments"),
            "reportsUploaded": outcomes.get("reportsUploaded"),
            "disputeSelectionsSaved": outcomes.get("disputeSelectionsSaved"),
            "lettersGenerated": outcomes.get("lettersGenerated"),
        },
        "catalog": {
            "productId": cat["product_id"],
            "priceCents": int(cat["price_cents"]),
            "label": cat["label"],
        },
    }
