import time as _time
_t0 = _time.time()
def _dbg(msg):
    with open('/tmp/app_debug.log', 'a') as f:
        f.write(f"{_time.time()-_t0:.3f}s {msg}\n")
_dbg("START")

import streamlit as st
_dbg("streamlit imported")

st.set_page_config(page_title="850 Lab", page_icon="💡", layout="wide")
_dbg("page_config done")

try:
    from streamlit import user_info
    user_info.has_shown_experimental_user_warning = True
except Exception:
    pass

import pandas as pd
import json
import re
import zipfile
import hashlib
import html as html_mod
import time
import os
from io import BytesIO
from datetime import datetime

import database as db
import auth
import diagnostics_store as diag_store
import traceback
import lob_client

from claims import ClaimState, extract_claims
from review_claims import ReviewType, Severity, compress_claims
from letter_generator import generate_letter_from_claims, format_letter_filename, generate_letter_pdf, generate_round1_letter
from normalization import normalize_parsed_data
from identity_block import build_dispute_identity_block
from constants import BLOCKER_MAPPING, CAPACITY_LIMIT_V1, SYSTEM_ERROR_UI_STATE
from readiness import Decision, evaluate_claim_readiness, group_into_letters, apply_capacity
from evidence_chain import build_evidence_chain, validate_evidence_chain
from truth_posture import forbidden_assertions_scan
from resend_client import send_reminder_email
from drip_emails import process_drip_emails
from referral import get_referral_link, get_referral_stats, get_reports_analyzed_count
from approval import create_approval
from layout_extract import extract_layout, to_plain_text
from translator import build_account_records, detect_tu_variant_from_text, canonical_records_to_parsed_accounts
from totals_detector import detect_section_totals_with_sources, detect_totals_mode_with_sources, self_verify_totals
from completeness import compute_completeness
from aggregator import compute_unified_summary, get_multi_bureau_accounts, get_discrepant_accounts
from classifier import classify_accounts, compute_negative_items, count_by_classification
from stripe_client import create_checkout_session, verify_checkout_session, list_recent_paid_sessions
from dispute_strategy import build_ai_strategy, build_deterministic_strategy
from ui.css import inject_css, GOLD, GOLD_DIM, BG_0, BG_1, BG_2, TEXT_0, TEXT_1, BORDER
from ui.components import lab_system_error_banner, CARD_ORDER, render_card_progress
from views.auth_page import render_auth_page
from views.admin_dashboard import render_admin_dashboard
from parsers import (
    sanitize_identity_info, run_tu_diagnostics, detect_bureau,
    extract_text_from_pdf, parse_credit_report_data,
)

_dbg("all imports done")

@st.cache_resource(show_spinner=False)
def _init_db():
    _dbg("_init_db start")
    try:
        db.init_database()
        _dbg("init_database done")
    except Exception as e:
        _dbg(f"init_database error: {e}")
    try:
        auth.init_auth_tables()
        _dbg("auth tables done")
    except Exception as e:
        _dbg(f"auth tables error: {e}")
    return True

_init_db()
_dbg("_init_db returned")

inject_css()
_dbg("inject_css done")

_do_scroll_to_top = st.session_state.get('_scroll_to_top', False)
if _do_scroll_to_top:
    del st.session_state._scroll_to_top

if 'auth_token' not in st.session_state:
    st.session_state.auth_token = None
if 'auth_user' not in st.session_state:
    st.session_state.auth_user = None
if 'auth_page' not in st.session_state:
    st.session_state.auth_page = 'landing'

def get_current_user():
    if st.session_state.auth_user:
        try:
            fresh = auth.validate_session(st.session_state.auth_token)
            if fresh:
                st.session_state.auth_user = fresh
                return fresh
            else:
                st.session_state.auth_token = None
                st.session_state.auth_user = None
                return None
        except Exception:
            return st.session_state.auth_user
    return None

current_user = get_current_user()

_test_card = st.query_params.get('test')
if _test_card and _test_card.upper() in ['UPLOAD', 'SUMMARY', 'DISPUTES', 'DONE']:
    if not current_user or not auth.is_admin(current_user):
        st.error("Preview mode is only available to admin users.")
        st.stop()
    target_card = _test_card.upper()
    if st.session_state.get('ui_card') != target_card or not st.session_state.get('_test_mode_initialized'):
        st.session_state.ui_card = target_card
        st.session_state._test_mode_initialized = True
        if target_card in ('DISPUTES', 'DONE') and not st.session_state.get('uploaded_reports'):
            from review_claims import (ReviewClaim, EvidenceSummary, ConsumerResponse,
                                       ImpactAssessment, Audit, CrossBureauStatus,
                                       ConsumerResponseStatus, CreditImpact, Severity,
                                       ClaimConfidenceSummary)
            mock_reports = {
                'test_equifax': {
                    'bureau': 'equifax', 'report_id': 'test_eq_001',
                    'parsed_data': {'personal_info': {
                        'name': 'Jane Doe', 'address': '123 Main St, Anytown, USA 12345',
                        'ssn': '***-**-1234', 'dob': '01/15/1990',
                    }},
                },
                'test_transunion': {
                    'bureau': 'transunion', 'report_id': 'test_tu_001',
                    'parsed_data': {'personal_info': {
                        'name': 'Jane Doe', 'address': '123 Main St, Anytown, USA 12345',
                        'ssn': '***-**-1234', 'dob': '01/15/1990',
                    }},
                },
            }
            mock_claims = []
            sample_items = [
                ("Capital One Platinum", "negative_impact", "Late payment reported 03/2024 — 30 days past due", "equifax"),
                ("Chase Sapphire", "accuracy_verification", "Balance reported as $4,200 but actual balance is $2,100", "equifax"),
                ("Collections Agency LLC", "account_ownership", "Collection account not recognized by consumer", "transunion"),
                ("Amex Gold", "negative_impact", "Charge-off reported but account was settled in full", "transunion"),
                ("Discover It", "accuracy_verification", "Credit limit incorrectly reported as $500 instead of $5,000", "equifax"),
            ]
            for i, (acct, rtype, summary, bureau) in enumerate(sample_items):
                rc = ReviewClaim(
                    review_claim_id=f"test_rc_{i}",
                    review_type=ReviewType(rtype),
                    summary=summary,
                    question=f"Is this {acct} information accurate?",
                    entities={'account_name': acct, 'bureau': bureau},
                    supporting_claim_ids=[f"test_claim_{i}"],
                    evidence_summary=EvidenceSummary(
                        system_observations=[f"Reported by {bureau.title()}", summary],
                        cross_bureau_status=CrossBureauStatus.UNKNOWN,
                        claim_confidence_summary=ClaimConfidenceSummary(high=1, medium=0, low=0),
                    ),
                    consumer_response=ConsumerResponse(),
                    impact_assessment=ImpactAssessment(
                        credit_impact=CreditImpact.NEGATIVE if rtype == "negative_impact" else CreditImpact.NEUTRAL,
                        severity=Severity.HIGH if rtype == "negative_impact" else Severity.MODERATE,
                    ),
                    audit=Audit(),
                )
                mock_claims.append(rc)
            st.session_state.uploaded_reports = mock_reports
            st.session_state.review_claims = mock_claims
            st.session_state.identity_confirmed = {}
    st.markdown(
        '<div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;padding:8px 12px;margin-bottom:12px;font-size:0.8rem;">'
        f'Preview mode — viewing <strong>{target_card}</strong> with sample data. '
        'Use <code>?test=upload</code>, <code>?test=disputes</code>, etc. to switch pages.'
        '</div>',
        unsafe_allow_html=True,
    )

_dbg("current_user check")
if not current_user:
    _dbg("no current_user, about to render auth page")
    render_auth_page()
    _dbg("auth page rendered, calling st.stop()")
    st.stop()

user_id = current_user.get('id') or current_user.get('user_id')
if not auth.is_email_verified(user_id):
    st.session_state.auth_page = 'verify_email'
    if not st.session_state.get('_pending_verify_email'):
        st.session_state._pending_verify_email = True
    render_auth_page()
    st.stop()

if not st.session_state.get('_activity_session_logged'):
    db.log_activity(user_id, 'session_load', current_user.get('email', ''), st.session_state.get('ui_card', 'UPLOAD'))
    st.session_state._activity_session_logged = True
    db.cleanup_old_activity(days=7)

PRODUCT_CATALOG = {}
for pid, p in auth.PACKS.items():
    PRODUCT_CATALOG[pid] = {'price_cents': p['price_cents'], 'ai_rounds': p['ai_rounds'], 'letters': p['letters'], 'mailings': p['mailings'], 'label': p['label']}
for pid, p in auth.ALA_CARTE.items():
    ent = {'ai_rounds': 0, 'letters': 0, 'mailings': 0}
    ent[p['type']] = p['qty']
    PRODUCT_CATALOG[pid] = {'price_cents': p['price_cents'], 'label': p['label'], **ent}

qp = st.query_params
if qp.get('payment') == 'success' and qp.get('session_id'):
    sid = qp.get('session_id')
    if auth.entitlement_purchase_processed(sid):
        pass
    else:
        result = verify_checkout_session(sid)
        if result and result.get('payment_status') == 'paid':
            meta = result.get('metadata', {})
            meta_uid = meta.get('user_id')
            session_email = (result.get('customer_email') or '').lower().strip()
            current_email = (current_user.get('email') or '').lower().strip()
            amount = result.get('amount_total', 0)
            product_id = meta.get('product_id', '')

            owner_match = (
                str(current_user.get('user_id')) == str(meta_uid)
                and session_email == current_email
            )

            catalog_entry = PRODUCT_CATALOG.get(product_id)
            product_valid = catalog_entry is not None and catalog_entry['price_cents'] == amount

            if owner_match and product_valid:
                auth.add_entitlements(
                    current_user['user_id'],
                    ai_rounds=catalog_entry['ai_rounds'],
                    letters=catalog_entry['letters'],
                    mailings=catalog_entry['mailings'],
                    source=f'stripe:{product_id}',
                    stripe_session_id=sid,
                    note=f'Purchased {catalog_entry["label"]} for ${amount/100:.2f}',
                )
                db.log_activity(user_id, 'purchase', f"{catalog_entry['label']} (${amount/100:.2f})", st.session_state.get('ui_card'))
                auth.record_payment(
                    current_user['user_id'],
                    amount,
                    stripe_session_id=sid,
                    status='completed',
                )
                st.success("Purchase complete! Your entitlements have been added.")
                if product_id == 'deletion_sprint':
                    db.create_sprint_guarantee(current_user['user_id'], stripe_session_id=sid)
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg, rgba(212,160,23,0.10), rgba(212,160,23,0.03));'
                        f'border:1px solid {GOLD};border-radius:10px;padding:16px 18px;margin:12px 0;">'
                        f'<div style="font-size:1rem;font-weight:700;color:{GOLD};margin-bottom:6px;">'
                        f'&#x1f6e1;&#xfe0f; You\'re covered by the 2-Round Guarantee</div>'
                        f'<div style="font-size:0.85rem;color:{TEXT_0};line-height:1.6;">'
                        f'If nothing changes after Round 1 and Round 2, Round 3 is on us. '
                        f'After each round, mark whether any items were deleted or corrected. '
                        f'If both rounds show no changes, your free Round 3 unlocks automatically.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            elif not owner_match:
                st.error("This payment does not match your account.")
            elif not product_valid:
                st.error("Invalid product or payment amount.")
    st.query_params.clear()
elif qp.get('payment') == 'cancelled':
    st.info("Payment was cancelled. You can purchase anytime.")
    st.query_params.clear()

if not st.session_state.get('_payment_reconciled'):
    st.session_state._payment_reconciled = True
    try:
        paid_sessions = list_recent_paid_sessions(current_user.get('email', ''), limit=10)
        reconciled_count = 0
        for ps in paid_sessions:
            sid = ps.get('id', '')
            if not sid or auth.entitlement_purchase_processed(sid):
                continue
            meta = ps.get('metadata', {})
            meta_uid = meta.get('user_id')
            if str(current_user.get('user_id')) != str(meta_uid):
                continue
            product_id = meta.get('product_id', '')
            amount = ps.get('amount_total', 0)
            catalog_entry = PRODUCT_CATALOG.get(product_id)
            if catalog_entry and catalog_entry['price_cents'] == amount:
                auth.add_entitlements(
                    current_user['user_id'],
                    ai_rounds=catalog_entry['ai_rounds'],
                    letters=catalog_entry['letters'],
                    mailings=catalog_entry['mailings'],
                    source=f'stripe_reconcile:{product_id}',
                    stripe_session_id=sid,
                    note=f'Reconciled {catalog_entry["label"]} for ${amount/100:.2f}',
                )
                auth.record_payment(current_user['user_id'], amount, stripe_session_id=sid, status='completed')
                if product_id == 'deletion_sprint':
                    db.create_sprint_guarantee(current_user['user_id'], stripe_session_id=sid)
                reconciled_count += 1
        if reconciled_count > 0:
            st.success(f"We found {reconciled_count} payment{'s' if reconciled_count > 1 else ''} that hadn't been applied yet. Your credits have been updated!")
            st.rerun()
    except Exception as e:
        print(f"[PAYMENT_RECONCILE] {type(e).__name__}: {e}")

if not st.session_state.get('_sessions_cleaned'):
    st.session_state._sessions_cleaned = True
    try:
        auth.cleanup_expired_sessions()
    except Exception:
        pass

if not st.session_state.get('_drip_checked'):
    st.session_state._drip_checked = True
    try:
        process_drip_emails(
            current_user['user_id'],
            current_user.get('email', ''),
            current_user.get('display_name'),
        )
    except Exception as e:
        print(f"[DRIP_EMAIL] {type(e).__name__}: {e}")

is_admin_user = auth.is_admin(current_user)
user_entitlements = auth.get_entitlements(current_user['user_id'])

st.markdown(
    '<div class="main-header">💡 850 Lab</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-header">Credit Report Intelligence</div>',
    unsafe_allow_html=True,
)

if 'uploaded_reports' not in st.session_state:
    st.session_state.uploaded_reports = {}
if 'current_report' not in st.session_state:
    st.session_state.current_report = None
if 'report_id' not in st.session_state:
    st.session_state.report_id = None
if 'extracted_claims' not in st.session_state:
    st.session_state.extracted_claims = []
if 'review_claims' not in st.session_state:
    st.session_state.review_claims = []
if 'claim_responses' not in st.session_state:
    st.session_state.claim_responses = {}
if 'review_claim_responses' not in st.session_state:
    st.session_state.review_claim_responses = {}
if 'identity_confirmed' not in st.session_state:
    st.session_state.identity_confirmed = {}
if 'generated_letters' not in st.session_state:
    st.session_state.generated_letters = {}
if 'letter_candidates' not in st.session_state:
    st.session_state.letter_candidates = []
if 'letter_removed_rcs' not in st.session_state:
    st.session_state.letter_removed_rcs = {}
if 'readiness_decisions' not in st.session_state:
    st.session_state.readiness_decisions = {}
if 'current_approval' not in st.session_state:
    st.session_state.current_approval = None
if 'dispute_rounds' not in st.session_state:
    st.session_state.dispute_rounds = []
if 'selected_dispute_strategy' not in st.session_state:
    st.session_state.selected_dispute_strategy = None
if 'ai_strategy_result' not in st.session_state:
    st.session_state.ai_strategy_result = None
if 'ai_strategy_running' not in st.session_state:
    st.session_state.ai_strategy_running = False
if 'capacity_selection' not in st.session_state:
    st.session_state.capacity_selection = None
if 'unified_summary' not in st.session_state:
    st.session_state.unified_summary = None
if 'parsed_totals' not in st.session_state:
    st.session_state.parsed_totals = None
if 'report_totals' not in st.session_state:
    st.session_state.report_totals = None
if 'upload_diagnostics' not in st.session_state:
    st.session_state.upload_diagnostics = {}
if 'review_exactness_state' not in st.session_state:
    st.session_state.review_exactness_state = None
if 'review_incomplete_ack' not in st.session_state:
    st.session_state.review_incomplete_ack = False
if 'system_error_message' not in st.session_state:
    st.session_state.system_error_message = None
if 'confirm_delete' not in st.session_state:
    st.session_state.confirm_delete = False
if 'analytics_last_card' not in st.session_state:
    st.session_state.analytics_last_card = None
if 'analytics_card_enter_ts' not in st.session_state:
    st.session_state.analytics_card_enter_ts = None
if 'ui_card' not in st.session_state:
    st.session_state.ui_card = "UPLOAD"
if 'ui_card_last' not in st.session_state:
    st.session_state.ui_card_last = None
if 'ui_transition_ts' not in st.session_state:
    st.session_state.ui_transition_ts = time.time()
if 'ui_autoadvance_enabled' not in st.session_state:
    st.session_state.ui_autoadvance_enabled = True
if 'ux_events' not in st.session_state:
    st.session_state.ux_events = []
if 'ux_test_active' not in st.session_state:
    st.session_state.ux_test_active = False
if 'ux_last_ts' not in st.session_state:
    st.session_state.ux_last_ts = None
if 'ux_report' not in st.session_state:
    st.session_state.ux_report = None
if 'ux_last_tab' not in st.session_state:
    st.session_state.ux_last_tab = None
if 'ux_review_banner_logged' not in st.session_state:
    st.session_state.ux_review_banner_logged = False
if 'admin_dashboard_active' not in st.session_state:
    st.session_state.admin_dashboard_active = False
if 'completeness_report' not in st.session_state:
    st.session_state.completeness_report = None
if 'totals_confidence' not in st.session_state:
    st.session_state.totals_confidence = None
if 'exactness' not in st.session_state:
    st.session_state.exactness = None
if 'show_payment' not in st.session_state:
    st.session_state.show_payment = False


def _sprint_guarantee_html():
    return (
        f'<div style="background:linear-gradient(135deg, rgba(212,160,23,0.08), rgba(212,160,23,0.02));'
        f'border:1px solid {GOLD};border-radius:8px;padding:10px 14px;margin:8px 0;'
        f'font-size:0.82rem;color:{TEXT_0};line-height:1.5;">'
        f'<span style="font-size:1rem;">&#x1f6e1;&#xfe0f;</span> '
        f'<strong style="color:{GOLD};">2-Round Guarantee:</strong> '
        f'If nothing changes after 2 rounds, Round 3 is on us.'
        f'</div>'
    )


def _open_checkout(url: str, product_id: str = ""):
    if product_id == 'deletion_sprint':
        st.markdown(_sprint_guarantee_html(), unsafe_allow_html=True)
    st.markdown(
        f'<a href="{url}" target="_blank" rel="noopener noreferrer"'
        f' style="display:inline-block;padding:10px 20px;background:{GOLD};color:#1a1a1a;'
        f' border-radius:8px;text-decoration:none;font-weight:700;font-size:0.92rem;'
        f' font-family:Inter,sans-serif;text-align:center;width:100%;box-sizing:border-box;">'
        f' Continue to Checkout &rarr;</a>',
        unsafe_allow_html=True,
    )

