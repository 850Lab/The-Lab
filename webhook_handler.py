"""
webhook_handler.py | 850 Lab
Stripe webhook handler for reliable payment processing.
Processes checkout.session.completed events to credit entitlements
even if the user closes their browser after paying.
"""

import json
import os
import stripe
from stripe_client import get_stripe_credentials
import auth
import database as db


def _get_webhook_secret():
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "")


def handle_stripe_webhook(payload: bytes, sig_header: str) -> dict:
    webhook_secret = _get_webhook_secret()

    creds = get_stripe_credentials()
    if not creds:
        return {"status": 400, "body": "Stripe not configured"}

    stripe.api_key = creds["secret_key"]

    is_production = os.environ.get("REPLIT_DEPLOYMENT") == "1"

    if webhook_secret:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.error.SignatureVerificationError:
            return {"status": 400, "body": "Invalid signature"}
        except Exception as e:
            return {"status": 400, "body": f"Webhook error: {str(e)}"}
    elif is_production:
        print("[WEBHOOK] REJECTED: No STRIPE_WEBHOOK_SECRET set in production")
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

    if auth.entitlement_purchase_processed(session_id):
        return {"status": 200, "body": "Already processed"}

    metadata = session.get("metadata", {})
    user_id_str = metadata.get("user_id")
    product_id = metadata.get("product_id", "")
    amount = session.get("amount_total", 0)

    if not user_id_str:
        return {"status": 200, "body": "No user_id in metadata"}

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
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
        print(f"[WEBHOOK] Product mismatch: {product_id}, amount={amount}")
        return {"status": 200, "body": "Product/amount mismatch"}

    session_email = (session.get("customer_email") or session.get("customer_details", {}).get("email") or "").lower().strip()
    user = auth.get_user_by_id(user_id)
    if not user:
        print(f"[WEBHOOK] User {user_id} not found")
        return {"status": 200, "body": "User not found"}

    user_email = (user.get("email") or "").lower().strip()
    if session_email and session_email != user_email:
        print(f"[WEBHOOK] Email mismatch: session={session_email}, user={user_email}")
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
            print(f"[WEBHOOK] Sprint guarantee created for user {user_id}")
        except Exception as e:
            print(f"[WEBHOOK] Sprint guarantee creation failed: {e}")

    print(f"[WEBHOOK] Credited user {user_id}: {catalog_entry['label']}")
    return {"status": 200, "body": "OK"}
