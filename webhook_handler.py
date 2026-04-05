"""
webhook_handler.py | 850 Lab
Stripe webhook handler for reliable payment processing.
Processes checkout.session.completed events to credit entitlements
even if the user closes their browser after paying.
"""

import json
import logging
import os

import stripe
import auth
import database as db
from stripe_client import get_stripe_credentials

_log = logging.getLogger(__name__)


def _get_webhook_secret():
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "")


def handle_stripe_webhook(payload: bytes, sig_header: str) -> dict:
    webhook_secret = _get_webhook_secret()

    creds = get_stripe_credentials()
    if not creds:
        _log.error("Stripe webhook rejected: credentials not configured")
        return {"status": 400, "body": "Stripe not configured"}

    stripe.api_key = creds["secret_key"]

    is_production = os.environ.get("REPLIT_DEPLOYMENT") == "1"

    if webhook_secret:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.error.SignatureVerificationError:
            _log.warning("Stripe webhook signature verification failed")
            return {"status": 400, "body": "Invalid signature"}
        except Exception as e:
            _log.exception("Stripe webhook construct_event failed: %s", e)
            return {"status": 400, "body": f"Webhook error: {str(e)}"}
    elif is_production:
        _log.error("Stripe webhook rejected: STRIPE_WEBHOOK_SECRET missing in production")
        return {"status": 403, "body": "Webhook secret required in production"}
    else:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return {"status": 400, "body": "Invalid JSON"}

    if event.get("type") == "checkout.session.completed":
        session = event.get("data", {}).get("object", {})
        return _process_checkout_completed(session)

    return {"status": 200, "body": "OK"}


def _process_checkout_completed(session: dict) -> dict:
    session_id = session.get("id", "")
    payment_status = session.get("payment_status", "")

    if payment_status != "paid":
        return {"status": 200, "body": "Not paid yet, skipping"}

    metadata = session.get("metadata", {}) or {}
    purchase_kind = (metadata.get("purchase_kind") or "").strip()
    if purchase_kind == "org_program_activation":
        try:
            from services.org_commerce_service import process_org_activation_checkout_session

            out = process_org_activation_checkout_session(session=session)
            if out.get("skipped"):
                return {"status": 200, "body": "OK"}
            if not out.get("ok"):
                _log.error(
                    "Stripe webhook org activation FAILED session=%s out=%s",
                    session_id,
                    out,
                )
                return {
                    "status": 500,
                    "body": json.dumps(
                        {"error": "org_activation_failed", "detail": out.get("error")}
                    ),
                }
            if out.get("programUnlockVerified") is False:
                _log.error(
                    "Stripe webhook org activation: unlock not verified session=%s org=%s",
                    session_id,
                    out.get("organizationId"),
                )
                return {
                    "status": 500,
                    "body": json.dumps({"error": "org_unlock_verify_failed"}),
                }
            _log.info(
                "Stripe webhook org activation ok session=%s org=%s",
                session_id,
                out.get("organizationId"),
            )
            return {"status": 200, "body": "OK"}
        except Exception as e:
            _log.exception("Stripe webhook org program activation exception session=%s", session_id)
            return {"status": 500, "body": str(e)}

    if auth.entitlement_purchase_processed(session_id):
        return {"status": 200, "body": "Already processed"}

    user_id_str = metadata.get("user_id")
    workflow_id = (metadata.get("workflow_id") or "").strip() or None
    product_id = metadata.get("product_id", "")
    amount = session.get("amount_total", 0)

    if not user_id_str:
        _log.error(
            "Stripe webhook PAID session missing user_id metadata; session=%s amount=%s",
            session_id,
            amount,
        )
        return {"status": 200, "body": "No user_id in metadata"}

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        _log.error("Stripe webhook invalid user_id metadata session=%s", session_id)
        return {"status": 200, "body": "Invalid user_id"}

    PRODUCT_CATALOG = {}
    for pid, p in auth.PACKS.items():
        PRODUCT_CATALOG[pid] = {
            "price_cents": p["price_cents"],
            "ai_rounds": p["ai_rounds"],
            "letters": p["letters"],
            "mailings": p["mailings"],
            "label": p["label"],
        }
    for pid, p in auth.ALA_CARTE.items():
        ent = {"ai_rounds": 0, "letters": 0, "mailings": 0}
        ent[p["type"]] = p["qty"]
        PRODUCT_CATALOG[pid] = {
            "price_cents": p["price_cents"],
            "label": p["label"],
            **ent,
        }

    catalog_entry = PRODUCT_CATALOG.get(product_id)
    if not catalog_entry or catalog_entry["price_cents"] != amount:
        _log.error(
            "Stripe webhook product/amount mismatch session=%s product=%s amount=%s expected_cents=%s",
            session_id,
            product_id,
            amount,
            catalog_entry.get("price_cents") if catalog_entry else None,
        )
        return {"status": 200, "body": "Product/amount mismatch"}

    session_email = (
        session.get("customer_email") or session.get("customer_details", {}).get("email") or ""
    ).lower().strip()
    user = auth.get_user_by_id(user_id)
    if not user:
        _log.error(
            "Stripe webhook PAID but user not found session=%s user_id=%s",
            session_id,
            user_id,
        )
        return {"status": 200, "body": "User not found"}

    user_email = (user.get("email") or "").lower().strip()
    if session_email and session_email != user_email:
        _log.error(
            "Stripe webhook email mismatch session=%s session_email=%s user_email=%s",
            session_id,
            session_email,
            user_email,
        )
        return {"status": 200, "body": "Email mismatch"}

    auth.add_entitlements(
        user_id,
        ai_rounds=catalog_entry["ai_rounds"],
        letters=catalog_entry["letters"],
        mailings=catalog_entry["mailings"],
        source=f"stripe_webhook:{product_id}",
        stripe_session_id=session_id,
        note=f"Webhook: {catalog_entry['label']} for ${amount/100:.2f}",
    )
    auth.record_payment(
        user_id,
        amount,
        stripe_session_id=session_id,
        status="completed",
    )

    if product_id == "deletion_sprint":
        try:
            db.create_sprint_guarantee(user_id, stripe_session_id=session_id)
            _log.info("Stripe webhook sprint guarantee created user=%s", user_id)
        except Exception as e:
            _log.error("Stripe webhook sprint guarantee failed user=%s: %s", user_id, e)

    _log.info(
        "Stripe webhook credited user=%s product=%s session=%s",
        user_id,
        product_id,
        session_id,
    )

    if not workflow_id:
        _log.warning(
            "Stripe webhook missing workflow_id in metadata; entitlements credited but "
            "payment step not advanced session=%s user=%s",
            session_id,
            user_id,
        )
    else:
        try:
            from services.workflow.repository import fetch_session
            from services.workflow import hooks as workflow_hooks

            wf_row = fetch_session(workflow_id)
            if not wf_row or int(wf_row["user_id"]) != int(user_id):
                _log.critical(
                    "Stripe webhook: entitlements credited but workflow payment step skipped "
                    "(workflow missing or wrong owner) session=%s workflow_id=%s user=%s",
                    session_id,
                    workflow_id,
                    user_id,
                )
            else:
                workflow_hooks.notify_payment_completed(
                    user_id,
                    session_id,
                    workflow_id=workflow_id,
                    amount_cents=amount,
                )
        except Exception:
            _log.critical(
                "Stripe webhook: entitlements credited but workflow payment hook raised "
                "session=%s workflow=%s",
                session_id,
                workflow_id,
                exc_info=True,
            )

    return {"status": 200, "body": "OK"}
