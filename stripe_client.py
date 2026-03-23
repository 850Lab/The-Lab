"""
stripe_client.py | 850 Lab
Stripe integration for Python/Streamlit via Replit Connection API
Supports pack and à la carte entitlement purchases
"""

import os
import json
import requests

_stripe = None

def _get_stripe():
    global _stripe
    if _stripe is None:
        import stripe
        _stripe = stripe
    return _stripe


_cached_credentials = None


def _get_replit_token():
    repl_identity = os.environ.get('REPL_IDENTITY')
    if repl_identity:
        return f'repl {repl_identity}'
    web_repl_renewal = os.environ.get('WEB_REPL_RENEWAL')
    if web_repl_renewal:
        return f'depl {web_repl_renewal}'
    return None


def get_stripe_credentials():
    global _cached_credentials
    if _cached_credentials:
        return _cached_credentials

    secret = os.environ.get('STRIPE_SECRET_KEY')
    publishable = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    if secret and publishable:
        _cached_credentials = {
            'publishable_key': publishable,
            'secret_key': secret,
        }
        return _cached_credentials

    hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
    token = _get_replit_token()

    if not hostname or not token:
        return None

    is_production = os.environ.get('REPLIT_DEPLOYMENT') == '1'
    target_env = 'production' if is_production else 'development'

    try:
        url = f'https://{hostname}/api/v2/connection'
        resp = requests.get(
            url,
            params={
                'include_secrets': 'true',
                'connector_names': 'stripe',
                'environment': target_env,
            },
            headers={
                'Accept': 'application/json',
                'X_REPLIT_TOKEN': token,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        connection = data.get('items', [None])[0]
        if not connection:
            return None

        settings = connection.get('settings', {})
        publishable = settings.get('publishable')
        secret = settings.get('secret')

        if not publishable or not secret:
            return None

        _cached_credentials = {
            'publishable_key': publishable,
            'secret_key': secret,
        }
        return _cached_credentials

    except Exception as e:
        print(f"[stripe_client] Error fetching credentials: {e}")
        return None


def get_stripe_client():
    creds = get_stripe_credentials()
    if not creds:
        return None
    s = _get_stripe()
    s.api_key = creds['secret_key']
    return s


def create_checkout_session(user_id: int, user_email: str, product_id: str,
                            product_label: str, amount_cents: int,
                            ai_rounds: int = 0, letters: int = 0, mailings: int = 0,
                            success_url: str = None, cancel_url: str = None):
    client = get_stripe_client()
    if not client:
        return {'error': 'Stripe is not configured'}

    domains = os.environ.get('REPLIT_DOMAINS', '')
    base_url = f'https://{domains.split(",")[0]}' if domains else 'http://localhost:5000'

    if not success_url:
        success_url = f'{base_url}/?payment=success&session_id={{CHECKOUT_SESSION_ID}}'
    if not cancel_url:
        cancel_url = f'{base_url}/?payment=cancelled'

    try:
        session = client.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'850 Lab - {product_label}',
                        'description': f'{product_label} for credit report dispute services',
                    },
                    'unit_amount': amount_cents,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user_email,
            metadata={
                'user_id': str(user_id),
                'product_id': product_id,
                'ai_rounds': str(ai_rounds),
                'letters': str(letters),
                'mailings': str(mailings),
            },
        )
        return {'url': session.url, 'session_id': session.id}
    except Exception as e:
        return {'error': str(e)}


def verify_checkout_session(session_id: str):
    client = get_stripe_client()
    if not client:
        return None

    try:
        session = client.checkout.Session.retrieve(session_id)
        return {
            'id': session.id,
            'payment_status': session.payment_status,
            'status': session.status,
            'customer_email': session.customer_email,
            'metadata': dict(session.metadata) if session.metadata else {},
            'amount_total': session.amount_total,
        }
    except Exception as e:
        print(f"[stripe_client] Error verifying session: {e}")
        return None


def list_recent_paid_sessions(user_email: str, limit: int = 10):
    client = get_stripe_client()
    if not client:
        return []

    try:
        sessions = client.checkout.Session.list(
            customer_details={'email': user_email},
            status='complete',
            limit=limit,
        )
        results = []
        for s in sessions.data:
            if s.payment_status == 'paid':
                results.append({
                    'id': s.id,
                    'payment_status': s.payment_status,
                    'status': s.status,
                    'customer_email': s.customer_details.email if s.customer_details else user_email,
                    'metadata': dict(s.metadata) if s.metadata else {},
                    'amount_total': s.amount_total,
                })
        return results
    except Exception as e:
        print(f"[stripe_client] Error listing sessions: {e}")
        return []