def render_purchase_options(context: str = "sidebar", needed_ai: int = 0, needed_letters: int = 0, needed_mailings: int = 0):
    uid = current_user['user_id']
    email = current_user.get('email', '')

    recommended = None
    if needed_ai > 0 or needed_letters > 0 or needed_mailings > 0:
        for pack_id, pack in auth.PACKS.items():
            if pack['ai_rounds'] >= needed_ai and pack['letters'] >= needed_letters and pack['mailings'] >= needed_mailings:
                recommended = pack_id
                break

    is_sidebar = context == "sidebar"

    if is_sidebar:
        st.markdown("##### Packs")
        for pack_id, pack in auth.PACKS.items():
            rec_tag = " ⭐ Recommended" if pack_id == recommended else ""
            label = f"{pack['label']} — ${pack['price_cents']/100:.2f}{rec_tag}"
            desc = f"{pack['ai_rounds']} AI · {pack['letters']} Letters · {pack['mailings']} Mail"
            if st.button(label, key=f"buy_{context}_{pack_id}", use_container_width=True, help=desc):
                result = create_checkout_session(
                    uid, email, pack_id, pack['label'], pack['price_cents'],
                    ai_rounds=pack['ai_rounds'], letters=pack['letters'], mailings=pack['mailings'],
                )
                if result.get('url'):
                    _open_checkout(result['url'], product_id=pack_id)
                else:
                    st.error(f"Payment error: {result.get('error', 'Unknown')}")
        st.markdown("##### À La Carte")
        for item_id, item in auth.ALA_CARTE.items():
            if st.button(f"{item['label']} ${item['price_cents']/100:.2f}", key=f"buy_{context}_{item_id}", use_container_width=True):
                kw = {'ai_rounds': 0, 'letters': 0, 'mailings': 0}
                kw[item['type']] = item['qty']
                result = create_checkout_session(
                    uid, email, item_id, item['label'], item['price_cents'], **kw,
                )
                if result.get('url'):
                    _open_checkout(result['url'])
                else:
                    st.error(f"Payment error: {result.get('error', 'Unknown')}")
        return

    rec_pack_id = recommended or 'digital_only'
    rec_pack = auth.PACKS[rec_pack_id]
    full_round = auth.PACKS.get('full_round', {})

    deprivation_msg = ""
    if context.startswith("disputes_ai"):
        deprivation_msg = (
            f'<div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:10px;line-height:1.5;">'
            f'Users who run AI analysis dispute <strong style="color:{GOLD};">the right items first</strong> — '
            f'maximizing impact and avoiding wasted effort.</div>'
        )
    elif context.startswith("disputes_letters"):
        deprivation_msg = (
            f'<div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:10px;line-height:1.5;">'
            f'Your letters are ready to generate. Without them, these {needed_letters} dispute{"s go" if needed_letters != 1 else " goes"} nowhere.</div>'
        )
    elif context.startswith("done_mail"):
        deprivation_msg = (
            f'<div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:10px;line-height:1.5;">'
            f'Without certified mail, bureaus can claim they <strong style="color:{GOLD};">never received your dispute</strong>. '
            f'Certified mail creates a legal record they can\'t ignore.</div>'
        )

    if deprivation_msg:
        st.markdown(deprivation_msg, unsafe_allow_html=True)

    includes_parts = []
    if rec_pack.get('ai_rounds', 0) > 0:
        includes_parts.append(f"{rec_pack['ai_rounds']} AI analysis")
    if rec_pack.get('letters', 0) > 0:
        includes_parts.append(f"{rec_pack['letters']} letters")
    if rec_pack.get('mailings', 0) > 0:
        includes_parts.append(f"{rec_pack['mailings']} certified mailings")
    includes_text = " + ".join(includes_parts)

    st.markdown(
        f'<div style="background:linear-gradient(135deg, rgba(212,160,23,0.10), rgba(212,160,23,0.03));'
        f'border:1px solid {GOLD};border-radius:10px;padding:14px 16px;margin-bottom:8px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
        f'<span style="font-size:0.95rem;font-weight:700;color:{TEXT_0};">{rec_pack["label"]}</span>'
        f'<span style="font-size:1.1rem;font-weight:700;color:{GOLD};">${rec_pack["price_cents"]/100:.2f}</span>'
        f'</div>'
        f'<div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:2px;">{includes_text}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if rec_pack_id == 'deletion_sprint':
        st.markdown(_sprint_guarantee_html(), unsafe_allow_html=True)
    if st.button(f"Get {rec_pack['label']}", key=f"buy_{context}_{rec_pack_id}", type="primary", use_container_width=True):
        result = create_checkout_session(
            uid, email, rec_pack_id, rec_pack['label'], rec_pack['price_cents'],
            ai_rounds=rec_pack['ai_rounds'], letters=rec_pack['letters'], mailings=rec_pack['mailings'],
        )
        if result.get('url'):
            _open_checkout(result['url'], product_id=rec_pack_id)
        else:
            st.error(f"Payment error: {result.get('error', 'Unknown')}")

    if rec_pack_id == 'digital_only' and full_round:
        per_mail_cost = auth.ALA_CARTE.get('mailing', {}).get('price_cents', 799) / 100
        ala_carte_cost = per_mail_cost * full_round.get('mailings', 3)
        st.markdown(
            f'<div style="font-size:0.78rem;color:{TEXT_1};text-align:center;margin:6px 0 4px 0;line-height:1.5;">'
            f'Want bureaus to <em>legally</em> have to respond? '
            f'<strong style="color:{GOLD};">Full Round ${full_round["price_cents"]/100:.2f}</strong> adds {full_round["mailings"]} certified mailings '
            f'(${ala_carte_cost:.2f} value separately).'
            f'</div>',
            unsafe_allow_html=True,
        )

    relevant_type = None
    if needed_ai > 0 and needed_letters == 0 and needed_mailings == 0:
        relevant_type = 'ai_rounds'
    elif needed_letters > 0 and needed_ai == 0 and needed_mailings == 0:
        relevant_type = 'letters'
    elif needed_mailings > 0 and needed_ai == 0 and needed_letters == 0:
        relevant_type = 'mailings'

    other_packs = {k: v for k, v in auth.PACKS.items() if k != rec_pack_id}
    filtered_items = {k: v for k, v in auth.ALA_CARTE.items() if relevant_type is None or v['type'] == relevant_type}

    if other_packs or filtered_items:
        with st.expander("See all options"):
            if other_packs:
                for pack_id, pack in other_packs.items():
                    label = f"{pack['label']} — ${pack['price_cents']/100:.2f}"
                    desc = f"{pack['ai_rounds']} AI · {pack['letters']} Letters · {pack['mailings']} Mail"
                    if pack_id == 'deletion_sprint':
                        st.markdown(_sprint_guarantee_html(), unsafe_allow_html=True)
                    if st.button(label, key=f"buy_{context}_{pack_id}", use_container_width=True, help=desc):
                        result = create_checkout_session(
                            uid, email, pack_id, pack['label'], pack['price_cents'],
                            ai_rounds=pack['ai_rounds'], letters=pack['letters'], mailings=pack['mailings'],
                        )
                        if result.get('url'):
                            _open_checkout(result['url'], product_id=pack_id)
                        else:
                            st.error(f"Payment error: {result.get('error', 'Unknown')}")
            if filtered_items:
                st.markdown(f'<div style="font-size:0.82rem;color:{TEXT_1};margin:8px 0 4px 0;">Individual items:</div>', unsafe_allow_html=True)
                for item_id, item in filtered_items.items():
                    if st.button(f"{item['label']} ${item['price_cents']/100:.2f}", key=f"buy_{context}_{item_id}", use_container_width=True):
                        kw = {'ai_rounds': 0, 'letters': 0, 'mailings': 0}
                        kw[item['type']] = item['qty']
                        result = create_checkout_session(
                            uid, email, item_id, item['label'], item['price_cents'], **kw,
                        )
                        if result.get('url'):
                            _open_checkout(result['url'])
                        else:
                            st.error(f"Payment error: {result.get('error', 'Unknown')}")



VALID_CARDS = set(CARD_ORDER) | {"PREPARING", "GENERATING", "LETTERS_READY"}

def advance_card(target_card):
    if target_card in VALID_CARDS:
        if st.session_state.analytics_card_enter_ts and st.session_state.analytics_last_card:
            duration = int((time.time() - st.session_state.analytics_card_enter_ts) * 1000)
            track_analytics('card_transition', st.session_state.analytics_last_card,
                          f'to:{target_card},duration_ms:{duration}')
        st.session_state.ui_card = target_card
        st.session_state._scroll_to_top = True
        _uid = (st.session_state.get('auth_user') or {}).get('user_id')
        if _uid:
            db.log_activity(_uid, 'view_card', target_card, target_card)

def track_analytics(event_type, page, detail=None):
    try:
        user = st.session_state.get('auth_user')
        if user:
            user_id = user.get('user_id') or user.get('id')
            session_id = st.session_state.get('auth_token', '')
            db.log_analytics_event(user_id, session_id, event_type, page, detail)
    except Exception:
        pass

def log_ux(screen, event, target, cc):
    if not st.session_state.ux_test_active:
        return
    now = time.time()
    st.session_state.ux_events.append({
        "ts": now,
        "screen": screen,
        "event": event,
        "target": target,
        "cc": cc,
    })
    st.session_state.ux_last_ts = now


def compute_uxfs_report(events):
    COUNTED_EVENTS = {"TAP", "UPLOAD", "CHECK", "APPROVE", "GENERATE"}
    screens = ["UPLOAD", "REVIEW", "BUILD", "GENERATE"]

    screen_events = {s: [] for s in screens}
    for ev in events:
        s = ev["screen"]
        if s not in screen_events:
            screen_events[s] = []
        screen_events[s].append(ev)

    screen_dt_seconds = {s: 0.0 for s in screen_events}
    for i in range(len(events) - 1):
        delta = events[i + 1]["ts"] - events[i]["ts"]
        s = events[i]["screen"]
        screen_dt_seconds[s] += delta

    def dt_bucket(seconds):
        if seconds < 1:
            return 1
        elif seconds <= 3:
            return 2
        elif seconds <= 7:
            return 3
        else:
            return 4

    report_rows = []
    total_uxfs = 0.0

    for s in screen_events:
        counted = [e for e in screen_events[s] if e["event"] in COUNTED_EVENTS]
        fc = len(counted)
        dt_sec = screen_dt_seconds.get(s, 0.0)
        dt_b = dt_bucket(dt_sec)
        if counted:
            cc_avg = round(sum(e["cc"] for e in counted) / len(counted), 2)
        else:
            cc_avg = 4
            fc = 0
        uxfs = (fc * dt_b) / max(cc_avg, 1)
        total_uxfs += uxfs
        report_rows.append({
            "screen": s,
            "FC": fc,
            "DT_seconds": round(dt_sec, 3),
            "DT_bucket": dt_b,
            "CC_avg": cc_avg,
            "UXFS": round(uxfs, 4),
        })

    return {
        "rows": report_rows,
        "total_uxfs": round(total_uxfs, 4),
        "raw_event_count": len(events),
    }


def count_hard_inquiries(parsed_data):
    return sum(1 for inq in parsed_data.get('inquiries', [])
               if 'hard' in inq.get('type', '').lower() or inq.get('type', '') == 'Inquiry')


def compute_report_totals(raw_text, bureau):
    result = {
        "accounts_total": None,
        "inquiries_total": None,
        "negatives_total": None,
        "public_records_total": None,
        "confidence": "LOW",
        "receipts": {"accounts": [], "inquiries": [], "negatives": [], "public_records": []},
    }

    text_lower = raw_text.lower()

    acct_total = None
    acct_receipts = []
    tu_acct_match = re.search(
        r'(?:total\s+(?:number\s+of\s+)?accounts|number\s+of\s+accounts|accounts?\s*:\s*)[\s:]*(\d+)',
        text_lower,
    )
    if tu_acct_match:
        acct_total = int(tu_acct_match.group(1))
        acct_receipts.append(tu_acct_match.group(0).strip()[:120])

    inq_total = None
    inq_receipts = []
    inq_match = re.search(
        r'(?:total\s+(?:number\s+of\s+)?inquiries|number\s+of\s+inquiries|inquiries?\s*:\s*)[\s:]*(\d+)',
        text_lower,
    )
    if inq_match:
        inq_total = int(inq_match.group(1))
        inq_receipts.append(inq_match.group(0).strip()[:120])

    neg_total = None
    neg_receipts = []
    neg_match = re.search(
        r'(?:total\s+(?:number\s+of\s+)?negative\s+items?|negative\s+items?\s*:\s*|adverse\s+items?\s*:\s*)[\s:]*(\d+)',
        text_lower,
    )
    if neg_match:
        neg_total = int(neg_match.group(1))
        neg_receipts.append(neg_match.group(0).strip()[:120])

    pr_total = None
    pr_receipts = []
    pr_match = re.search(
        r'(?:total\s+(?:number\s+of\s+)?public\s+records?|public\s+records?\s*:\s*)[\s:]*(\d+)',
        text_lower,
    )
    if pr_match:
        pr_total = int(pr_match.group(1))
        pr_receipts.append(pr_match.group(0).strip()[:120])

    result["accounts_total"] = acct_total
    result["inquiries_total"] = inq_total
    result["negatives_total"] = neg_total
    result["public_records_total"] = pr_total
    result["receipts"]["accounts"] = acct_receipts
    result["receipts"]["inquiries"] = inq_receipts
    result["receipts"]["negatives"] = neg_receipts
    result["receipts"]["public_records"] = pr_receipts

    all_sections = [acct_total, inq_total, neg_total, pr_total]
    non_none = [v for v in all_sections if v is not None]
    if len(non_none) == 4:
        result["confidence"] = "HIGH"
    elif len(non_none) >= 2:
        result["confidence"] = "MEDIUM"
    else:
        result["confidence"] = "LOW"

    return result


def compute_exactness(report_totals, parsed_data):
    parsed_totals = {
        "accounts_total": len(parsed_data.get("accounts", [])),
        "inquiries_total": len(parsed_data.get("inquiries", [])),
        "negatives_total": len(parsed_data.get("negative_items", [])),
        "public_records_total": len(parsed_data.get("public_records", [])),
    }

    if report_totals.get("confidence") != "HIGH":
        return parsed_totals, "NOT_EXACT"

    section_keys = ["accounts_total", "inquiries_total", "negatives_total", "public_records_total"]
    for key in section_keys:
        report_val = report_totals.get(key)
        if report_val is None:
            return parsed_totals, "NOT_EXACT"
        if parsed_totals[key] != report_val:
            return parsed_totals, "NOT_EXACT"

    return parsed_totals, "EXACT"


def _review_claim_to_canonical(rc, user_response, bureau_key, identity_confirmed_for_bureau):
    entities = getattr(rc, 'entities', {}) or {}
    evidence = getattr(rc, 'evidence_summary', None)
    review_type = getattr(rc, 'review_type', None)
    confidence_summary = evidence.claim_confidence_summary if evidence else None

    review_type_to_claim_type = {
        "identity_verification": "identity",
        "account_ownership": "account",
        "duplicate_account": "account",
        "negative_impact": "negative_item",
        "accuracy_verification": "account",
        "unverifiable_information": "account",
    }
    claim_type = review_type_to_claim_type.get(
        review_type.value if review_type else "", "account"
    )

    bureau_map = {
        "equifax": "EQ", "experian": "EX", "transunion": "TU",
        "eq": "EQ", "ex": "EX", "tu": "TU",
    }
    bureau_code = bureau_map.get(bureau_key.lower(), bureau_key.upper()[:2])

    if confidence_summary:
        if confidence_summary.high > 0:
            confidence_level = "high"
        elif confidence_summary.medium > 0:
            confidence_level = "medium"
        else:
            confidence_level = "low"
    else:
        confidence_level = "low"

    user_confirmation_complete = user_response in ("inaccurate", "unsure")
    user_assertions = []
    if user_response == "inaccurate":
        if claim_type == "identity":
            user_assertions.append("INCORRECT_IDENTITY")
        elif review_type and review_type.value == "accuracy_verification":
            user_assertions.append("INCORRECT_BALANCE")
        else:
            user_assertions.append("NOT_MINE")

    fields = {}
    creditor = (
        entities.get('creditor') or entities.get('_extracted_creditor')
        or entities.get('account_name') or entities.get('furnisher')
        or entities.get('inquirer') or ""
    )
    if creditor:
        fields["creditor"] = creditor
        fields["normalized_creditor_name"] = creditor.upper().strip()
    account_ref = (
        entities.get('account_mask') or entities.get('last4')
        or entities.get('account') or entities.get('account_reference') or ""
    )
    if account_ref:
        fields["account_reference"] = account_ref
    for key in ('balance', 'status', 'opened_date', 'inquiry_date'):
        val = entities.get(key)
        if val:
            fields[key] = val

    receipt_snippets = []
    if evidence and evidence.system_observations:
        receipt_snippets = evidence.system_observations[:3]

    cross_bureau = getattr(evidence, 'cross_bureau_status', None)
    inconsistencies_present = (
        cross_bureau is not None
        and hasattr(cross_bureau, 'value')
        and cross_bureau.value == "multi_bureau"
    )

    actionable_basis = user_confirmation_complete or confidence_level == "high"

    canonical = {
        "claim_id": rc.review_claim_id,
        "claim_type": claim_type,
        "bureau": bureau_code,
        "fields": fields,
        "inconsistencies_present": inconsistencies_present,
        "actionable_basis_present": actionable_basis,
        "requires_user_confirmation": not user_confirmation_complete and confidence_level != "high",
        "confidence_level": confidence_level,
        "ownership_confirmed": True if identity_confirmed_for_bureau else "unknown",
        "user_confirmation_complete": user_confirmation_complete,
        "user_assertion_flags": user_assertions,
        "last_action_type": "NONE",
        "last_action_target": "BUREAU",
        "last_action_sent_at": None,
        "deadline_at": None,
        "response_received": False,
        "response_received_at": None,
        "response_resolved_issue": False,
        "verification_allowed": True,
        "action_possible": True,
        "action_now_is_suboptimal": False,
        "escalation_allowed": False,
        "receipt_snippet": "; ".join(receipt_snippets) if receipt_snippets else "",
    }
    return canonical


def smart_account_dedupe_key(account):
    """Build dedupe key for accounts using creditor name + account number + date opened + high credit"""
    name = (account.get('account_name', '') or '').upper().strip()
    name = re.sub(r'[^A-Z0-9]', '', name)[:20] if name else ''

    acct_num = (account.get('account_number', '') or '').strip()
    date_opened = (account.get('date_opened', '') or account.get('opened_date', '') or '').strip()
    high_credit = (account.get('high_credit', '') or account.get('credit_limit', '') or '').replace(',', '').replace('$', '').strip()
    balance = (account.get('balance', '') or '').replace(',', '').replace('$', '').strip()

    parts = [name]
    if acct_num:
        parts.append(acct_num)
    if date_opened:
        parts.append(date_opened)
    if high_credit:
        parts.append(high_credit)

    if len(parts) >= 3:
        return '|'.join(parts)

    if name and balance:
        return f"{name}|{balance}"

    if name:
        return f"{name}|NODATE"

    raw = (account.get('raw_section', '') or '')[:100]
    return f"UNK|{hash(raw)}"

def smart_inquiry_dedupe_key(inquiry):
    """Build robust dedupe key for inquiries - extract creditor name + date"""
    raw_text = (inquiry.get('raw_text', '') or '').upper()
    date = inquiry.get('date', '') or ''
    
    # Common creditor patterns for inquiries
    creditor_patterns = [
        r'(CAPITAL\s*ONE)',
        r'(CHASE)',
        r'(BANK\s*OF\s*AMERICA)',
        r'(DISCOVER)',
        r'(AMERICAN\s*EXPRESS)',
        r'(CITIBANK)',
        r'(WELLS\s*FARGO)',
        r'(SYNCHRONY)',
        r'([A-Z]{4,}\s*(?:BANK|FINANCIAL|AUTO|CREDIT))',
    ]
    
    for pattern in creditor_patterns:
        match = re.search(pattern, raw_text)
        if match:
            creditor = re.sub(r'[^A-Z0-9]', '', match.group(1))[:12]
            return f"{creditor}|{date}" if date else creditor
    
    # Fallback: first significant word
    words = re.findall(r'[A-Z]{4,}', raw_text)
    skip = {'INQUIRY', 'CREDIT', 'CHECK', 'DATE', 'TYPE', 'HARD', 'SOFT'}
    for word in words:
        if word not in skip:
            return f"{word[:12]}|{date}" if date else word[:12]
    
    return f"INQ|{date}" if date else f"INQ|{hash(raw_text[:20])}"

def smart_negative_dedupe_key(item):
    """Build robust dedupe key for negative items - aggressive by type + creditor"""
    item_type = (item.get('type', '') or '').upper().strip()[:10]
    context = (item.get('context', '') or '')
    
    creditor_match = re.search(r'([A-Z][A-Za-z\s&]+)', context.upper())
    creditor = re.sub(r'[^A-Z0-9]', '', creditor_match.group(1))[:12] if creditor_match else ''
    
    if item_type and creditor:
        return f"{item_type}|{creditor}"
    if item_type:
        return item_type
    
    return f"NEG|{hash(context[:30])}"

def is_hard_inquiry(inquiry):
    """Classify if inquiry is HARD (credit-impacting) vs SOFT
    
    Credit report inquiries are HARD unless explicitly marked as soft/promotional.
    Most inquiries from banks/lenders applying for credit are hard inquiries.
    """
    raw_text = (inquiry.get('raw_text', '') or '').lower()
    inq_type = (inquiry.get('type', '') or '').lower()
    
    # Explicit soft inquiry indicators - only these are NOT hard
    soft_indicators = [
        'soft', 'promotional', 'preapproved', 'pre-approved', 'promo',
        'account review', 'consumer disclosure', 'account monitoring',
        'insurance', 'employment', 'marketing', 'periodic review',
        'existing account', 'ar ', 'prom', 'am '
    ]
    
    # Check for soft indicators first
    if any(s in raw_text for s in soft_indicators):
        return False
    if any(s in inq_type for s in soft_indicators):
        return False
    
    # Look for hard inquiry section headers in Experian format
    # Experian separates "Regular Inquiries" (hard) from "Promotional Inquiries" (soft)
    if 'regular inquir' in raw_text or 'credit inquir' in raw_text:
        return True
    
    # Default: treat as hard inquiry (most inquiries on credit reports are hard)
    return True

def dedupe_list(items, key_func):
    """Simple deduplication using key function"""
    seen = set()
    result = []
    for item in items:
        key = key_func(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result

def compute_deduped_counts(parsed_data):
    """Compute deduped counts for truth layer display.
    
    Uses local smart dedupe functions for robust deduplication.
    """
    accounts = parsed_data.get('accounts', [])
    inquiries = parsed_data.get('inquiries', [])
    negatives = parsed_data.get('negative_items', [])
    
    deduped_accounts = dedupe_list(accounts, smart_account_dedupe_key)
    deduped_inquiries = dedupe_list(inquiries, smart_inquiry_dedupe_key)
    deduped_negatives = dedupe_list(negatives, smart_negative_dedupe_key)
    
    hard_inquiries = [i for i in deduped_inquiries if is_hard_inquiry(i)]
    soft_inquiries = [i for i in deduped_inquiries if not is_hard_inquiry(i)]
    
    return {
        'accounts': len(deduped_accounts),
        'hard_inquiries': len(hard_inquiries),
        'soft_inquiries': len(soft_inquiries),
        'negative_items': len(deduped_negatives),
        'raw_accounts': len(accounts),
        'raw_inquiries': len(inquiries),
        'raw_negatives': len(negatives),
    }

with st.sidebar:
    user_display_name = current_user.get('display_name', current_user.get('email', 'User'))
    role_display = " (Admin)" if is_admin_user else ""
    ent = user_entitlements
    st.markdown(
        f'<div class="sidebar-user-card">'
        f'<div class="sidebar-user-name">{user_display_name}{role_display}</div>'
        f'<div class="sidebar-entitlements">'
        f'<span class="ent-badge" title="AI Strategy Rounds">{ent["ai_rounds"]} AI</span>'
        f'<span class="ent-badge" title="Enhanced Letters">{ent["letters"]} Letters</span>'
        f'<span class="ent-badge" title="Certified Mailings">{ent["mailings"]} Mail</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Buy More", expanded=False):
        render_purchase_options(context="sidebar")

    with st.expander("Refer & Earn", expanded=False):
        try:
            ref_link = get_referral_link(current_user['user_id'])
            ref_stats = get_referral_stats(current_user['user_id'])
            st.markdown(
                '<p style="color:#B0B0B0; font-size:0.85rem; margin-bottom:8px;">'
                'Share your link. When someone signs up, <strong style="color:#D4AF37;">you get 1 free AI round</strong>.</p>',
                unsafe_allow_html=True,
            )
            st.code(ref_link, language=None)
            col_r1, col_r2 = st.columns(2)
            col_r1.metric("Referrals", ref_stats['total_referrals'])
            col_r2.metric("Rewards", ref_stats['rewards_earned'])
        except Exception:
            st.caption("Referral program loading...")

    if st.button("Sign Out", key="logout_btn", use_container_width=True):
        auth.delete_session(st.session_state.auth_token)
        st.session_state.auth_token = None
        st.session_state.auth_user = None
        st.rerun()

    st.markdown('<div class="sidebar-section-title">Account</div>', unsafe_allow_html=True)

    with st.expander("Account Settings"):
        new_name = st.text_input("Display Name", value=current_user.get('display_name', ''), key="settings_name")
        if st.button("Update Name", key="update_name_btn"):
            if new_name.strip():
                auth.update_display_name(current_user['user_id'], new_name)
                st.success("Name updated!")
                st.rerun()

        st.markdown("**Change Password**")
        cur_pw = st.text_input("Current Password", type="password", key="cur_pw")
        new_pw = st.text_input("New Password", type="password", key="new_pw_settings")
        if st.button("Change Password", key="change_pw_btn"):
            if cur_pw and new_pw:
                if len(new_pw) < 8:
                    st.error("New password must be at least 8 characters.")
                elif not any(c.isupper() for c in new_pw):
                    st.error("Password must include at least one uppercase letter.")
                elif not any(c.islower() for c in new_pw):
                    st.error("Password must include at least one lowercase letter.")
                elif not any(c.isdigit() for c in new_pw):
                    st.error("Password must include at least one number.")
                else:
                    current_token = st.session_state.get('auth_token')
                    result = auth.update_password(current_user['user_id'], cur_pw, new_pw, except_token=current_token)
                    if 'error' in result:
                        st.error(result['error'])
                    else:
                        st.success("Password changed! Other sessions have been signed out.")

        st.markdown("**Payment History**")
        payments = auth.get_user_payments(current_user['user_id'])
        if payments:
            for p in payments:
                amount_str = f"${p['amount']/100:.2f}" if p['amount'] else "$0.00"
                date_str = p['created_at'].strftime('%m/%d/%Y') if hasattr(p['created_at'], 'strftime') else str(p['created_at'])
                status_icon = "✅" if p['status'] == 'completed' else "⏳"
                st.caption(f"{status_icon} {amount_str} — {date_str}")
        else:
            st.caption("No payments yet.")

        st.markdown("**Entitlement History**")
        ent_txns = auth.get_entitlement_transactions(current_user['user_id'], limit=10)
        if ent_txns:
            for tx in ent_txns:
                tx_type = "+" if tx['transaction_type'] == 'credit' else "-"
                parts = []
                if tx['ai_rounds']:
                    parts.append(f"{tx['ai_rounds']} AI")
                if tx['letters']:
                    parts.append(f"{tx['letters']} Letters")
                if tx['mailings']:
                    parts.append(f"{tx['mailings']} Mail")
                detail = ", ".join(parts) if parts else "—"
                dt_str = tx['created_at'].strftime('%m/%d/%Y') if hasattr(tx['created_at'], 'strftime') else str(tx['created_at'])
                st.caption(f"{tx_type} {detail} — {tx['source']} — {dt_str}")
        else:
            st.caption("No purchases yet.")

        st.markdown("**Sent Mail**")
        lob_history = db.get_lob_sends_for_user(current_user['user_id'])
        if lob_history:
            for ls in lob_history[:10]:
                b_name = ls['bureau'].title() if ls['bureau'] else 'Unknown'
                cost_str = f"${ls['cost_cents']/100:.2f}" if ls['cost_cents'] else "$0.00"
                dt_str = ls['created_at'].strftime('%m/%d/%Y') if hasattr(ls['created_at'], 'strftime') else str(ls['created_at'])
                test_tag = " (TEST)" if ls.get('is_test') else ""
                track = ls.get('tracking_number', '')
                track_str = f" | #{track}" if track else ""
                st.caption(f"📬 {b_name} — {cost_str} — {dt_str}{test_tag}{track_str}")
        else:
            st.caption("No letters sent yet.")

    with st.expander("Privacy & Data"):
        st.markdown(
            "Your credit report data is stored securely and used only to generate dispute letters. "
            "You can delete all your uploaded data at any time."
        )
        if st.button("Delete All My Data", key="delete_data_btn", type="secondary"):
            st.session_state.confirm_delete = True
        if st.session_state.get('confirm_delete'):
            st.warning("This will permanently delete all your uploaded reports, findings, and letters. This cannot be undone.")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Yes, Delete Everything", key="confirm_delete_yes"):
                    db.delete_user_reports(current_user['user_id'])
                    st.session_state.confirm_delete = False
                    st.session_state.uploaded_reports = {}
                    st.session_state.extracted_claims = {}
                    st.session_state.review_claims = []
                    st.session_state.generated_letters = {}
                    st.session_state.ai_strategy_result = None
                    st.session_state.ui_card = "UPLOAD"
                    st.success("All your data has been deleted.")
                    st.rerun()
            with col_no:
                if st.button("Cancel", key="confirm_delete_no"):
                    st.session_state.confirm_delete = False
                    st.rerun()

    st.markdown('<div class="sidebar-section-title">Settings</div>', unsafe_allow_html=True)

    if is_admin_user:
        use_ocr = st.checkbox("Enable OCR", value=False, help="Use OCR for scanned PDFs")
        DEBUG_MODE = st.checkbox("Debug mode", value=False, help="Show raw/normalized counts and technical details")
    else:
        use_ocr = False
        DEBUG_MODE = False

    st.markdown('<div class="sidebar-section-title">Reports</div>', unsafe_allow_html=True)
    _sidebar_needs_rerun = False
    try:
        previous_reports = db.get_all_reports(user_id=current_user['user_id'])
        if previous_reports:
            report_options = {}
            for r in previous_reports[:10]:
                try:
                    date_str = r['upload_date'].strftime('%m/%d') if hasattr(r['upload_date'], 'strftime') else str(r['upload_date'])[:5]
                except Exception:
                    date_str = "?"
                label = f"{r['file_name']} ({r['bureau'].title()}) - {date_str}"
                report_options[label] = r['id']
            selected_reports = st.multiselect("Load previous reports:", list(report_options.keys()))
            if selected_reports:
                if st.button("Load Report" if len(selected_reports) == 1 else f"Load {len(selected_reports)} Reports"):
                    st.session_state.uploaded_reports = {}
                    st.session_state.extracted_claims = {}
                    all_claims = []
                    diagnostic_logs = []

                    for sel in selected_reports:
                        report_id = report_options[sel]
                        report_data = db.get_report(report_id, user_id=current_user['user_id'])
                        if report_data:
                            parsed = report_data.get('parsed_data') or {}
                            parsed = normalize_parsed_data(parsed)
                            bureau = report_data.get('bureau', 'unknown')
                            snapshot_key = f"RPT_{report_id}"

                            rpt_entry = {
                                'upload_id': snapshot_key,
                                'file_name': report_data.get('file_name', 'Unknown'),
                                'bureau': bureau,
                                'parsed_data': parsed,
                                'full_text': report_data.get('full_text', ''),
                                'num_pages': 0,
                                'report_id': report_id,
                            }
                            st.session_state.uploaded_reports[snapshot_key] = rpt_entry
                            claims = extract_claims(parsed, bureau)
                            st.session_state.extracted_claims[snapshot_key] = claims
                            all_claims.extend(claims)
                            diagnostic_logs.append({
                                'upload_id': snapshot_key,
                                'filename': report_data.get('file_name', 'Unknown'),
                                'detected_bureau': bureau,
                                'source': 'loaded_from_db',
                            })

                    last_key = list(st.session_state.uploaded_reports.keys())[-1] if st.session_state.uploaded_reports else None
                    if last_key:
                        st.session_state.current_report = st.session_state.uploaded_reports[last_key]
                        st.session_state.report_id = st.session_state.current_report.get('report_id')

                    st.session_state.review_claims = compress_claims(all_claims)
                    st.session_state.claim_responses = {}
                    st.session_state.review_claim_responses = {}
                    st.session_state.identity_confirmed = {}
                    st.session_state.generated_letters = {}
                    st.session_state.readiness_decisions = []
                    st.session_state.letter_candidates = []
                    st.session_state.current_approval = None
                    st.session_state.capacity_selection = {}
                    st.session_state.system_error_message = None
                    st.session_state.upload_diagnostics = diagnostic_logs
                    st.session_state.review_incomplete_ack = False
                    st.session_state.report_totals = None
                    st.session_state.parsed_totals = None
                    st.session_state.review_exactness_state = None
                    st.session_state.completeness_report = None
                    st.session_state.totals_confidence = None
                    st.session_state.exactness = None

                    if len(st.session_state.uploaded_reports) == 1 and last_key:
                        rpt = st.session_state.uploaded_reports[last_key]
                        load_text = rpt.get('full_text', '')
                        parsed = rpt.get('parsed_data', {})
                        bureau = rpt.get('bureau', '')
                        if load_text and parsed:
                            rt = compute_report_totals(load_text, bureau)
                            pt, exactness = compute_exactness(rt, parsed)
                            st.session_state.report_totals = rt
                            st.session_state.parsed_totals = pt
                            c_totals, c_sources = detect_section_totals_with_sources(load_text, bureau)
                            c_mode = detect_totals_mode_with_sources(c_totals, c_sources, bureau, load_text)
                            load_pi = parsed.get('personal_info', {})
                            load_pif = sum(1 for k in ['name', 'address', 'dob', 'ssn_last4'] if load_pi.get(k))
                            c_ext = {
                                "accounts": len(parsed.get("accounts", [])),
                                "inquiries": count_hard_inquiries(parsed),
                                "negative_items": len(parsed.get("negative_items", [])),
                                "public_records": len(parsed.get("public_records", [])),
                                "personal_info_fields": load_pif,
                            }
                            sv = self_verify_totals(load_text, bureau, c_ext)
                            c_rpt = compute_completeness(bureau, c_totals, c_ext, totals_mode=c_mode, self_verification=sv)
                            st.session_state.completeness_report = c_rpt
                            st.session_state.totals_confidence = c_rpt.totals_confidence
                            st.session_state.exactness = c_rpt.exactness
                            st.session_state.review_exactness_state = c_rpt.exactness

                    unified = compute_unified_summary(st.session_state.uploaded_reports)
                    st.session_state.unified_summary = unified
                    advance_card("SUMMARY")
                    _sidebar_needs_rerun = True
        else:
            st.caption("No previous reports")
    except Exception as sidebar_err:
        print(f"[SIDEBAR_ERROR] {sidebar_err}")
        print(traceback.format_exc())
        st.error(f"Error loading reports: {sidebar_err}")
    if _sidebar_needs_rerun:
        st.rerun()

    if st.session_state.uploaded_reports:
        st.markdown("")
        if st.button("Start Over", key="sidebar_reset_btn", use_container_width=True):
            st.session_state.uploaded_reports = {}
            st.session_state.extracted_claims = {}
            st.session_state.review_claims = []
            st.session_state.claim_responses = {}
            st.session_state.review_claim_responses = {}
            st.session_state.identity_confirmed = {}
            st.session_state.generated_letters = {}
            st.session_state.readiness_decisions = []
            st.session_state.letter_candidates = []
            st.session_state.current_approval = None
            st.session_state.capacity_selection = {}
            st.session_state.system_error_message = None
            st.session_state.ai_strategy_result = None
            st.session_state.upload_diagnostics = []
            st.session_state.review_incomplete_ack = False
            st.session_state.report_totals = None
            st.session_state.parsed_totals = None
            st.session_state.review_exactness_state = None
            st.session_state.completeness_report = None
            st.session_state.totals_confidence = None
            st.session_state.exactness = None
            st.session_state.unified_summary = None
            st.session_state.current_report = None
            st.session_state.report_id = None
            st.session_state.ui_card = "UPLOAD"
            st.rerun()

    st.markdown("")
    st.caption("Letters are **factual disputes** under the FCRA. They do not constitute legal advice.")

    DEV_MODE = os.environ.get("DEV_MODE", "0") == "1"

    if is_admin_user:
        st.markdown('<div class="sidebar-section-title">Admin Tools</div>', unsafe_allow_html=True)
        if st.session_state.admin_dashboard_active:
            if st.button("Back to App", key="admin_back_btn", type="secondary", use_container_width=True):
                st.session_state.admin_dashboard_active = False
                st.rerun()
        else:
            if st.button("Admin Dashboard", key="admin_dash_btn", type="primary", use_container_width=True):
                st.session_state.admin_dashboard_active = True
                st.rerun()
        if st.button("Start UX Test", key="ux_start_btn"):
            st.session_state.ux_test_active = True
            st.session_state.ux_events = []
            st.session_state.ux_report = None
            st.session_state.ux_last_ts = time.time()
            st.session_state.ux_last_tab = None
            st.session_state.ux_review_banner_logged = False
            st.rerun()
        if st.button("Stop + Compute UXFS", key="ux_stop_btn"):
            if st.session_state.ux_events:
                stop_event = {
                    "ts": time.time(),
                    "screen": st.session_state.ux_events[-1]["screen"],
                    "event": "NAV",
                    "target": "ux_stop",
                    "cc": 1,
                }
                st.session_state.ux_events.append(stop_event)
                st.session_state.ux_report = compute_uxfs_report(st.session_state.ux_events)
            st.session_state.ux_test_active = False
        if st.session_state.ux_test_active:
            st.success(f"Recording... ({len(st.session_state.ux_events)} events)")
        if st.session_state.ux_report:
            report = st.session_state.ux_report
            st.markdown(f"**Total UXFS: {report['total_uxfs']}**")
            st.markdown(f"Raw events: {report['raw_event_count']}")
            st.dataframe(pd.DataFrame(report["rows"]), use_container_width=True)
            report_json = json.dumps(report, indent=2)
            st.download_button(
                "Download UX Report JSON",
                data=report_json,
                file_name="ux_report.json",
                mime="application/json",
                key="ux_download_json",
            )

        with st.expander("Analytics Dashboard"):
            analytics_days = st.selectbox("Time range:", [7, 14, 30, 90], index=2, key="analytics_days")
            try:
                analytics = db.get_analytics_summary(days=analytics_days)

                funnel = analytics.get('funnel', {})
                f_upload = funnel.get('upload', 0) or 0
                f_summary = funnel.get('summary', 0) or 0
                f_disputes = funnel.get('disputes', 0) or 0
                f_done = funnel.get('done', 0) or 0

                signup_s = analytics.get('signup_stats', {})
                upload_s = analytics.get('upload_stats', {})
                purchase_s = analytics.get('purchase_stats', {})
                referral_s = analytics.get('referral_stats', {})

                st.markdown("**Key Metrics**")
                km1, km2, km3, km4 = st.columns(4)
                km1.metric("Signups", signup_s.get('recent_signups', 0))
                km2.metric("Uploaders", upload_s.get('uploaders', 0))
                km3.metric("Purchases", purchase_s.get('total_purchases', 0))
                rev_cents = purchase_s.get('total_revenue', 0) or 0
                km4.metric("Revenue", f"${rev_cents/100:.2f}")

                signup_total = signup_s.get('recent_signups', 0) or 0
                uploaders = upload_s.get('uploaders', 0) or 0
                purchases = purchase_s.get('total_purchases', 0) or 0
                if signup_total > 0:
                    st.markdown("**Conversion Rates**")
                    cr1, cr2, cr3 = st.columns(3)
                    cr1.metric("Signup → Upload", f"{uploaders/signup_total*100:.0f}%")
                    cr2.metric("Upload → Purchase", f"{purchases/uploaders*100:.0f}%" if uploaders else "0%")
                    cr3.metric("Signup → Purchase", f"{purchases/signup_total*100:.0f}%")

                if referral_s.get('total_referrals', 0) > 0:
                    st.markdown("**Referral Program**")
                    rr1, rr2 = st.columns(2)
                    rr1.metric("Referral Signups", referral_s.get('total_referrals', 0))
                    rr2.metric("Rewards Given", referral_s.get('rewarded', 0))

                st.markdown("**Conversion Funnel**")
                funnel_data = {
                    "Step": ["Upload", "Summary", "Disputes", "Done"],
                    "Views": [f_upload, f_summary, f_disputes, f_done],
                }
                if f_upload > 0:
                    funnel_data["Drop-off"] = [
                        "—",
                        f"{100 - (f_summary / f_upload * 100):.0f}%" if f_upload else "—",
                        f"{100 - (f_disputes / f_upload * 100):.0f}%" if f_upload else "—",
                        f"{100 - (f_done / f_upload * 100):.0f}%" if f_upload else "—",
                    ]
                st.table(pd.DataFrame(funnel_data))

                page_views = analytics.get('page_views', [])
                if page_views:
                    st.markdown("**Page Views & Time**")
                    pv_rows = []
                    for pv in page_views:
                        avg_ms = pv.get('avg_duration_ms', 0) or 0
                        avg_sec = avg_ms / 1000 if avg_ms else 0
                        pv_rows.append({
                            "Page": pv['page'],
                            "Views": pv['views'],
                            "Users": pv['unique_users'],
                            "Avg Time": f"{avg_sec:.1f}s",
                        })
                    st.table(pd.DataFrame(pv_rows))

                daily = analytics.get('daily_activity', [])
                if daily:
                    st.markdown("**Daily Activity**")
                    daily_rows = []
                    for d in daily[:7]:
                        daily_rows.append({
                            "Date": str(d['day']),
                            "Active Users": d['active_users'],
                            "Events": d['total_events'],
                        })
                    st.table(pd.DataFrame(daily_rows))

                top_users = analytics.get('top_users', [])
                if top_users:
                    st.markdown("**Top Users**")
                    tu_rows = []
                    for tu in top_users[:10]:
                        tu_rows.append({
                            "User": tu.get('display_name') or tu.get('email', ''),
                            "Tier": tu.get('tier', '').title(),
                            "Events": tu['event_count'],
                        })
                    st.table(pd.DataFrame(tu_rows))

                if not page_views and not daily:
                    st.caption("No analytics data yet. Events will appear as users interact with the app.")

            except Exception as e:
                st.caption(f"Analytics unavailable: {e}")

        if DEV_MODE or DEBUG_MODE:
            st.markdown("### Developer")
            dev_show_all = st.checkbox("Show all cards", value=False, key="dev_show_all_cards")
            if dev_show_all:
                dev_card = st.selectbox("Jump to card:", CARD_ORDER, index=CARD_ORDER.index(st.session_state.ui_card), key="dev_card_select")
                if dev_card != st.session_state.ui_card:
                    advance_card(dev_card)
                    st.rerun()

        if DEBUG_MODE:
            with st.expander("Debug: Count Audit", expanded=True):
                if st.session_state.uploaded_reports:
                    from audit_counts import dedupe_items, build_account_dedupe_key, build_inquiry_dedupe_key, classify_inquiry_type

                    for snapshot_key, report_data in st.session_state.uploaded_reports.items():
                        bureau = report_data.get('bureau', 'unknown')
                        parsed = report_data.get('parsed_data', {})
                        st.markdown(f"**{bureau.title()}** (`{snapshot_key}`)")

                        raw_accts = len(parsed.get('accounts', []))
                        raw_inqs = len(parsed.get('inquiries', []))

                        deduped_accts, acct_dups = dedupe_items(parsed.get('accounts', []), build_account_dedupe_key)
                        deduped_inqs, inq_dups = dedupe_items(parsed.get('inquiries', []), build_inquiry_dedupe_key)

                        hard = sum(1 for i in parsed.get('inquiries', []) if classify_inquiry_type(i) == 'HARD')
                        soft = sum(1 for i in parsed.get('inquiries', []) if classify_inquiry_type(i) == 'SOFT')
                        unknown = sum(1 for i in parsed.get('inquiries', []) if classify_inquiry_type(i) == 'UNKNOWN')

                        st.caption(f"**Raw counts:** {raw_accts} accounts, {raw_inqs} inquiries")
                        st.caption(f"**Deduped:** {len(deduped_accts)} accounts, {len(deduped_inqs)} inquiries")
                        st.caption(f"**Inquiry breakdown:** HARD={hard}, SOFT={soft}, UNKNOWN={unknown}")

                        acct_dup_count = sum(1 for k, v in acct_dups.items() if len(v) > 1)
                        inq_dup_count = sum(1 for k, v in inq_dups.items() if len(v) > 1)
                        if acct_dup_count > 0:
                            st.warning(f"{acct_dup_count} account duplicate groups")
                        if inq_dup_count > 0:
                            st.warning(f"{inq_dup_count} inquiry duplicate groups")
                else:
                    st.caption("Upload a report first")

            with st.expander("Upload Diagnostics", expanded=False):
                if hasattr(st.session_state, 'upload_diagnostics') and st.session_state.upload_diagnostics:
                    for diag in st.session_state.upload_diagnostics:
                        st.markdown(f"**Upload ID:** `{diag.get('upload_id', 'N/A')}`")
                        st.markdown(f"**File:** {diag.get('filename', 'N/A')}")
                        st.markdown(f"**Detected Bureau:** `{diag.get('detected_bureau', 'N/A')}`")
                        st.markdown(f"**File Hash:** `{diag.get('file_hash', 'N/A')}`")
                        counts = diag.get('snapshot_counts', {})
                        if counts:
                            st.markdown(f"**Counts:** Accounts={counts.get('accounts', 0)}, Hard Inq={counts.get('hard_inquiries', 0)}, Soft Inq={counts.get('soft_inquiries', 0)}, Neg={counts.get('negative_items', 0)}")
                        st.markdown("---")
                else:
                    st.caption("No upload diagnostics yet")

    st.markdown("---")
    st.markdown("**850 Lab** | Credit Report Intelligence")

if st.session_state.ui_card not in VALID_CARDS:
    st.session_state.ui_card = "SUMMARY" if st.session_state.uploaded_reports else "UPLOAD"

if st.session_state.uploaded_reports and st.session_state.ui_card == "UPLOAD":
    advance_card("SUMMARY")

if st.session_state.generated_letters and st.session_state.ui_card in ("DISPUTES", "SUMMARY") and not st.session_state.get('manual_nav_back'):
    advance_card("DONE")

if st.session_state.analytics_last_card != st.session_state.ui_card:
    track_analytics('page_view', st.session_state.ui_card)
    st.session_state.analytics_last_card = st.session_state.ui_card
    st.session_state.analytics_card_enter_ts = time.time()

if st.session_state.admin_dashboard_active:
    if not is_admin_user:
        st.session_state.admin_dashboard_active = False
        st.rerun()
    else:
        render_admin_dashboard()
        st.stop()

render_card_progress()
st.markdown('<div class="card-viewport">', unsafe_allow_html=True)

MAX_FILE_SIZE_MB = 25

if st.session_state.ui_card == "UPLOAD":
    st.markdown('<div class="card-title">Upload your credit report</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-body-copy">'
        'Upload an Equifax, Experian, or TransUnion credit report PDF. '
        "We'll extract what we can confidently read and only generate disputes "
        'that meet verification standards.'
        '</div>',
        unsafe_allow_html=True,
    )

    if 'privacy_consent' not in st.session_state:
        st.session_state.privacy_consent = False

    privacy_agreed = st.checkbox(
        "I understand that my credit report data will be processed and stored securely to generate dispute letters. "
        "I can delete my data at any time from Account Settings.",
        value=st.session_state.privacy_consent,
        key="privacy_checkbox",
    )
    st.session_state.privacy_consent = privacy_agreed

    if not privacy_agreed:
        st.info("Please agree to the data processing terms above to upload your credit report.")
    else:
        uploaded_files = st.file_uploader(
            "Upload Credit Report PDF(s)",
            type=['pdf'],
            accept_multiple_files=True,
            help=f"Upload one or more credit report PDFs. Max {MAX_FILE_SIZE_MB}MB per file."
        )
        import streamlit.components.v1 as stc
        stc.html("""
        <script>
        (function() {
            var doc = window.parent.document;
            if (!doc.getElementById('dz-fix-style')) {
                var s = doc.createElement('style');
                s.id = 'dz-fix-style';
                s.textContent = '[data-testid="stFileUploadDropzone"] span,' +
                    '[data-testid="stFileUploadDropzone"] small,' +
                    '[data-testid="stFileUploadDropzone"] div,' +
                    '[data-testid="stFileUploadDropzone"] p {' +
                    '  color: #1A1A1A !important;' +
                    '  opacity: 1 !important;' +
                    '  -webkit-text-fill-color: #1A1A1A !important;' +
                    '}' +
                    '[data-testid="stFileUploadDropzone"] small {' +
                    '  color: #666666 !important;' +
                    '  -webkit-text-fill-color: #666666 !important;' +
                    '}';
                doc.head.appendChild(s);
            }
        })();
        </script>
        """, height=0)

        if uploaded_files:
            oversized = [uf for uf in uploaded_files if uf.size > MAX_FILE_SIZE_MB * 1024 * 1024]
            valid_files = [uf for uf in uploaded_files if uf.size <= MAX_FILE_SIZE_MB * 1024 * 1024]

            if oversized:
                for uf in oversized:
                    st.error(f"**{uf.name}** is too large ({uf.size/1024/1024:.1f}MB). Maximum file size is {MAX_FILE_SIZE_MB}MB.")

            if valid_files:
                st.markdown(f"**{len(valid_files)} file(s) ready**")
                for uf in valid_files:
                    st.markdown(f"- {uf.name} ({uf.size/1024:.1f} KB)")
            else:
                uploaded_files = None

            if valid_files and st.button("Extract & Analyze All", type="primary", use_container_width=True):
              try:
                all_claims = []
                reports_processed = 0
                diagnostic_logs = []

                st.session_state.uploaded_reports = {}
                st.session_state.extracted_claims = {}

                for uploaded_file in valid_files:
                  with st.status(f"Analyzing {uploaded_file.name}...", expanded=True) as status:
                    status.update(label=f"Reading {uploaded_file.name}...", state="running")
                    st.write("Opening your PDF and extracting text...")
                    pdf_bytes = uploaded_file.read()
                    uploaded_file.seek(0)
                    file_hash = hashlib.sha256(pdf_bytes).hexdigest()[:16]
                    upload_id = f"UPL_{file_hash}"
                    upload_time = datetime.now().isoformat()

                    full_text, page_texts, num_pages, _pdf_extract_error = extract_text_from_pdf(
                        uploaded_file, use_ocr
                    )

                    if full_text:
                        st.write(f"Read {num_pages} pages successfully.")
                        status.update(label=f"Identifying bureau for {uploaded_file.name}...", state="running")
                        st.write("Detecting which credit bureau this report is from...")
                        bureau, bureau_scores, bureau_evidence = detect_bureau(full_text, debug=DEBUG_MODE, return_details=True)
    
                        diag_store.record_upload(
                            bureau_guess=bureau,
                            file_type="pdf",
                            file_size_bytes=len(pdf_bytes),
                            page_count=num_pages,
                            file_name=uploaded_file.name
                        )
    
                        diag_store.record_raw_text_sample(
                            sample=full_text[:1000] if full_text else "",
                            enabled=DEBUG_MODE
                        )
    
                        diag = {
                            'upload_id': upload_id,
                            'filename': uploaded_file.name,
                            'file_hash': file_hash,
                            'upload_time': upload_time,
                            'detected_bureau': bureau,
                            'text_length': len(full_text),
                            'first_200_chars': full_text[:200].replace('\n', ' ')[:100],
                        }
                        diagnostic_logs.append(diag)
    
                        if DEBUG_MODE:
                            print(f"[UPLOAD_DIAG] {json.dumps(diag, indent=2)}")
    
                        if bureau == '3bureau':
                            status.update(label=f"{uploaded_file.name} — 3-bureau report detected", state="error")
                            st.warning(f"⚠️ **{uploaded_file.name}** is a combined 3-bureau report (e.g., SmartCredit). Please upload individual single-bureau reports from TransUnion, Experian, and Equifax for accurate parsing.")
                            continue
    
                        if bureau == 'unknown':
                            status.update(label=f"{uploaded_file.name} — Bureau not identified", state="error")
                            st.warning(f"⚠️ **{uploaded_file.name}** — Could not identify the credit bureau. Please verify this is a TransUnion, Experian, or Equifax credit report.")
                            continue

                        bureau_display = bureau.replace('transunion', 'TransUnion').replace('experian', 'Experian').replace('equifax', 'Equifax')
                        st.write(f"Detected **{bureau_display}** report.")
    
                        status.update(label=f"Parsing accounts from {bureau_display} report...", state="running")
                        st.write("Extracting accounts, balances, and payment history...")
                        try:
                            parsed_data = parse_credit_report_data(full_text, bureau)
                        except Exception as parse_err:
                            diag_store.record_error("parse_credit_report_data", str(parse_err), parse_err)
                            raise

                        status.update(label=f"Deep-reading {bureau_display} report layout...", state="running")
                        st.write("Analyzing page layout for additional detail...")
                        translator_used = False
                        translator_count = 0
                        existing_accounts_count = len(parsed_data.get('accounts', []))
                        try:
                            layout = extract_layout(pdf_bytes)
                            layout_plain_text = to_plain_text(layout)
                            tu_variant_layout = detect_tu_variant_from_text(layout_plain_text)
                            if bureau == 'transunion':
                                canonical_records = build_account_records(layout, tu_variant_layout)
                                translator_count = len(canonical_records)
                                if translator_count > 0 and translator_count >= existing_accounts_count:
                                    translated_accounts = canonical_records_to_parsed_accounts(canonical_records)
                                    parsed_data['accounts'] = translated_accounts
                                    translator_used = True
                                    if DEBUG_MODE:
                                        print(f"[TRANSLATOR] Used layout translator: {translator_count} accounts (was {existing_accounts_count})")
                                elif DEBUG_MODE:
                                    print(f"[TRANSLATOR] Kept regex parser: {existing_accounts_count} accounts (translator found {translator_count})")
                            if DEV_MODE or DEBUG_MODE:
                                st.session_state["layout"] = layout
                            st.session_state["plain_text"] = layout_plain_text
                        except Exception as layout_err:
                            if DEBUG_MODE:
                                print(f"[TRANSLATOR] Layout extraction failed: {layout_err}")
                            layout_plain_text = full_text
                            tu_variant_layout = None
                            st.session_state["plain_text"] = full_text

                        status.update(label=f"Classifying accounts and identifying issues...", state="running")
                        st.write("Checking for negative items, inquiries, and potential disputes...")
                        tu_diag = run_tu_diagnostics(full_text, bureau, bureau_scores, bureau_evidence, parsed_data)
                        if translator_used:
                            tu_diag['translator'] = {
                                'used': True,
                                'translator_accounts': translator_count,
                                'regex_accounts': existing_accounts_count,
                            }
                        diag['tu_diagnostics'] = tu_diag
    
                        source_type = 'ocr' if use_ocr else 'unknown'
                        parsed_data = normalize_parsed_data(parsed_data, source_type=source_type)
    
                        classify_text = layout_plain_text if layout_plain_text else full_text
                        classify_accounts(parsed_data.get('accounts', []), classify_text, variant=tu_variant_layout if bureau == 'transunion' else None, bureau=bureau)
                        cls_neg = compute_negative_items(parsed_data.get('accounts', []))
                        if cls_neg or not parsed_data.get('negative_items'):
                            parsed_data['negative_items'] = cls_neg
                        parsed_data['classification_counts'] = count_by_classification(parsed_data.get('accounts', []))
                        if DEBUG_MODE:
                            cls_counts = parsed_data['classification_counts']
                            print(f"[CLASSIFIER] Adverse={cls_counts.get('ADVERSE',0)}, Good={cls_counts.get('GOOD_STANDING',0)}, Unknown={cls_counts.get('UNKNOWN',0)}")

                        status.update(label=f"Saving results...", state="running")
                        st.write("Storing your parsed report securely...")
                        try:
                            report_id = db.save_report(bureau, uploaded_file.name, parsed_data, full_text, user_id=current_user['user_id'])
                            track_analytics('upload', 'UPLOAD', f'bureau:{bureau}')
                        except Exception:
                            report_id = None
    
                        report_data = {
                            'upload_id': upload_id,
                            'file_name': uploaded_file.name,
                            'file_hash': file_hash,
                            'bureau': bureau,
                            'parsed_data': parsed_data,
                            'full_text': full_text,
                            'num_pages': num_pages,
                            'report_id': report_id,
                            'upload_time': upload_time,
                        }
    
                        snapshot_key = upload_id
                        st.session_state.uploaded_reports[snapshot_key] = report_data
    
                        claims = extract_claims(parsed_data, bureau)
                        st.session_state.extracted_claims[snapshot_key] = claims
    
                        all_claims.extend(claims)
                        reports_processed += 1
    
                        accounts_count = len(parsed_data.get('accounts', []))
                        all_inquiries = parsed_data.get('inquiries', [])
                        hard_inq = len([i for i in all_inquiries if is_hard_inquiry(i)])
                        soft_inq = len([i for i in all_inquiries if not is_hard_inquiry(i)])
                        neg_count = len(parsed_data.get('negative_items', []))
                        public_records_count = len(parsed_data.get('public_records', []))
    
                        personal_info = parsed_data.get('personal_info', {})
                        personal_fields_found = [k for k, v in personal_info.items() if v]
    
                        missing_critical = []
                        if not personal_info.get('name'):
                            missing_critical.append('name')
                        if not personal_info.get('address'):
                            missing_critical.append('address')
    
                        reject_counters = parsed_data.get('reject_counters', {})
                        dedupe_rules = ['smart_account_dedupe_key', 'smart_inquiry_dedupe_key', 'smart_negative_dedupe_key']
    
                        confidence_signals = []
                        if parsed_data.get('confidence_level'):
                            confidence_signals.append(f"Overall: {parsed_data.get('confidence_level')}")
                        for acct in parsed_data.get('accounts', [])[:3]:
                            if acct.get('confidence'):
                                confidence_signals.append(f"Account: {acct.get('confidence')}")
    
                        diag_store.record_extraction(
                            accounts_found=accounts_count,
                            inquiries_found=len(all_inquiries),
                            public_records_found=public_records_count,
                            negative_items_found=neg_count,
                            personal_info_fields=personal_fields_found,
                            missing_critical_fields=missing_critical,
                            dedupe_rules=dedupe_rules,
                            confidence_signals=confidence_signals[:5],
                            reject_counters=reject_counters
                        )
    
                        diag['snapshot_counts'] = {
                            'accounts': accounts_count,
                            'hard_inquiries': hard_inq,
                            'soft_inquiries': soft_inq,
                            'negative_items': neg_count,
                        }
    
                        if DEBUG_MODE:
                            print(f"[SNAPSHOT_BIND] upload_id={upload_id}, bureau={bureau}, report_id={report_id}")
                            print(f"[SNAPSHOT_COUNTS] accounts={accounts_count}, hard_inq={hard_inq}, soft_inq={soft_inq}, neg={neg_count}")

                        status.update(label=f"{bureau_display} report analyzed — {accounts_count} accounts, {neg_count} negative items found", state="complete")

                st.session_state.review_claims = compress_claims(all_claims)
                st.session_state.claim_responses = {}
                st.session_state.review_claim_responses = {}
                st.session_state.identity_confirmed = {}
                st.session_state.generated_letters = {}
                st.session_state.readiness_decisions = []
                st.session_state.letter_candidates = []
                st.session_state.current_approval = None
                st.session_state.capacity_selection = {}
                st.session_state.system_error_message = None
                st.session_state.upload_diagnostics = diagnostic_logs
                st.session_state.review_incomplete_ack = False
    
                if reports_processed > 0:
                    st.session_state.current_report = list(st.session_state.uploaded_reports.values())[0]
                    first_report = st.session_state.current_report
                    first_text = first_report.get('full_text', '')
                    first_bureau = first_report.get('bureau', 'unknown')
                    first_parsed = first_report.get('parsed_data', {})
                    completeness_text = st.session_state.get("plain_text", first_text)
                    c_totals, c_sources = detect_section_totals_with_sources(completeness_text, first_bureau)
                    c_mode = detect_totals_mode_with_sources(c_totals, c_sources, first_bureau, completeness_text)
                    personal_info = first_parsed.get('personal_info', {})
                    pif_count = sum(1 for k in ['name', 'address', 'dob', 'ssn_last4'] if personal_info.get(k))
                    c_extracted = {
                        "accounts": len(first_parsed.get("accounts", [])),
                        "inquiries": count_hard_inquiries(first_parsed),
                        "negative_items": len(first_parsed.get("negative_items", [])),
                        "public_records": len(first_parsed.get("public_records", [])),
                        "personal_info_fields": pif_count,
                    }
                    sv = self_verify_totals(completeness_text, first_bureau, c_extracted)
                    c_report = compute_completeness(first_bureau, c_totals, c_extracted, totals_mode=c_mode, self_verification=sv)
                    st.session_state.completeness_report = c_report
                    st.session_state.totals_confidence = c_report.totals_confidence
                    st.session_state.exactness = c_report.exactness
                    rt = compute_report_totals(first_text, first_bureau)
                    pt, exactness = compute_exactness(rt, first_parsed)
                    st.session_state.report_totals = rt
                    st.session_state.parsed_totals = pt
                    st.session_state.review_exactness_state = c_report.exactness
    
                    unified = compute_unified_summary(st.session_state.uploaded_reports)
                    st.session_state.unified_summary = unified
    
                log_ux("UPLOAD", "UPLOAD", "file_uploader", 4)
                db.log_activity(user_id, 'upload', f"Uploaded {len(st.session_state.uploaded_reports)} report(s)", 'UPLOAD')
                advance_card("SUMMARY")
                st.rerun()
              except Exception as upload_err:
                st.error(f"Error processing report: {upload_err}")
                st.code(traceback.format_exc())


elif st.session_state.ui_card == "SUMMARY":
  try:
    if is_admin_user:
        st.markdown('<div class="card-title">System Extract Summary</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-body-copy">'
            'This view shows what 850 Lab was able to confidently extract from your report.<br/>'
            'If a section is incomplete due to formatting, we will NOT generate disputes from missing or uncertain data.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="card-title">What We Found</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-body-copy">'
            "Here's a summary of what 850 Lab extracted from your credit report. "
            "Items highlighted in gold may be hurting your score and could be candidates for dispute."
            '</div>',
            unsafe_allow_html=True,
        )

    if st.session_state.uploaded_reports:
        log_ux("SUMMARY", "TAP", "summary_render", 4)

        if not is_admin_user:
            total_accounts = 0
            total_negatives = 0
            total_inquiries = 0
            total_adverse = 0
            total_good = 0
            total_unknown = 0
            for sk, rr in st.session_state.uploaded_reports.items():
                pd_c = rr['parsed_data']
                d_c = compute_deduped_counts(pd_c)
                total_accounts += d_c['accounts']
                total_negatives += d_c['negative_items']
                total_inquiries += d_c['hard_inquiries']
                cls_c = pd_c.get('classification_counts', {})
                if cls_c:
                    total_adverse += cls_c.get('ADVERSE', 0)
                    total_good += cls_c.get('GOOD_STANDING', 0)
                    total_unknown += cls_c.get('UNKNOWN', 0)
                else:
                    accts = pd_c.get('accounts', [])
                    total_adverse += sum(1 for a in accts if a.get('classification') == 'ADVERSE')
                    total_good += sum(1 for a in accts if a.get('classification') == 'GOOD_STANDING')
                    total_unknown += sum(1 for a in accts if a.get('classification', 'UNKNOWN') == 'UNKNOWN')
            all_review_claims = st.session_state.get('review_claims', [])
            disputable_count = 0
            for rc in all_review_claims:
                if rc.review_type == ReviewType.IDENTITY_VERIFICATION:
                    continue
                bureau_for_rc = (rc.entities.get('bureau') or '').lower()
                if not bureau_for_rc:
                    disputable_count += 1
                    continue
                identity_block = build_dispute_identity_block(rc, bureau_for_rc)
                if identity_block.is_complete:
                    disputable_count += 1

            classified_accounts = total_good + total_adverse
            if classified_accounts > 0:
                health_pct = max(0, min(100, int(100 * total_good / classified_accounts)))
            elif total_accounts > 0:
                health_pct = 50
            else:
                health_pct = 100
            if health_pct >= 80:
                health_color = "#4CAF50"
                health_label = "Good"
            elif health_pct >= 50:
                health_color = "#D4A017"
                health_label = "Needs Attention"
            else:
                health_color = "#E53935"
                health_label = "Needs Work"

            st.markdown(
                f'<div style="text-align:center;margin:0.5rem 0 1.5rem 0;">'
                f'<div style="display:inline-block;width:80px;height:80px;border-radius:50%;'
                f'border:4px solid {health_color};position:relative;margin-bottom:0.5rem;">'
                f'<span style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);'
                f'font-size:1.4rem;font-weight:700;color:{health_color};">{health_pct}%</span>'
                f'</div>'
                f'<div style="font-size:1rem;font-weight:600;color:{health_color};">{health_label}</div>'
                f'<div style="font-size:0.8rem;color:#9a9a9a;margin-top:0.2rem;">'
                f'{total_good} of {total_accounts} accounts in good standing</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            fc1, fc2, fc3, fc4 = st.columns(4)
            with fc1:
                st.markdown(
                    f'<div class="findings-card"><div class="findings-count">{total_accounts}</div>'
                    f'<div class="findings-label">Accounts Found</div>'
                    f'<div class="findings-context">Across all uploaded reports</div></div>',
                    unsafe_allow_html=True,
                )
            with fc2:
                neg_note = "May be hurting your score" if total_negatives > 0 else "Nothing flagged"
                st.markdown(
                    f'<div class="findings-card"><div class="findings-count">{total_negatives}</div>'
                    f'<div class="findings-label">Negative Items</div>'
                    f'<div class="findings-context">{neg_note}</div></div>',
                    unsafe_allow_html=True,
                )
            with fc3:
                inq_note = "Each one can lower your score" if total_inquiries > 0 else "None detected"
                st.markdown(
                    f'<div class="findings-card"><div class="findings-count">{total_inquiries}</div>'
                    f'<div class="findings-label">Hard Inquiries</div>'
                    f'<div class="findings-context">{inq_note}</div></div>',
                    unsafe_allow_html=True,
                )
            with fc4:
                disp_note = "Ready for dispute letters" if disputable_count > 0 else "No disputes needed"
                st.markdown(
                    f'<div class="findings-card"><div class="findings-count">{disputable_count}</div>'
                    f'<div class="findings-label">Disputable Items</div>'
                    f'<div class="findings-context">{disp_note}</div></div>',
                    unsafe_allow_html=True,
                )

        with st.expander("Report Details"):
            for snapshot_key, report in st.session_state.uploaded_reports.items():
                bureau = report.get('bureau', 'unknown')
                parsed_data = report.get('parsed_data') or {}

                deduped = compute_deduped_counts(parsed_data)

                personal_info = parsed_data.get('personal_info', {})
                personal_fields_count = len([v for v in personal_info.values() if v])

                summary_data = {
                    "Section": ["Accounts", "Inquiries", "Negative Items", "Public Records", "Personal Info Fields Found"],
                    "Extracted Count": [
                        deduped['accounts'],
                        deduped['hard_inquiries'] + deduped['soft_inquiries'],
                        deduped['negative_items'],
                        len(parsed_data.get('public_records', [])),
                        personal_fields_count,
                    ],
                }
                st.markdown(f"**{bureau.title()}** — {report['file_name']}")
                df_summary = pd.DataFrame(summary_data)
                st.table(df_summary.set_index(df_summary.columns[0]))

        unified = st.session_state.get("unified_summary")
        if unified and len(unified.bureaus_found) > 1:
            with st.expander("Cross-Bureau Analysis"):
                st.markdown(
                    '<div class="lab-banner">'
                    '<div class="lab-banner-title">Cross-Bureau Intelligence</div>'
                    f'<div class="lab-banner-body">We compared your reports from {len(unified.bureaus_found)} bureaus '
                    f'({", ".join(b.title() for b in unified.bureaus_found)}) '
                    f'and found {unified.total_accounts_unique} unique accounts.</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

                bureau_abbrev = {"equifax": "EQ", "experian": "EX", "transunion": "TU"}
                bureau_order = [b for b in ["equifax", "experian", "transunion"] if b in unified.per_bureau]
                extra_bureaus = sorted([k for k in unified.per_bureau if k not in bureau_order])
                bureau_order.extend(extra_bureaus)
                for eb in extra_bureaus:
                    bureau_abbrev[eb] = eb.upper()[:3]

                per_bureau_rows = []
                metrics_list = [
                    ("accounts", "Accounts"),
                    ("adverse", "Adverse"),
                    ("good_standing", "Good Standing"),
                    ("unknown", "Unknown"),
                    ("hard_inquiries", "Hard Inquiries"),
                    ("soft_inquiries", "Soft Inquiries"),
                    ("negative_items", "Negative Items"),
                    ("public_records", "Public Records"),
                ]
                for metric_key, metric_label in metrics_list:
                    row = {"Metric": metric_label}
                    total_val = 0
                    for b in bureau_order:
                        val = unified.per_bureau.get(b, {}).get(metric_key, 0)
                        row[bureau_abbrev.get(b, b.upper())] = val
                        total_val += val
                    row["Combined"] = total_val
                    per_bureau_rows.append(row)
                st.markdown("**Per-Bureau Breakdown**")
                df_bureau = pd.DataFrame(per_bureau_rows)
                st.table(df_bureau.set_index(df_bureau.columns[0]))

                multi_matches = get_multi_bureau_accounts(unified.cross_bureau_matches)
                single_matches = [m for m in unified.cross_bureau_matches if not m.is_multi_bureau]
                discrepant = get_discrepant_accounts(unified.cross_bureau_matches)

                total_matches = len(unified.cross_bureau_matches)

                sev_high = 0
                sev_med = 0
                sev_low = 0
                for m in unified.cross_bureau_matches:
                    for d in m.discrepancies:
                        sev = d.get('severity', 'MEDIUM')
                        if sev == "HIGH":
                            sev_high += 1
                        elif sev == "LOW":
                            sev_low += 1
                        else:
                            sev_med += 1

                col_a, col_b, col_c, col_d = st.columns(4)
                with col_a:
                    st.metric("Total Accounts", total_matches)
                with col_b:
                    st.metric("Reported by Multiple Bureaus", len(multi_matches))
                with col_c:
                    st.metric("Single Bureau Only", len(single_matches))
                with col_d:
                    st.metric("Discrepancies Found", unified.discrepancy_count)

                if discrepant:
                    st.markdown("**Cross-Bureau Discrepancies**")
                    if sev_high or sev_med or sev_low:
                        sev_cols = st.columns(3)
                        with sev_cols[0]:
                            st.metric("High Severity", sev_high)
                        with sev_cols[1]:
                            st.metric("Medium Severity", sev_med)
                        with sev_cols[2]:
                            st.metric("Low Severity", sev_low)

                    discrepant_sorted = sorted(discrepant, key=lambda x: -sum(1 for d in x.discrepancies if d.get('severity') == 'HIGH'))
                    disc_show_limit = 10
                    disc_to_show = discrepant_sorted[:disc_show_limit]
                    disc_remaining = len(discrepant_sorted) - disc_show_limit

                    for dm in disc_to_show:
                        acct_name = dm.accounts[0].get('account_name', 'Unknown') if dm.accounts else 'Unknown'
                        acct_num = ''
                        for a in dm.accounts:
                            raw_num = (a.get('account_number', '') or a.get('account_mask', '') or '').strip()
                            if raw_num:
                                digits = ''.join(c for c in raw_num if c.isdigit())
                                acct_num = f" (****{digits[-4:]})" if len(digits) >= 4 else f" ({raw_num})"
                                break
                        bureaus_str = ", ".join(bureau_abbrev.get(b, b.upper()) for b in dm.bureaus)
                        with st.expander(f"{acct_name}{acct_num} — {bureaus_str} — {len(dm.discrepancies)} issue(s)"):
                            disc_rows = []
                            for d in dm.discrepancies:
                                row = {"Field": d['field'], "Severity": d.get('severity', '—')}
                                vals = d.get('values', {})
                                for b in bureau_order:
                                    col_name = bureau_abbrev.get(b, b.upper())
                                    row[col_name] = vals.get(b, "—")
                                disc_rows.append(row)
                            if disc_rows:
                                st.table(pd.DataFrame(disc_rows))

                    if disc_remaining > 0:
                        st.caption(f"Showing top {disc_show_limit} of {len(discrepant_sorted)} discrepant accounts (sorted by severity).")

                if multi_matches:
                    st.markdown("**Account Cross-Bureau Presence**")
                    presence_rows = []
                    for m in sorted(multi_matches, key=lambda x: -x.bureau_count)[:25]:
                        acct_name = m.accounts[0].get('account_name', 'Unknown') if m.accounts else 'Unknown'
                        row = {"Account": acct_name, "Confidence": m.match_confidence}
                        for b in bureau_order:
                            col_name = bureau_abbrev.get(b, b.upper())
                            if b in m.bureaus:
                                row[col_name] = "Y"
                            else:
                                row[col_name] = "—"
                        row["Issues"] = len(m.discrepancies)
                        presence_rows.append(row)
                    if presence_rows:
                        st.table(pd.DataFrame(presence_rows))

        if not is_admin_user:
            for sk_c, rr_c in st.session_state.uploaded_reports.items():
                bureau_c = rr_c.get('bureau', 'unknown')
                pd_cc = rr_c['parsed_data']
                d_cc = compute_deduped_counts(pd_cc)
                pi_c = sanitize_identity_info(pd_cc.get('personal_info', {}))
                pi_fields = [k for k in ['name', 'address', 'dob', 'ssn'] if pi_c.get(k)]
                accounts_list = pd_cc.get('accounts', [])
                negative_items_list = pd_cc.get('negative_items', [])

                neg_account_names = set()
                for ni in negative_items_list:
                    ni_name = (ni.get('account_name') or ni.get('creditor') or ni.get('raw_text', '')).lower().strip()
                    if ni_name:
                        neg_account_names.add(ni_name)

                adverse_accts = [a for a in accounts_list if a.get('classification') == 'ADVERSE']
                good_accts = [a for a in accounts_list if a.get('classification') == 'GOOD_STANDING']
                other_accts = [a for a in accounts_list if a.get('classification') not in ('ADVERSE', 'GOOD_STANDING')]
                adverse_count = len(adverse_accts)
                label_suffix = f" — {adverse_count} adverse" if adverse_count > 0 else ""

                with st.expander(f"{bureau_c.title()} — {rr_c['file_name']} ({d_cc['accounts']} accounts{label_suffix})", expanded=False):
                    if pi_fields:
                        st.caption(f"Personal info detected: {', '.join(pi_fields)}")
                    else:
                        st.caption("Personal info: limited data detected — identity step may show minimal details")
                    st.caption(f"Hard inquiries: {d_cc['hard_inquiries']} | Soft inquiries: {d_cc['soft_inquiries']}")

                    adverse_keywords = ['collection', 'charge-off', 'charged off', 'late',
                                        'delinquent', 'past due', 'repossession', 'foreclosure',
                                        'bankruptcy', 'surrendered']

                    def _render_account(acct, neg_account_names):
                        acct_name = acct.get('account_name', 'Unknown Account')
                        acct_status = acct.get('status', '')
                        acct_balance = acct.get('balance', '')
                        acct_cls = acct.get('classification', 'UNKNOWN')
                        acct_remarks = acct.get('remarks', '')
                        acct_pay_status = acct.get('pay_status', '')

                        flags = []
                        status_lower = (acct_status or '').lower()
                        for kw in adverse_keywords:
                            if kw in status_lower:
                                flags.append(acct_status.strip())
                                break

                        if acct_pay_status:
                            ps_lower = acct_pay_status.lower()
                            for kw in adverse_keywords:
                                if kw in ps_lower:
                                    if acct_pay_status.strip() not in flags:
                                        flags.append(f"Pay status: {acct_pay_status.strip()}")
                                    break

                        if acct_remarks:
                            remarks_lower = acct_remarks.lower()
                            for kw in adverse_keywords:
                                if kw in remarks_lower:
                                    flags.append(f"Remark: {acct_remarks.strip()}")
                                    break

                        try:
                            bal_val = float(str(acct_balance).replace('$', '').replace(',', '').strip())
                            if bal_val > 0 and any(kw in status_lower for kw in ['collection', 'charge-off', 'charged off']):
                                flags.append(f"Balance: ${bal_val:,.0f}")
                        except (ValueError, TypeError):
                            pass

                        if not flags and acct_name.lower().strip() in neg_account_names:
                            flags.append("Listed in negative items")

                        if not flags and acct_cls == 'ADVERSE':
                            flags.append("Classified as adverse")

                        if flags:
                            flag_text = " · ".join(flags)
                            st.markdown(
                                f'<div style="padding:8px 12px;margin-bottom:6px;border-left:3px solid #d4a017;'
                                f'background:rgba(212,160,23,0.08);border-radius:4px;">'
                                f'<span style="font-weight:600;color:#e8e8e8;">{acct_name}</span><br/>'
                                f'<span style="color:#d4a017;font-size:0.85em;">{flag_text}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f'<div style="padding:8px 12px;margin-bottom:6px;border-left:3px solid #4a4a4a;'
                                f'background:rgba(255,255,255,0.03);border-radius:4px;">'
                                f'<span style="color:#b0b0b0;">{acct_name}</span><br/>'
                                f'<span style="color:#6a6a6a;font-size:0.85em;">No negative indicators found</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                    if adverse_accts:
                        st.markdown(f"**Adverse Accounts ({len(adverse_accts)})** — these may be hurting your score")
                        for acct in adverse_accts:
                            _render_account(acct, neg_account_names)

                    if other_accts:
                        st.markdown(f"**Other Accounts ({len(other_accts)})**")
                        for acct in other_accts:
                            _render_account(acct, neg_account_names)

                    if good_accts:
                        st.markdown(f"**Good Standing ({len(good_accts)})**")
                        for acct in good_accts:
                            _render_account(acct, neg_account_names)

                    if not accounts_list:
                        st.caption("No accounts extracted from this report.")

            if disputable_count > 0:
                st.markdown(
                    f'<div class="summary-cta">'
                    f'<div class="summary-cta-text">We found <strong>{disputable_count} item{"s" if disputable_count != 1 else ""}</strong> '
                    f'that could be disputed. Continue to review and generate your dispute letters.</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="summary-cta">'
                    '<div class="summary-cta-text">Your report looks clean. Continue to see all available options.</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

        if is_admin_user:
            c_report = st.session_state.get("completeness_report")
            if c_report:
                tc = c_report.totals_confidence
                ex = c_report.exactness
                v_method = getattr(c_report, 'verification_method', 'standard')
                v_sections = getattr(c_report, 'matched_sections', [])
            else:
                r_totals = st.session_state.get("report_totals") or {}
                tc = r_totals.get("confidence", "LOW")
                ex = st.session_state.get("review_exactness_state", "UNKNOWN")
                v_method = "standard"
                v_sections = []

            if ex in ("EXACT", "PROVABLE") and tc in ("HIGH", "MED"):
                exactness_label = "EXACT" if ex == "EXACT" else "PROVABLE"
                if v_method == "self_verified":
                    matched_str = ", ".join(s.replace("_", " ").title() for s in v_sections) if v_sections else "multiple sections"
                    exactness_detail = f"cross-verified via independent counting ({matched_str})."
                elif v_method == "section_derived":
                    exactness_detail = "counts match section-derived totals (report does not print explicit totals)."
                elif ex == "EXACT":
                    exactness_detail = "all extracted counts match the report totals."
                else:
                    exactness_detail = "counts verified against report structure."
                st.markdown(
                    '<div class="lab-banner">'
                    f'<div class="lab-banner-title">Totals Confidence: {tc}</div>'
                    f'<div class="lab-banner-body">Exactness: {exactness_label} &mdash; {exactness_detail}</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            elif ex == "UNPROVABLE":
                st.markdown(
                    '<div class="lab-banner">'
                    f'<div class="lab-banner-title">Totals Confidence: {tc}</div>'
                    '<div class="lab-banner-body">Exactness: UNPROVABLE &mdash; this report format does not include summary totals for verification. Extracted counts are used as-is.</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="lab-banner">'
                    f'<div class="lab-banner-title">Totals Confidence: {tc}</div>'
                    f'<div class="lab-banner-body">Exactness: {ex or "UNKNOWN"}</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    "Note: Your report format limits exact counting in some sections. "
                    "This does not block disputes\u2014only dispute-ready items proceed."
                )

            if c_report and c_report.sections:
                section_rows = []
                section_display = {
                    "accounts": "Accounts",
                    "inquiries": "Inquiries",
                    "negative_items": "Negative Items",
                    "public_records": "Public Records",
                    "personal_info_fields": "Personal Info Fields",
                }
                for s_key, s_label in section_display.items():
                    sc = c_report.sections.get(s_key)
                    if sc:
                        section_rows.append({
                            "Section": s_label,
                            "Expected": sc.expected_total if sc.expected_total is not None else "\u2014",
                            "Extracted": sc.extracted_total,
                            "Delta": sc.delta if sc.delta is not None else "\u2014",
                            "Match": "\u2713" if sc.section_pass is True else ("\u2717" if sc.section_pass is False else "\u2014"),
                        })
                if section_rows:
                    st.table(pd.DataFrame(section_rows))

            for snapshot_key_cls, report_cls in st.session_state.uploaded_reports.items():
                cls_counts = report_cls['parsed_data'].get('classification_counts', {})
                if cls_counts:
                    adverse_n = cls_counts.get('ADVERSE', 0)
                    good_n = cls_counts.get('GOOD_STANDING', 0)
                    unknown_n = cls_counts.get('UNKNOWN', 0)
                    total_n = adverse_n + good_n + unknown_n
                    cls_data = {
                        "Classification": ["Adverse", "Good Standing", "Unknown", "Total Accounts"],
                        "Count": [adverse_n, good_n, unknown_n, total_n],
                    }
                    st.markdown("**Account Classification**")
                    st.table(pd.DataFrame(cls_data))

        if DEBUG_MODE:
            with st.expander("View All Extracted Data"):
                all_accounts = []
                all_inquiries_debug = []
                all_negatives = []
                all_personal = {}

                for sk, r in st.session_state.uploaded_reports.items():
                    b = r.get('bureau', 'unknown')
                    pd_data = r['parsed_data']
                    if pd_data.get('personal_info'):
                        all_personal.update(pd_data['personal_info'])
                    for acct in pd_data.get('accounts', []):
                        acct['bureau'] = b
                        all_accounts.append(acct)
                    for inq in pd_data.get('inquiries', []):
                        inq['bureau'] = b
                        all_inquiries_debug.append(inq)
                    for neg in pd_data.get('negative_items', []):
                        neg['bureau'] = b
                        all_negatives.append(neg)

                if all_personal:
                    st.markdown("**Personal Info**")
                    for k, v in all_personal.items():
                        st.write(f"**{k.title()}:** {v}")
                if all_accounts:
                    st.markdown("**Accounts**")
                    df = pd.DataFrame(all_accounts)
                    cols = ['bureau', 'account_name', 'balance', 'status', 'date_opened']
                    display_cols = [c for c in cols if c in df.columns]
                    st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
                if all_negatives:
                    st.markdown("**Negative Items**")
                    df = pd.DataFrame(all_negatives)
                    cols = ['bureau', 'type', 'date', 'amount']
                    display_cols = [c for c in cols if c in df.columns]
                    st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
                if all_inquiries_debug:
                    st.markdown("**Inquiries**")
                    st.dataframe(pd.DataFrame(all_inquiries_debug), use_container_width=True)

        if DEBUG_MODE or DEV_MODE:
            tu_diag_data = st.session_state.get('upload_diagnostics', [])
            any_tu_diag = any(d.get('tu_diagnostics') for d in tu_diag_data) if tu_diag_data else False
            if any_tu_diag:
                with st.expander("TEMP: TransUnion Diagnostics", expanded=True):
                    for d in tu_diag_data:
                        td = d.get('tu_diagnostics')
                        if not td:
                            continue
                        st.markdown(f"**File:** `{d.get('filename', '?')}`")

                        st.markdown("**1) Bureau Detection**")
                        bd = td.get('bureau_detection', {})
                        st.code(f"Detected: {bd.get('bureau_detected')}\nScores: {json.dumps(bd.get('scores', {}))}\nPatterns: {json.dumps(bd.get('matched_patterns', {}))}", language=None)

                        st.markdown("**2) Parser Path**")
                        pp = td.get('parser_path', {})
                        st.code(f"Parser called: {pp.get('parser_called')}\nTU parser used: {pp.get('tu_parser_used')}\nTU Variant Detected: {pp.get('tu_variant', 'N/A')}\nAccounts Parser Used: {pp.get('accounts_parser', 'N/A')}\nWARNING: {pp.get('WARNING', 'None')}", language=None)

                        st.markdown("**3) Raw Text Sanity**")
                        rts = td.get('raw_text_sanity', {})
                        needle_lines = '\n'.join(f"  {k}: {v}" for k, v in rts.get('needle_hits', {}).items())
                        st.code(f"Text length: {rts.get('raw_text_length')} chars\nNeedle hits:\n{needle_lines}", language=None)

                        st.markdown("**4) TU Section Anchors**")
                        anchors = td.get('tu_section_anchors', {}).get('found', 'NO_TU_SECTIONS_FOUND')
                        st.code(f"Found: {anchors}", language=None)

                        st.markdown("**5) Safety Gate**")
                        sg = td.get('safety_gate', {})
                        st.code(f"Accounts returned: {sg.get('accounts_returned')}\nEmpty reason: {sg.get('empty_reason')}\nReject counters: {json.dumps(sg.get('reject_counters', {}))}\nTotal rejects: {sg.get('total_rejects')}", language=None)

                        st.markdown("**6) TU Header Regex Scan**")
                        hrs = td.get('tu_header_regex_scan', {})
                        samples_str = '\n'.join(f"  {s}" for s in hrs.get('sample_matches', []))
                        st.code(f"Pattern: {hrs.get('pattern')}\nMatches found: {hrs.get('matches_in_full_text')}\nSample matches:\n{samples_str if samples_str else '  (none)'}", language=None)

                        st.markdown("---")

        review_claims_list = st.session_state.review_claims
        has_eligible = False
        if review_claims_list:
            has_eligible = True

        if has_eligible:
            st.markdown("---")
            st.markdown("### Confirm Your Identity")
            st.caption("Please verify the personal information extracted from your reports before continuing.")

            all_confirmed = True
            all_bureau_infos = {}
            for sk, rpt in st.session_state.uploaded_reports.items():
                b = rpt.get('bureau', 'unknown').lower()
                raw = rpt.get('parsed_data', {}).get('personal_info', {})
                all_bureau_infos[b] = sanitize_identity_info(raw)
            merged_pi = {}
            for field in ['name', 'address', 'dob', 'date_of_birth', 'ssn']:
                for bi in all_bureau_infos.values():
                    val = bi.get(field)
                    if val and (not merged_pi.get(field) or len(str(val)) > len(str(merged_pi[field]))):
                        merged_pi[field] = val

            for snapshot_key, report in st.session_state.uploaded_reports.items():
                bureau = report.get('bureau', 'unknown')
                bureau_key = bureau.lower()

                bureau_info = all_bureau_infos.get(bureau_key, {})
                has_valid_fields = any(v for v in bureau_info.values() if v)

                display_info = dict(bureau_info)
                for field in ['name', 'address', 'dob', 'date_of_birth', 'ssn']:
                    if not display_info.get(field) and merged_pi.get(field):
                        display_info[field] = merged_pi[field]
                    elif display_info.get(field) and merged_pi.get(field) and len(str(merged_pi[field])) > len(str(display_info[field])):
                        display_info[field] = merged_pi[field]

                has_valid_fields = has_valid_fields or any(v for v in display_info.values() if v)

                if has_valid_fields:
                    with st.expander(f"{bureau.title()} Identity", expanded=False):
                        info_items = []
                        if display_info.get('name'):
                            info_items.append(f"Name: {display_info['name']}")
                        else:
                            info_items.append("Name: Not detected")
                        if display_info.get('address'):
                            info_items.append(f"Address: {display_info['address']}")
                        if display_info.get('dob') or display_info.get('date_of_birth'):
                            dob = display_info.get('dob') or display_info.get('date_of_birth')
                            info_items.append(f"Date of Birth: {dob}")
                        if display_info.get('ssn'):
                            info_items.append(f"SSN: {display_info['ssn']}")
                        for key, value in bureau_info.items():
                            if key not in ['name', 'address', 'dob', 'date_of_birth', 'ssn'] and value:
                                info_items.append(f"{key.replace('_', ' ').title()}: {value}")
                        for item in info_items:
                            st.write(f"- {item}")

                        bureau_confirmed = st.checkbox(
                            f"I confirm this is my {bureau.title()} credit report.",
                            value=st.session_state.identity_confirmed.get(bureau_key, False),
                            key=f"identity_confirmation_{bureau_key}"
                        )
                        st.session_state.identity_confirmed[bureau_key] = bureau_confirmed
                        if not bureau_confirmed:
                            all_confirmed = False
                else:
                    st.session_state.identity_confirmed[bureau_key] = True

            if not all_confirmed:
                st.warning("Please confirm your identity for all bureaus before continuing.")
            else:
                st.info(
                    "📋 **Heads up — you'll need proof of identity and address.**\n\n"
                    "When you mail your dispute letters, each bureau requires a copy of "
                    "a government-issued ID (driver's license, passport, or state ID) "
                    "and a recent proof of address (utility bill, bank statement, or "
                    "insurance statement). Have these ready to include with your letters."
                )

            if st.button("Continue", type="primary", use_container_width=True, key="summary_continue_btn", disabled=not all_confirmed):
                st.session_state.manual_nav_back = False
                advance_card("PREPARING")
                st.rerun()
        else:
            if st.button("Finish", type="primary", use_container_width=True, key="summary_finish_btn"):
                st.session_state.manual_nav_back = False
                advance_card("DONE")
                st.rerun()
    else:
        st.info("No report data available. Please upload a report first.")
        if st.button("Go to Upload", type="primary", use_container_width=True, key="summary_back_btn"):
            advance_card("UPLOAD")
            st.rerun()
  except Exception as summary_err:
    st.error(f"Error rendering summary: {summary_err}")
    st.code(traceback.format_exc())

elif st.session_state.ui_card == "PREPARING":
    bureau_names = []
    if st.session_state.uploaded_reports and isinstance(st.session_state.uploaded_reports, dict):
        for key, val in st.session_state.uploaded_reports.items():
            if isinstance(val, dict) and val.get('bureau'):
                b = val['bureau'].title()
            else:
                b = key.title()
            if b not in bureau_names:
                bureau_names.append(b)
    bureau_text = " and ".join(bureau_names) if bureau_names else "your bureaus"

    st.markdown(f"""
    <style>
    @keyframes bulb-glow {{
        0% {{ opacity: 0.3; filter: grayscale(1); transform: scale(0.8); }}
        40% {{ opacity: 0.5; filter: grayscale(0.5); transform: scale(0.95); }}
        70% {{ opacity: 1; filter: grayscale(0); transform: scale(1.05);
               text-shadow: 0 0 30px rgba(212,160,23,0.6); }}
        100% {{ opacity: 1; filter: grayscale(0); transform: scale(1);
                text-shadow: 0 0 20px rgba(212,160,23,0.3); }}
    }}
    @keyframes text-fade {{
        0% {{ opacity: 0; transform: translateY(12px); }}
        100% {{ opacity: 1; transform: translateY(0); }}
    }}
    .bulb-icon {{
        font-size: 4rem;
        animation: bulb-glow 1.2s ease-out forwards;
    }}
    .aha-title {{
        font-size: 1.6rem;
        font-weight: 700;
        color: {TEXT_0};
        opacity: 0;
        animation: text-fade 0.6s ease-out 0.8s forwards;
    }}
    .aha-sub {{
        font-size: 1rem;
        color: {TEXT_1};
        max-width: 360px;
        line-height: 1.6;
        opacity: 0;
        animation: text-fade 0.6s ease-out 1.2s forwards;
    }}
    .aha-btn-wrap {{
        opacity: 0;
        animation: text-fade 0.5s ease-out 1.6s forwards;
    }}
    </style>
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                min-height:55vh;text-align:center;padding:2rem 1rem;">
        <div class="bulb-icon">&#x1f4a1;</div>
        <div class="aha-title" style="margin-top:1rem;">
            Aha! We built your dispute plan
        </div>
        <div class="aha-sub" style="margin-top:0.75rem;">
            We analyzed your {bureau_text} reports and know exactly what to dispute and why.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="aha-btn-wrap">', unsafe_allow_html=True)
    if st.button("See Your Dispute Plan", type="primary", use_container_width=True, key="preparing_continue_btn"):
        advance_card("DISPUTES")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.ui_card == "DISPUTES":
    if st.session_state.uploaded_reports:
        if st.button("← Back to Summary", key="disputes_back_summary"):
            st.session_state.manual_nav_back = True
            advance_card("SUMMARY")
            st.rerun()

    st.markdown('<div class="card-title">Your Dispute Plan</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-body-copy">'
        'We analyzed your reports and built a plan. Every item below is something we can dispute on your behalf.<br/>'
        'Uncheck anything you don\'t want to include, then hit Generate.'
        '</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.uploaded_reports:
        st.info("Upload and parse a credit report first.")
    else:
        review_claims_list = st.session_state.review_claims

        if not review_claims_list:
            st.success("No claims found in the uploaded reports.")
        else:
            previously_disputed_ids = []
            for prev_round in st.session_state.dispute_rounds:
                previously_disputed_ids.extend(prev_round.get('claim_ids', []))
            round_number = len(st.session_state.dispute_rounds) + 1

            eligible_items = []
            _seen_rc_ids = set()
            for rc in review_claims_list:
                if rc.review_type == ReviewType.IDENTITY_VERIFICATION:
                    continue
                if rc.review_claim_id in previously_disputed_ids:
                    continue
                if rc.review_claim_id in _seen_rc_ids:
                    continue
                _seen_rc_ids.add(rc.review_claim_id)
                eligible_items.append(rc)

            r1_actions = {
                ReviewType.NEGATIVE_IMPACT: "We'll ask the bureau to reinvestigate and confirm accuracy. If they can't verify it, it gets removed.",
                ReviewType.ACCOUNT_OWNERSHIP: "We'll ask the bureau to confirm you opened these accounts. Unverifiable items get deleted.",
                ReviewType.DUPLICATE_ACCOUNT: "We'll ask the bureau to reinvestigate and merge or remove duplicate entries.",
                ReviewType.ACCURACY_VERIFICATION: "We'll ask the bureau to reinvestigate the details and correct anything that can't be verified.",
                ReviewType.UNVERIFIABLE_INFORMATION: "We'll ask the bureau to verify these items. Anything they can't confirm gets removed.",
            }
            r2_actions = {
                ReviewType.NEGATIVE_IMPACT: "We'll demand the bureau verify each item. If the creditor can't confirm it, it gets removed.",
                ReviewType.ACCOUNT_OWNERSHIP: "We'll challenge the bureau to prove you opened these accounts.",
                ReviewType.DUPLICATE_ACCOUNT: "We'll request the bureau merge or remove the duplicate entries.",
                ReviewType.ACCURACY_VERIFICATION: "We'll ask the bureau to verify the details with the creditor and correct what's wrong.",
                ReviewType.UNVERIFIABLE_INFORMATION: "Under FCRA \u00a7 611, the bureau must verify or remove items within 30 days.",
            }
            action_map = r1_actions if round_number == 1 else r2_actions
            CATEGORY_CONFIG = {
                ReviewType.NEGATIVE_IMPACT: {
                    "label": "Late Payments & Negative Marks",
                    "icon": "\u26a0\ufe0f",
                    "why": "These items are hurting your score the most. Removing even one can make a real difference.",
                    "action": action_map[ReviewType.NEGATIVE_IMPACT],
                },
                ReviewType.ACCOUNT_OWNERSHIP: {
                    "label": "Accounts to Verify Ownership",
                    "icon": "\U0001f6ab",
                    "why": "These accounts may not belong to you, or could be the result of identity theft or a mixed file.",
                    "action": action_map[ReviewType.ACCOUNT_OWNERSHIP],
                },
                ReviewType.DUPLICATE_ACCOUNT: {
                    "label": "Duplicate Entries",
                    "icon": "\U0001f4cb",
                    "why": "The same account appears more than once, unfairly inflating your debt on paper.",
                    "action": action_map[ReviewType.DUPLICATE_ACCOUNT],
                },
                ReviewType.ACCURACY_VERIFICATION: {
                    "label": "Inaccurate Details",
                    "icon": "\U0001f4ca",
                    "why": "These accounts have wrong balances, dates, or statuses that misrepresent your credit history.",
                    "action": action_map[ReviewType.ACCURACY_VERIFICATION],
                },
                ReviewType.UNVERIFIABLE_INFORMATION: {
                    "label": "Unverifiable Information",
                    "icon": "\U0001f50d",
                    "why": "These items lack the documentation needed to prove they're accurate.",
                    "action": action_map[ReviewType.UNVERIFIABLE_INFORMATION],
                },
            }

            if not eligible_items:
                if previously_disputed_ids:
                    st.markdown(
                        f'<div style="background:{BG_1};border-radius:12px;padding:2rem;text-align:center;">'
                        f'<div style="font-size:2.5rem;margin-bottom:0.75rem;">&#x2705;</div>'
                        f'<div style="font-size:1.2rem;font-weight:600;color:{TEXT_0};margin-bottom:0.5rem;">All Items Disputed</div>'
                        f'<div style="color:{TEXT_1};">You\'ve disputed all {len(previously_disputed_ids)} eligible items across {len(st.session_state.dispute_rounds)} round{"s" if len(st.session_state.dispute_rounds) != 1 else ""}. '
                        f'Check your letters on the next screen.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div style="background:{BG_1};border-radius:12px;padding:2rem;text-align:center;">'
                        f'<div style="font-size:2.5rem;margin-bottom:0.75rem;">&#x1f389;</div>'
                        f'<div style="font-size:1.2rem;font-weight:600;color:{TEXT_0};margin-bottom:0.5rem;">Your Reports Look Good</div>'
                        f'<div style="color:{TEXT_1};">We didn\'t find any items that need disputing. Your credit reports appear accurate.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            else:
                if round_number > 1:
                    st.markdown(
                        f'<div style="background:{BG_2};border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:0.9rem;color:{TEXT_1};">'
                        f'Round {round_number} &mdash; {len(previously_disputed_ids)} items already disputed in previous rounds'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                grouped = {}
                for rc in eligible_items:
                    rt = rc.review_type
                    if rt not in grouped:
                        grouped[rt] = []
                    grouped[rt].append(rc)

                category_order = [
                    ReviewType.NEGATIVE_IMPACT,
                    ReviewType.ACCOUNT_OWNERSHIP,
                    ReviewType.DUPLICATE_ACCOUNT,
                    ReviewType.ACCURACY_VERIFICATION,
                    ReviewType.UNVERIFIABLE_INFORMATION,
                ]

                current_letter_balance_init = user_entitlements.get('letters', 0)
                has_used_free = auth.has_used_free_letters(current_user['user_id']) if not is_admin_user else False
                using_free_mode = (current_letter_balance_init == 0 and not has_used_free and not is_admin_user)

                if 'battle_plan_items' not in st.session_state:
                    if using_free_mode:
                        bureau_counts = {}
                        sorted_eligible = sorted(eligible_items, key=lambda rc: (
                            0 if hasattr(rc, 'impact_assessment') and rc.impact_assessment and rc.impact_assessment.severity == Severity.HIGH else
                            1 if hasattr(rc, 'impact_assessment') and rc.impact_assessment and rc.impact_assessment.severity == Severity.MODERATE else 2
                        ))
                        st.session_state.battle_plan_items = {}
                        for rc in sorted_eligible:
                            bureau = (rc.entities.get('bureau') or 'unknown').lower()
                            bureau_counts[bureau] = bureau_counts.get(bureau, 0)
                            if bureau_counts[bureau] < auth.FREE_PER_BUREAU_LIMIT:
                                st.session_state.battle_plan_items[rc.review_claim_id] = True
                                bureau_counts[bureau] += 1
                            else:
                                st.session_state.battle_plan_items[rc.review_claim_id] = False
                    else:
                        st.session_state.battle_plan_items = {rc.review_claim_id: True for rc in eligible_items}
                else:
                    for rc in eligible_items:
                        if rc.review_claim_id not in st.session_state.battle_plan_items:
                            st.session_state.battle_plan_items[rc.review_claim_id] = (not using_free_mode)

                all_bureaus = set()
                total_high = 0
                for rc in eligible_items:
                    b = (rc.entities.get('bureau') or '').lower()
                    if b:
                        all_bureaus.add(b)
                    if hasattr(rc, 'impact_assessment') and rc.impact_assessment and rc.impact_assessment.severity == Severity.HIGH:
                        total_high += 1

                total_items = len(eligible_items)
                total_letters = len(all_bureaus) if all_bureaus else 1

                summary_parts = []
                summary_parts.append(f'{total_items} item{"s" if total_items != 1 else ""}')
                summary_parts.append(f'{total_letters} letter{"s" if total_letters != 1 else ""}')
                if total_high:
                    summary_parts.append(f'{total_high} high impact')

                st.markdown(
                    f'<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">'
                    + ''.join(
                        f'<span style="background:{GOLD};color:#1A1A1A;padding:4px 12px;border-radius:16px;font-size:0.85rem;font-weight:600;">{p}</span>'
                        for p in summary_parts
                    )
                    + f'</div>',
                    unsafe_allow_html=True,
                )

                ai_balance = user_entitlements.get('ai_rounds', 0)
                has_ai_ent = is_admin_user or ai_balance > 0
                ai_result = st.session_state.ai_strategy_result

                if st.session_state.pop('_ai_spend_failed', False):
                    st.warning("Your AI analysis completed, but we couldn't deduct the credit. Your balance may not reflect this usage — please contact support if it persists.")

                if ai_result and ai_result.get('source') in ('ai', 'deterministic'):
                    source_label = "AI Strategy Analysis" if ai_result.get('source') == 'ai' else "Strategy Analysis"
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg, rgba(212,160,23,0.08), rgba(212,160,23,0.02));'
                        f'border:1px solid {GOLD};border-radius:12px;padding:18px 20px;margin-bottom:16px;">'
                        f'<div style="font-size:1.05rem;font-weight:700;color:{TEXT_0};margin-bottom:6px;">'
                        f'{source_label}</div>'
                        f'<div style="font-size:0.88rem;color:{TEXT_1};line-height:1.5;margin-bottom:10px;">'
                        f'{ai_result.get("rationale", "")}</div>'
                        f'<div style="font-size:0.82rem;color:{GOLD_DIM};font-style:italic;">'
                        f'{ai_result.get("round_summary", "")}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button("Clear Analysis", key="clear_ai_strategy", type="secondary"):
                        st.session_state.ai_strategy_result = None
                        st.rerun()
                else:
                    if has_ai_ent:
                        ai_col1, ai_col2 = st.columns([3, 1])
                        with ai_col1:
                            st.markdown(
                                f'<div style="font-size:0.92rem;color:{TEXT_0};font-weight:600;margin-bottom:2px;">'
                                f'Want smarter prioritization?</div>'
                                f'<div style="font-size:0.82rem;color:{TEXT_1};">'
                                f'AI analyzes your items and recommends which to dispute first for maximum impact.</div>',
                                unsafe_allow_html=True,
                            )
                        with ai_col2:
                            if st.button("Analyze with AI", key="run_ai_strategy", type="primary", use_container_width=True):
                                st.session_state.ai_strategy_running = True
                                st.rerun()
                    else:
                        st.markdown(
                            f'<div style="background:linear-gradient(135deg, rgba(212,160,23,0.08), rgba(212,160,23,0.02));'
                            f'border:1px solid rgba(212,160,23,0.3);border-radius:10px;padding:14px 16px;margin-bottom:8px;">'
                            f'<div style="font-size:0.95rem;font-weight:700;color:{TEXT_0};margin-bottom:6px;">'
                            f'Unlock AI-Powered Strategy</div>'
                            f'<div style="font-size:0.82rem;color:{TEXT_1};line-height:1.5;margin-bottom:8px;">'
                            f'AI ranks your {total_items} items by impact and tells you <strong style="color:{GOLD};">exactly which to dispute first</strong> '
                            f'— with legal reasoning for each one. Don\'t waste your round on low-priority items.</div>'
                            f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:6px;">'
                            f'<span style="font-size:0.78rem;color:{TEXT_1};">&#x2713; Priority ranking</span>'
                            f'<span style="font-size:0.78rem;color:{TEXT_1};">&#x2713; Legal reasoning</span>'
                            f'<span style="font-size:0.78rem;color:{TEXT_1};">&#x2713; Impact scores</span>'
                            f'</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        render_purchase_options(context="disputes_ai", needed_ai=1)

                if st.session_state.ai_strategy_running and not ai_result:
                    with st.spinner("Running AI analysis..."):
                        previously_excluded = []
                        for prev_round in st.session_state.dispute_rounds:
                            previously_excluded.extend(prev_round.get('claim_ids', []))
                        try:
                            strategy = build_ai_strategy(
                                review_claims_list,
                                round_size=min(len(eligible_items), 10),
                                excluded_ids=previously_excluded,
                            )
                        except Exception as e:
                            print(f"[AI_STRATEGY_ERROR] {type(e).__name__}: {e}")
                            strategy = build_deterministic_strategy(
                                review_claims_list,
                                round_size=min(len(eligible_items), 10),
                                excluded_ids=previously_excluded,
                            )

                        ai_per_claim = {}
                        for sc in strategy.selected_claims:
                            rc_id = sc.review_claim.review_claim_id
                            per_rationale = strategy.per_claim_rationale.get(rc_id, '')
                            ai_per_claim[rc_id] = {
                                'rationale': per_rationale,
                                'score': round(sc.impact_score, 1),
                                'rank': sc.rank,
                            }
                        st.session_state.ai_strategy_result = {
                            'source': strategy.source,
                            'rationale': strategy.rationale,
                            'round_summary': strategy.round_summary,
                            'per_claim': ai_per_claim,
                            'selected_ids': [sc.review_claim.review_claim_id for sc in strategy.selected_claims],
                        }
                        if strategy.source == 'ai' and not is_admin_user:
                            if auth.spend_entitlement(current_user['user_id'], 'ai_rounds', 1):
                                user_entitlements['ai_rounds'] = max(0, ai_balance - 1)
                            else:
                                st.session_state._ai_spend_failed = True

                        st.session_state.ai_strategy_running = False
                        st.rerun()

                ai_per_claim_data = (ai_result or {}).get('per_claim', {})

                _bp_key_counter = {}
                for rt in category_order:
                    if rt not in grouped:
                        continue
                    items = grouped[rt]
                    config = CATEGORY_CONFIG.get(rt, {"label": rt.value.replace("_", " ").title(), "icon": "\U0001f4cc", "why": "", "action": ""})

                    high_in_cat = sum(1 for rc in items if hasattr(rc, 'impact_assessment') and rc.impact_assessment and rc.impact_assessment.severity == Severity.HIGH)
                    impact_badge = ""
                    if high_in_cat:
                        impact_badge = f' <span style="background:{GOLD};color:#1A1A1A;padding:1px 7px;border-radius:4px;font-size:0.72rem;font-weight:600;">HIGH IMPACT</span>'

                    st.markdown(
                        f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;padding:14px 18px;margin-bottom:6px;">'
                        f'<div style="font-size:1.05rem;font-weight:600;color:{TEXT_0};margin-bottom:3px;">{config["icon"]} {config["label"]}{impact_badge}</div>'
                        f'<div style="font-size:0.85rem;color:{TEXT_1};margin-bottom:4px;">{config["why"]}</div>'
                        f'<div style="font-size:0.82rem;color:{GOLD_DIM};margin-bottom:8px;font-style:italic;">{config["action"]}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    _STRATEGY_LABELS = {
                        ReviewType.NEGATIVE_IMPACT: "Dispute negative mark",
                        ReviewType.ACCOUNT_OWNERSHIP: "Challenge account ownership",
                        ReviewType.DUPLICATE_ACCOUNT: "Remove duplicate",
                        ReviewType.ACCURACY_VERIFICATION: "Correct inaccurate details",
                        ReviewType.UNVERIFIABLE_INFORMATION: "Request verification",
                    }

                    for rc in items:
                        acct_name = rc.entities.get('account_name', '') or rc.entities.get('creditor', '') or 'Unknown Account'
                        bureau = (rc.entities.get('bureau') or 'Unknown').title()
                        strategy_label = _STRATEGY_LABELS.get(rc.review_type, "Dispute item")

                        severity_label = ""
                        if hasattr(rc, 'impact_assessment') and rc.impact_assessment:
                            sev = rc.impact_assessment.severity
                            if sev == Severity.HIGH:
                                severity_label = f' <span style="color:{GOLD};font-weight:600;font-size:0.75rem;">&#x25cf; High Impact</span>'
                            elif sev == Severity.MODERATE:
                                severity_label = f' <span style="color:{TEXT_1};font-size:0.75rem;">&#x25cf; Moderate</span>'

                        why_text = rc.summary or ""
                        observations = []
                        if hasattr(rc, 'evidence_summary') and rc.evidence_summary:
                            observations = rc.evidence_summary.system_observations or []

                        why_detail = why_text
                        if observations:
                            obs_text = observations[0] if len(observations) == 1 else observations[0]
                            if obs_text and obs_text != why_text:
                                why_detail = obs_text

                        _bp_key_counter[rc.review_claim_id] = _bp_key_counter.get(rc.review_claim_id, 0) + 1
                        _bp_suffix = f"_{_bp_key_counter[rc.review_claim_id]}" if _bp_key_counter[rc.review_claim_id] > 1 else ""
                        checkbox_label = f"{acct_name} — {strategy_label} ({bureau})"
                        is_checked = st.checkbox(
                            checkbox_label,
                            value=st.session_state.battle_plan_items.get(rc.review_claim_id, True),
                            key=f"bp_{rc.review_claim_id}{_bp_suffix}",
                        )
                        st.session_state.battle_plan_items[rc.review_claim_id] = is_checked

                        if why_detail:
                            st.markdown(
                                f'<div style="font-size:0.82rem;color:{TEXT_1};margin:-10px 0 8px 28px;line-height:1.4;">'
                                f'{why_detail}{severity_label}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                        ai_claim_info = ai_per_claim_data.get(rc.review_claim_id)
                        if ai_claim_info and ai_claim_info.get('rationale'):
                            rank_badge = f'#{ai_claim_info["rank"]} ' if ai_claim_info.get('rank') else ''
                            score_badge = f' (score: {ai_claim_info["score"]})' if ai_claim_info.get('score') else ''
                            st.markdown(
                                f'<div style="font-size:0.80rem;color:{GOLD};margin:-4px 0 10px 28px;line-height:1.4;'
                                f'padding:4px 10px;background:rgba(212,160,23,0.06);border-left:2px solid {GOLD};border-radius:0 6px 6px 0;">'
                                f'<span style="font-weight:600;">{rank_badge}AI Insight{score_badge}:</span> '
                                f'{ai_claim_info["rationale"]}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        elif not ai_result and not has_ai_ent:
                            has_severity = hasattr(rc, 'impact_assessment') and rc.impact_assessment
                            if has_severity and rc.impact_assessment.severity in (Severity.HIGH, Severity.MODERATE):
                                st.markdown(
                                    f'<div style="font-size:0.78rem;color:{TEXT_1};margin:-4px 0 10px 28px;line-height:1.4;'
                                    f'padding:4px 10px;background:rgba(102,102,102,0.06);border-left:2px solid {BORDER};border-radius:0 6px 6px 0;'
                                    f'filter:blur(0px);opacity:0.7;">'
                                    f'<span style="font-weight:600;">&#x1f512; AI Insight:</span> '
                                    f'<span style="filter:blur(3px);user-select:none;">Priority ranking and legal strategy available for this item</span>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )

                selected_items = [rc for rc in eligible_items if st.session_state.battle_plan_items.get(rc.review_claim_id, True)]
                selected_count = len(selected_items)

                selected_bureaus = set()
                selected_per_bureau = {}
                for rc in selected_items:
                    b = (rc.entities.get('bureau') or 'unknown').lower()
                    selected_bureaus.add(b)
                    selected_per_bureau[b] = selected_per_bureau.get(b, 0) + 1
                selected_letter_count = len(selected_bureaus) if selected_bureaus else (1 if selected_items else 0)

                free_limit_exceeded = False
                free_exceeded_bureaus = []
                if using_free_mode:
                    for bureau_name, count in selected_per_bureau.items():
                        if count > auth.FREE_PER_BUREAU_LIMIT:
                            free_limit_exceeded = True
                            free_exceeded_bureaus.append((bureau_name, count))

                is_free_generation = (using_free_mode and not free_limit_exceeded and selected_count > 0)

                st.markdown(f"---")

                if free_limit_exceeded:
                    exceeded_details = ", ".join(
                        f"{b.title()} ({c} selected)" for b, c in free_exceeded_bureaus
                    )
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg, rgba(212,160,23,0.10), rgba(212,160,23,0.03));'
                        f'border:1px solid {GOLD};border-radius:10px;padding:12px 16px;margin-bottom:12px;text-align:center;">'
                        f'<div style="font-size:0.88rem;color:{TEXT_0};font-weight:600;margin-bottom:4px;">'
                        f'Free plan: {auth.FREE_PER_BUREAU_LIMIT} items per bureau</div>'
                        f'<div style="font-size:0.82rem;color:{TEXT_1};line-height:1.4;">'
                        f'You\'ve exceeded the limit for: {exceeded_details}. '
                        f'Uncheck items to stay within {auth.FREE_PER_BUREAU_LIMIT} per bureau, '
                        f'or upgrade to dispute everything at once.'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    render_purchase_options(context="disputes_letters", needed_letters=selected_letter_count)
                elif using_free_mode:
                    total_eligible = len(eligible_items)
                    max_free = auth.FREE_PER_BUREAU_LIMIT * len(all_bureaus) if all_bureaus else auth.FREE_PER_BUREAU_LIMIT
                    extra_items = total_eligible - min(total_eligible, max_free)
                    if extra_items > 0:
                        st.markdown(
                            f'<div style="background:linear-gradient(135deg, rgba(212,160,23,0.08), rgba(212,160,23,0.02));'
                            f'border:1px solid rgba(212,160,23,0.3);border-radius:10px;padding:12px 16px;margin-bottom:12px;text-align:center;">'
                            f'<div style="font-size:0.88rem;color:{TEXT_0};font-weight:600;margin-bottom:4px;">'
                            f'Free plan: up to {auth.FREE_PER_BUREAU_LIMIT} items per bureau</div>'
                            f'<div style="font-size:0.82rem;color:{TEXT_1};line-height:1.4;">'
                            f'You have <strong>{extra_items} more item{"s" if extra_items != 1 else ""}</strong> that could be disputed. '
                            f'Upgrade to dispute all your items with personalized letters for each one.'
                            f'</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                if selected_count == 0:
                    st.markdown(
                        f'<div style="text-align:center;color:{TEXT_1};padding:1rem;">No items selected. Check at least one item to generate letters.</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    bureau_names_display = ", ".join(sorted(b.title() for b in selected_bureaus)) if selected_bureaus else "the bureau"
                    free_tag = f' <span style="color:{GOLD};font-weight:600;">(free)</span>' if is_free_generation else ''
                    st.markdown(
                        f'<div style="background:{BG_1};border-radius:10px;padding:14px 18px;margin-bottom:12px;text-align:center;">'
                        f'<div style="font-size:0.95rem;color:{TEXT_0};font-weight:600;">'
                        f'{selected_count} item{"s" if selected_count != 1 else ""} &rarr; {selected_letter_count} dispute letter{"s" if selected_letter_count != 1 else ""}{free_tag}'
                        f'</div>'
                        f'<div style="font-size:0.82rem;color:{TEXT_1};margin-top:4px;">'
                        f'Letters will be sent to {bureau_names_display}. Bureaus have 30 days to respond.'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                is_free_round3 = (round_number >= 3 and db.check_free_round_eligible(current_user['user_id']))
                has_letter_ent = is_admin_user or is_free_generation or is_free_round3 or auth.has_entitlement(current_user['user_id'], 'letters', selected_letter_count)
                current_letter_balance = user_entitlements.get('letters', 0)

                if is_free_round3:
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg, rgba(102,187,106,0.12), rgba(102,187,106,0.03));'
                        f'border:1px solid #66BB6A;border-radius:10px;padding:14px 16px;margin-bottom:8px;">'
                        f'<div style="font-size:0.92rem;font-weight:700;color:#66BB6A;margin-bottom:4px;">'
                        f'&#x1f6e1;&#xfe0f; 2-Round Guarantee Active</div>'
                        f'<div style="font-size:0.84rem;color:{TEXT_0};line-height:1.5;">'
                        f'Nothing changed after 2 rounds — this Round 3 is on us. No charge for letters.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                if not has_letter_ent and selected_count > 0:
                    shortfall = selected_letter_count - current_letter_balance
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg, rgba(212,160,23,0.10), rgba(212,160,23,0.03));'
                        f'border:1px solid {GOLD};border-radius:10px;padding:14px 18px;margin-bottom:8px;text-align:center;">'
                        f'<div style="font-size:0.95rem;color:{TEXT_0};font-weight:700;margin-bottom:6px;">'
                        f'Your {selected_letter_count} dispute letter{"s are" if selected_letter_count != 1 else " is"} ready to generate</div>'
                        f'<div style="font-size:0.82rem;color:{TEXT_1};line-height:1.5;">'
                        f'Each letter is customized to {bureau_names_display} with <strong style="color:{GOLD};">your specific dispute items and legal basis</strong>. '
                        f'Bureaus are legally required to investigate within 30 days of receiving them.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    render_purchase_options(context="disputes_letters", needed_letters=selected_letter_count)

                if st.button("Generate My Dispute Letters", type="primary", use_container_width=True, key="battle_plan_generate_btn", disabled=(selected_count == 0 or not has_letter_ent or free_limit_exceeded)):
                    gen_id = hashlib.md5(f"{current_user['user_id']}_{round_number}_{selected_count}_{time.time()}".encode()).hexdigest()[:12]
                    st.session_state.selected_dispute_strategy = "battle_plan"
                    log_ux("DISPUTES", "GENERATE", "battle_plan_generate", 4)
                    st.session_state.system_error_message = None
                    st.session_state.current_approval = None
                    st.session_state._gen_selected_items = selected_items
                    st.session_state._gen_review_claims_list = review_claims_list
                    st.session_state._gen_round_number = round_number
                    st.session_state._gen_letter_count_to_deduct = selected_letter_count
                    st.session_state._gen_is_free = is_free_generation
                    st.session_state._gen_free_item_count = selected_count if is_free_generation else 0
                    st.session_state._gen_free_max_capacity = (auth.FREE_PER_BUREAU_LIMIT * len(all_bureaus)) if is_free_generation else 0
                    st.session_state._gen_id = gen_id
                    st.session_state._gen_completed = False
                    advance_card("GENERATING")
                    st.rerun()

elif st.session_state.ui_card == "GENERATING":
    if st.session_state.get('_gen_completed'):
        advance_card("DONE")
        st.rerun()

    selected_items_gen = st.session_state.get('_gen_selected_items', [])
    review_claims_list_gen = st.session_state.get('_gen_review_claims_list', [])
    round_number_gen = st.session_state.get('_gen_round_number', 1)

    st.markdown(f"""
    <style>
    @keyframes pen-write {{
        0% {{ transform: rotate(-5deg) translateY(0); }}
        25% {{ transform: rotate(2deg) translateY(-3px); }}
        50% {{ transform: rotate(-3deg) translateY(0); }}
        75% {{ transform: rotate(4deg) translateY(-2px); }}
        100% {{ transform: rotate(-5deg) translateY(0); }}
    }}
    @keyframes paper-stack {{
        0% {{ opacity: 0.4; transform: scale(0.9); }}
        50% {{ opacity: 0.7; transform: scale(0.95); }}
        100% {{ opacity: 1; transform: scale(1); }}
    }}
    @keyframes dot-pulse {{
        0%, 20% {{ opacity: 0.2; }}
        50% {{ opacity: 1; }}
        80%, 100% {{ opacity: 0.2; }}
    }}
    .gen-icon {{
        font-size: 3.5rem;
        animation: pen-write 1.2s ease-in-out infinite;
        display: inline-block;
    }}
    .gen-title {{
        font-size: 1.5rem;
        font-weight: 700;
        color: {TEXT_0};
        margin-top: 1rem;
    }}
    .gen-sub {{
        font-size: 1rem;
        color: {TEXT_1};
        max-width: 380px;
        line-height: 1.6;
        margin-top: 0.5rem;
    }}
    .gen-dots span {{
        animation: dot-pulse 1.4s ease-in-out infinite;
        font-size: 2rem;
        color: {GOLD};
        margin: 0 3px;
    }}
    .gen-dots span:nth-child(2) {{ animation-delay: 0.2s; }}
    .gen-dots span:nth-child(3) {{ animation-delay: 0.4s; }}
    </style>
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                min-height:55vh;text-align:center;padding:2rem 1rem;">
        <div class="gen-icon">&#x270D;&#xFE0F;</div>
        <div class="gen-title">Building your dispute letters</div>
        <div class="gen-sub">
            Crafting personalized letters with the right legal language for each bureau.
        </div>
        <div class="gen-dots" style="margin-top:1rem;">
            <span>&bull;</span><span>&bull;</span><span>&bull;</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    gen_error = False
    gen_error_msg = ""

    if selected_items_gen:
        included_rc_ids_gen = [rc.review_claim_id for rc in selected_items_gen]

        for rc_id in included_rc_ids_gen:
            st.session_state.review_claim_responses[rc_id] = "inaccurate"

        canonical_claims = []
        for snapshot_key_c, report_c in st.session_state.uploaded_reports.items():
            bureau_key_c = report_c.get('bureau', 'unknown').lower()
            identity_ok_c = st.session_state.identity_confirmed.get(bureau_key_c, False)
            bureau_rcs_c = [
                rc for rc in review_claims_list_gen
                if (rc.entities.get('bureau') or '').lower() == bureau_key_c
            ]
            for rc in bureau_rcs_c:
                response_c = st.session_state.review_claim_responses.get(rc.review_claim_id, "awaiting")
                canonical_c = _review_claim_to_canonical(rc, response_c, bureau_key_c, identity_ok_c)
                canonical_claims.append(canonical_c)

        canonical_inputs = {
            "identity_confirmed": any(st.session_state.identity_confirmed.values()),
        }

        decisions = []
        for cc in canonical_claims:
            bureau_code = cc.get("bureau", "")
            bureau_lower_map = {"EQ": "equifax", "EX": "experian", "TU": "transunion"}
            bureau_lower = bureau_lower_map.get(bureau_code, bureau_code.lower())
            per_claim_inputs = dict(canonical_inputs)
            per_claim_inputs["identity_confirmed"] = st.session_state.identity_confirmed.get(bureau_lower, False)
            decision = evaluate_claim_readiness(cc, per_claim_inputs)
            decisions.append(decision)

        for i, decision in enumerate(decisions):
            if decision.include_reason_code:
                cc = canonical_claims[i]
                if decision.include_reason_code == "USER_CONFIRMED_FACT" and cc.get("user_assertion_flags"):
                    continue
                chain = build_evidence_chain(cc, canonical_inputs)
                tier = decision.letter_language_tier
                if tier and not validate_evidence_chain(chain, tier):
                    mapping = BLOCKER_MAPPING["MISSING_REQUIRED_FIELDS"]
                    decisions[i] = Decision(
                        claim_id=decision.claim_id,
                        blocker_reason_code="MISSING_REQUIRED_FIELDS",
                        ui_label=mapping["ui_label"],
                        user_action=mapping["user_action"],
                        posture="NONE",
                    )

        st.session_state.readiness_decisions = decisions
        include_decisions = [d for d in decisions if d.include_reason_code]
        blocked_decisions = [d for d in decisions if d.blocker_reason_code]

        if include_decisions:
            letter_candidates = group_into_letters(include_decisions, canonical_claims)
            capacity_result = apply_capacity(letter_candidates, CAPACITY_LIMIT_V1)
            final_selected = capacity_result["selected"]

            st.session_state.letter_candidates = final_selected

            approved_letter_keys = [c.letter_key for c in final_selected]
            approved_claim_ids = []
            approved_postures = set()
            approved_targets = set()
            for c in final_selected:
                approved_claim_ids.extend(c.claims)
                approved_targets.add(c.letter_key[0])
            for d in include_decisions:
                if d.claim_id in approved_claim_ids:
                    approved_postures.add(d.posture)

            approval_obj = create_approval(
                user_id="session_user",
                capacity_limit=CAPACITY_LIMIT_V1,
                approved_letters=approved_letter_keys,
                approved_items=approved_claim_ids,
                approved_postures=list(approved_postures),
                approved_targets=list(approved_targets),
            )
            st.session_state.current_approval = approval_obj

            try:
                letters_generated = {}
                rc_map = {rc.review_claim_id: rc for rc in review_claims_list_gen}

                bureau_aggregated_claims = {}
                bureau_consumer_info = {}
                bureau_report_data = {}
                bureau_rc_details = {}

                for candidate in final_selected:
                    target_type, creditor_norm, bureau_code = candidate.letter_key
                    bureau_lower_map = {"EQ": "equifax", "EX": "experian", "TU": "transunion"}
                    bureau_lower = bureau_lower_map.get(bureau_code, bureau_code.lower())

                    matching_snapshot = next(
                        ((k, r) for k, r in st.session_state.uploaded_reports.items()
                         if r.get('bureau', '').lower() == bureau_lower),
                        (None, None)
                    )
                    snapshot_key_l, report_data = matching_snapshot
                    if not snapshot_key_l:
                        continue

                    bureau_claims_raw = st.session_state.extracted_claims.get(snapshot_key_l, [])

                    rc_claim_ids_in_letter = set()
                    for claim_id in candidate.claims:
                        rc_l = rc_map.get(claim_id)
                        if rc_l:
                            rc_claim_ids_in_letter.update(rc_l.supporting_claim_ids)
                            if bureau_lower not in bureau_rc_details:
                                bureau_rc_details[bureau_lower] = []
                            creditor_display = rc_l.entities.get('creditor') or rc_l.entities.get('account_name') or rc_l.entities.get('_extracted_creditor') or rc_l.entities.get('furnisher') or rc_l.entities.get('inquirer') or 'Unknown Account'
                            review_type_display = rc_l.review_type.value.replace('_', ' ').title() if hasattr(rc_l.review_type, 'value') else str(rc_l.review_type)
                            if not any(d['rc_id'] == claim_id for d in bureau_rc_details[bureau_lower]):
                                bureau_rc_details[bureau_lower].append({
                                    'rc_id': claim_id,
                                    'creditor': creditor_display,
                                    'review_type': review_type_display,
                                })

                    seen_ids = {c.claim_id for c in bureau_aggregated_claims.get(bureau_lower, [])}
                    for claim in bureau_claims_raw:
                        if claim.claim_id in rc_claim_ids_in_letter and claim.claim_id not in seen_ids:
                            if claim.state == ClaimState.AWAITING_CONSUMER_REVIEW:
                                response_l = st.session_state.review_claim_responses.get(
                                    next((rc_id for rc_id, rc_v in rc_map.items()
                                          if claim.claim_id in rc_v.supporting_claim_ids), ""),
                                    "awaiting"
                                )
                                if response_l == "inaccurate":
                                    claim.consumer_marks_inaccurate()
                                elif response_l == "unsure":
                                    claim.consumer_marks_unverifiable()
                            if claim.state in [ClaimState.CONSUMER_MARKED_INACCURATE, ClaimState.CONSUMER_MARKED_UNVERIFIABLE]:
                                claim.promote_to_legally_actionable()
                            if claim.state == ClaimState.LEGALLY_ACTIONABLE:
                                claim.fields['letter_eligible'] = True
                                if bureau_lower not in bureau_aggregated_claims:
                                    bureau_aggregated_claims[bureau_lower] = []
                                bureau_aggregated_claims[bureau_lower].append(claim)

                    if bureau_lower not in bureau_consumer_info:
                        bureau_consumer_info[bureau_lower] = (report_data or {}).get('parsed_data', {}).get('personal_info', {})
                    if bureau_lower not in bureau_report_data:
                        bureau_report_data[bureau_lower] = report_data

                if round_number_gen == 1:
                    bureau_round1_items = {}
                    for candidate in final_selected:
                        target_type, creditor_norm, bureau_code = candidate.letter_key
                        bureau_lower_r1 = {"EQ": "equifax", "EX": "experian", "TU": "transunion"}.get(bureau_code, bureau_code.lower())
                        for claim_id in candidate.claims:
                            rc_r1 = rc_map.get(claim_id)
                            if rc_r1:
                                if bureau_lower_r1 not in bureau_round1_items:
                                    bureau_round1_items[bureau_lower_r1] = []
                                rt_val = rc_r1.review_type.value if hasattr(rc_r1.review_type, 'value') else str(rc_r1.review_type)
                                ct_val = ''
                                merged_fields = {}
                                if rc_r1.supporting_claim_ids:
                                    snapshot_key_ct = next(
                                        (k for k, r in st.session_state.uploaded_reports.items()
                                         if r.get('bureau', '').lower() == bureau_lower_r1), None)
                                    if snapshot_key_ct:
                                        raw_claims_ct = st.session_state.extracted_claims.get(snapshot_key_ct, [])
                                        for rc_claim in raw_claims_ct:
                                            if rc_claim.claim_id in rc_r1.supporting_claim_ids:
                                                if not ct_val:
                                                    ct_val = rc_claim.claim_type.value if hasattr(rc_claim.claim_type, 'value') else str(rc_claim.claim_type)
                                                if hasattr(rc_claim, 'fields') and rc_claim.fields:
                                                    for fk, fv in rc_claim.fields.items():
                                                        if fv and fk not in merged_fields:
                                                            merged_fields[fk] = fv
                                bureau_round1_items[bureau_lower_r1].append({
                                    'entities': dict(rc_r1.entities) if rc_r1.entities else {},
                                    'fields': merged_fields,
                                    'claim_type': ct_val,
                                    'review_type': rt_val,
                                    'rc_id': claim_id,
                                })

                    for bureau_lower_r1, items_r1 in bureau_round1_items.items():
                        if not items_r1:
                            continue
                        consumer_info = bureau_consumer_info.get(bureau_lower_r1, {})
                        try:
                            letter_data = generate_round1_letter(bureau_lower_r1, consumer_info, items_r1)
                        except ValueError as ve:
                            print(f"[ROUND1_LETTER_ERROR] {ve}")
                            continue

                        letter_text = letter_data.get('letter_text', '')
                        if not forbidden_assertions_scan(letter_text):
                            continue

                        letter_data['rc_details'] = bureau_rc_details.get(bureau_lower_r1, [])
                        letters_generated[bureau_lower_r1] = letter_data

                        report_data = bureau_report_data.get(bureau_lower_r1)
                        report_id_val = (report_data or {}).get('report_id')
                        if report_id_val:
                            try:
                                uid = current_user.get('user_id')
                                db.save_letter(
                                    report_id_val,
                                    letter_data['letter_text'],
                                    bureau_lower_r1,
                                    letter_data.get('claim_count', 0),
                                    letter_data.get('categories', []),
                                    user_id=uid,
                                )
                            except Exception:
                                pass
                else:
                    for bureau_lower, actionable_claims in bureau_aggregated_claims.items():
                        if not actionable_claims:
                            continue

                        consumer_info = bureau_consumer_info.get(bureau_lower, {})

                        letter_data = generate_letter_from_claims(
                            actionable_claims, consumer_info, bureau_lower,
                        )

                        letter_text = letter_data.get('letter_text', '')
                        if not forbidden_assertions_scan(letter_text):
                            continue

                        letter_data['rc_details'] = bureau_rc_details.get(bureau_lower, [])
                        letters_generated[bureau_lower] = letter_data

                        report_data = bureau_report_data.get(bureau_lower)
                        report_id_val = (report_data or {}).get('report_id')
                        if report_id_val:
                            try:
                                uid = current_user.get('user_id')
                                db.save_letter(
                                    report_id_val,
                                    letter_data['letter_text'],
                                    bureau_lower,
                                    letter_data.get('claim_count', 0),
                                    letter_data.get('categories', []),
                                    user_id=uid,
                                )
                            except Exception:
                                pass

                if letters_generated:
                    is_free_gen = st.session_state.get('_gen_is_free', False)
                    free_item_count = st.session_state.get('_gen_free_item_count', 0)
                    free_max_cap = st.session_state.get('_gen_free_max_capacity', 0)
                    letter_deduct_count = min(
                        st.session_state.get('_gen_letter_count_to_deduct', len(letters_generated)),
                        len(letters_generated),
                    )
                    is_sprint_free_r3 = (round_number_gen >= 3 and db.check_free_round_eligible(current_user['user_id']))
                    if is_sprint_free_r3 and not is_admin_user:
                        db.use_free_round(current_user['user_id'])
                        db.log_activity(user_id, 'free_round3', 'Sprint guarantee Round 3 used', 'GENERATING')
                    elif is_free_gen and not is_admin_user:
                        if not auth.spend_free_letters(current_user['user_id'], free_item_count, max_capacity=free_max_cap if free_max_cap > 0 else None):
                            st.session_state._letter_spend_failed = True
                    elif not is_admin_user and letter_deduct_count > 0:
                        if auth.spend_entitlement(current_user['user_id'], 'letters', letter_deduct_count):
                            user_entitlements['letters'] = max(0, user_entitlements.get('letters', 0) - letter_deduct_count)
                        else:
                            st.session_state._letter_spend_failed = True

                    st.session_state.dispute_rounds.append({
                        'round_number': round_number_gen,
                        'claim_ids': included_rc_ids_gen,
                        'letters': list(letters_generated.keys()),
                        'source': 'battle_plan',
                    })
                    st.session_state.generated_letters.update(letters_generated)
                    st.session_state.selected_dispute_strategy = None
                    st.session_state._gen_letters_count = len(letters_generated)
                    st.session_state._gen_bureau_names = [b.title() for b in letters_generated.keys()]
                    st.session_state._gen_completed = True
                    db.log_activity(user_id, 'generate_letters', f"{len(letters_generated)} letter(s) for {', '.join(b.title() for b in letters_generated.keys())}", 'GENERATING')
                    advance_card("LETTERS_READY")
                    st.rerun()
                else:
                    gen_error = True
                    gen_error_msg = "no_letters"

            except Exception as e:
                gen_error = True
                gen_error_msg = "exception"
                print(f"[LETTER_GEN_ERROR] {type(e).__name__}: {str(e)}")
                print(f"[LETTER_GEN_TRACE] {traceback.format_exc()}")
        else:
            gen_error = True
            gen_error_msg = "blocked"

    if gen_error:
        if gen_error_msg == "exception":
            st.session_state.system_error_message = SYSTEM_ERROR_UI_STATE
            advance_card("DISPUTES")
            st.rerun()
        elif gen_error_msg == "no_letters":
            advance_card("DISPUTES")
            st.rerun()
        elif gen_error_msg == "blocked":
            advance_card("DISPUTES")
            st.rerun()

elif st.session_state.ui_card == "LETTERS_READY":
    letter_count = st.session_state.get('_gen_letters_count', 0)
    bureau_names_ready = st.session_state.get('_gen_bureau_names', [])
    bureau_display = " & ".join(bureau_names_ready) if bureau_names_ready else "the bureaus"

    st.markdown(f"""
    <style>
    @keyframes check-pop {{
        0% {{ opacity: 0; transform: scale(0.3) rotate(-20deg); }}
        50% {{ opacity: 1; transform: scale(1.15) rotate(5deg); }}
        70% {{ transform: scale(0.95) rotate(-2deg); }}
        100% {{ transform: scale(1) rotate(0); }}
    }}
    @keyframes confetti-fall {{
        0% {{ opacity: 0; transform: translateY(-20px); }}
        30% {{ opacity: 1; }}
        100% {{ opacity: 0.8; transform: translateY(0); }}
    }}
    @keyframes ready-text {{
        0% {{ opacity: 0; transform: translateY(15px); }}
        100% {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes ready-btn {{
        0% {{ opacity: 0; transform: translateY(10px); }}
        100% {{ opacity: 1; transform: translateY(0); }}
    }}
    .ready-check {{
        font-size: 4rem;
        animation: check-pop 0.8s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
    }}
    .ready-confetti {{
        font-size: 1.5rem;
        opacity: 0;
        animation: confetti-fall 0.6s ease-out 0.4s forwards;
    }}
    .ready-title {{
        font-size: 1.6rem;
        font-weight: 700;
        color: {TEXT_0};
        opacity: 0;
        animation: ready-text 0.6s ease-out 0.6s forwards;
    }}
    .ready-detail {{
        font-size: 1rem;
        color: {TEXT_1};
        max-width: 380px;
        line-height: 1.6;
        opacity: 0;
        animation: ready-text 0.6s ease-out 0.9s forwards;
    }}
    .ready-stat {{
        display: inline-block;
        background: {BG_1};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 12px 20px;
        margin: 6px;
        opacity: 0;
        animation: ready-text 0.5s ease-out 1.1s forwards;
    }}
    .ready-stat-num {{
        font-size: 1.8rem;
        font-weight: 800;
        color: {GOLD};
    }}
    .ready-stat-label {{
        font-size: 0.8rem;
        color: {TEXT_1};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    .ready-btn-wrap {{
        opacity: 0;
        animation: ready-btn 0.5s ease-out 1.4s forwards;
    }}
    </style>
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                min-height:55vh;text-align:center;padding:2rem 1rem;">
        <div class="ready-confetti">&#x1f389;</div>
        <div class="ready-check">&#x2705;</div>
        <div class="ready-title" style="margin-top:1rem;">
            Your letters are ready!
        </div>
        <div class="ready-detail" style="margin-top:0.75rem;">
            We built {letter_count} dispute letter{"s" if letter_count != 1 else ""} tailored to {bureau_display} with the right legal citations and evidence.
        </div>
        <div style="margin-top:1.2rem;">
            <div class="ready-stat">
                <div class="ready-stat-num">{letter_count}</div>
                <div class="ready-stat-label">Letter{"s" if letter_count != 1 else ""} Created</div>
            </div>
            <div class="ready-stat">
                <div class="ready-stat-num">{len(bureau_names_ready)}</div>
                <div class="ready-stat-label">Bureau{"s" if len(bureau_names_ready) != 1 else ""} Targeted</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="ready-btn-wrap">', unsafe_allow_html=True)
    if st.button("View My Letters", type="primary", use_container_width=True, key="letters_ready_continue_btn"):
        advance_card("DONE")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.ui_card == "DONE":
    if st.session_state.uploaded_reports:
        if st.button("← Back to Dispute Plan", key="done_back_disputes"):
            st.session_state.manual_nav_back = True
            advance_card("DISPUTES")
            st.rerun()

    if st.session_state.pop('_letter_spend_failed', False):
        st.warning("Your letters were generated, but we couldn't deduct the credits. Your balance may not reflect this usage — please contact support if it persists.")

    has_letters = bool(st.session_state.generated_letters)

    CATEGORY_DISPLAY = {
        'balance_reported': 'Balance Reported',
        'payment_history': 'Payment History',
        'account_status': 'Account Status',
        'date_opened': 'Date Opened',
        'date_closed': 'Date Closed',
        'credit_limit': 'Credit Limit',
        'high_balance': 'High Balance',
        'personal_info': 'Personal Information',
        'public_record': 'Public Record',
        'inquiry': 'Inquiry',
        'collection': 'Collection',
        'late_payment': 'Late Payment',
        'charge_off': 'Charge-Off',
        'repossession': 'Repossession',
        'foreclosure': 'Foreclosure',
        'bankruptcy': 'Bankruptcy',
        'account_ownership': 'Account Ownership',
        'payment_amount': 'Payment Amount',
        'terms': 'Account Terms',
        'remarks': 'Remarks / Comments',
    }

    def humanize_category(cat):
        if cat in CATEGORY_DISPLAY:
            return CATEGORY_DISPLAY[cat]
        return cat.replace('_', ' ').title()

    if has_letters:
        letters = st.session_state.generated_letters
        letter_count_done = len(letters)
        bureau_names_done = [k.title() for k in letters.keys() if k != 'unknown']
        total_claims_done = sum(ld.get('claim_count', 0) for ld in letters.values())
        round_number_done = st.session_state.get('dispute_round_number', 1)

        st.markdown(
            f'<div style="text-align:center;padding:1.25rem 0 0.75rem 0;">'
            f'<div style="font-size:2.2rem;margin-bottom:6px;">&#x1f4e8;</div>'
            f'<div class="card-title" style="text-align:center;">Round {round_number_done} — {letter_count_done} Letter{"s" if letter_count_done != 1 else ""} Ready to Send</div>'
            f'<div class="card-body-copy" style="text-align:center;max-width:480px;margin:0 auto;">'
            f'You\'re disputing {total_claims_done} item{"s" if total_claims_done != 1 else ""} across '
            f'{" & ".join(bureau_names_done) if bureau_names_done else "your bureaus"}. '
            f'Every letter is backed by the right legal citations.'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown(f"""
        <div style="display:flex;gap:0;margin:1rem 0 1.5rem 0;border:1px solid {BORDER};border-radius:14px;overflow:hidden;background:{BG_1};">
            <div style="flex:1;text-align:center;padding:14px 8px;border-right:1px solid {BORDER};">
                <div style="font-size:1.3rem;margin-bottom:2px;">&#x2709;&#xFE0F;</div>
                <div style="font-size:0.7rem;font-weight:700;color:{GOLD};text-transform:uppercase;letter-spacing:0.04em;">Step 1</div>
                <div style="font-size:0.8rem;color:{TEXT_1};margin-top:2px;">Send letters</div>
            </div>
            <div style="flex:1;text-align:center;padding:14px 8px;border-right:1px solid {BORDER};">
                <div style="font-size:1.3rem;margin-bottom:2px;">&#x23F3;</div>
                <div style="font-size:0.7rem;font-weight:700;color:{TEXT_1};text-transform:uppercase;letter-spacing:0.04em;">Step 2</div>
                <div style="font-size:0.8rem;color:{TEXT_1};margin-top:2px;">Wait 30 days</div>
            </div>
            <div style="flex:1;text-align:center;padding:14px 8px;border-right:1px solid {BORDER};">
                <div style="font-size:1.3rem;margin-bottom:2px;">&#x1f4cb;</div>
                <div style="font-size:0.7rem;font-weight:700;color:{TEXT_1};text-transform:uppercase;letter-spacing:0.04em;">Step 3</div>
                <div style="font-size:0.8rem;color:{TEXT_1};margin-top:2px;">Check results</div>
            </div>
            <div style="flex:1;text-align:center;padding:14px 8px;">
                <div style="font-size:1.3rem;margin-bottom:2px;">&#x1f504;</div>
                <div style="font-size:0.7rem;font-weight:700;color:{TEXT_1};text-transform:uppercase;letter-spacing:0.04em;">Step 4</div>
                <div style="font-size:0.8rem;color:{TEXT_1};margin-top:2px;">Dispute again</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="font-size:1.1rem;font-weight:700;color:{TEXT_0};margin-bottom:4px;">
            Your Dispute Letters
        </div>
        <div style="font-size:0.84rem;color:{TEXT_1};margin-bottom:14px;line-height:1.4;">
            Expand each letter below to <strong style="color:{GOLD};">review and edit</strong> before downloading.
            Add personal details or adjust wording to make each letter your own.
        </div>
        """, unsafe_allow_html=True)

        if 'letter_edits' not in st.session_state:
            st.session_state.letter_edits = {}

        for bureau_key_l, letter_data in letters.items():
            bureau_title = bureau_key_l.title() if bureau_key_l != 'unknown' else 'Credit Bureau'
            categories = letter_data.get('categories', [])
            claim_count = letter_data.get('claim_count', 0)

            human_cats = [humanize_category(c) for c in categories[:6]]
            cat_summary = ", ".join(human_cats) if human_cats else ""
            expander_label = f"{bureau_title} — {claim_count} disputed item{'s' if claim_count != 1 else ''}"

            with st.expander(expander_label, expanded=(letter_count_done == 1)):
                if cat_summary:
                    st.markdown(
                        f'<div style="font-size:0.82rem;font-weight:600;color:{TEXT_0};margin-bottom:4px;">Dispute categories:</div>'
                        f'<div style="font-size:0.85rem;color:{TEXT_1};margin-bottom:10px;">{cat_summary}</div>',
                        unsafe_allow_html=True,
                    )

                rc_details = letter_data.get('rc_details', [])
                if rc_details:
                    st.markdown(
                        f'<div style="font-size:0.82rem;font-weight:600;color:{TEXT_0};margin-bottom:6px;">Accounts in this letter:</div>',
                        unsafe_allow_html=True,
                    )
                    if 'letter_removed_rcs' not in st.session_state:
                        st.session_state.letter_removed_rcs = {}
                    removed_set = st.session_state.letter_removed_rcs.get(bureau_key_l, set())
                    for rc_detail in rc_details:
                        rc_id_d = rc_detail['rc_id']
                        creditor_d = rc_detail['creditor']
                        rtype_d = rc_detail['review_type']
                        is_removed = rc_id_d in removed_set
                        acct_col, btn_col = st.columns([5, 1])
                        with acct_col:
                            style_extra = f"text-decoration:line-through;opacity:0.5;" if is_removed else ""
                            st.markdown(
                                f'<div style="font-size:0.82rem;color:{TEXT_1};padding:4px 0;{style_extra}">'
                                f'{creditor_d} <span style="color:{TEXT_1};opacity:0.6;">— {rtype_d}</span></div>',
                                unsafe_allow_html=True,
                            )
                        with btn_col:
                            if not is_removed:
                                if st.button("Remove", key=f"rm_{bureau_key_l}_{rc_id_d}", type="secondary"):
                                    if bureau_key_l not in st.session_state.letter_removed_rcs:
                                        st.session_state.letter_removed_rcs[bureau_key_l] = set()
                                    st.session_state.letter_removed_rcs[bureau_key_l].add(rc_id_d)
                                    st.rerun()
                            else:
                                if st.button("Undo", key=f"undo_{bureau_key_l}_{rc_id_d}", type="secondary"):
                                    st.session_state.letter_removed_rcs[bureau_key_l].discard(rc_id_d)
                                    st.rerun()

                    any_removed = any(len(v) > 0 for v in st.session_state.letter_removed_rcs.values())
                    if any_removed:
                        total_removed = sum(len(v) for v in st.session_state.letter_removed_rcs.values())
                        st.markdown(
                            f'<div style="background:rgba(212,160,23,0.08);border:1px solid {GOLD};border-radius:8px;'
                            f'padding:10px 14px;margin:8px 0;font-size:0.84rem;color:{TEXT_0};">'
                            f'{total_removed} account{"s" if total_removed != 1 else ""} marked for removal. '
                            f'Click below to rebuild your letters without them.</div>',
                            unsafe_allow_html=True,
                        )
                        if st.button("Regenerate Letters", key=f"regen_{bureau_key_l}", type="primary", use_container_width=True):
                            for b_key, removed_ids in st.session_state.letter_removed_rcs.items():
                                for removed_rc_id in removed_ids:
                                    st.session_state.battle_plan_items[removed_rc_id] = False
                            st.session_state.letter_removed_rcs = {}
                            st.session_state.generated_letters = {}
                            st.session_state.selected_dispute_strategy = "battle_plan"
                            selected_items_regen = []
                            review_claims_regen = st.session_state.get('review_claims', [])
                            for rc in review_claims_regen:
                                if st.session_state.battle_plan_items.get(rc.review_claim_id, False):
                                    selected_items_regen.append(rc)
                            st.session_state._gen_selected_items = selected_items_regen
                            st.session_state._gen_review_claims_list = review_claims_regen
                            st.session_state._gen_round_number = st.session_state.get('dispute_round_number', 1)
                            st.session_state._gen_letter_count_to_deduct = 0
                            if not st.session_state.dispute_rounds:
                                pass
                            elif st.session_state.dispute_rounds[-1].get('source') == 'battle_plan':
                                st.session_state.dispute_rounds.pop()
                            advance_card("GENERATING")
                            st.rerun()

                    st.markdown(f'<div style="margin-top:6px;"></div>', unsafe_allow_html=True)

                letter_text_original = letter_data['letter_text']

                if 'letter_edits' not in st.session_state:
                    st.session_state.letter_edits = {}
                if bureau_key_l not in st.session_state.letter_edits:
                    st.session_state.letter_edits[bureau_key_l] = letter_text_original

                edit_key = f"edit_area_{bureau_key_l}"
                edited_text = st.text_area(
                    "Edit your letter below:",
                    value=st.session_state.letter_edits[bureau_key_l],
                    height=320,
                    key=edit_key,
                    label_visibility="collapsed",
                )

                st.session_state.letter_edits[bureau_key_l] = edited_text
                is_edited = edited_text != letter_text_original

                reset_col, status_col = st.columns([1, 3])
                with reset_col:
                    if is_edited:
                        if st.button("Reset to Original", key=f"reset_{bureau_key_l}", use_container_width=True):
                            st.session_state.letter_edits[bureau_key_l] = letter_text_original
                            st.rerun()
                with status_col:
                    if is_edited:
                        st.markdown(
                            f'<div style="font-size:0.78rem;color:{GOLD};padding-top:8px;">Edited — downloads will include your changes</div>',
                            unsafe_allow_html=True,
                        )

                letter_text_final = edited_text
                filename = format_letter_filename(bureau_key_l)
                pdf_bytes = generate_letter_pdf(letter_text_final)

                dl_col1, dl_col2 = st.columns(2)
                with dl_col1:
                    st.download_button(
                        "Download PDF",
                        data=pdf_bytes,
                        file_name=f"{filename}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"pdf_{bureau_key_l}",
                        type="primary",
                    )
                with dl_col2:
                    st.download_button(
                        "Download Text",
                        data=letter_text_final,
                        file_name=f"{filename}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key=f"txt_{bureau_key_l}",
                    )

        if len(letters) > 1:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for bureau_zip, letter_data_zip in letters.items():
                    filename_zip = format_letter_filename(bureau_zip)
                    zip_text = st.session_state.letter_edits.get(bureau_zip, letter_data_zip['letter_text'])
                    zip_file.writestr(f"{filename_zip}.txt", zip_text)
                    zip_file.writestr(f"{filename_zip}.pdf", generate_letter_pdf(zip_text))
            zip_bytes = zip_buffer.getvalue()
            any_edited = any(
                st.session_state.letter_edits.get(b, ld['letter_text']) != ld['letter_text']
                for b, ld in letters.items()
            )
            dl_label = f"Download All {letter_count_done} Letters (ZIP)"
            if any_edited:
                dl_label = f"Download All {letter_count_done} Letters with Edits (ZIP)"
            st.download_button(
                dl_label,
                data=zip_bytes,
                file_name=f"dispute_letters_{datetime.now().strftime('%Y%m%d')}.zip",
                mime="application/zip",
                use_container_width=True,
                key="download_all_zip",
                type="primary",
            )

        _upgrade_user_has_mail = auth.has_entitlement(current_user['user_id'], 'mailings') or is_admin_user
        if not _upgrade_user_has_mail:
            _bureau_count = len([k for k in letters.keys() if k != 'unknown'])
            _diy_per_letter = 5.50
            _diy_total = _diy_per_letter * max(_bureau_count, 1)
            _full_round_price = auth.PACKS.get('full_round', {}).get('price_cents', 2499) / 100

            _letter_word = f"{letter_count_done} dispute letters are" if letter_count_done != 1 else f"{letter_count_done} dispute letter is"
            _upgrade_html = f"""<div style="background:linear-gradient(135deg, rgba(212,160,23,0.12) 0%, rgba(212,160,23,0.03) 100%);border:2px solid {GOLD};border-radius:16px;padding:24px 22px;margin:0;">
<div style="text-align:center;margin-bottom:16px;">
<div style="font-size:1.4rem;margin-bottom:4px;">&#x26A0;&#xFE0F;</div>
<div style="font-size:1.15rem;font-weight:800;color:{TEXT_0};line-height:1.3;">Don&#39;t Risk Mailing These Incorrectly</div>
<div style="font-size:0.84rem;color:{TEXT_1};margin-top:6px;line-height:1.5;">Your {_letter_word} ready &#8212; but the 30-day investigation clock <strong style="color:{GOLD};">doesn&#39;t start</strong> until bureaus receive them via certified mail.</div>
</div>
<div style="display:flex;gap:12px;margin-bottom:18px;flex-wrap:wrap;">
<div style="flex:1;min-width:200px;background:{BG_0};border:1px solid #E57373;border-radius:12px;padding:14px 12px;">
<div style="font-size:0.76rem;font-weight:700;color:#E57373;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:8px;">Do It Yourself</div>
<div style="font-size:0.82rem;color:{TEXT_1};line-height:1.7;">&#x274C; Print all letters<br/>&#x274C; Sign each one<br/>&#x274C; Find bureau addresses<br/>&#x274C; Drive to USPS<br/>&#x274C; Pay ~${_diy_per_letter:.2f}/letter certified<br/>&#x274C; Track each mailing yourself</div>
<div style="margin-top:10px;padding:8px;background:rgba(229,115,115,0.08);border-radius:8px;text-align:center;">
<span style="font-size:0.82rem;color:#E57373;font-weight:700;">~${_diy_total:.2f} + your time</span>
</div>
</div>
<div style="flex:1;min-width:200px;background:{BG_0};border:2px solid {GOLD};border-radius:12px;padding:14px 12px;">
<div style="font-size:0.76rem;font-weight:700;color:{GOLD};text-transform:uppercase;letter-spacing:0.04em;margin-bottom:8px;">Full Round</div>
<div style="font-size:0.82rem;color:{TEXT_1};line-height:1.7;">&#x2705; We print &#38; format<br/>&#x2705; Certified Mail with proof<br/>&#x2705; Correct bureau addresses<br/>&#x2705; Tracking in your dashboard<br/>&#x2705; Legal proof of delivery<br/>&#x2705; 30-day clock starts for you</div>
<div style="margin-top:10px;padding:8px;background:rgba(212,160,23,0.08);border-radius:8px;text-align:center;">
<span style="font-size:1.05rem;color:{GOLD};font-weight:800;">${_full_round_price:.2f}</span>
<span style="font-size:0.76rem;color:{TEXT_1};"> total</span>
</div>
</div>
</div>
</div>"""
            st.html(_upgrade_html)

            _fr_pack = auth.PACKS.get('full_round', {})
            if st.button("Upgrade to Full Round — We Handle Everything", key="upgrade_full_round_post_download", type="primary", use_container_width=True):
                result = create_checkout_session(
                    current_user['user_id'], current_user.get('email', ''),
                    'full_round', _fr_pack.get('label', 'Full Round'), _fr_pack.get('price_cents', 2499),
                    ai_rounds=_fr_pack.get('ai_rounds', 1), letters=_fr_pack.get('letters', 3), mailings=_fr_pack.get('mailings', 3),
                )
                if result.get('url'):
                    _open_checkout(result['url'])
                else:
                    st.error(f"Payment error: {result.get('error', 'Unknown')}")

        st.markdown(f"""
        <div style="background:{BG_1};border:1px solid {BORDER};border-radius:12px;
                    padding:14px 18px;margin:1.25rem 0 0.75rem 0;">
            <div style="font-size:0.88rem;color:{TEXT_0};font-weight:600;margin-bottom:6px;">
                &#x1f4ec; Mailing tips
            </div>
            <div style="font-size:0.84rem;color:{TEXT_1};line-height:1.6;">
                <strong>Best method:</strong> USPS Certified Mail with Return Receipt. This gives you a tracking number
                and legal proof that the bureau received your dispute, which starts the 30-day investigation clock
                under FCRA &sect; 611.<br/>
                <strong>Where to send:</strong> Each letter already includes the correct bureau mailing address.
                Print, sign, and mail each letter to the bureau listed at the top.
            </div>
        </div>
        """, unsafe_allow_html=True)

        has_mail_ent = auth.has_entitlement(current_user['user_id'], 'mailings') or is_admin_user
        if has_mail_ent and lob_client.is_configured():
            if 'lob_return_address' not in st.session_state:
                st.session_state.lob_return_address = {}
            if 'lob_send_results' not in st.session_state:
                st.session_state.lob_send_results = {}

            test_mode = lob_client.is_test_mode()
            if test_mode:
                st.markdown(
                    '<div class="lab-banner"><div class="lab-banner-title">Test Mode</div>'
                    '<div class="lab-banner-body">Lob is running in test mode. No real mail will be sent.</div></div>',
                    unsafe_allow_html=True,
                )

            st.markdown(
                f'<div style="background:linear-gradient(135deg, {BG_1} 0%, rgba(212,160,23,0.08) 100%);'
                f'border:2px solid {GOLD};border-radius:14px;padding:18px 20px;margin-bottom:1rem;">'
                f'<div style="font-size:1.05rem;font-weight:700;color:{GOLD};margin-bottom:6px;">'
                f'&#x2709;&#xFE0F; Send via Certified Mail</div>'
                f'<div style="font-size:0.86rem;color:{TEXT_1};line-height:1.5;margin-bottom:10px;">'
                f'Skip the post office. We\'ll print, certify, and mail your letters for you — '
                f'with tracking and legal proof of delivery.</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            saved_addr = st.session_state.lob_return_address
            addr_name = st.text_input("Your Full Name (return address)", value=saved_addr.get('name', current_user.get('display_name', '')), key="lob_addr_name")
            addr_line1 = st.text_input("Street Address", value=saved_addr.get('address_line1', ''), key="lob_addr_line1")
            addr_line2 = st.text_input("Apt / Suite / Unit (optional)", value=saved_addr.get('address_line2', ''), key="lob_addr_line2")

            addr_col1, addr_col2, addr_col3 = st.columns([2, 1, 1])
            with addr_col1:
                addr_city = st.text_input("City", value=saved_addr.get('address_city', ''), key="lob_addr_city")
            with addr_col2:
                state_idx = 0
                saved_state = saved_addr.get('address_state', '')
                if saved_state and saved_state.upper() in lob_client.US_STATES:
                    state_idx = lob_client.US_STATES.index(saved_state.upper())
                addr_state = st.selectbox("State", options=lob_client.US_STATES, index=state_idx, key="lob_addr_state")
            with addr_col3:
                addr_zip = st.text_input("ZIP Code", value=saved_addr.get('address_zip', ''), key="lob_addr_zip")

            return_receipt = st.checkbox("Include Return Receipt (signature confirmation)", value=True, key="lob_return_receipt")
            cost_info = lob_client.estimate_cost(return_receipt=return_receipt)
            st.caption(f"Estimated cost per letter: **{cost_info['total_display']}** ({cost_info['breakdown']})")

            from_addr = {
                'name': addr_name,
                'address_line1': addr_line1,
                'address_line2': addr_line2,
                'address_city': addr_city,
                'address_state': addr_state,
                'address_zip': addr_zip,
            }

            addr_valid = lob_client.validate_address(from_addr)

            st.markdown("---")
            st.markdown(
                f'<div style="font-size:0.95rem;font-weight:600;color:{TEXT_0};margin-bottom:4px;">'
                f'Proof of Identity &amp; Address</div>'
                f'<div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:10px;">'
                f'Bureaus require a copy of your government-issued ID and a recent proof of address '
                f'(utility bill, bank statement, etc.) with every dispute. Upload them here and '
                f'they\'ll be included automatically with each letter.</div>',
                unsafe_allow_html=True,
            )
            id_col, addr_col = st.columns(2)
            with id_col:
                id_file = st.file_uploader(
                    "Government-Issued ID",
                    type=["png", "jpg", "jpeg", "pdf"],
                    key="lob_id_upload",
                    help="Driver's license, passport, or state ID",
                )
            with addr_col:
                addr_proof_file = st.file_uploader(
                    "Proof of Address",
                    type=["png", "jpg", "jpeg", "pdf"],
                    key="lob_addr_proof_upload",
                    help="Utility bill, bank statement, or insurance statement",
                )
            max_size = 5 * 1024 * 1024
            size_error = False
            if id_file and len(id_file.getvalue()) > max_size:
                st.error("ID file is too large. Please upload a file under 5 MB.")
                size_error = True
            if addr_proof_file and len(addr_proof_file.getvalue()) > max_size:
                st.error("Address proof file is too large. Please upload a file under 5 MB.")
                size_error = True
            if not id_file or not addr_proof_file:
                st.warning("Both proof of ID and proof of address are required to send certified mail.")

            if st.session_state.lob_send_results:
                for bk, res in st.session_state.lob_send_results.items():
                    if res.get('success'):
                        tracking_url = lob_client.get_tracking_url(res.get('tracking_number', ''))
                        st.success(
                            f"Letter to **{bk.title()}** sent successfully! "
                            f"Tracking: {res.get('tracking_number', 'N/A')} "
                            f"| Expected delivery: {res.get('expected_delivery', 'N/A')}"
                        )
                        if tracking_url:
                            st.markdown(f"[Track on USPS]({tracking_url})")
                    elif res.get('error'):
                        st.error(f"Failed to send to {bk.title()}: {res['error']}")

            for bureau_key_send, letter_data_send in letters.items():
                bureau_title_send = bureau_key_send.title() if bureau_key_send != 'unknown' else 'Credit Bureau'

                already_sent = bureau_key_send in st.session_state.lob_send_results and st.session_state.lob_send_results[bureau_key_send].get('success')
                current_report_id = st.session_state.get('current_report', {}).get('id') if st.session_state.get('current_report') else None
                already_in_db = db.has_been_sent_via_lob(
                    current_user.get('user_id'),
                    bureau_key_send,
                    report_id=current_report_id
                )

                if already_sent or already_in_db:
                    st.markdown(
                        f'<div style="background:{BG_1};border:1px solid {BORDER};border-left:4px solid {GOLD};'
                        f'border-radius:10px;padding:10px 14px;margin-bottom:8px;">'
                        f'<strong>{bureau_title_send}</strong> &mdash; &#x2705; Sent via certified mail'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    send_key = f"send_lob_{bureau_key_send}"
                    docs_ready = id_file is not None and addr_proof_file is not None and not size_error
                    if st.button(
                        f"Send to {bureau_title_send} ({cost_info['total_display']})",
                        key=send_key,
                        use_container_width=True,
                        type="primary",
                        disabled=not docs_ready,
                    ):
                        if not addr_valid['valid']:
                            st.error(f"Please fix your return address: {addr_valid['error']}")
                        elif not is_admin_user and not auth.spend_entitlement(current_user['user_id'], 'mailings', 1):
                            st.error("You don't have any mailing entitlements remaining. Purchase more to send certified mail.")
                        else:
                            st.session_state.lob_return_address = from_addr

                            attachments = []
                            if id_file is not None:
                                attachments.append({"name": "Government-Issued ID", "data": id_file.getvalue(), "type": id_file.type or "image/png"})
                            if addr_proof_file is not None:
                                attachments.append({"name": "Proof of Address", "data": addr_proof_file.getvalue(), "type": addr_proof_file.type or "image/png"})

                            with st.spinner(f"Sending certified letter to {bureau_title_send}..."):
                                result = lob_client.create_certified_letter(
                                    from_address=from_addr,
                                    to_bureau=bureau_key_send,
                                    letter_text=letter_data_send['letter_text'],
                                    return_receipt=return_receipt,
                                    description=f"850 Lab dispute - {bureau_title_send}",
                                    attachments=attachments,
                                )

                            st.session_state.lob_send_results[bureau_key_send] = result

                            if result.get('success'):
                                db.log_activity(user_id, 'mail_sent', f"Certified mail to {bureau_title_send}", 'DONE')
                                report_id = None
                                if st.session_state.get('current_report'):
                                    report_id = st.session_state.current_report.get('id')

                                db.save_lob_send(
                                    user_id=current_user.get('user_id'),
                                    report_id=report_id,
                                    bureau=bureau_key_send,
                                    lob_id=result.get('lob_id', ''),
                                    tracking_number=result.get('tracking_number', ''),
                                    status='mailed',
                                    from_address=from_addr,
                                    to_address=lob_client.get_bureau_address(bureau_key_send) or {},
                                    cost_cents=cost_info['total_cents'],
                                    return_receipt=return_receipt,
                                    is_test=result.get('is_test', False),
                                    expected_delivery=result.get('expected_delivery', ''),
                                )

                            st.rerun()

        elif not has_mail_ent:
            st.markdown(
                f'<div style="background:linear-gradient(135deg, {BG_1} 0%, rgba(212,160,23,0.06) 100%);'
                f'border:2px solid {GOLD};border-radius:14px;padding:20px;margin:0.75rem 0 0.5rem 0;">'
                f'<div style="font-size:1.1rem;font-weight:700;color:{GOLD};margin-bottom:6px;text-align:center;">'
                f'&#x2709;&#xFE0F; Skip the Post Office</div>'
                f'<div style="font-size:0.88rem;color:{TEXT_1};line-height:1.6;text-align:center;margin-bottom:12px;">'
                f'Send your dispute letters as USPS Certified Mail directly from 850 Lab. '
                f'You get a tracking number and legal proof of delivery — starting the 30-day clock.</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            render_purchase_options(context="done_mail", needed_mailings=1)

        elif not lob_client.is_configured():
            st.markdown(
                f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;'
                f'padding:12px 16px;margin:0.5rem 0;">'
                f'<div style="font-size:0.86rem;color:{TEXT_1};line-height:1.5;">'
                f'&#x2709;&#xFE0F; <strong>Certified mail coming soon.</strong> '
                f'In the meantime, download your letters and mail them yourself via USPS Certified Mail '
                f'for tracking and legal proof of delivery.</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        user_id_dash = current_user['user_id']
        user_tier = auth.get_user_tier(user_id_dash) if not is_admin_user else 'deletion_sprint'
        tier_rank = auth.TIER_HIERARCHY.get(user_tier, 0)
        tier_label = auth.TIER_LABELS.get(user_tier, 'Free')

        tier_colors = {
            'free': (TEXT_1, BG_1, BORDER),
            'digital_only': (GOLD, 'rgba(212,160,23,0.06)', GOLD),
            'full_round': ('#66BB6A', 'rgba(102,187,106,0.06)', '#66BB6A'),
            'deletion_sprint': ('#7E57C2', 'rgba(126,87,194,0.06)', '#7E57C2'),
        }
        t_color, t_bg, t_border = tier_colors.get(user_tier, tier_colors['free'])

        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">'
            f'<div style="font-size:1.15rem;font-weight:700;color:{TEXT_0};">Your 30-Day Dashboard</div>'
            f'<div style="background:{t_bg};border:1px solid {t_border};border-radius:20px;'
            f'padding:3px 14px;font-size:0.78rem;font-weight:700;color:{t_color};">{tier_label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        tracker = db.get_dispute_tracker(user_id_dash, round_number_done)
        lob_sends = db.get_lob_sends_for_user(user_id_dash)
        round_lob_sends = [s for s in lob_sends if s.get('status') == 'mailed']

        if not tracker and round_lob_sends:
            earliest = min(s['created_at'] for s in round_lob_sends)
            db.save_dispute_tracker(user_id_dash, round_number_done, earliest, 'certified_mail')
            tracker = db.get_dispute_tracker(user_id_dash, round_number_done)

        if tracker and tracker.get('mailed_at'):
            from datetime import timedelta
            mailed_dt = tracker['mailed_at']
            deadline = mailed_dt + timedelta(days=30)
            now = datetime.now()
            days_elapsed = (now - mailed_dt).days
            days_remaining = max(0, 30 - days_elapsed)
            pct = min(100, int(days_elapsed / 30 * 100))

            if days_remaining > 0:
                status_label = f"{days_remaining} day{'s' if days_remaining != 1 else ''} remaining"
                status_color = GOLD if days_remaining > 7 else "#E57373"
            else:
                status_label = "30-day window complete — time to check results"
                status_color = "#66BB6A"

            st.markdown(f"""
            <div style="background:{BG_1};border:1px solid {BORDER};border-radius:14px;padding:18px 20px;margin-bottom:16px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <div style="font-size:0.92rem;font-weight:600;color:{TEXT_0};">Investigation Window</div>
                    <div style="font-size:0.88rem;font-weight:700;color:{status_color};">{status_label}</div>
                </div>
                <div style="background:{BG_0};border-radius:8px;height:10px;overflow:hidden;">
                    <div style="width:{pct}%;height:100%;background:linear-gradient(90deg, {GOLD}, {status_color});border-radius:8px;transition:width 0.3s ease;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;margin-top:8px;">
                    <div style="font-size:0.78rem;color:{TEXT_1};">Mailed: {mailed_dt.strftime('%b %d, %Y')}</div>
                    <div style="font-size:0.78rem;color:{TEXT_1};">Deadline: {deadline.strftime('%b %d, %Y')}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:rgba(229,115,115,0.06);border:1px solid #E57373;border-radius:14px;padding:18px 20px;margin-bottom:16px;">
                <div style="font-size:0.92rem;font-weight:700;color:#E57373;margin-bottom:6px;">
                    &#x23F0; Your 30-day clock hasn't started yet
                </div>
                <div style="font-size:0.84rem;color:{TEXT_1};margin-bottom:10px;line-height:1.5;">
                    Bureaus are required to investigate within <strong>30 days of receiving your dispute</strong> under FCRA &sect; 611.
                    Every day your letters sit unmailed is a day wasted.
                    Set your mail date below to start the countdown.
                </div>
            </div>
            """, unsafe_allow_html=True)
            mail_date = st.date_input("Date letters were mailed", value=datetime.now().date(), key="dash_mail_date")
            if st.button("Start My 30-Day Countdown", key="dash_start_countdown", type="primary", use_container_width=True):
                db.save_dispute_tracker(user_id_dash, round_number_done, datetime.combine(mail_date, datetime.min.time()), 'manual')
                st.rerun()

        if round_lob_sends:
            with st.expander("Mail Tracker", expanded=True):
                for send in round_lob_sends:
                    bureau_name = send.get('bureau', 'Unknown').title()
                    tracking = send.get('tracking_number', '')
                    expected = send.get('expected_delivery', '')
                    tracking_url = lob_client.get_tracking_url(tracking) if tracking else None
                    sent_date = send['created_at'].strftime('%b %d') if hasattr(send['created_at'], 'strftime') else str(send['created_at'])[:10]

                    st.markdown(f"""
                    <div style="background:{BG_0};border:1px solid {BORDER};border-radius:10px;padding:12px 16px;margin-bottom:8px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <div>
                                <span style="font-weight:600;color:{TEXT_0};">{bureau_name}</span>
                                <span style="color:{TEXT_1};font-size:0.82rem;margin-left:8px;">Sent {sent_date}</span>
                            </div>
                            <div style="background:rgba(102,187,106,0.15);color:#66BB6A;font-size:0.75rem;font-weight:600;padding:3px 10px;border-radius:20px;">
                                Mailed
                            </div>
                        </div>
                        {'<div style="font-size:0.82rem;color:' + TEXT_1 + ';margin-top:6px;">Tracking: <code>' + tracking + '</code>' + (' | <a href="' + tracking_url + '" target="_blank" style="color:' + GOLD + ';">Track on USPS</a>' if tracking_url else '') + '</div>' if tracking else ''}
                        {'<div style="font-size:0.78rem;color:' + TEXT_1 + ';margin-top:4px;">Expected delivery: ' + expected + '</div>' if expected else ''}
                    </div>
                    """, unsafe_allow_html=True)

        if tier_rank >= 1:
            with st.expander("Proof Collection (for Round 2+)", expanded=False):
                st.markdown(f"""
                <div style="font-size:0.84rem;color:{TEXT_1};margin-bottom:12px;line-height:1.5;">
                    Log bureau responses and notes here to stay organized for Round 2. Keep your physical copies safe &mdash; this tracker helps you remember what each bureau said and when.
                </div>
                """, unsafe_allow_html=True)

                existing_proofs = db.get_proof_uploads(user_id_dash, round_number_done)
                if existing_proofs:
                    for proof in existing_proofs:
                        p_date = proof['created_at'].strftime('%b %d') if hasattr(proof['created_at'], 'strftime') else ''
                        p_bureau = proof.get('bureau', '').title() or 'General'
                        p_col1, p_col2 = st.columns([5, 1])
                        with p_col1:
                            st.markdown(f"""
                            <div style="font-size:0.85rem;color:{TEXT_0};padding:4px 0;">
                                {proof['file_name']} <span style="color:{TEXT_1};font-size:0.78rem;">({p_bureau} &mdash; {p_date})</span>
                                {'<br/><span style="color:' + TEXT_1 + ';font-size:0.78rem;">' + proof["notes"] + '</span>' if proof.get('notes') else ''}
                            </div>
                            """, unsafe_allow_html=True)
                        with p_col2:
                            if st.button("Remove", key=f"rm_proof_{proof['id']}", type="secondary"):
                                db.delete_proof_upload(proof['id'], user_id_dash)
                                st.rerun()

                proof_bureau = st.selectbox("Bureau", ["Equifax", "Experian", "TransUnion", "General"], key="proof_bureau")
                proof_desc = st.text_input("What did you receive?", key="proof_desc", placeholder="e.g., Response letter from Equifax")
                proof_notes = st.text_input("Details / notes", key="proof_notes", placeholder="e.g., They verified Account #1234 as accurate")
                if st.button("Log Response", key="save_proof_btn", use_container_width=True):
                    if proof_desc and proof_desc.strip():
                        db.save_proof_upload(
                            user_id_dash, round_number_done,
                            proof_bureau.lower(), proof_desc.strip(),
                            'note',
                            proof_notes.strip() if proof_notes else None
                        )
                        st.rerun()
                    else:
                        st.warning("Please describe what you received.")
        else:
            st.markdown(
                f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;'
                f'padding:14px 18px;margin-bottom:8px;">'
                f'<div style="font-size:0.92rem;font-weight:600;color:{TEXT_0};margin-bottom:4px;">'
                f'&#x1f512; Proof Collection</div>'
                f'<div style="font-size:0.82rem;color:{TEXT_1};">Track bureau responses and build your Round 2 evidence file.</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        CHECKLIST_ITEMS = [
            ("save_receipt", "Save your mailing receipt / tracking number"),
            ("keep_copies", "Keep copies of all letters you sent"),
            ("monitor_credit", "Check your credit report for updates"),
            ("collect_responses", "Save any bureau response letters"),
            ("prep_round2", "Prepare evidence for items not corrected"),
        ]
        with st.expander("Action Checklist", expanded=True):
            saved_checks = db.get_checklist_items(user_id_dash, round_number_done)
            completed_count = sum(1 for v in saved_checks.values() if v)
            total_items = len(CHECKLIST_ITEMS)

            st.markdown(f"""
            <div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:10px;">
                {completed_count} of {total_items} complete
            </div>
            """, unsafe_allow_html=True)

            for item_key, item_label in CHECKLIST_ITEMS:
                is_checked = saved_checks.get(item_key, False)
                new_val = st.checkbox(item_label, value=is_checked, key=f"cl_{item_key}_{round_number_done}")
                if new_val != is_checked:
                    db.toggle_checklist_item(user_id_dash, round_number_done, item_key, new_val)
                    st.rerun()

        sprint_g = db.get_sprint_guarantee(user_id_dash)
        if sprint_g and not sprint_g.get('free_round_used', False):
            with st.expander("2-Round Guarantee Tracker", expanded=True):
                sg_rounds = sprint_g.get('rounds_completed', 0)
                sg_r1 = sprint_g.get('round1_change_detected', False)
                sg_r2 = sprint_g.get('round2_change_detected', False)
                sg_free = sprint_g.get('free_round_available', False)

                st.markdown(
                    f'<div style="background:linear-gradient(135deg, rgba(212,160,23,0.08), rgba(212,160,23,0.02));'
                    f'border:1px solid {GOLD};border-radius:10px;padding:14px 16px;margin-bottom:12px;">'
                    f'<div style="font-size:0.92rem;font-weight:700;color:{GOLD};margin-bottom:6px;">'
                    f'&#x1f6e1;&#xfe0f; Deletion Sprint Guarantee</div>'
                    f'<div style="font-size:0.82rem;color:{TEXT_1};line-height:1.5;">'
                    f'If nothing changes after Round 1 and Round 2, Round 3 is on us. '
                    f'After each round\'s 30-day window, record whether any items were deleted or corrected.</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                r1_col, r2_col = st.columns(2)
                with r1_col:
                    if sg_rounds >= 1:
                        r1_icon = "&#x2705;" if not sg_r1 else "&#x1f504;"
                        r1_label = "No changes" if not sg_r1 else "Changes detected"
                        st.markdown(
                            f'<div style="text-align:center;padding:8px;background:{BG_1};border-radius:8px;">'
                            f'<div style="font-size:0.78rem;color:{TEXT_1};">Round 1</div>'
                            f'<div style="font-size:0.88rem;color:{TEXT_0};">{r1_icon} {r1_label}</div></div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f'<div style="text-align:center;padding:8px;background:{BG_1};border-radius:8px;">'
                            f'<div style="font-size:0.78rem;color:{TEXT_1};">Round 1</div>'
                            f'<div style="font-size:0.82rem;color:{TEXT_1};">Awaiting results</div></div>',
                            unsafe_allow_html=True,
                        )
                with r2_col:
                    if sg_rounds >= 2:
                        r2_icon = "&#x2705;" if not sg_r2 else "&#x1f504;"
                        r2_label = "No changes" if not sg_r2 else "Changes detected"
                        st.markdown(
                            f'<div style="text-align:center;padding:8px;background:{BG_1};border-radius:8px;">'
                            f'<div style="font-size:0.78rem;color:{TEXT_1};">Round 2</div>'
                            f'<div style="font-size:0.88rem;color:{TEXT_0};">{r2_icon} {r2_label}</div></div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f'<div style="text-align:center;padding:8px;background:{BG_1};border-radius:8px;">'
                            f'<div style="font-size:0.78rem;color:{TEXT_1};">Round 2</div>'
                            f'<div style="font-size:0.82rem;color:{TEXT_1};">Awaiting results</div></div>',
                            unsafe_allow_html=True,
                        )

                if round_number_done <= 2 and sg_rounds < round_number_done:
                    st.markdown(f'<div style="font-size:0.84rem;color:{TEXT_0};margin:12px 0 6px 0;font-weight:600;">'
                                f'Record Round {round_number_done} Results</div>', unsafe_allow_html=True)
                    change_choice = st.radio(
                        f"Were any disputed items deleted or corrected after Round {round_number_done}?",
                        ["No changes — nothing was deleted or corrected", "Yes — at least one item was deleted or corrected"],
                        key=f"sprint_r{round_number_done}_change",
                        index=None,
                    )
                    if st.button(f"Save Round {round_number_done} Results", key=f"sprint_save_r{round_number_done}",
                                 type="primary", use_container_width=True, disabled=(change_choice is None)):
                        change_detected = change_choice is not None and "Yes" in change_choice
                        db.update_sprint_round(user_id_dash, round_number_done, change_detected)
                        st.rerun()

                if sg_free:
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg, rgba(102,187,106,0.12), rgba(102,187,106,0.03));'
                        f'border:1px solid #66BB6A;border-radius:10px;padding:14px 16px;margin-top:12px;">'
                        f'<div style="font-size:0.95rem;font-weight:700;color:#66BB6A;margin-bottom:4px;">'
                        f'&#x2705; Free Round 3 Unlocked!</div>'
                        f'<div style="font-size:0.84rem;color:{TEXT_0};line-height:1.5;">'
                        f'Nothing changed after 2 rounds — your guarantee is active. '
                        f'Upload your updated report and generate Round 3 letters at no charge.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        if tier_rank >= 2:
            st.markdown(f"""
            <div style="background:linear-gradient(135deg, {BG_1} 0%, rgba(212,160,23,0.06) 100%);
                        border:1px solid {BORDER};border-radius:14px;padding:20px;margin:16px 0 0.75rem 0;">
                <div style="font-size:1.05rem;font-weight:700;color:{TEXT_0};margin-bottom:8px;">
                    Planning Round {round_number_done + 1}
                </div>
                <div style="font-size:0.88rem;color:{TEXT_1};line-height:1.6;">
                    After the bureaus respond (usually 30–45 days), pull your updated credit report and upload it
                    here. 850 Lab will detect what changed and help you dispute anything that wasn't corrected.
                    <br/><br/>
                    This was <strong>Round {round_number_done}</strong>. Most consumers see meaningful results within 2–3 rounds.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:14px;'
                f'padding:20px;margin:16px 0 0.75rem 0;position:relative;overflow:hidden;">'
                f'<div style="filter:blur(3px);pointer-events:none;">'
                f'<div style="font-size:1.05rem;font-weight:700;color:{TEXT_0};margin-bottom:8px;">'
                f'Planning Round {round_number_done + 1}</div>'
                f'<div style="font-size:0.88rem;color:{TEXT_1};line-height:1.6;">'
                f'After the bureaus respond, upload your updated report and we\'ll build Round 2 automatically.</div>'
                f'</div>'
                f'<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);'
                f'background:rgba(26,26,26,0.85);border-radius:8px;padding:8px 16px;'
                f'font-size:0.82rem;font-weight:600;color:{GOLD};white-space:nowrap;">'
                f'&#x1f512; Full Round unlocks multi-round planning</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if tier_rank >= 1:
            if 'reminder_email_sent' not in st.session_state:
                st.session_state.reminder_email_sent = False

            user_email = current_user.get('email', '')
            if user_email and not st.session_state.reminder_email_sent:
                if st.button("Email Me a 30-Day Reminder", use_container_width=True, key="send_reminder_btn"):
                    result = send_reminder_email(
                        to_email=user_email,
                        display_name=current_user.get('display_name'),
                        round_number=round_number_done,
                        bureau_names=bureau_names_done,
                    )
                    if result:
                        st.session_state.reminder_email_sent = True
                        st.rerun()
                    else:
                        st.warning("We couldn't send the reminder right now. You can try again later.")

            if st.session_state.reminder_email_sent:
                st.markdown(
                    f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;'
                    f'padding:10px 14px;text-align:center;color:{TEXT_1};font-size:0.88rem;">'
                    f'&#x2705; Reminder set — we\'ll email <strong>{user_email}</strong> '
                    f'when it\'s time to check your results.'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;'
                f'padding:10px 14px;text-align:center;margin-bottom:8px;">'
                f'<span style="font-size:0.82rem;color:{TEXT_1};">&#x1f512; Email reminders available with Digital Only+</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    else:
        st.markdown('<div class="card-title">You\'re set</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-body-copy">'
            'You currently have no dispute-ready items based on what could be confidently extracted. '
            'Try a different bureau report or re-upload a clearer PDF.'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    if 'confirm_start_over' not in st.session_state:
        st.session_state.confirm_start_over = False

    if not st.session_state.confirm_start_over:
        if st.button("Start New Analysis", use_container_width=True, key="done_start_over_btn"):
            st.session_state.confirm_start_over = True
            st.rerun()
    else:
        st.markdown(
            f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:12px;'
            f'padding:16px;text-align:center;margin-bottom:12px;">'
            f'<div style="font-size:0.95rem;color:{TEXT_0};font-weight:600;margin-bottom:4px;">'
            f'Start fresh?</div>'
            f'<div style="font-size:0.85rem;color:{TEXT_1};">'
            f'This will clear your current reports and letters. Downloaded files are yours to keep.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        col_confirm1, col_confirm2 = st.columns(2)
        with col_confirm1:
            if st.button("Yes, start over", use_container_width=True, key="confirm_start_over_yes", type="primary"):
                st.session_state.uploaded_reports = {}
                st.session_state.extracted_claims = {}
                st.session_state.review_claims = []
                st.session_state.review_claim_responses = {}
                st.session_state.identity_confirmed = {}
                st.session_state.generated_letters = {}
                st.session_state.readiness_decisions = []
                st.session_state.letter_candidates = []
                st.session_state.current_approval = None
                st.session_state.capacity_selection = {}
                st.session_state.system_error_message = None
                st.session_state.current_report = None
                st.session_state.confirm_start_over = False
                st.session_state.reminder_email_sent = False
                advance_card("UPLOAD")
                st.rerun()
        with col_confirm2:
            if st.button("Cancel", use_container_width=True, key="confirm_start_over_no"):
                st.session_state.confirm_start_over = False
                st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

