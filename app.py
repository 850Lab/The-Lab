import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout,
)
_startup_logger = logging.getLogger('850lab.startup')
_startup_logger.info("App module loading started")
print("[850lab] App module loading started", flush=True)

import streamlit as st

from patch_viewport import patch as _patch_viewport
_patch_viewport()

st.set_page_config(page_title="850 Lab", page_icon="💡", layout="wide")

try:
    from streamlit import user_info
    user_info.has_shown_experimental_user_warning = True
except Exception:
    pass

import json
import re
import hashlib
import html as html_mod
import time
import os
from io import BytesIO
from datetime import datetime
import traceback
from nudge_rules import evaluate_rules as evaluate_nudge_rules, NUDGE_SEVERITY_COLORS, NUDGE_SEVERITY_LABELS

_boot_errors = []

try:
    _t0 = time.time()

    class _LazyModule:
        __slots__ = ('_name', '_mod')
        def __init__(self, name):
            object.__setattr__(self, '_name', name)
            object.__setattr__(self, '_mod', None)
        def _resolve(self):
            mod = object.__getattribute__(self, '_mod')
            if mod is None:
                import importlib
                mod = importlib.import_module(object.__getattribute__(self, '_name'))
                object.__setattr__(self, '_mod', mod)
            return mod
        def __getattr__(self, attr):
            return getattr(self._resolve(), attr)

    pd = _LazyModule('pandas')
    zipfile = _LazyModule('zipfile')
    lob_client = _LazyModule('lob_client')
    diag_store = _LazyModule('diagnostics_store')

    import database as db
    import auth
    from constants import BLOCKER_MAPPING, CAPACITY_LIMIT_V1, SYSTEM_ERROR_UI_STATE
    from ui.css import inject_css, GOLD, GOLD_DIM, BG_0, BG_1, BG_2, TEXT_0, TEXT_1, BORDER
    from ui.components import lab_system_error_banner, CARD_ORDER
    from views.auth_page import render_auth_page

    from claims import ClaimState, extract_claims
    from review_claims import ReviewType, Severity, compress_claims
    from letter_generator import generate_letter_from_claims, format_letter_filename, generate_letter_pdf, generate_round1_letter, generate_round2_letter
    from normalization import normalize_parsed_data
    from identity_block import build_dispute_identity_block
    from readiness import Decision, evaluate_claim_readiness, group_into_letters, apply_capacity
    from evidence_chain import build_evidence_chain, validate_evidence_chain
    from truth_posture import forbidden_assertions_scan
    from resend_client import send_reminder_email, send_nudge_email
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
    from services.workflow.repository import ensure_active_workflow_id
    from dispute_strategy import build_ai_strategy, build_deterministic_strategy
    from strike_metrics import compute_strike_metrics
    from war_room_plan import build_war_room_plan, PHASE_LABELS
    from views.admin_dashboard import render_admin_dashboard
    from parsers import (
        sanitize_identity_info, run_tu_diagnostics, detect_bureau,
        extract_text_from_pdf, parse_credit_report_data,
    )
    _startup_logger.info(f"All modules imported in {time.time()-_t0:.2f}s")
    print(f"[850lab] All modules imported in {time.time()-_t0:.2f}s", flush=True)
except Exception as _boot_exc:
    _boot_errors.append(traceback.format_exc())
    _startup_logger.error(f"Boot error: {traceback.format_exc()}")
    print(f"[BOOT_ERROR] {traceback.format_exc()}", flush=True)
    sys.stdout.flush()
    sys.stderr.flush()

if _boot_errors:
    st.markdown("""
    <style>
    .recovery-card {
        background: #1a1a2e; color: #e0e0e0; border-radius: 12px;
        padding: 48px 32px; text-align: center; max-width: 500px;
        margin: 80px auto; font-family: 'Inter', sans-serif;
        box-shadow: 0 4px 24px rgba(0,0,0,0.3);
    }
    .recovery-card h2 { color: #D4A017; margin-bottom: 12px; }
    .recovery-card p { color: #aaa; margin-bottom: 24px; font-size: 15px; }
    </style>
    <div class="recovery-card">
        <h2>We'll be right back</h2>
        <p>850 Lab is refreshing. Please click below to retry.</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Refresh Now", use_container_width=True):
        st.rerun()
    st.stop()

_env_logger = logging.getLogger('850lab.env')
_required_env = ['DATABASE_URL']
_recommended_env = ['STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY', 'STRIPE_WEBHOOK_SECRET', 'LOB_API_KEY']
_optional_env = ['RESEND_FROM_EMAIL']
_missing_required = [k for k in _required_env if not os.environ.get(k)]
_missing_recommended = [k for k in _recommended_env if not os.environ.get(k)]
_missing_optional = [k for k in _optional_env if not os.environ.get(k)]
if _missing_required:
    _env_logger.error(f"Missing required env vars: {_missing_required}")
    st.error(f"850 Lab cannot start: missing required configuration ({', '.join(_missing_required)}). Please contact support.")
    st.stop()
if _missing_recommended:
    _env_logger.warning(f"Missing recommended env vars: {_missing_recommended} — some features will be unavailable")
if _missing_optional:
    _env_logger.info(f"Missing optional env vars: {_missing_optional}")

import threading

_db_ready = False
_db_init_error = False
_db_init_lock = threading.Lock()
_db_init_logger = logging.getLogger('850lab.db_init')

def _init_db():
    global _db_ready, _db_init_error
    if _db_ready:
        return True
    with _db_init_lock:
        if _db_ready:
            return True
        _t = time.time()
        try:
            db._get_pool_with_retry()
            _db_init_logger.info(f"DB pool ready in {time.time()-_t:.2f}s")
        except Exception as e:
            _db_init_logger.error(f"DB pool creation failed: {e}")
            _db_init_error = True
            return False
        try:
            db.init_database()
            _db_init_logger.info(f"init_database() completed in {time.time()-_t:.2f}s")
        except Exception as e:
            _db_init_logger.error(f"init_database() failed: {e}")
            _db_init_error = True
            return False
        try:
            auth.init_auth_tables()
            _db_init_logger.info("init_auth_tables() completed")
        except Exception as e:
            _db_init_logger.error(f"init_auth_tables() failed: {e}")
            _db_init_error = True
            return False
        try:
            _seed_admin()
        except Exception as e:
            _db_init_logger.warning(f"seed_admin() failed (non-critical): {e}")
        _db_ready = True
        _db_init_logger.info(f"DB init total: {time.time()-_t:.2f}s")
    return True

def _init_db_background():
    t = threading.Thread(target=_init_db, daemon=True)
    t.start()

def _seed_admin():
    import bcrypt
    admin_email = '850creditlab@gmail.com'
    try:
        with db.get_db(dict_cursor=True) as (conn, cur):
            cur.execute('SELECT id FROM users WHERE email = %s', (admin_email,))
            if cur.fetchone():
                return
            pw_hash = bcrypt.hashpw('Pr0$perity2026'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute(
                'INSERT INTO users (email, password_hash, display_name, role, email_verified) VALUES (%s, %s, %s, %s, TRUE)',
                (admin_email, pw_hash, '850 Lab Admin', 'admin')
            )
            conn.commit()
    except Exception:
        pass

_init_db_background()
_startup_logger.info("Background DB init thread started")

inject_css()

_do_scroll_to_top = st.session_state.get('_scroll_to_top', False)
if _do_scroll_to_top:
    del st.session_state._scroll_to_top

def _set_auth_cookie(token: str):
    try:
        st.query_params['session'] = token
    except Exception:
        pass
    try:
        import streamlit.components.v1 as _cookie_comp
        _cookie_comp.html(
            f'''<script>
            document.cookie="auth_token={token};path=/;max-age=2592000;SameSite=Lax;Secure";
            try{{window.parent.document.cookie="auth_token={token};path=/;max-age=2592000;SameSite=Lax;Secure";}}catch(e){{}}
            </script>''',
            height=0, width=0,
        )
    except Exception:
        pass

def _clear_auth_cookie():
    try:
        if 'session' in st.query_params:
            del st.query_params['session']
    except Exception:
        pass
    try:
        import streamlit.components.v1 as _cookie_comp
        _cookie_comp.html(
            '''<script>
            document.cookie="auth_token=;path=/;max-age=0;SameSite=Lax";
            try{window.parent.document.cookie="auth_token=;path=/;max-age=0;SameSite=Lax";}catch(e){}
            </script>''',
            height=0, width=0,
        )
    except Exception:
        pass

if 'auth_token' not in st.session_state:
    st.session_state.auth_token = None
if 'auth_user' not in st.session_state:
    st.session_state.auth_user = None
if 'auth_page' not in st.session_state:
    st.session_state.auth_page = 'landing'

def _get_device_id():
    try:
        import hashlib
        headers = st.context.headers
        parts = [
            headers.get('User-Agent', ''),
            headers.get('Accept-Language', ''),
            headers.get('X-Forwarded-For', headers.get('X-Real-Ip', '')),
        ]
        raw = '|'.join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:32] if any(parts) else None
    except Exception:
        return None

if not st.session_state.auth_token:
    try:
        cookie_token = st.context.cookies.get('auth_token')
        if cookie_token:
            st.session_state.auth_token = cookie_token
    except Exception:
        pass

if not st.session_state.auth_token:
    _qp_token = st.query_params.get('session')
    if _qp_token:
        st.session_state.auth_token = _qp_token

if not st.session_state.auth_token:
    _dev_id = _get_device_id()
    if _dev_id and _db_ready:
        try:
            _dev_token = auth.get_device_session_token(_dev_id)
            if _dev_token:
                st.session_state.auth_token = _dev_token
                _startup_logger.info("Session recovered via device fingerprint")
        except Exception:
            pass

def _wait_for_db(timeout=10):
    if _db_ready:
        return True
    if _db_init_error:
        return False
    start = time.time()
    while not _db_ready and not _db_init_error and (time.time() - start) < timeout:
        time.sleep(0.1)
    if not _db_ready:
        _startup_logger.warning(f"DB not ready after {timeout}s wait (error={_db_init_error})")
    return _db_ready

def get_current_user():
    if st.session_state.auth_user:
        last_validated = st.session_state.get('_session_validated_at', 0)
        now = time.time()
        if now - last_validated < 300:
            return st.session_state.auth_user
        if not _db_ready:
            return st.session_state.auth_user
        try:
            fresh = auth.validate_session(st.session_state.auth_token)
            if fresh:
                st.session_state.auth_user = fresh
                st.session_state._session_validated_at = now
                return fresh
            else:
                st.session_state.auth_token = None
                st.session_state.auth_user = None
                st.session_state._session_validated_at = 0
                st.session_state._clear_auth_cookie_pending = True
                return None
        except Exception:
            st.session_state._session_validated_at = now
            return st.session_state.auth_user
    if st.session_state.auth_token and not st.session_state.auth_user:
        if not _db_ready and not _wait_for_db(timeout=8):
            return None
        try:
            user = auth.validate_session(st.session_state.auth_token)
            if user:
                st.session_state.auth_user = user
                st.session_state._session_validated_at = time.time()
                return user
            else:
                st.session_state.auth_token = None
                st.session_state._clear_auth_cookie_pending = True
                return None
        except Exception as _auth_exc:
            _startup_logger.warning(f"Session validation failed (transient): {_auth_exc}")
            _retry_count = st.session_state.get('_session_retry_count', 0)
            if _retry_count < 3:
                st.session_state._session_retry_count = _retry_count + 1
                return None
            st.session_state.auth_token = None
            st.session_state._session_retry_count = 0
            return None
    return None

current_user = get_current_user()

_pending_cookie = st.session_state.pop('_set_auth_cookie_pending', None)
if _pending_cookie:
    _set_auth_cookie(_pending_cookie)
_clear_cookie = st.session_state.pop('_clear_auth_cookie_pending', None)
if _clear_cookie:
    _clear_auth_cookie()

_PREVIEW_CARDS = ['UPLOAD', 'SUMMARY', 'DISPUTES', 'VOICE_PROFILE', 'GENERATING', 'LETTERS_READY', 'DONE', 'MISSION_SETUP']
_test_card = st.query_params.get('test')
if _test_card and _test_card.upper() in _PREVIEW_CARDS:
    if not current_user or not auth.is_admin(current_user):
        st.error("Preview mode is only available to admin users.")
        st.stop()
    target_card = _test_card.upper()
    _prev_test = st.session_state.get('_test_mode_card')
    if _prev_test != target_card:
        st.session_state.ui_card = target_card
        st.session_state._test_mode_card = target_card
        st.session_state._test_mode_initialized = True
        _needs_reports = target_card in ('SUMMARY', 'DISPUTES', 'VOICE_PROFILE', 'GENERATING', 'LETTERS_READY', 'DONE')
        if _needs_reports and not st.session_state.get('uploaded_reports'):
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
                'test_experian': {
                    'bureau': 'experian', 'report_id': 'test_ex_001',
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
                ("Wells Fargo Auto", "accuracy_verification", "Account status shows 'Open' but was closed 06/2023", "equifax"),
                ("Synchrony Bank", "negative_impact", "30-day late payment 11/2023 — payment was made on time", "equifax"),
                ("Collections Agency LLC", "account_ownership", "Collection account not recognized by consumer", "transunion"),
                ("Amex Gold", "negative_impact", "Charge-off reported but account was settled in full 01/2024", "transunion"),
                ("Midland Credit Mgmt", "account_ownership", "Debt collector account — original creditor unknown", "transunion"),
                ("US Bank", "accuracy_verification", "Payment history shows missed payment 08/2023 — no record of missed payment", "transunion"),
                ("Citi Double Cash", "negative_impact", "Account reported 60 days past due 05/2024 — was in hardship program", "transunion"),
                ("Discover It", "accuracy_verification", "Credit limit incorrectly reported as $500 instead of $5,000", "experian"),
                ("Navy Federal CU", "negative_impact", "Late payment 02/2024 — auto-pay was active", "experian"),
                ("Portfolio Recovery", "account_ownership", "Collection for $1,847 — account does not belong to consumer", "experian"),
                ("Bank of America", "accuracy_verification", "Date opened shows 2019 but account opened 2016", "experian"),
                ("Affirm Loans", "accuracy_verification", "Balance reported $890 but loan was paid in full 12/2023", "experian"),
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
        _needs_letters = target_card in ('LETTERS_READY', 'DONE')
        if _needs_letters and not st.session_state.get('generated_letters'):
            _mock_letter_equifax = (
                "Jane Doe\n123 Main St\nAnytown, USA 12345\n\n"
                f"{datetime.now().strftime('%B %d, %Y')}\n\n"
                "Equifax Information Services LLC\nP.O. Box 740256\nAtlanta, GA 30374\n\n"
                "Re: Dispute of Inaccurate Information — Request for Investigation\n\n"
                "Dear Equifax Disputes Department,\n\n"
                "I am writing pursuant to my rights under the Fair Credit Reporting Act, 15 U.S.C. § 1681 et seq., "
                "to dispute the following inaccurate information appearing on my credit report.\n\n"
                "DISPUTED ITEM #1: Capital One Platinum\n"
                "Issue: Late payment reported 03/2024 — 30 days past due\n"
                "This information is inaccurate and must be corrected or removed.\n\n"
                "DISPUTED ITEM #2: Chase Sapphire\n"
                "Issue: Balance reported as $4,200 but actual balance is $2,100\n"
                "This information is inaccurate and must be corrected or removed.\n\n"
                "DISPUTED ITEM #3: Wells Fargo Auto\n"
                "Issue: Account status shows 'Open' but was closed 06/2023\n"
                "This information is inaccurate and must be corrected.\n\n"
                "DISPUTED ITEM #4: Synchrony Bank\n"
                "Issue: 30-day late payment 11/2023 — payment was made on time\n"
                "This information is inaccurate and must be corrected or removed.\n\n"
                "I request that you investigate these items and provide me with the results within 30 days "
                "as required by FCRA § 611(a)(1).\n\n"
                "Sincerely,\nJane Doe"
            )
            _mock_letter_transunion = (
                "Jane Doe\n123 Main St\nAnytown, USA 12345\n\n"
                f"{datetime.now().strftime('%B %d, %Y')}\n\n"
                "TransUnion Consumer Solutions\nP.O. Box 2000\nChester, PA 19016\n\n"
                "Re: Dispute of Inaccurate Information — Request for Investigation\n\n"
                "Dear TransUnion Disputes Department,\n\n"
                "I am writing pursuant to my rights under the Fair Credit Reporting Act, 15 U.S.C. § 1681 et seq., "
                "to dispute the following inaccurate information appearing on my credit report.\n\n"
                "DISPUTED ITEM #1: Collections Agency LLC\n"
                "Issue: Collection account not recognized by consumer\n"
                "This information is inaccurate and must be removed.\n\n"
                "DISPUTED ITEM #2: Amex Gold\n"
                "Issue: Charge-off reported but account was settled in full 01/2024\n"
                "This information is inaccurate and must be corrected or removed.\n\n"
                "DISPUTED ITEM #3: Midland Credit Mgmt\n"
                "Issue: Debt collector account — original creditor unknown, cannot verify debt\n"
                "This information cannot be verified and must be removed per FCRA § 611.\n\n"
                "DISPUTED ITEM #4: US Bank\n"
                "Issue: Payment history shows missed payment 08/2023 — no record of missed payment\n"
                "This information is inaccurate and must be corrected or removed.\n\n"
                "DISPUTED ITEM #5: Citi Double Cash\n"
                "Issue: Account reported 60 days past due 05/2024 — was enrolled in hardship program\n"
                "This information is inaccurate and must be corrected or removed.\n\n"
                "I request that you investigate these items and provide me with the results within 30 days "
                "as required by FCRA § 611(a)(1).\n\n"
                "Sincerely,\nJane Doe"
            )
            _mock_letter_experian = (
                "Jane Doe\n123 Main St\nAnytown, USA 12345\n\n"
                f"{datetime.now().strftime('%B %d, %Y')}\n\n"
                "Experian\nP.O. Box 4500\nAllen, TX 75013\n\n"
                "Re: Dispute of Inaccurate Information — Request for Investigation\n\n"
                "Dear Experian Disputes Department,\n\n"
                "I am writing pursuant to my rights under the Fair Credit Reporting Act, 15 U.S.C. § 1681 et seq., "
                "to dispute the following inaccurate information appearing on my credit report.\n\n"
                "DISPUTED ITEM #1: Discover It\n"
                "Issue: Credit limit incorrectly reported as $500 instead of $5,000\n"
                "This information is inaccurate and must be corrected or removed.\n\n"
                "DISPUTED ITEM #2: Navy Federal CU\n"
                "Issue: Late payment 02/2024 — auto-pay was active at time of alleged late payment\n"
                "This information is inaccurate and must be corrected or removed.\n\n"
                "DISPUTED ITEM #3: Portfolio Recovery\n"
                "Issue: Collection for $1,847 — this account does not belong to me\n"
                "This information is inaccurate and must be removed immediately.\n\n"
                "DISPUTED ITEM #4: Bank of America\n"
                "Issue: Date opened shows 2019 but account was opened in 2016\n"
                "This information is inaccurate and must be corrected.\n\n"
                "DISPUTED ITEM #5: Affirm Loans\n"
                "Issue: Balance reported $890 but loan was paid in full 12/2023\n"
                "This information is inaccurate and must be corrected or removed.\n\n"
                "I request that you investigate these items and provide me with the results within 30 days "
                "as required by FCRA § 611(a)(1).\n\n"
                "Sincerely,\nJane Doe"
            )
            st.session_state.generated_letters = {
                'equifax': {
                    'letter_text': _mock_letter_equifax,
                    'bureau': 'equifax',
                    'claim_count': 4,
                    'categories': ['negative_impact', 'accuracy_verification'],
                    'rc_details': [
                        {'account_name': 'Capital One Platinum', 'issue': 'Late payment 03/2024', 'type': 'negative_impact'},
                        {'account_name': 'Chase Sapphire', 'issue': 'Balance discrepancy', 'type': 'accuracy_verification'},
                        {'account_name': 'Wells Fargo Auto', 'issue': 'Account status error', 'type': 'accuracy_verification'},
                        {'account_name': 'Synchrony Bank', 'issue': 'False late payment', 'type': 'negative_impact'},
                    ],
                },
                'transunion': {
                    'letter_text': _mock_letter_transunion,
                    'bureau': 'transunion',
                    'claim_count': 5,
                    'categories': ['account_ownership', 'negative_impact', 'accuracy_verification'],
                    'rc_details': [
                        {'account_name': 'Collections Agency LLC', 'issue': 'Unrecognized collection', 'type': 'account_ownership'},
                        {'account_name': 'Amex Gold', 'issue': 'Charge-off vs settled', 'type': 'negative_impact'},
                        {'account_name': 'Midland Credit Mgmt', 'issue': 'Unknown original creditor', 'type': 'account_ownership'},
                        {'account_name': 'US Bank', 'issue': 'False missed payment', 'type': 'accuracy_verification'},
                        {'account_name': 'Citi Double Cash', 'issue': 'Hardship program dispute', 'type': 'negative_impact'},
                    ],
                },
                'experian': {
                    'letter_text': _mock_letter_experian,
                    'bureau': 'experian',
                    'claim_count': 5,
                    'categories': ['accuracy_verification', 'negative_impact', 'account_ownership'],
                    'rc_details': [
                        {'account_name': 'Discover It', 'issue': 'Credit limit error', 'type': 'accuracy_verification'},
                        {'account_name': 'Navy Federal CU', 'issue': 'Late payment with auto-pay', 'type': 'negative_impact'},
                        {'account_name': 'Portfolio Recovery', 'issue': 'Not my account', 'type': 'account_ownership'},
                        {'account_name': 'Bank of America', 'issue': 'Date opened wrong', 'type': 'accuracy_verification'},
                        {'account_name': 'Affirm Loans', 'issue': 'Balance paid in full', 'type': 'accuracy_verification'},
                    ],
                },
            }
            st.session_state._letters_generated_at = datetime.now().isoformat()
        if target_card == 'DONE':
            st.session_state.active_panel = st.session_state.get('active_panel', 'home')
    _card_links = ' &middot; '.join(
        f'<a href="?test={c.lower()}" style="color:{GOLD};text-decoration:none;">{c}</a>'
        if c != target_card else f'<strong style="color:{TEXT_0};">{c}</strong>'
        for c in _PREVIEW_CARDS
    )
    st.markdown(
        f'<div style="background:rgba(212,160,23,0.08);border:1px solid {GOLD};border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:0.78rem;color:{TEXT_1};">'
        f'Preview mode — {_card_links}'
        f'</div>',
        unsafe_allow_html=True,
    )

_page_param = st.query_params.get('page')
if _page_param in ('terms', 'privacy', 'refund', 'guide'):
    from views.legal import render_terms_of_service, render_privacy_policy, render_refund_policy, render_how_it_works_guide
    if _page_param == 'terms':
        render_terms_of_service()
    elif _page_param == 'privacy':
        render_privacy_policy()
    elif _page_param == 'refund':
        render_refund_policy()
    elif _page_param == 'guide':
        render_how_it_works_guide()
    st.stop()

_upload_token_param = st.query_params.get('upload')
if _upload_token_param:
    _token_user_id = db.validate_upload_token(_upload_token_param)
    if _token_user_id:
        db.mark_upload_token_used(_upload_token_param)
        _token_user = auth.get_user_by_id(_token_user_id)
        if _token_user:
            from views.legal import render_proof_upload_page
            render_proof_upload_page(current_user={'user_id': _token_user_id, 'display_name': _token_user.get('display_name', ''), 'email': _token_user.get('email', '')}, via_token=True)
            st.stop()
    from ui.css import inject_css
    inject_css()
    st.markdown(f'''
    <div style="max-width:420px;margin:3rem auto;text-align:center;padding:2rem;">
        <div style="font-size:2.5rem;margin-bottom:1rem;">&#x1F512;</div>
        <div style="font-size:1.1rem;font-weight:800;color:#f5f5f5;margin-bottom:0.5rem;">This link has expired</div>
        <div style="font-size:0.88rem;color:#a0a0a8;line-height:1.6;margin-bottom:1.5rem;">
            Upload links are good for 7 days. Log in to your account to upload your documents.</div>
        <a href="/" target="_self" style="display:inline-block;padding:12px 28px;
            background:linear-gradient(90deg,#D4A017,#f2c94c);color:#1a1a1f;font-weight:700;
            font-size:0.95rem;border-radius:10px;text-decoration:none;">Log In to 850 Lab</a>
    </div>
    ''', unsafe_allow_html=True)
    st.stop()

if _page_param == 'proof':
    from views.legal import render_proof_upload_page
    render_proof_upload_page(current_user=current_user)
    st.stop()

if _page_param == 'go':
    from ui.css import inject_css
    inject_css()
    from views.landing import render_ad_landing
    render_ad_landing()
    st.stop()

_demo_nav = st.query_params.get('nav', '')
_exit_demo = _demo_nav == 'exit_demo' or (_demo_nav in ('signup', 'login') and st.session_state.get('_demo_mode'))
if _exit_demo or (not current_user and st.session_state.get('_demo_mode') and st.session_state.get('auth_page') != 'demo'):
    st.session_state._demo_mode = False
    _target_page = _demo_nav if _demo_nav in ('signup', 'login') else 'landing'
    st.session_state.auth_page = _target_page
    for _dk in ('_demo_show_sample_letter', 'uploaded_reports', 'review_claims',
                'identity_confirmed', 'dispute_rounds', 'generated_letters',
                'ui_card', 'claim_responses', 'review_claim_responses',
                'battle_plan_items', '_credit_command_plan', 'panel',
                'report_id', 'current_report', '_cached_entitlements',
                '_email_verified_cached', '_activity_session_logged',
                'unified_summary', 'parsed_totals', 'report_totals',
                'readiness_decisions', 'letter_candidates', 'current_approval',
                'capacity_selection', 'ai_strategy_result'):
        st.session_state.pop(_dk, None)
    st.query_params.clear()
    st.rerun()

if not current_user and st.session_state.get('auth_page') == 'demo':
    from demo_data import load_demo_session
    if not st.session_state.get('_demo_mode'):
        load_demo_session()
        st.rerun()
    from ui.css import inject_css
    inject_css()

if not current_user and not st.session_state.get('_demo_mode'):
    _ref_code = st.query_params.get('ref')
    if _ref_code and _ref_code.strip():
        st.session_state._referral_code = _ref_code.strip()
        st.session_state.auth_page = 'signup'
    elif not _ref_code and st.session_state.get('_referral_code'):
        try:
            st.query_params['ref'] = st.session_state._referral_code
        except Exception:
            pass

    _cookie_accepted = False
    try:
        _cookie_accepted = st.context.cookies.get('cookie_consent') == '1'
    except Exception:
        pass
    if st.session_state.get('_cookie_consent_accepted'):
        _cookie_accepted = True
    if not _cookie_accepted:
        import streamlit.components.v1 as _cc_comp
        _cc_comp.html(f'''
        <div id="cc-banner" style="position:fixed;bottom:0;left:0;right:0;z-index:99999;
            background:{BG_2};border-top:1px solid rgba(255,215,140,0.15);
            padding:12px 20px;display:flex;align-items:center;justify-content:space-between;
            font-family:Inter,sans-serif;font-size:13px;color:{TEXT_1};gap:12px;">
            <span>We use cookies for authentication and to improve your experience.
            <a href="?page=privacy" target="_top" style="color:{GOLD};text-decoration:underline;">Privacy Policy</a></span>
            <button onclick="document.cookie='cookie_consent=1;path=/;max-age=31536000;SameSite=Lax;Secure';
            try{{window.parent.document.cookie='cookie_consent=1;path=/;max-age=31536000;SameSite=Lax;Secure';}}catch(e){{}}
            document.getElementById('cc-banner').style.display='none';"
            style="background:{GOLD};color:#000;border:none;border-radius:6px;padding:8px 20px;
            font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap;">Accept</button>
        </div>''', height=60)

    render_auth_page()
    st.stop()

if st.query_params.get('nav') == 'sprint':
    st.query_params.clear()
    from views.sprint_intake import render_sprint_intake
    render_sprint_intake()
    st.stop()

_is_demo = st.session_state.get('_demo_mode', False)

if _is_demo:
    user_id = None
    is_admin_user = False
    user_entitlements = {}
else:
    user_id = current_user.get('id') or current_user.get('user_id')
    _email_verified_cache = st.session_state.get('_email_verified_cached')
    if _email_verified_cache is None:
        _email_verified_cache = auth.is_email_verified(user_id)
        st.session_state._email_verified_cached = _email_verified_cache
    if not _email_verified_cache:
        st.session_state.auth_page = 'verify_email'
        if not st.session_state.get('_pending_verify_email'):
            st.session_state._pending_verify_email = True
        render_auth_page()
        st.stop()

    if not st.session_state.get('_activity_session_logged'):
        db.log_activity(user_id, 'session_load', current_user.get('email', ''), st.session_state.get('ui_card', 'UPLOAD'))
        st.session_state._activity_session_logged = True
        db.cleanup_old_activity(days=7)

if _is_demo:
    PRODUCT_CATALOG = {}
else:
    PRODUCT_CATALOG = {}
    for pid, p in auth.PACKS.items():
        PRODUCT_CATALOG[pid] = {'price_cents': p['price_cents'], 'ai_rounds': p['ai_rounds'], 'letters': p['letters'], 'mailings': p['mailings'], 'label': p['label']}
    for pid, p in auth.ALA_CARTE.items():
        ent = {'ai_rounds': 0, 'letters': 0, 'mailings': 0}
        ent[p['type']] = p['qty']
        PRODUCT_CATALOG[pid] = {'price_cents': p['price_cents'], 'label': p['label'], **ent}

qp = st.query_params
if not _is_demo and qp.get('payment') == 'success' and qp.get('session_id'):
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
                    user_id,
                    ai_rounds=catalog_entry['ai_rounds'],
                    letters=catalog_entry['letters'],
                    mailings=catalog_entry['mailings'],
                    source=f'stripe:{product_id}',
                    stripe_session_id=sid,
                    note=f'Purchased {catalog_entry["label"]} for ${amount/100:.2f}',
                )
                db.log_activity(user_id, 'purchase', f"{catalog_entry['label']} (${amount/100:.2f})", st.session_state.get('ui_card'))
                auth.record_payment(
                    user_id,
                    amount,
                    stripe_session_id=sid,
                    status='completed',
                )
                wf_meta = (meta.get("workflow_id") or "").strip()
                if wf_meta:
                    try:
                        from services.workflow import hooks as _wf_hooks

                        _wf_hooks.notify_payment_completed(
                            user_id,
                            sid,
                            workflow_id=wf_meta,
                            amount_cents=amount,
                            audit_source="streamlit:payment_return",
                        )
                    except Exception as _wf_pay_exc:
                        print(f"[WORKFLOW_PAYMENT] return-path notify failed: {_wf_pay_exc}")
                st.success("Purchase complete! Your entitlements have been added.")
                if product_id == 'deletion_sprint':
                    db.create_sprint_guarantee(user_id, stripe_session_id=sid)
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg, rgba(212,160,23,0.10), rgba(212,160,23,0.03));'
                        f'border:1px solid {GOLD};border-radius:10px;padding:16px 18px;margin:12px 0;">'
                        f'<div style="font-size:1rem;font-weight:700;color:{GOLD};margin-bottom:6px;">'
                        f'&#x1f6e1;&#xfe0f; You\'re covered by the 2-Round Guarantee</div>'
                        f'<div style="font-size:0.85rem;color:{TEXT_0};line-height:1.6;">'
                        f'If no disputed item is deleted or updated after completing 2 rounds, Round 3 is on us. '
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
elif not _is_demo and qp.get('payment') == 'cancelled':
    st.info("Payment was cancelled. You can purchase anytime.")
    st.query_params.clear()

_bg_results_lock = threading.Lock()
_bg_results = {}

def _run_background_tasks_once(_uid, _email, _display_name, _catalog, _session_id):
    reconciled = 0
    try:
        paid_sessions = list_recent_paid_sessions(_email, limit=10)
        for ps in paid_sessions:
            sid = ps.get('id', '')
            if not sid or auth.entitlement_purchase_processed(sid):
                continue
            meta = ps.get('metadata', {})
            meta_uid = meta.get('user_id')
            if str(_uid) != str(meta_uid):
                continue
            product_id = meta.get('product_id', '')
            amount = ps.get('amount_total', 0)
            catalog_entry = _catalog.get(product_id)
            if catalog_entry and catalog_entry['price_cents'] == amount:
                auth.add_entitlements(
                    _uid,
                    ai_rounds=catalog_entry['ai_rounds'],
                    letters=catalog_entry['letters'],
                    mailings=catalog_entry['mailings'],
                    source=f'stripe_reconcile:{product_id}',
                    stripe_session_id=sid,
                    note=f'Reconciled {catalog_entry["label"]} for ${amount/100:.2f}',
                )
                auth.record_payment(_uid, amount, stripe_session_id=sid, status='completed')
                wf_meta = (meta.get("workflow_id") or "").strip()
                if wf_meta:
                    try:
                        from services.workflow import hooks as _wf_hooks

                        _wf_hooks.notify_payment_completed(
                            _uid,
                            sid,
                            workflow_id=wf_meta,
                            amount_cents=amount,
                            audit_source="stripe_reconcile:list",
                        )
                    except Exception as _wf_rec_exc:
                        print(f"[WORKFLOW_PAYMENT] reconcile notify failed: {_wf_rec_exc}")
                if product_id == 'deletion_sprint':
                    db.create_sprint_guarantee(_uid, stripe_session_id=sid)
                reconciled += 1
    except Exception as e:
        print(f"[PAYMENT_RECONCILE] {type(e).__name__}: {e}")
    try:
        auth.cleanup_expired_sessions()
    except Exception:
        pass
    try:
        process_drip_emails(_uid, _email, _display_name)
    except Exception as e:
        print(f"[DRIP_EMAIL] {type(e).__name__}: {e}")
    try:
        pending_lob = db.get_pending_lob_sends()
        for ls in pending_lob:
            lob_id = ls.get('lob_id', '')
            if lob_id:
                status_result = lob_client.get_letter_status(lob_id)
                if status_result.get('success') and status_result.get('status') != ls.get('status'):
                    db.update_lob_send_status(ls['id'], status_result['status'])
    except Exception as e:
        print(f"[LOB_POLL] {type(e).__name__}: {e}")
    if reconciled > 0:
        with _bg_results_lock:
            _bg_results[_session_id] = reconciled

def _invalidate_entitlement_cache():
    st.session_state._entitlements_cached_at = 0

if not _is_demo:
    if not st.session_state.get('_bg_tasks_started'):
        st.session_state._bg_tasks_started = True
        _session_id = id(st.session_state)
        _bg = threading.Thread(
            target=_run_background_tasks_once,
            args=(user_id, current_user.get('email', ''), current_user.get('display_name'), PRODUCT_CATALOG, _session_id),
            daemon=True,
        )
        _bg.start()
        st.session_state._last_reconcile_ts = time.time()

    _RECONCILE_INTERVAL = 60
    _last_rec = st.session_state.get('_last_reconcile_ts', 0)
    if time.time() - _last_rec > _RECONCILE_INTERVAL:
        st.session_state._last_reconcile_ts = time.time()
        _recon_session_id = id(st.session_state)
        _recon_bg = threading.Thread(
            target=_run_background_tasks_once,
            args=(user_id, current_user.get('email', ''), current_user.get('display_name'), PRODUCT_CATALOG, _recon_session_id),
            daemon=True,
        )
        _recon_bg.start()

    _cur_session_id = id(st.session_state)
    with _bg_results_lock:
        _reconciled_n = _bg_results.pop(_cur_session_id, 0)
    if _reconciled_n > 0:
        st.success(f"We found {_reconciled_n} payment{'s' if _reconciled_n > 1 else ''} that hadn't been applied yet. Your credits have been updated!")
        _invalidate_entitlement_cache()
        st.rerun()

    is_admin_user = auth.is_admin(current_user)

    _ent_cache_ts = st.session_state.get('_entitlements_cached_at', 0)
    if time.time() - _ent_cache_ts > 30 or '_cached_entitlements' not in st.session_state:
        user_entitlements = auth.get_entitlements(user_id)
        st.session_state._cached_entitlements = user_entitlements
        st.session_state._entitlements_cached_at = time.time()
    else:
        user_entitlements = st.session_state._cached_entitlements


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
    _restored_state = None
    _restore_uid = None
    if current_user and _db_ready:
        _restore_uid = current_user.get('id') or current_user.get('user_id')
        if _restore_uid:
            _restored_state = db.get_user_ui_state(_restore_uid)
    _restorable_cards = ('DONE', 'LETTERS_READY', 'SUMMARY', 'DISPUTES')
    if _restored_state and _restored_state.get('ui_card') in _restorable_cards:
        _restored_card = _restored_state['ui_card']
        if _restored_card in ('SUMMARY', 'DISPUTES'):
            try:
                _saved_reports = db.get_reports(user_id=_restore_uid)
                if _saved_reports:
                    _recent_reports = _saved_reports[:3]
                    st.session_state.uploaded_reports = {}
                    st.session_state.extracted_claims = {}
                    _all_restore_claims = []
                    for _sr in _recent_reports:
                        _sr_data = db.get_report(_sr['id'], user_id=_restore_uid)
                        if _sr_data:
                            _sr_parsed = _sr_data.get('parsed_data') or {}
                            _sr_parsed = normalize_parsed_data(_sr_parsed)
                            _sr_bureau = _sr_data.get('bureau', 'unknown')
                            _sr_key = f"RPT_{_sr['id']}"
                            st.session_state.uploaded_reports[_sr_key] = {
                                'upload_id': _sr_key,
                                'file_name': _sr_data.get('file_name', 'Unknown'),
                                'bureau': _sr_bureau,
                                'parsed_data': _sr_parsed,
                                'full_text': _sr_data.get('full_text', ''),
                                'num_pages': 0,
                                'report_id': _sr['id'],
                            }
                            _sr_claims = extract_claims(_sr_parsed, _sr_bureau)
                            st.session_state.extracted_claims[_sr_key] = _sr_claims
                            _all_restore_claims.extend(_sr_claims)
                    if st.session_state.uploaded_reports:
                        _last_rk = list(st.session_state.uploaded_reports.keys())[-1]
                        st.session_state.current_report = st.session_state.uploaded_reports[_last_rk]
                        st.session_state.report_id = st.session_state.current_report.get('report_id')
                        st.session_state.review_claims = compress_claims(_all_restore_claims)
                        st.session_state.claim_responses = {}
                        st.session_state.review_claim_responses = {}
                        st.session_state.identity_confirmed = {}
                        st.session_state.ui_card = _restored_card
                        st.session_state._ui_state_restored = True
                    else:
                        st.session_state.ui_card = "UPLOAD"
                else:
                    st.session_state.ui_card = "UPLOAD"
            except Exception:
                st.session_state.ui_card = "UPLOAD"
        else:
            st.session_state.ui_card = _restored_card
            if _restored_state.get('active_panel'):
                st.session_state.panel = _restored_state['active_panel']
            st.session_state._ui_state_restored = True
    else:
        _fallback_uid = None
        if current_user and _db_ready:
            _fallback_uid = current_user.get('id') or current_user.get('user_id')
        if _fallback_uid:
            try:
                _fb_letters = db.get_latest_letters_for_user(_fallback_uid)
                if _fb_letters:
                    _fb_restored = {}
                    for _fb_b, _fb_d in _fb_letters.items():
                        if _fb_d.get('letter_text'):
                            _fb_restored[_fb_b] = {
                                'letter_text': _fb_d['letter_text'],
                                'bureau': _fb_b,
                                'rc_details': [],
                            }
                    if _fb_restored:
                        st.session_state.generated_letters = _fb_restored
                        st.session_state._gen_letters_count = len(_fb_restored)
                        st.session_state._gen_bureau_names = [b.title() for b in _fb_restored.keys()]
                        st.session_state._gen_completed = True
                        st.session_state._letters_generated_at = datetime.now().isoformat()
                        _fb_has_sig = db.get_user_signature(_fallback_uid)
                        _fb_has_proof = db.has_proof_docs(_fallback_uid)
                        if _fb_has_sig and _fb_has_proof and _fb_has_proof.get('both'):
                            st.session_state.ui_card = "DONE"
                            st.session_state.panel = 'home'
                        else:
                            st.session_state.ui_card = "DONE"
                            st.session_state.panel = 'documents'
                        st.session_state._ui_state_restored = True
                    else:
                        st.session_state.ui_card = "UPLOAD"
                else:
                    st.session_state.ui_card = "UPLOAD"
            except Exception:
                st.session_state.ui_card = "UPLOAD"
        else:
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
        f'If no disputed item is deleted or updated after completing 2 rounds, Round 3 is on us.'
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
    if _is_demo:
        return
    uid = user_id
    email = current_user.get('email', '')
    is_founder = st.session_state.get('_cached_is_founder', False)

    recommended = None
    if needed_ai > 0 or needed_letters > 0 or needed_mailings > 0:
        for pack_id, pack in auth.PACKS.items():
            if is_founder and pack_id == 'deletion_sprint':
                continue
            if pack['ai_rounds'] >= needed_ai and pack['letters'] >= needed_letters and pack['mailings'] >= needed_mailings:
                recommended = pack_id
                break

    is_sidebar = context == "sidebar"

    if is_sidebar:
        st.markdown("##### Packs")
        for pack_id, pack in auth.PACKS.items():
            if is_founder and pack_id == 'deletion_sprint':
                continue
            rec_tag = " ⭐ Recommended" if pack_id == recommended else ""
            label = f"{pack['label']} — ${pack['price_cents']/100:.2f}{rec_tag}"
            desc = f"{pack['ai_rounds']} AI · {pack['letters']} Letters · {pack['mailings']} Mail"
            if st.button(label, key=f"buy_{context}_{pack_id}", use_container_width=True, help=desc):
                result = create_checkout_session(
                    uid, email, pack_id, pack['label'], pack['price_cents'],
                    ai_rounds=pack['ai_rounds'], letters=pack['letters'], mailings=pack['mailings'],
                    workflow_id=ensure_active_workflow_id(uid),
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
                    workflow_id=ensure_active_workflow_id(uid),
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
            f'Your <strong style="color:{TEXT_0};">free analysis</strong> found patterns and quick wins. '
            f'<strong style="color:{GOLD};">Paid AI strategy</strong> goes deeper: it ranks your disputes by '
            f'impact, picks which items to fight first, and writes stronger legal reasoning into every letter. '
            f'Users who run AI strategy dispute <strong style="color:{GOLD};">the right items first</strong> — '
            f'maximizing deletions and avoiding wasted rounds.</div>'
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

    if rec_pack_id == 'deletion_sprint':
        badge_html = (
            f'<div style="display:inline-block;background:linear-gradient(135deg, {GOLD}, #e8c848);'
            f'color:#1a1a1a;font-size:0.7rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.8px;padding:3px 10px;border-radius:20px;margin-bottom:8px;">'
            f'2-Round Guarantee</div>'
        )
        card_border = GOLD
        card_bg = f'linear-gradient(135deg, rgba(212,160,23,0.10), rgba(212,160,23,0.03))'
        price_color = GOLD
        btn_label = f"Start the 30-Day Sprint — ${rec_pack['price_cents']/100:.0f}"
    elif rec_pack_id == 'full_round':
        badge_html = (
            f'<div style="display:inline-block;background:#1a1a1a;'
            f'color:#fff;font-size:0.7rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.8px;padding:3px 10px;border-radius:20px;margin-bottom:8px;">'
            f'Single Round</div>'
        )
        card_border = BORDER
        card_bg = f'linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01))'
        price_color = TEXT_0
        btn_label = f"Get {rec_pack['label']} — ${rec_pack['price_cents']/100:.2f}"
    else:
        badge_html = ''
        card_border = BORDER
        card_bg = f'linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01))'
        price_color = TEXT_0
        btn_label = f"Get {rec_pack['label']} — ${rec_pack['price_cents']/100:.2f}"

    st.markdown(
        f'{badge_html}'
        f'<div style="background:{card_bg};'
        f'border:1px solid {card_border};border-radius:10px;padding:14px 16px;margin-bottom:8px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
        f'<span style="font-size:0.95rem;font-weight:700;color:{TEXT_0};">{rec_pack["label"]}</span>'
        f'<span style="font-size:1.1rem;font-weight:700;color:{price_color};">${rec_pack["price_cents"]/100:.2f}</span>'
        f'</div>'
        f'<div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:2px;">{includes_text}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if rec_pack_id == 'deletion_sprint':
        st.markdown(_sprint_guarantee_html(), unsafe_allow_html=True)
    if st.button(btn_label, key=f"buy_{context}_{rec_pack_id}", type="primary", use_container_width=True):
        result = create_checkout_session(
            uid, email, rec_pack_id, rec_pack['label'], rec_pack['price_cents'],
            ai_rounds=rec_pack['ai_rounds'], letters=rec_pack['letters'], mailings=rec_pack['mailings'],
            workflow_id=ensure_active_workflow_id(uid),
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
                        st.markdown(
                            f'<div style="display:inline-block;background:linear-gradient(135deg, {GOLD}, #e8c848);'
                            f'color:#1a1a1a;font-size:0.65rem;font-weight:700;text-transform:uppercase;'
                            f'letter-spacing:0.6px;padding:2px 8px;border-radius:12px;margin-bottom:4px;">'
                            f'2-Round Guarantee</div>', unsafe_allow_html=True)
                        st.markdown(_sprint_guarantee_html(), unsafe_allow_html=True)
                    elif pack_id == 'full_round':
                        st.markdown(
                            f'<div style="display:inline-block;background:#1a1a1a;'
                            f'color:#fff;font-size:0.65rem;font-weight:700;text-transform:uppercase;'
                            f'letter-spacing:0.6px;padding:2px 8px;border-radius:12px;margin-bottom:4px;">'
                            f'Single Round</div>', unsafe_allow_html=True)
                    if st.button(label, key=f"buy_{context}_{pack_id}", use_container_width=True, help=desc):
                        result = create_checkout_session(
                            uid, email, pack_id, pack['label'], pack['price_cents'],
                            ai_rounds=pack['ai_rounds'], letters=pack['letters'], mailings=pack['mailings'],
                            workflow_id=ensure_active_workflow_id(uid),
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
                            workflow_id=ensure_active_workflow_id(uid),
                        )
                        if result.get('url'):
                            _open_checkout(result['url'])
                        else:
                            st.error(f"Payment error: {result.get('error', 'Unknown')}")



VALID_CARDS = set(CARD_ORDER) | {"PREPARING", "GENERATING", "LETTERS_READY", "VOICE_PROFILE", "MISSION_SETUP"}

def _report_has_extracted_items(uploaded_reports) -> bool:
    """True when at least one report has accounts, negatives, inquiries, or classified account counts."""
    if not uploaded_reports or not isinstance(uploaded_reports, dict):
        return False
    for _source_key, rr in uploaded_reports.items():
        if not isinstance(rr, dict):
            continue
        pd = rr.get("parsed_data") or {}
        if not isinstance(pd, dict):
            continue
        if pd.get("accounts"):
            return True
        if pd.get("negative_items"):
            return True
        if pd.get("inquiries"):
            return True
        counts = pd.get("classification_counts") or {}
        if isinstance(counts, dict) and sum(int(v or 0) for v in counts.values()) > 0:
            return True
    return False

def _step2_data_ready(uploaded_reports, is_admin: bool) -> bool:
    if _report_has_extracted_items(uploaded_reports):
        return True
    if is_admin and st.session_state.get("_test_mode_initialized") and uploaded_reports:
        return True
    return False

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
            _panel = st.session_state.get('active_panel')
            db.save_user_ui_state(_uid, target_card, _panel)

def _get_proof_docs_for_pdf(uid):
    if not uid:
        return None
    try:
        docs = []
        id_docs = db.get_proof_docs_for_user(uid, doc_types=['government_id'])
        if id_docs:
            id_file = db.get_proof_doc_file(id_docs[0]['id'], uid)
            if id_file and id_file.get('file_data'):
                docs.append({'label': 'Government-Issued Photo ID', 'data': bytes(id_file['file_data'])})
        addr_docs = db.get_proof_docs_for_user(uid, doc_types=['address_proof'])
        if addr_docs:
            addr_file = db.get_proof_doc_file(addr_docs[0]['id'], uid)
            if addr_file and addr_file.get('file_data'):
                docs.append({'label': 'Proof of Current Address', 'data': bytes(addr_file['file_data'])})
        return docs if docs else None
    except Exception:
        return None


def reset_analysis_state(full=False):
    for key in [
        '_processed_files_sig', '_report_outcome', '_auto_round1',
        'battle_plan_items', '_ai_analysis_cache',
        '_gen_selected_items', '_gen_review_claims_list', '_gen_round_number',
        '_gen_letter_count_to_deduct', '_gen_is_free', '_gen_free_item_count',
        '_gen_free_max_capacity', '_gen_id', '_gen_completed',
        '_gen_letters_count', '_gen_bureau_names',
        'letter_edits', 'letter_removed_rcs',
    ]:
        st.session_state.pop(key, None)
    if full:
        st.session_state.uploaded_reports = {}
        st.session_state.extracted_claims = {}
        st.session_state.review_claims = []
        st.session_state.claim_responses = {}
        st.session_state.review_claim_responses = {}
        st.session_state.identity_confirmed = {}
        st.session_state.generated_letters = {}
        st.session_state.readiness_decisions = {}
        st.session_state.letter_candidates = []
        st.session_state.current_approval = None
        st.session_state.capacity_selection = None
        st.session_state.system_error_message = None
        st.session_state.ai_strategy_result = None
        st.session_state.upload_diagnostics = {}
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

if _is_demo:
    st.markdown(
        '<style>[data-testid="stSidebar"] { display: none !important; }</style>',
        unsafe_allow_html=True,
    )
    use_ocr = False
    DEBUG_MODE = False
    DEV_MODE = False

if not _is_demo:
  with st.sidebar:
    user_display_name = current_user.get('display_name', current_user.get('email', 'User'))
    role_display = " (Admin)" if is_admin_user else ""
    _founder_cache_ts = st.session_state.get('_founder_cached_at', 0)
    if time.time() - _founder_cache_ts > 300 or '_cached_is_founder' not in st.session_state:
        _is_founder = auth.is_user_founder(user_id)
        st.session_state._cached_is_founder = _is_founder
        st.session_state._founder_cached_at = time.time()
    else:
        _is_founder = st.session_state._cached_is_founder
    founder_badge_html = '<span class="lp-founder-sidebar-badge">Founding Member</span>' if _is_founder else ''
    ent = user_entitlements
    st.markdown(
        f'<div class="sidebar-user-card">'
        f'<div class="sidebar-user-name">{user_display_name}{role_display}{founder_badge_html}</div>'
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
            _ref_cache_ts = st.session_state.get('_referral_cached_at', 0)
            if time.time() - _ref_cache_ts > 120 or '_cached_ref_link' not in st.session_state:
                ref_link = get_referral_link(user_id)
                ref_stats = get_referral_stats(user_id)
                st.session_state._cached_ref_link = ref_link
                st.session_state._cached_ref_stats = ref_stats
                st.session_state._referral_cached_at = time.time()
            else:
                ref_link = st.session_state._cached_ref_link
                ref_stats = st.session_state._cached_ref_stats
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

    st.markdown(
        f'<a href="?page=guide" target="_self" style="display:block;text-align:center;'
        f'color:{GOLD};font-size:0.85rem;margin:8px 0 12px;text-decoration:none;">'
        f'How It Works</a>',
        unsafe_allow_html=True,
    )

    if st.button("Sign Out", key="logout_btn", use_container_width=True):
        auth.delete_session(st.session_state.auth_token)
        st.session_state.auth_token = None
        st.session_state.auth_user = None
        for _sig_key in ('_user_signature_bytes', 'user_signature_confirmed', 'sig_data_transfer_area', 'sig_redrawing'):
            st.session_state.pop(_sig_key, None)
        _clear_auth_cookie()
        st.rerun()

    st.markdown('<div class="sidebar-section-title">Account</div>', unsafe_allow_html=True)

    with st.expander("Account Settings"):
        new_name = st.text_input("Display Name", value=current_user.get('display_name', ''), key="settings_name")
        if st.button("Update Name", key="update_name_btn"):
            if new_name.strip():
                auth.update_display_name(user_id, new_name)
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
                    result = auth.update_password(user_id, cur_pw, new_pw, except_token=current_token)
                    if 'error' in result:
                        st.error(result['error'])
                    else:
                        st.success("Password changed! Other sessions have been signed out.")

        st.markdown("**Payment History**")
        if st.button("Load Payment History", key="load_payments_btn"):
            st.session_state._show_payments = True
        if st.session_state.get('_show_payments'):
            payments = auth.get_user_payments(user_id)
            if payments:
                for p in payments:
                    amount_str = f"${p['amount']/100:.2f}" if p['amount'] else "$0.00"
                    date_str = p['created_at'].strftime('%m/%d/%Y') if hasattr(p['created_at'], 'strftime') else str(p['created_at'])
                    status_icon = "✅" if p['status'] == 'completed' else "⏳"
                    st.caption(f"{status_icon} {amount_str} — {date_str}")
            else:
                st.caption("No payments yet.")

            st.markdown("**Entitlement History**")
            ent_txns = auth.get_entitlement_transactions(user_id, limit=10)
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
            lob_history = db.get_lob_sends_for_user(user_id)
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

    if st.session_state.get('_cached_is_founder', False):
        with st.expander("Transfer Rounds", expanded=False):
            st.markdown(
                '<p style="color:#B0B0B0; font-size:0.85rem; margin-bottom:8px;">'
                'Share your unused AI rounds or letters with another 850 Lab user.</p>',
                unsafe_allow_html=True,
            )
            transfer_email = st.text_input("Recipient email", key="transfer_email", placeholder="friend@example.com")
            tc1, tc2 = st.columns(2)
            with tc1:
                transfer_ai = st.number_input("AI Rounds", min_value=0, max_value=max(ent.get('ai_rounds', 0), 0), value=0, key="transfer_ai")
            with tc2:
                transfer_letters = st.number_input("Letters", min_value=0, max_value=max(ent.get('letters', 0), 0), value=0, key="transfer_letters")
            if st.button("Send Transfer", key="send_transfer_btn", use_container_width=True):
                if not transfer_email or not transfer_email.strip():
                    st.error("Please enter the recipient's email.")
                elif transfer_ai == 0 and transfer_letters == 0:
                    st.error("Select at least 1 round or letter to transfer.")
                else:
                    result = auth.transfer_rounds(user_id, transfer_email, ai_rounds=transfer_ai, letters=transfer_letters)
                    if 'error' in result:
                        st.error(result['error'])
                    else:
                        st.success(f"Transferred {transfer_ai} AI rounds and {transfer_letters} letters!")
                        from referral import get_or_create_referral_code
                        ref_code = get_or_create_referral_code(user_id)
                        if ref_code:
                            ref_link = f"https://850lab.replit.app/?ref={ref_code}"
                            st.info(f"Share your referral link with others too — you earn a free AI round for each signup: `{ref_link}`")
                        st.rerun()
            _xfer_cache_ts = st.session_state.get('_transfers_cached_at', 0)
            if time.time() - _xfer_cache_ts > 120 or '_cached_transfers' not in st.session_state:
                transfers = db.get_round_transfers(user_id, direction='both', limit=5)
                st.session_state._cached_transfers = transfers
                st.session_state._transfers_cached_at = time.time()
            else:
                transfers = st.session_state._cached_transfers
            if transfers:
                st.markdown("**Recent transfers**")
                for t in transfers:
                    d = t.get('direction', 'sent')
                    partner = t.get('to_email', '') if d == 'sent' else t.get('from_email', '')
                    parts = []
                    if t.get('ai_rounds'):
                        parts.append(f"{t['ai_rounds']} AI")
                    if t.get('letters'):
                        parts.append(f"{t['letters']} Letters")
                    detail = ", ".join(parts)
                    dt_str = t['created_at'].strftime('%m/%d/%Y') if hasattr(t['created_at'], 'strftime') else str(t['created_at'])
                    arrow = "→" if d == 'sent' else "←"
                    st.caption(f"{arrow} {detail} {arrow} {partner} — {dt_str}")

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
                    db.delete_user_reports(user_id)
                    st.session_state.confirm_delete = False
                    reset_analysis_state(full=True)
                    st.session_state.ui_card = "UPLOAD"
                    st.success("All your data has been deleted.")
                    st.rerun()
            with col_no:
                if st.button("Cancel", key="confirm_delete_no"):
                    st.session_state.confirm_delete = False
                    st.rerun()

    st.markdown('<div class="sidebar-section-title">Settings</div>', unsafe_allow_html=True)

    use_ocr = False
    if is_admin_user:
        use_ocr = st.checkbox("Enable OCR", value=False, help="Use OCR for scanned PDFs")
        DEBUG_MODE = st.checkbox("Debug mode", value=False, help="Show raw/normalized counts and technical details")
    else:
        DEBUG_MODE = False

    st.markdown('<div class="sidebar-section-title">Reports</div>', unsafe_allow_html=True)
    _sidebar_needs_rerun = False
    try:
        previous_reports = db.get_all_reports(user_id=user_id)
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
                        report_data = db.get_report(report_id, user_id=user_id)
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

                    _reloaded_letters = {}
                    try:
                        for _rl_key, _rl_val in st.session_state.uploaded_reports.items():
                            _rl_rid = _rl_val.get('report_id')
                            if _rl_rid:
                                _saved_letters = db.get_letters_for_report(_rl_rid, user_id=user_id)
                                for _sl in _saved_letters:
                                    _sl_bureau = _sl.get('bureau', '').lower()
                                    if _sl_bureau and _sl.get('letter_text'):
                                        _meta = {}
                                        if _sl.get('metadata'):
                                            try:
                                                import json as _rl_json
                                                _meta = _rl_json.loads(_sl['metadata']) if isinstance(_sl['metadata'], str) else (_sl['metadata'] or {})
                                            except Exception:
                                                _meta = {}
                                        _reloaded_letters[_sl_bureau] = {
                                            'letter_text': _sl['letter_text'],
                                            'claim_count': _meta.get('claim_count', 0),
                                            'categories': _meta.get('categories', []),
                                        }
                    except Exception as _rl_err:
                        print(f"[LETTER_RELOAD] Error: {_rl_err}")
                    st.session_state.generated_letters = _reloaded_letters

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
                    st.session_state._report_uploaded_at = datetime.now().isoformat()
                    if _reloaded_letters:
                        st.session_state._gen_letters_count = len(_reloaded_letters)
                        st.session_state._gen_bureau_names = [b.title() for b in _reloaded_letters.keys()]
                        st.session_state._gen_completed = True
                        st.session_state._letters_generated_at = datetime.now().isoformat()
                        advance_card("DONE")
                        st.toast(f"Loaded {len(_reloaded_letters)} saved letter{'s' if len(_reloaded_letters) != 1 else ''}")
                    else:
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
            reset_analysis_state(full=True)
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
            import base64 as _b64_ux
            _b64_ux_data = _b64_ux.b64encode(report_json.encode()).decode()
            _ux_fn = "ux_report.json"
            import streamlit.components.v1 as _dl_ux_comp
            _dl_ux_comp.html(
                f'''<button onclick="dlUx()" style="width:100%;padding:10px 16px;background:{BG_2};color:{TEXT_0};
                font-weight:500;font-size:0.88rem;border-radius:10px;border:1px solid rgba(255,215,140,0.15);cursor:pointer;
                font-family:'Inter',-apple-system,sans-serif;">Download UX Report JSON</button>
                <script>function dlUx(){{var b=atob("{_b64_ux_data}");var a=new Uint8Array(b.length);
                for(var i=0;i<b.length;i++)a[i]=b.charCodeAt(i);var bl=new Blob([a],{{type:"application/json"}});
                var u=URL.createObjectURL(bl);var l=document.createElement('a');l.href=u;l.download="{_ux_fn}";
                document.body.appendChild(l);l.click();setTimeout(function(){{document.body.removeChild(l);URL.revokeObjectURL(u);}},100);
                }}</script>''',
                height=46,
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
    st.session_state.ui_card = "SUMMARY" if _step2_data_ready(st.session_state.get("uploaded_reports"), is_admin_user) else "UPLOAD"

if not _is_demo and not st.session_state.uploaded_reports and st.session_state.ui_card == "UPLOAD":
    if '_mission_loaded' not in st.session_state:
        try:
            _existing_mission = db.get_active_mission(user_id)
            if _existing_mission:
                st.session_state['mission_goal'] = _existing_mission.get('goal', 'General Rebuild')
                st.session_state['mission_timeline'] = _existing_mission.get('timeline', 'ASAP (7 days)')
                st.session_state['_active_mission_id'] = _existing_mission.get('id')
            st.session_state['_mission_loaded'] = True
        except Exception:
            st.session_state['_mission_loaded'] = True

    if not st.session_state.get('mission_goal') and not st.session_state.get('_mission_skip') and not st.session_state.get('_test_mode_initialized'):
        st.session_state.ui_card = "MISSION_SETUP"

if not st.session_state.get('_test_mode_initialized'):
    if _step2_data_ready(st.session_state.uploaded_reports, is_admin_user) and st.session_state.ui_card == "UPLOAD":
        advance_card("SUMMARY")

    if not _is_demo and st.session_state.generated_letters and st.session_state.ui_card in ("DISPUTES", "SUMMARY") and not st.session_state.get('manual_nav_back'):
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

if _is_demo:
    st.markdown(
        f'<div style="background:linear-gradient(135deg,rgba(212,160,23,0.12),rgba(212,160,23,0.04));'
        f'border:1px solid rgba(212,160,23,0.3);border-radius:10px;padding:10px 18px;margin-bottom:12px;'
        f'display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">'
        f'<span style="color:{GOLD};font-weight:600;font-size:0.9rem;">Demo Mode &mdash; Sample Data</span>'
        f'<span style="display:flex;gap:8px;align-items:center;">'
        f'<a href="/?nav=signup" target="_self" style="background:{GOLD};color:#000;padding:6px 16px;'
        f'border-radius:8px;font-size:0.82rem;font-weight:600;text-decoration:none;">Sign Up Free &rarr;</a>'
        f'<a href="/?nav=exit_demo" target="_self" style="color:{TEXT_1};font-size:0.82rem;text-decoration:underline;">Exit Demo</a>'
        f'</span></div>',
        unsafe_allow_html=True,
    )
else:
    _menu_col1, _menu_col2 = st.columns([1, 8])
    with _menu_col1:
        _menu_pop = st.popover("\u2630", use_container_width=True)
        with _menu_pop:
            st.markdown(
                f'<div style="font-weight:700;color:{TEXT_0};font-size:0.95rem;margin-bottom:8px;">'
                f'{current_user.get("display_name", "User")}'
                f'{"  (Admin)" if is_admin_user else ""}</div>',
                unsafe_allow_html=True,
            )
            ent = user_entitlements
            st.markdown(
                f'<div style="font-size:0.8rem;color:{TEXT_1};margin-bottom:10px;">'
                f'{ent["ai_rounds"]} AI &middot; {ent["letters"]} Letters &middot; {ent["mailings"]} Mail</div>',
                unsafe_allow_html=True,
            )
            if is_admin_user:
                if not st.session_state.get('admin_dashboard_active'):
                    if st.button("Admin Dashboard", key="mobile_admin_btn", type="primary", use_container_width=True):
                        st.session_state.admin_dashboard_active = True
                        st.rerun()
                else:
                    if st.button("Back to App", key="mobile_admin_back_btn", use_container_width=True):
                        st.session_state.admin_dashboard_active = False
                        st.rerun()
            if st.button("Sign Out", key="mobile_logout_btn", use_container_width=True):
                auth.delete_session(st.session_state.auth_token)
                st.session_state.auth_token = None
                st.session_state.auth_user = None
                for _sig_key in ('_user_signature_bytes', 'user_signature_confirmed', 'sig_data_transfer_area', 'sig_redrawing'):
                    st.session_state.pop(_sig_key, None)
                _clear_auth_cookie()
                st.rerun()
    with _menu_col2:
        st.empty()

from ui.stepper import render_stepper_bar

_stepper_has_letters = bool(st.session_state.generated_letters)
_stepper_round = st.session_state.get('dispute_round_number', 1)
_stepper_card = st.session_state.ui_card
_stepper_panel = st.session_state.get('panel', 'home')
_stepper_page_param = st.query_params.get('page', '')

_stepper_docs_ok = False
_stepper_mailed = False
_stepper_mail_done = False
if _stepper_has_letters and not _is_demo:
    try:
        _stepper_proof = db.has_proof_docs(user_id)
        _stepper_docs_ok = _stepper_proof.get('both', False)
    except Exception:
        pass
    try:
        _stepper_tracker = db.get_dispute_tracker(user_id, _stepper_round)
        _stepper_mailed = bool(_stepper_tracker and _stepper_tracker.get('mailed_at'))
        if _stepper_mailed:
            _stepper_elapsed = (datetime.now() - _stepper_tracker['mailed_at']).days
            _stepper_mail_done = _stepper_elapsed >= 30
    except Exception:
        pass

_stepper_completed = set()
if _stepper_has_letters:
    _stepper_completed.add(1)
    _stepper_completed.add(2)
    _stepper_completed.add(3)
if _stepper_docs_ok:
    _stepper_completed.add(4)
if _stepper_mailed:
    _stepper_completed.add(5)
if _stepper_mail_done:
    _stepper_completed.add(6)

if _stepper_card in ('UPLOAD', 'MISSION_SETUP'):
    _stepper_current = 1
elif _stepper_card in ('SUMMARY', 'DISPUTES', 'PREPARING'):
    _stepper_current = 2
elif _stepper_card in ('VOICE_PROFILE', 'GENERATING', 'LETTERS_READY'):
    _stepper_current = 3
elif _stepper_page_param == 'proof':
    _stepper_current = 4
elif _stepper_card == 'DONE' and _stepper_panel == 'send_mail':
    _stepper_current = 5
elif _stepper_card == 'DONE' and _stepper_panel in ('tracker', 'escalation'):
    _stepper_current = 6
elif _stepper_card == 'DONE' and _stepper_mailed:
    _stepper_current = 6
elif _stepper_has_letters and not _stepper_docs_ok:
    _stepper_current = 4
elif _stepper_has_letters and _stepper_docs_ok and not _stepper_mailed:
    _stepper_current = 5
elif _stepper_mailed:
    _stepper_current = 6
else:
    _stepper_current = 1

render_stepper_bar(_stepper_current, _stepper_completed, _stepper_round)
st.markdown('<div class="card-viewport">', unsafe_allow_html=True)

MAX_FILE_SIZE_MB = 25

if st.session_state.ui_card == "MISSION_SETUP":
    MISSION_GOALS = ["Auto Purchase", "Apartment", "Credit Card", "Bank Account", "General Rebuild"]
    MISSION_TIMELINES = ["ASAP (7 days)", "30 days", "90 days"]

    _ms_goal_icons = {"Auto Purchase": "\U0001F697", "Apartment": "\U0001F3E0", "Credit Card": "\U0001F4B3", "Bank Account": "\U0001F3E6", "General Rebuild": "\U0001F527"}
    _ms_goal_descs = {
        "Auto Purchase": "Auto lending",
        "Apartment": "Rental approval",
        "Credit Card": "Card approval",
        "Bank Account": "Banking access",
        "General Rebuild": "Full credit health",
    }

    _ms_selected_goal = st.session_state.get('_ms_selected_goal', None)
    _ms_selected_tl = st.session_state.get('_ms_selected_timeline', None)

    _ms_goal_css = ""
    for _gi, _goal in enumerate(MISSION_GOALS):
        _is_sel = _ms_selected_goal == _goal
        if _is_sel:
            _ms_goal_css += f'''
            [data-testid="stHorizontalBlock"] [data-testid="column"]:has(button[key="ms_g_{_gi}"]) button,
            button[kind="secondary"][key="ms_g_{_gi}"],
            div:has(> div > button[key="ms_g_{_gi}"]) button {{
                border-color:{GOLD} !important;
                background:rgba(212,160,23,0.1) !important;
                box-shadow:0 0 14px rgba(212,160,23,0.18) !important;
            }}
            '''

    for _ti, _tl in enumerate(MISSION_TIMELINES):
        _is_sel = _ms_selected_tl == _tl
        if _is_sel:
            _ms_goal_css += f'''
            div:has(> div > button[key="ms_tl_{_ti}"]) button {{
                border-color:{GOLD} !important;
                background:rgba(212,160,23,0.15) !important;
                color:{GOLD} !important;
                box-shadow:0 0 10px rgba(212,160,23,0.12) !important;
            }}
            '''

    st.markdown(f'''
    <style>
    .ms-goal-btn .stButton button {{
        background:rgba(255,215,140,0.04) !important;
        border:1px solid rgba(255,215,140,0.12) !important;
        border-radius:12px !important;
        padding:12px 8px !important;
        min-height:80px !important;
        color:{TEXT_0} !important;
        font-size:0.82rem !important;
        font-weight:700 !important;
        transition:all 0.15s ease !important;
        white-space:pre-line !important;
        line-height:1.4 !important;
    }}
    .ms-goal-btn .stButton button:hover {{
        border-color:rgba(212,160,23,0.4) !important;
        background:rgba(255,215,140,0.07) !important;
    }}
    .ms-goal-btn .stButton button p {{
        color:{TEXT_0} !important;
        font-weight:700 !important;
    }}
    .ms-goal-full .stButton button {{
        min-height:48px !important;
        padding:10px 8px !important;
    }}
    .ms-tl-btn .stButton button {{
        background:rgba(255,215,140,0.04) !important;
        border:1px solid rgba(255,215,140,0.1) !important;
        border-radius:8px !important;
        padding:10px 6px !important;
        min-height:42px !important;
        color:{TEXT_1} !important;
        font-size:0.82rem !important;
        font-weight:600 !important;
        transition:all 0.15s ease !important;
    }}
    .ms-tl-btn .stButton button:hover {{
        border-color:rgba(212,160,23,0.35) !important;
        background:rgba(255,215,140,0.06) !important;
    }}
    .ms-tl-btn .stButton button p {{
        color:{TEXT_1} !important;
        font-weight:600 !important;
    }}
    .ms-skip-btn .stButton button {{
        background:transparent !important;
        border:none !important;
        color:{TEXT_1} !important;
        font-size:0.78rem !important;
        box-shadow:none !important;
        font-weight:400 !important;
        padding:4px !important;
        min-height:0 !important;
    }}
    .ms-skip-btn .stButton button:hover {{
        color:{TEXT_0} !important;
    }}
    {_ms_goal_css}
    </style>
    ''', unsafe_allow_html=True)

    st.markdown(
        f'<div style="text-align:center;padding:1rem 0.5rem 0.5rem;">'
        f'<div style="font-size:1.6rem;font-weight:900;color:{TEXT_0};line-height:1.1;letter-spacing:-0.03em;">'
        f'What\'s Your <span style="color:{GOLD};">Mission?</span></div>'
        f'<div style="font-size:0.85rem;color:{TEXT_1};margin-top:0.4rem;">Pick a goal and timeline for your strike plan.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    _ms_r1c1, _ms_r1c2 = st.columns(2, gap="small")
    with _ms_r1c1:
        st.markdown('<div class="ms-goal-btn">', unsafe_allow_html=True)
        _g0_check = " \u2713" if _ms_selected_goal == "Auto Purchase" else ""
        if st.button(f'{_ms_goal_icons["Auto Purchase"]}\nAuto Purchase{_g0_check}', key="ms_g_0", use_container_width=True):
            st.session_state['_ms_selected_goal'] = "Auto Purchase"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with _ms_r1c2:
        st.markdown('<div class="ms-goal-btn">', unsafe_allow_html=True)
        _g1_check = " \u2713" if _ms_selected_goal == "Apartment" else ""
        if st.button(f'{_ms_goal_icons["Apartment"]}\nApartment{_g1_check}', key="ms_g_1", use_container_width=True):
            st.session_state['_ms_selected_goal'] = "Apartment"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    _ms_r2c1, _ms_r2c2 = st.columns(2, gap="small")
    with _ms_r2c1:
        st.markdown('<div class="ms-goal-btn">', unsafe_allow_html=True)
        _g2_check = " \u2713" if _ms_selected_goal == "Credit Card" else ""
        if st.button(f'{_ms_goal_icons["Credit Card"]}\nCredit Card{_g2_check}', key="ms_g_2", use_container_width=True):
            st.session_state['_ms_selected_goal'] = "Credit Card"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with _ms_r2c2:
        st.markdown('<div class="ms-goal-btn">', unsafe_allow_html=True)
        _g3_check = " \u2713" if _ms_selected_goal == "Bank Account" else ""
        if st.button(f'{_ms_goal_icons["Bank Account"]}\nBank Account{_g3_check}', key="ms_g_3", use_container_width=True):
            st.session_state['_ms_selected_goal'] = "Bank Account"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="ms-goal-btn ms-goal-full">', unsafe_allow_html=True)
    _g4_check = " \u2713" if _ms_selected_goal == "General Rebuild" else ""
    if st.button(f'{_ms_goal_icons["General Rebuild"]}  General Rebuild{_g4_check}', key="ms_g_4", use_container_width=True):
        st.session_state['_ms_selected_goal'] = "General Rebuild"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="font-size:0.65rem;font-weight:800;text-transform:uppercase;'
        f'letter-spacing:0.1em;color:{GOLD_DIM};margin:12px 0 4px;">Timeline</div>',
        unsafe_allow_html=True,
    )

    _tl_icons = {MISSION_TIMELINES[0]: "\u26A1", MISSION_TIMELINES[1]: "\U0001F4C5", MISSION_TIMELINES[2]: "\U0001F4C6"}
    _tl_c0, _tl_c1, _tl_c2 = st.columns(3, gap="small")
    for _ti, (_tl, _col) in enumerate(zip(MISSION_TIMELINES, [_tl_c0, _tl_c1, _tl_c2])):
        with _col:
            st.markdown('<div class="ms-tl-btn">', unsafe_allow_html=True)
            _tl_check = " \u2713" if _ms_selected_tl == _tl else ""
            if st.button(f'{_tl_icons[_tl]} {_tl}{_tl_check}', key=f"ms_tl_{_ti}", use_container_width=True):
                st.session_state['_ms_selected_timeline'] = _tl
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    _ms_ready = _ms_selected_goal and _ms_selected_tl

    if _ms_ready:
        if st.button("Continue \u2192", key="ms_confirm", type="primary", use_container_width=True):
            st.session_state['mission_goal'] = _ms_selected_goal
            st.session_state['mission_timeline'] = _ms_selected_tl
            try:
                db.create_mission(user_id, _ms_selected_goal, _ms_selected_tl)
            except Exception:
                pass
            st.session_state.pop('_ms_selected_goal', None)
            st.session_state.pop('_ms_selected_timeline', None)
            advance_card("UPLOAD")
            st.rerun()
    else:
        if st.button("Continue \u2192", key="ms_confirm_disabled", use_container_width=True):
            st.toast("Pick a goal and timeline first.")

    st.markdown('<div class="ms-skip-btn">', unsafe_allow_html=True)
    if st.button("Skip for now", key="ms_skip", use_container_width=True):
        st.session_state['_mission_skip'] = True
        st.session_state['mission_goal'] = 'General Rebuild'
        st.session_state['mission_timeline'] = 'ASAP (7 days)'
        advance_card("UPLOAD")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.ui_card == "UPLOAD":
    st.markdown(
        f'<div style="text-align:center;padding:2rem 1rem 1rem;overflow:hidden;">'
        f'<div style="font-size:clamp(1.6rem, 6vw, 2.4rem);font-weight:900;color:{TEXT_0};line-height:1.15;letter-spacing:-0.03em;">'
        f'Drop Your Report.<br/><span style="color:{GOLD};">We&#39;ll Do the Rest.</span></div>'
        f'<div style="font-size:1rem;color:{TEXT_1};margin-top:0.75rem;">TransUnion, Equifax, or Experian PDF</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Need your credit report? Here's how", expanded=False):
        st.markdown(f"""
<div style="padding:4px 0;font-size:0.85rem;color:{TEXT_1};line-height:1.6;">
<strong style="color:{TEXT_0};">1.</strong> Go to <a href="https://www.annualcreditreport.com" target="_blank" rel="noopener" style="color:{GOLD};font-weight:600;">AnnualCreditReport.com</a><br/>
<strong style="color:{TEXT_0};">2.</strong> Verify your identity<br/>
<strong style="color:{TEXT_0};">3.</strong> Select all three bureaus<br/>
<strong style="color:{TEXT_0};">4.</strong> Download each as a PDF, then upload here<br/>
<span style="font-size:0.78rem;color:{TEXT_1};margin-top:6px;display:inline-block;">Free reports available every week.</span>
</div>
        """, unsafe_allow_html=True)

    if 'privacy_consent' not in st.session_state:
        st.session_state.privacy_consent = False

    privacy_agreed = st.checkbox(
        "I agree to secure processing of my report data.",
        value=st.session_state.privacy_consent,
        key="privacy_checkbox",
    )
    st.session_state.privacy_consent = privacy_agreed

    if not privacy_agreed:
        st.caption("Check the box above to continue.")
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
                pass
            else:
                uploaded_files = None

            _file_sig = tuple(sorted((f.name, f.size) for f in valid_files)) if valid_files else None
            _already_processed = (_file_sig is not None and st.session_state.get('_processed_files_sig') == _file_sig)

            if valid_files and not _already_processed:
              st.session_state._processed_files_sig = _file_sig
              try:
                all_claims = []
                reports_processed = 0
                diagnostic_logs = []

                st.session_state.uploaded_reports = {}
                st.session_state.extracted_claims = {}

                for uploaded_file in valid_files:
                  with st.status(f"Scanning your report...", expanded=False) as status:
                    status.update(label="Scanning your report...", state="running")
                    pdf_bytes = uploaded_file.read()
                    uploaded_file.seek(0)
                    file_hash = hashlib.sha256(pdf_bytes).hexdigest()[:16]
                    upload_id = f"UPL_{file_hash}"
                    upload_time = datetime.now().isoformat()

                    _startup_logger.info(f"Processing upload: {uploaded_file.name} ({len(pdf_bytes)} bytes, hash={file_hash})")
                    full_text, page_texts, num_pages, pdf_extract_error = extract_text_from_pdf(
                        uploaded_file, use_ocr
                    )
                    _startup_logger.info(f"Text extraction complete: {uploaded_file.name} — {num_pages} pages, {len(full_text) if full_text else 0} chars")

                    if not full_text:
                        _startup_logger.info(f"No text extracted from: {uploaded_file.name}")
                        if pdf_extract_error:
                            _startup_logger.info(
                                "PDF extract error code=%s detail=%s",
                                pdf_extract_error.get("code"),
                                pdf_extract_error.get("detail", pdf_extract_error.get("message")),
                            )
                        status.update(label=f"{uploaded_file.name} — Could not read this file", state="error")
                        st.warning(f"⚠️ **{uploaded_file.name}** — We could not read any text from this file. Please make sure it is a credit report PDF downloaded directly from the bureau website (not a screenshot or photo).")
                        continue

                    if full_text:
                        status.update(label="Finding errors...", state="running")
                        bureau, bureau_scores, bureau_evidence = detect_bureau(full_text, debug=DEBUG_MODE, return_details=True)
                        _startup_logger.info(f"Bureau detected: {bureau} for {uploaded_file.name}")
    
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
                            _startup_logger.info(f"Rejected 3-bureau report: {uploaded_file.name}")
                            status.update(label=f"{uploaded_file.name} — 3-bureau report detected", state="error")
                            st.warning(f"⚠️ **{uploaded_file.name}** is a combined 3-bureau report (e.g., SmartCredit). Please upload individual single-bureau reports from TransUnion, Experian, and Equifax for accurate parsing.")
                            continue
    
                        if bureau == 'unknown':
                            _startup_logger.info(f"Bureau unknown for: {uploaded_file.name}")
                            status.update(label=f"{uploaded_file.name} — Bureau not identified", state="error")
                            st.warning(f"⚠️ **{uploaded_file.name}** — Could not identify the credit bureau. Please verify this is a TransUnion, Experian, or Equifax credit report.")
                            continue

                        bureau_display = bureau.replace('transunion', 'TransUnion').replace('experian', 'Experian').replace('equifax', 'Equifax')
                        try:
                            parsed_data = parse_credit_report_data(full_text, bureau)
                        except Exception as parse_err:
                            diag_store.record_error("parse_credit_report_data", str(parse_err), parse_err)
                            raise

                        status.update(label="Finding errors...", state="running")
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

                        status.update(label="Building your plan...", state="running")
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

                        status.update(label="Building your plan...", state="running")
                        try:
                            report_id = db.save_report(bureau, uploaded_file.name, parsed_data, full_text, user_id=user_id)
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
                        st.session_state._report_uploaded_at = datetime.now().isoformat()

                        try:
                            _sm = compute_strike_metrics(parsed_data)
                            if 'strike_metrics' not in st.session_state:
                                st.session_state['strike_metrics'] = {}
                            st.session_state['strike_metrics'][bureau] = _sm.as_dict()
                        except Exception as _sm_err:
                            print(f"[STRIKE_METRICS_ERROR] {_sm_err}")

                        claims = extract_claims(parsed_data, bureau)
                        st.session_state.extracted_claims[snapshot_key] = claims
    
                        all_claims.extend(claims)
                        reports_processed += 1
    
                        accounts_count = len(parsed_data.get('accounts', []))
                        _startup_logger.info(f"Parse complete: {bureau} — {accounts_count} accounts, {len(claims)} claims, report_id={report_id}")
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

                        status.update(label=f"{bureau_display} report scanned", state="complete")

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

                try:
                    for _rpt_key, _rpt_val in st.session_state.uploaded_reports.items():
                        _v_report_id = _rpt_val.get('report_id')
                        _v_bureau = _rpt_val.get('bureau', 'unknown')
                        if _v_report_id:
                            for _rc in st.session_state.review_claims:
                                _rc_bureau = getattr(_rc, 'bureau', None) or (
                                    _rc.get('bureau') if isinstance(_rc, dict) else None
                                )
                                if _rc_bureau and _rc_bureau.lower() != _v_bureau.lower():
                                    continue
                                _rc_type = getattr(_rc, 'review_type', None)
                                if _rc_type and hasattr(_rc_type, 'value'):
                                    _rc_type = _rc_type.value
                                elif isinstance(_rc, dict):
                                    _rc_type = _rc.get('review_type', 'unknown')
                                _rc_summary = getattr(_rc, 'summary', '') or (
                                    _rc.get('summary', '') if isinstance(_rc, dict) else ''
                                )
                                _rc_evidence = getattr(_rc, 'evidence_summary', None)
                                if _rc_evidence and hasattr(_rc_evidence, 'as_dict'):
                                    _rc_evidence = _rc_evidence.as_dict()
                                elif isinstance(_rc, dict):
                                    _rc_evidence = _rc.get('evidence_summary', {})
                                else:
                                    _rc_evidence = {}
                                _rc_fcra = ''
                                if isinstance(_rc_evidence, dict):
                                    _rc_fcra = _rc_evidence.get('fcra_section', '') or ''
                                db.save_violation(
                                    report_id=_v_report_id,
                                    violation_type=str(_rc_type),
                                    fcra_section=_rc_fcra,
                                    triggering_data=_rc_evidence if isinstance(_rc_evidence, dict) else {},
                                    explanation=_rc_summary,
                                )
                except Exception as _viol_err:
                    print(f"[VIOLATION_SAVE] Error saving violations: {_viol_err}")
    
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

                _round_num_auto = len(st.session_state.get('dispute_rounds', [])) + 1
                review_claims_auto = st.session_state.review_claims

                if _round_num_auto == 1 and review_claims_auto and not is_admin_user:
                    _eligible_auto = [
                        rc for rc in review_claims_auto
                        if rc.review_type != ReviewType.IDENTITY_VERIFICATION
                    ]
                    _total_accts = sum(
                        len(r['parsed_data'].get('accounts', []))
                        for r in st.session_state.uploaded_reports.values()
                    )
                    _total_neg = sum(
                        len(r['parsed_data'].get('negative_items', []))
                        for r in st.session_state.uploaded_reports.values()
                    )

                    if not _eligible_auto:
                        if _total_accts < 3:
                            st.session_state._report_outcome = 'thin'
                        else:
                            st.session_state._report_outcome = 'clean'
                        advance_card("DONE")
                        st.rerun()
                    else:
                        st.session_state._report_outcome = 'disputes_found'
                        for sk_auto, rr_auto in st.session_state.uploaded_reports.items():
                            b_auto = rr_auto.get('bureau', '').lower()
                            if b_auto:
                                st.session_state.identity_confirmed[b_auto] = True

                        has_used_free_auto = auth.has_used_free_letters(user_id)
                        using_free_auto = (user_entitlements.get('letters', 0) == 0 and not has_used_free_auto)
                        all_bureaus_auto = set()
                        for rc in _eligible_auto:
                            b = (rc.entities.get('bureau') or '').lower()
                            if b:
                                all_bureaus_auto.add(b)

                        if using_free_auto:
                            _sorted_auto = sorted(_eligible_auto, key=lambda rc: (
                                0 if hasattr(rc, 'impact_assessment') and rc.impact_assessment and rc.impact_assessment.severity == Severity.HIGH else
                                1 if hasattr(rc, 'impact_assessment') and rc.impact_assessment and rc.impact_assessment.severity == Severity.MODERATE else 2
                            ))
                            bureau_counts_auto = {}
                            st.session_state.battle_plan_items = {}
                            for rc in _sorted_auto:
                                b = (rc.entities.get('bureau') or 'unknown').lower()
                                bureau_counts_auto[b] = bureau_counts_auto.get(b, 0)
                                if bureau_counts_auto[b] < auth.FREE_PER_BUREAU_LIMIT:
                                    st.session_state.battle_plan_items[rc.review_claim_id] = True
                                    bureau_counts_auto[b] += 1
                                else:
                                    st.session_state.battle_plan_items[rc.review_claim_id] = False
                        else:
                            st.session_state.battle_plan_items = {rc.review_claim_id: True for rc in _eligible_auto}

                        selected_auto = [rc for rc in _eligible_auto if st.session_state.battle_plan_items.get(rc.review_claim_id, True)]
                        selected_bureaus_auto = set()
                        for rc in selected_auto:
                            b = (rc.entities.get('bureau') or 'unknown').lower()
                            selected_bureaus_auto.add(b)
                        selected_letter_count_auto = len(selected_bureaus_auto) if selected_bureaus_auto else 1

                        is_free_gen_auto = (using_free_auto and len(selected_auto) > 0)
                        has_letter_ent_auto = is_free_gen_auto or auth.has_entitlement(user_id, 'letters', selected_letter_count_auto)

                        if not has_letter_ent_auto and not is_free_gen_auto:
                            advance_card("SUMMARY")
                            st.rerun()
                        else:
                            gen_id = hashlib.md5(f"{user_id}_1_{len(selected_auto)}_{time.time()}".encode()).hexdigest()[:12]
                            st.session_state.selected_dispute_strategy = "battle_plan"
                            st.session_state.system_error_message = None
                            st.session_state.current_approval = None
                            st.session_state._gen_selected_items = selected_auto
                            st.session_state._gen_review_claims_list = review_claims_auto
                            st.session_state._gen_round_number = 1
                            st.session_state._gen_letter_count_to_deduct = selected_letter_count_auto
                            st.session_state._gen_is_free = is_free_gen_auto
                            st.session_state._gen_free_item_count = len(selected_auto) if is_free_gen_auto else 0
                            st.session_state._gen_free_max_capacity = (auth.FREE_PER_BUREAU_LIMIT * len(all_bureaus_auto)) if is_free_gen_auto else 0
                            st.session_state._gen_id = gen_id
                            st.session_state._gen_completed = False
                            st.session_state._auto_round1 = True
                            _vp_auto = db.get_effective_voice_profile(user_id) if user_id else db.VOICE_PROFILE_DEFAULTS
                            st.session_state._voice_profile = _vp_auto
                            advance_card("GENERATING")
                            st.rerun()
                else:
                    advance_card("SUMMARY")
                    st.rerun()
              except Exception as upload_err:
                st.session_state.pop('_processed_files_sig', None)
                _startup_logger.error(f"Upload processing error: {upload_err}\n{traceback.format_exc()}")
                st.error("Something went wrong while reading your report. Please try again — if it keeps happening, try downloading a fresh copy of your report from the bureau website.")


elif st.session_state.ui_card == "SUMMARY":
  try:
    if _step2_data_ready(st.session_state.uploaded_reports, is_admin_user):
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
            _summary_round = len(st.session_state.get('dispute_rounds', [])) + 1
            disputable_count = 0
            for rc in all_review_claims:
                if rc.review_type == ReviewType.IDENTITY_VERIFICATION:
                    continue
                if _summary_round == 1 and rc.review_type == ReviewType.ACCOUNT_OWNERSHIP:
                    continue
                conf = rc.evidence_summary.claim_confidence_summary if rc.evidence_summary else None
                if not conf or conf.high == 0:
                    continue
                bureau_for_rc = (rc.entities.get('bureau') or '').lower()
                if not bureau_for_rc:
                    disputable_count += 1
                    continue
                identity_block = build_dispute_identity_block(rc, bureau_for_rc)
                if identity_block.is_complete:
                    disputable_count += 1

            _summary_bureaus = set()
            for sk, rr in st.session_state.uploaded_reports.items():
                _summary_bureaus.add((rr.get('bureau') or 'unknown').title())
            _summary_bureau_text = ", ".join(sorted(_summary_bureaus)) if _summary_bureaus else "your bureau"

            if disputable_count > 0:
                st.markdown(
                    f'<div style="text-align:center;padding:2.5rem 1rem 1rem;">'
                    f'<div style="font-size:2.6rem;font-weight:900;color:{TEXT_0};line-height:1.1;margin-bottom:0.75rem;letter-spacing:-0.03em;">'
                    f'<span style="color:{GOLD};">{disputable_count}</span> '
                    f'Error{"s" if disputable_count != 1 else ""} Found.</div>'
                    f'<div style="font-size:1.1rem;color:{TEXT_1};max-width:380px;margin:0 auto;line-height:1.6;">'
                    f'{_summary_bureau_text} &middot; {total_accounts} accounts scanned</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="text-align:center;padding:2.5rem 1rem 1rem;">'
                    f'<div style="font-size:2.6rem;font-weight:900;color:{TEXT_0};line-height:1.1;margin-bottom:0.75rem;letter-spacing:-0.03em;">'
                    f'Your Report<br/>Looks Clean.</div>'
                    f'<div style="font-size:1.1rem;color:{TEXT_1};max-width:380px;margin:0 auto;line-height:1.6;">'
                    f'{total_accounts} accounts on {_summary_bureau_text}. Nothing to dispute.</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        _prev_snapshot = st.session_state.get('_prev_round_snapshot')
        if _prev_snapshot and _prev_snapshot.get('items'):
            from normalization import canonicalize_creditor_name as _canon
            _prev_items = _prev_snapshot['items']
            _prev_round_num = _prev_snapshot.get('round_number', 1)
            _new_accounts = []
            for _sk_cmp, _rr_cmp in st.session_state.uploaded_reports.items():
                _pd_cmp = _rr_cmp.get('parsed_data', {})
                for _acct_cmp in _pd_cmp.get('accounts', []):
                    _raw_cred = _acct_cmp.get('creditor_name') or ''
                    _new_accounts.append({
                        'creditor_canon': _canon(_raw_cred),
                        'creditor_lower': _raw_cred.lower().strip(),
                        'bureau': (_rr_cmp.get('bureau') or 'unknown').lower(),
                        'account_number': (_acct_cmp.get('account_number') or '')[-4:] if _acct_cmp.get('account_number') else '',
                    })
            _new_creditor_keys = set()
            for _na in _new_accounts:
                _new_creditor_keys.add((_na['creditor_canon'], _na['bureau']))
                _new_creditor_keys.add((_na['creditor_canon'], 'any'))
                _new_creditor_keys.add((_na['creditor_lower'], _na['bureau']))
                _new_creditor_keys.add((_na['creditor_lower'], 'any'))
                if _na['account_number']:
                    _new_creditor_keys.add((_na['account_number'], _na['bureau']))

            _removed_items = []
            _still_present = []
            for _pi in _prev_items:
                _pi_raw = (_pi.get('creditor') or '')
                _pi_canon = _pi.get('creditor_canon') or _canon(_pi_raw)
                _pi_lower = _pi_raw.lower().strip()
                _pi_bureau = (_pi.get('bureau') or 'unknown').lower()
                _pi_acct = (_pi.get('account_number') or '')[-4:] if _pi.get('account_number') else ''
                _found = (
                    (_pi_canon, _pi_bureau) in _new_creditor_keys
                    or (_pi_canon, 'any') in _new_creditor_keys
                    or (_pi_lower, _pi_bureau) in _new_creditor_keys
                    or (_pi_lower, 'any') in _new_creditor_keys
                    or (_pi_acct and (_pi_acct, _pi_bureau) in _new_creditor_keys)
                )
                if _found:
                    _still_present.append(_pi)
                else:
                    _removed_items.append(_pi)

            _removed_count = len(_removed_items)
            _still_count = len(_still_present)
            _total_prev = len(_prev_items)

            with st.expander(f"Round {_prev_round_num} Results", expanded=True):
                if _removed_count > 0:
                    _pct = int(100 * _removed_count / _total_prev) if _total_prev > 0 else 0
                    st.markdown(
                        f'<div style="text-align:center;padding:10px 0 8px;">'
                        f'<div style="font-size:1rem;font-weight:700;color:#4CAF50;">'
                        f'&#x2705; {_removed_count} of {_total_prev} items removed ({_pct}% success)</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div style="text-align:center;padding:10px 0 8px;">'
                        f'<div style="font-size:1rem;font-weight:600;color:{GOLD};">'
                        f'All {_total_prev} items still present — Round {_prev_round_num + 1} escalates</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                if _removed_items:
                    st.markdown(
                        f'<div style="font-size:0.88rem;font-weight:600;color:#4CAF50;margin-bottom:8px;">'
                        f'&#x2705; Likely Removed ({_removed_count})</div>',
                        unsafe_allow_html=True,
                    )
                    for _ri in _removed_items:
                        st.markdown(
                            f'<div style="background:rgba(76,175,80,0.06);border-left:3px solid #4CAF50;'
                            f'border-radius:0 8px 8px 0;padding:8px 12px;margin-bottom:6px;">'
                            f'<div style="font-size:0.85rem;color:{TEXT_0};font-weight:600;text-decoration:line-through;opacity:0.7;">'
                            f'{_ri.get("creditor", "Unknown")}</div>'
                            f'<div style="font-size:0.78rem;color:{TEXT_1};">'
                            f'{_ri.get("summary", "")[:80]} — {_ri.get("bureau", "").title()}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                if _still_present:
                    st.markdown(
                        f'<div style="font-size:0.88rem;font-weight:600;color:{GOLD};margin:12px 0 8px 0;">'
                        f'&#x1f504; Still Present ({_still_count}) — Ready for Round {_prev_round_num + 1}</div>',
                        unsafe_allow_html=True,
                    )
                    for _sp in _still_present:
                        st.markdown(
                            f'<div style="background:rgba(212,160,23,0.06);border-left:3px solid {GOLD};'
                            f'border-radius:0 8px 8px 0;padding:8px 12px;margin-bottom:6px;">'
                            f'<div style="font-size:0.85rem;color:{TEXT_0};font-weight:600;">'
                            f'{_sp.get("creditor", "Unknown")}</div>'
                            f'<div style="font-size:0.78rem;color:{TEXT_1};">'
                            f'{_sp.get("summary", "")[:80]} — {_sp.get("bureau", "").title()}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                if _still_count > 0:
                    pass

        if is_admin_user:
          with st.expander("Admin: System Diagnostics", expanded=False):
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
        has_eligible = bool(review_claims_list) and _step2_data_ready(st.session_state.uploaded_reports, is_admin_user)

        if has_eligible:
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

            _id_name = merged_pi.get('name', '')
            _id_addr = merged_pi.get('address', '')
            _id_ssn = merged_pi.get('ssn', '')
            _has_any_id = bool(_id_name or _id_addr or _id_ssn)

            for snapshot_key, report in st.session_state.uploaded_reports.items():
                bureau_key = report.get('bureau', 'unknown').lower()
                bureau_info = all_bureau_infos.get(bureau_key, {})
                has_valid_fields = any(v for v in bureau_info.values() if v)
                if not has_valid_fields:
                    st.session_state.identity_confirmed[bureau_key] = True

            if _has_any_id:
                _id_parts = []
                if _id_name:
                    _id_parts.append(_id_name)
                if _id_addr:
                    _id_parts.append(_id_addr)
                if _id_ssn:
                    _id_parts.append(f"SSN: {_id_ssn}")
                _id_display = " · ".join(_id_parts)

                st.markdown(
                    f'<div style="text-align:center;margin-top:1.5rem;">'
                    f'<div style="font-size:0.92rem;color:{TEXT_0};font-weight:600;line-height:1.5;">{_id_display}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                _all_bureaus_for_confirm = []
                for snapshot_key, report in st.session_state.uploaded_reports.items():
                    bureau_key = report.get('bureau', 'unknown').lower()
                    bureau_info = all_bureau_infos.get(bureau_key, {})
                    if any(v for v in bureau_info.values() if v):
                        _all_bureaus_for_confirm.append(bureau_key)

                if _all_bureaus_for_confirm:
                    _confirm_label = "I confirm this is my credit report"
                    _any_unconfirmed = any(not st.session_state.identity_confirmed.get(bk, False) for bk in _all_bureaus_for_confirm)
                    _all_prev_confirmed = all(st.session_state.identity_confirmed.get(bk, False) for bk in _all_bureaus_for_confirm)

                    identity_confirmed_single = st.checkbox(
                        _confirm_label,
                        value=_all_prev_confirmed,
                        key="identity_confirmation_all"
                    )
                    for bk in _all_bureaus_for_confirm:
                        st.session_state.identity_confirmed[bk] = identity_confirmed_single
                    if not identity_confirmed_single:
                        all_confirmed = False
            else:
                for snapshot_key, report in st.session_state.uploaded_reports.items():
                    bureau_key = report.get('bureau', 'unknown').lower()
                    st.session_state.identity_confirmed[bureau_key] = True

            if st.button("Show My Plan", type="primary", use_container_width=True, key="summary_continue_btn", disabled=not all_confirmed):
                st.session_state.manual_nav_back = False
                advance_card("DISPUTES")
                st.rerun()
        else:
            if st.button("Finish", type="primary", use_container_width=True, key="summary_finish_btn"):
                st.session_state.manual_nav_back = False
                advance_card("DONE")
                st.rerun()
    else:
        st.info(
            "We need a parsed credit report with accounts or inquiries. "
            "Upload a full PDF from Equifax, Experian, or TransUnion."
        )
        if st.button("Go to Upload", type="primary", use_container_width=True, key="summary_back_btn"):
            advance_card("UPLOAD")
            st.rerun()
  except Exception as summary_err:
    st.error(f"Error rendering summary: {summary_err}")
    st.code(traceback.format_exc())

elif st.session_state.ui_card == "PREPARING":
    if not _step2_data_ready(st.session_state.get("uploaded_reports"), is_admin_user):
        st.info(
            "Upload a full bureau credit report PDF first. "
            "Once we extract accounts and inquiries, your dispute plan will appear here."
        )
        if st.button("Go to Upload", type="primary", use_container_width=True, key="preparing_need_upload_btn"):
            advance_card("UPLOAD")
            st.rerun()
    else:
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
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                    min-height:45vh;text-align:center;padding:2rem 1rem;">
            <div style="font-size:3rem;">&#x1f4a1;</div>
            <div style="font-size:1.5rem;font-weight:700;color:{TEXT_0};margin-top:0.75rem;">
                Your dispute plan is ready
            </div>
            <div style="font-size:0.95rem;color:{TEXT_1};max-width:340px;line-height:1.5;margin-top:0.5rem;">
                We analyzed your {bureau_text} reports and found what to dispute.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("See Your Dispute Plan", type="primary", use_container_width=True, key="preparing_continue_btn"):
            advance_card("DISPUTES")
            st.rerun()

elif st.session_state.ui_card == "DISPUTES":
    _disputes_ready = _step2_data_ready(st.session_state.get("uploaded_reports"), is_admin_user)
    if _disputes_ready:
        if st.button("← Back", key="disputes_back_summary"):
            st.session_state.manual_nav_back = True
            advance_card("SUMMARY")
            st.rerun()

    _dispute_round_num = len(st.session_state.get('dispute_rounds', [])) + 1

    if not _disputes_ready:
        st.markdown('<div class="card-title">Your Dispute Plan</div>', unsafe_allow_html=True)
        st.info(
            "Upload a full credit report PDF so we can extract accounts and inquiries. "
            "Personal information alone is not enough to build a dispute plan."
        )
        if st.button("Go to Upload", type="primary", use_container_width=True, key="disputes_go_upload_btn"):
            advance_card("UPLOAD")
            st.rerun()
    else:
        review_claims_list = st.session_state.review_claims

        if not review_claims_list:
            st.markdown('<div class="card-title">Your Dispute Plan</div>', unsafe_allow_html=True)
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
                if round_number == 1 and rc.review_type == ReviewType.ACCOUNT_OWNERSHIP:
                    continue
                if rc.review_claim_id in previously_disputed_ids:
                    continue
                if rc.review_claim_id in _seen_rc_ids:
                    continue
                conf = rc.evidence_summary.claim_confidence_summary if rc.evidence_summary else None
                if not conf or conf.high == 0:
                    continue
                _seen_rc_ids.add(rc.review_claim_id)
                eligible_items.append(rc)

            _CARD_META = {
                ReviewType.NEGATIVE_IMPACT: {"icon": "&#x1F534;", "label": "Negative Mark", "why": "Dragging your score down"},
                ReviewType.DUPLICATE_ACCOUNT: {"icon": "&#x1F4CB;", "label": "Duplicate", "why": "Same account counted twice"},
                ReviewType.ACCURACY_VERIFICATION: {"icon": "&#x26A0;&#xFE0F;", "label": "Wrong Details", "why": "Reported info doesn&#39;t match"},
                ReviewType.UNVERIFIABLE_INFORMATION: {"icon": "&#x2753;", "label": "Unverifiable", "why": "Can&#39;t be confirmed from records"},
                ReviewType.ACCOUNT_OWNERSHIP: {"icon": "&#x1F6AB;", "label": "Not Yours", "why": "Account you don&#39;t recognize"},
            }

            if not eligible_items:
                if previously_disputed_ids:
                    st.markdown(
                        f'<div style="text-align:center;padding:2rem 1rem;">'
                        f'<div style="font-size:3rem;margin-bottom:0.5rem;">&#x2705;</div>'
                        f'<div style="font-size:1.3rem;font-weight:700;color:{TEXT_0};margin-bottom:0.5rem;">All Items Disputed</div>'
                        f'<div style="font-size:0.9rem;color:{TEXT_1};">You\'ve disputed all {len(previously_disputed_ids)} items. Check your letters on the next screen.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div style="text-align:center;padding:2rem 1rem;">'
                        f'<div style="font-size:3rem;margin-bottom:0.5rem;">&#x1f389;</div>'
                        f'<div style="font-size:1.3rem;font-weight:700;color:{TEXT_0};margin-bottom:0.5rem;">Your Reports Look Good</div>'
                        f'<div style="font-size:0.9rem;color:{TEXT_1};">No items need disputing.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            else:
                if _is_demo:
                    current_letter_balance_init = 0
                    has_used_free = False
                    using_free_mode = False
                else:
                    current_letter_balance_init = user_entitlements.get('letters', 0)
                    has_used_free = auth.has_used_free_letters(user_id) if not is_admin_user else False
                    using_free_mode = (current_letter_balance_init == 0 and not has_used_free and not is_admin_user)

                all_bureaus = set()
                for rc in eligible_items:
                    b = (rc.entities.get('bureau') or '').lower()
                    if b:
                        all_bureaus.add(b)

                bureau_acct_caps = {}
                for _sk, _rr in st.session_state.uploaded_reports.items():
                    _b = (_rr.get('bureau') or 'unknown').lower()
                    _pd = _rr.get('parsed_data', {})
                    _acct_count = len(_pd.get('accounts', []))
                    bureau_acct_caps[_b] = max(bureau_acct_caps.get(_b, 0), _acct_count)

                eligible_items.sort(key=lambda _rc: (
                    0 if hasattr(_rc, 'impact_assessment') and _rc.impact_assessment and _rc.impact_assessment.severity == Severity.HIGH else
                    1 if hasattr(_rc, 'impact_assessment') and _rc.impact_assessment and _rc.impact_assessment.severity == Severity.MODERATE else 2
                ))

                _bureau_used = {}
                _capped_eligible = []
                for rc in eligible_items:
                    b = (rc.entities.get('bureau') or 'unknown').lower()
                    cap = bureau_acct_caps.get(b, 999)
                    _bureau_used[b] = _bureau_used.get(b, 0)
                    if _bureau_used[b] < cap:
                        _capped_eligible.append(rc)
                        _bureau_used[b] += 1
                eligible_items = _capped_eligible

                all_bureaus = set()
                for rc in eligible_items:
                    b = (rc.entities.get('bureau') or '').lower()
                    if b:
                        all_bureaus.add(b)

                total_items = len(eligible_items)
                total_letters = len(all_bureaus) if all_bureaus else 1

                if using_free_mode:
                    sorted_eligible = sorted(eligible_items, key=lambda rc: (
                        0 if hasattr(rc, 'impact_assessment') and rc.impact_assessment and rc.impact_assessment.severity == Severity.HIGH else
                        1 if hasattr(rc, 'impact_assessment') and rc.impact_assessment and rc.impact_assessment.severity == Severity.MODERATE else 2
                    ))

                if 'battle_plan_items' not in st.session_state:
                    if using_free_mode:
                        bureau_counts = {}
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

                bureau_names_sorted = sorted(b.title() for b in selected_bureaus) if selected_bureaus else ["the bureau"]
                bureau_display = " & ".join(bureau_names_sorted) if len(bureau_names_sorted) <= 2 else ", ".join(bureau_names_sorted[:-1]) + " & " + bureau_names_sorted[-1]
                _round_label = f"Round {round_number}" if round_number > 1 else ""

                _free_badge = ' <span style="font-size:0.6em;vertical-align:middle;background:#66BB6A;color:#fff;padding:2px 8px;border-radius:4px;font-weight:700;">FREE</span>' if is_free_generation else ''

                _strategy_cache_key = '_disputes_ai_strategy'
                if _strategy_cache_key not in st.session_state:
                    try:
                        from dispute_strategy import build_ai_strategy
                        _ai_strat = build_ai_strategy(review_claims_list, round_size=len(selected_items), excluded_ids=previously_disputed_ids)
                        st.session_state[_strategy_cache_key] = _ai_strat
                    except Exception:
                        st.session_state[_strategy_cache_key] = None
                _cached_strategy = st.session_state.get(_strategy_cache_key)

                items_by_type = {}
                for rc in selected_items:
                    rt = rc.review_type
                    if rt not in items_by_type:
                        items_by_type[rt] = []
                    items_by_type[rt].append(rc)

                _neg_count = len(items_by_type.get(ReviewType.NEGATIVE_IMPACT, []))
                _dup_count = len(items_by_type.get(ReviewType.DUPLICATE_ACCOUNT, []))
                _high_impact_count = sum(
                    1 for rc in selected_items
                    if hasattr(rc, 'impact_assessment') and rc.impact_assessment and rc.impact_assessment.severity == Severity.HIGH
                )
                if _high_impact_count == 0:
                    _high_impact_count = selected_count

                _chip_html = (
                    f'<span class="gc-chip gc-chip-major">{_high_impact_count} High Impact</span>'
                    + (f'<span class="gc-chip gc-chip-score">{_neg_count} Score-Damaging</span>' if _neg_count > 0 else '')
                    + (f'<span class="gc-chip gc-chip-dup">{_dup_count} Duplicate{"s" if _dup_count != 1 else ""}</span>' if _dup_count > 0 else '')
                )
                st.markdown(
                    f'<div class="gc-header">'
                    f'<div class="gc-title"><span class="gc-accent">{selected_count}</span> Reporting Error{"s" if selected_count != 1 else ""} Found{_free_badge}</div>'
                    f'<div class="gc-chips">{_chip_html}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                _CARD_WHY = {
                    ReviewType.NEGATIVE_IMPACT: "These can suppress your score and approvals.",
                    ReviewType.ACCURACY_VERIFICATION: "Inconsistent data can trigger verification penalties.",
                    ReviewType.DUPLICATE_ACCOUNT: "Double-reporting can cause double damage.",
                    ReviewType.UNVERIFIABLE_INFORMATION: "Unconfirmed records weaken your file.",
                    ReviewType.ACCOUNT_OWNERSHIP: "Accounts you don&#39;t recognize on your file.",
                }

                _type_order = [
                    ReviewType.NEGATIVE_IMPACT,
                    ReviewType.ACCURACY_VERIFICATION,
                    ReviewType.DUPLICATE_ACCOUNT,
                    ReviewType.UNVERIFIABLE_INFORMATION,
                    ReviewType.ACCOUNT_OWNERSHIP,
                ]

                for rt in _type_order:
                    if rt not in items_by_type:
                        continue
                    type_items = items_by_type[rt]
                    meta = _CARD_META.get(rt, {"icon": "&#x2022;", "label": "Dispute Item", "why": "Needs correction"})
                    impact_why = _CARD_WHY.get(rt, meta["why"])

                    acct_entries = []
                    for rc in type_items:
                        name = (
                            rc.entities.get('account_name', '') or
                            rc.entities.get('creditor', '') or
                            rc.entities.get('_extracted_creditor', '') or
                            rc.entities.get('furnisher', '') or
                            rc.entities.get('inquirer', '') or
                            rc.entity or 'Account'
                        )
                        bureau = (rc.entities.get('bureau') or '').title()
                        acct_entries.append((name, bureau))

                    _max_visible = 6
                    _visible = acct_entries[:_max_visible]
                    _overflow_n = len(acct_entries) - _max_visible

                    _acct_li = ""
                    for _name, _bur in _visible:
                        _bur_html = f'<span class="gc-acct-bureau">{_bur}</span>' if _bur else ''
                        _acct_li += f'<li><span class="gc-acct-dot"></span>{_name}{_bur_html}</li>'
                    if _overflow_n > 0:
                        _acct_li += f'<li class="gc-more">+ {_overflow_n} more</li>'

                    _expand_key = f"gc_expand_{rt.name}"
                    _is_open = st.session_state.get(f"_{_expand_key}_open", False)

                    _expand_html = ""
                    if _is_open:
                        _expand_html = f'<div class="gc-card-expand"><ul class="gc-acct-list">{_acct_li}</ul></div>'

                    _card_html = (
                        f'<div class="gc-card">'
                        f'<div class="gc-card-top">'
                        f'<div class="gc-card-icon">{meta["icon"]}</div>'
                        f'<div class="gc-card-info">'
                        f'<div class="gc-card-name">{meta["label"]}</div>'
                        f'<div class="gc-card-why">{impact_why}</div>'
                        f'</div>'
                        f'<div class="gc-card-right">'
                        f'<div class="gc-card-count">{len(type_items)}</div>'
                        f'<div class="gc-card-count-label">accounts</div>'
                        f'</div>'
                        f'</div>'
                        f'{_expand_html}'
                        f'</div>'
                    )
                    st.markdown(_card_html, unsafe_allow_html=True)

                    _btn_label = f"Hide Accounts" if _is_open else f"View Accounts ({len(type_items)})"
                    if st.button(_btn_label, key=_expand_key, type="secondary"):
                        st.session_state[f"_{_expand_key}_open"] = not _is_open
                        st.rerun()

                if _cached_strategy and _cached_strategy.round_summary:
                    st.markdown(
                        f'<div style="text-align:center;font-size:0.85rem;color:{TEXT_1};margin:10px 0 4px;font-style:italic;">'
                        f'{_cached_strategy.round_summary}</div>',
                        unsafe_allow_html=True,
                    )

                _ccp_cache_key = '_credit_command_plan'
                if _ccp_cache_key not in st.session_state:
                    from credit_command_plan import build_credit_command_plan
                    st.session_state[_ccp_cache_key] = build_credit_command_plan(
                        items_by_type=items_by_type,
                        selected_count=selected_count,
                        bureaus=selected_bureaus,
                        parsed_reports=st.session_state.uploaded_reports,
                    )
                _ccp = st.session_state[_ccp_cache_key]

                _ccp_open_key = '_ccp_section_open'
                _ccp_is_open = st.session_state.get(_ccp_open_key, False)
                _ccp_toggle_label = "Hide 72-Hour Plan" if _ccp_is_open else "View 72-Hour Plan"
                if st.button(_ccp_toggle_label, key="ccp_toggle_btn", type="secondary"):
                    st.session_state[_ccp_open_key] = not _ccp_is_open
                    st.rerun()

                if _ccp_is_open:
                    from credit_command_plan import render_command_plan_html
                    _ccp_colors = {"TEXT_0": TEXT_0, "TEXT_1": TEXT_1, "GOLD": GOLD, "BG_1": BG_1, "BORDER": BORDER}
                    st.markdown(render_command_plan_html(_ccp, _ccp_colors), unsafe_allow_html=True)

                if using_free_mode:
                    free_selected = [rc for rc in eligible_items if st.session_state.battle_plan_items.get(rc.review_claim_id, False)]
                    free_remaining = [rc for rc in eligible_items if not st.session_state.battle_plan_items.get(rc.review_claim_id, False)]
                    extra_items = len(free_remaining)

                    if extra_items > 0:
                        st.markdown(
                            f'<div style="background:linear-gradient(135deg, rgba(212,160,23,0.08), rgba(212,160,23,0.02));'
                            f'border:1px solid rgba(212,160,23,0.3);border-radius:10px;padding:14px 18px;margin:8px 0 16px;text-align:center;">'
                            f'<div style="font-size:0.92rem;font-weight:600;color:{TEXT_0};margin-bottom:4px;">'
                            f'{extra_items} more item{"s" if extra_items != 1 else ""} available with upgrade</div>'
                            f'<div style="font-size:0.82rem;color:{TEXT_1};line-height:1.5;">'
                            f'Free plan includes {auth.FREE_PER_BUREAU_LIMIT} items per bureau. Upgrade to dispute everything.</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        render_purchase_options(context="disputes_letters", needed_letters=total_letters)

                if round_number > 1:
                    st.markdown(
                        f'<div style="font-size:0.82rem;color:{TEXT_1};text-align:center;margin-bottom:8px;">'
                        f'{len(previously_disputed_ids)} items disputed in previous rounds</div>',
                        unsafe_allow_html=True,
                    )

                if free_limit_exceeded:
                    exceeded_details = ", ".join(
                        f"{b.title()} ({c} selected, max {auth.FREE_PER_BUREAU_LIMIT})" for b, c in free_exceeded_bureaus
                    )
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg, rgba(212,160,23,0.10), rgba(212,160,23,0.03));'
                        f'border:1px solid {GOLD};border-radius:10px;padding:12px 16px;margin-bottom:12px;text-align:center;">'
                        f'<div style="font-size:0.88rem;color:{TEXT_0};font-weight:600;margin-bottom:4px;">'
                        f'Too many items for free plan</div>'
                        f'<div style="font-size:0.82rem;color:{TEXT_1};line-height:1.4;">'
                        f'{exceeded_details}.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    render_purchase_options(context="disputes_letters", needed_letters=selected_letter_count)

                if _is_demo:
                    is_free_round3 = False
                    has_letter_ent = False
                    current_letter_balance = 0
                else:
                    is_free_round3 = (round_number >= 3 and db.check_free_round_eligible(user_id))
                    has_letter_ent = is_admin_user or is_free_generation or is_free_round3 or auth.has_entitlement(user_id, 'letters', selected_letter_count)
                    current_letter_balance = user_entitlements.get('letters', 0)

                if is_free_round3:
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg, rgba(102,187,106,0.12), rgba(102,187,106,0.03));'
                        f'border:1px solid #66BB6A;border-radius:10px;padding:14px 16px;margin-bottom:8px;text-align:center;">'
                        f'<div style="font-size:0.92rem;font-weight:700;color:#66BB6A;">2-Round Guarantee Active &mdash; This round is free</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                if not _is_demo and not has_letter_ent and selected_count > 0:
                    st.markdown(
                        f'<div style="text-align:center;font-size:0.88rem;color:{TEXT_1};margin-bottom:8px;">'
                        f'Unlock your letters to continue.</div>',
                        unsafe_allow_html=True,
                    )
                    render_purchase_options(context="disputes_letters", needed_letters=selected_letter_count)

                st.markdown(
                    f'<div class="gc-sticky-cta">'
                    f'<div class="gc-cta-selected">{selected_count} item{"s" if selected_count != 1 else ""} selected &middot; {bureau_display}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if _is_demo:
                    _demo_show_letter = st.button("Preview Sample Letter", type="primary", use_container_width=True, key="demo_preview_letter_btn")
                    if _demo_show_letter:
                        st.session_state._demo_show_sample_letter = True
                        st.rerun()
                    if st.session_state.get('_demo_show_sample_letter'):
                        from demo_data import DEMO_SAMPLE_LETTER_HTML
                        st.markdown(
                            f'<div style="margin:16px 0;border-radius:10px;overflow:hidden;background:#fff;color:#111 !important;box-shadow:0 2px 12px rgba(0,0,0,0.3);">{DEMO_SAMPLE_LETTER_HTML}</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f'<div style="background:linear-gradient(135deg,rgba(212,160,23,0.12),rgba(212,160,23,0.04));'
                            f'border:1px solid rgba(212,160,23,0.3);border-radius:10px;padding:16px 20px;margin:12px 0;text-align:center;">'
                            f'<div style="font-size:1rem;font-weight:700;color:{TEXT_0};margin-bottom:6px;">'
                            f'Want letters like this for YOUR report?</div>'
                            f'<div style="font-size:0.85rem;color:{TEXT_1};margin-bottom:12px;">'
                            f'Upload your credit report and get personalized dispute letters in minutes.</div>'
                            f'<a href="/?nav=signup" target="_self" style="display:inline-block;background:{GOLD};color:#000;'
                            f'padding:10px 28px;border-radius:8px;font-weight:700;font-size:0.9rem;text-decoration:none;">'
                            f'Sign Up Free &rarr;</a></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    gen_btn_label = "Generate My Free Dispute Letters" if is_free_generation else "Generate Dispute Letters"
                    if st.button(gen_btn_label, type="primary", use_container_width=True, key="battle_plan_generate_btn", disabled=(selected_count == 0 or not has_letter_ent or free_limit_exceeded)):
                        gen_id = hashlib.md5(f"{user_id}_{round_number}_{selected_count}_{time.time()}".encode()).hexdigest()[:12]
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
                        try:
                            from services.workflow import hooks as workflow_hooks

                            workflow_hooks.notify_review_claims_completed(
                                user_id,
                                item_count=len(review_claims_list),
                            )
                            workflow_hooks.notify_select_disputes_completed(
                                user_id,
                                selected_count=selected_count,
                                bureaus=list(selected_bureaus),
                            )
                        except Exception:
                            pass
                        _vp_exists = db.load_voice_profile(user_id) if user_id else None
                        if _vp_exists:
                            st.session_state._voice_profile = db.get_effective_voice_profile(user_id)
                            advance_card("GENERATING")
                        else:
                            advance_card("VOICE_PROFILE")
                        st.rerun()

elif st.session_state.ui_card == "VOICE_PROFILE":
    st.markdown(f"""
    <div style="text-align:center;padding:1.5rem 1rem 0.5rem;">
        <div style="font-size:1.3rem;font-weight:700;color:{TEXT_0};">Customize Your Letters</div>
        <div style="color:{TEXT_1};font-size:0.85rem;margin-top:0.25rem;">Choose tone and sign. Legal facts stay the same.</div>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        vp_tone = st.radio(
            "Tone",
            ["Calm & Professional", "Firm & Direct", "Short & Concise"],
            index=0,
            key="vp_tone",
            horizontal=True,
        )

        vp_detail = st.radio(
            "Detail Level",
            ["Minimal", "Standard", "Detailed"],
            index=1,
            key="vp_detail",
            horizontal=True,
        )

        vp_closing = st.selectbox(
            "Closing Sign-off",
            ["Sincerely,", "Respectfully,", "Thank you,"],
            index=0,
            key="vp_closing",
        )

        with st.expander("Preferred Phrases (optional)"):
            vp_dispute = st.selectbox(
                "Dispute verb",
                [
                    "I dispute the accuracy of…",
                    "I am challenging the accuracy of…",
                    "This information is inaccurate and must be corrected…",
                ],
                index=0,
                key="vp_dispute_phrase",
            )

            vp_request = st.selectbox(
                "Request verb",
                [
                    "Please investigate and correct or delete…",
                    "I request reinvestigation and correction/removal…",
                    "Please verify, update, or remove…",
                ],
                index=0,
                key="vp_request_phrase",
            )

            vp_verify = st.selectbox(
                "Verification phrase",
                [
                    "Provide the method of verification…",
                    "Provide how this was verified…",
                    "Provide verification procedures used…",
                ],
                index=0,
                key="vp_verify_phrase",
            )

        st.markdown(f"""
        <div style="margin-top:1rem;text-align:center;">
            <div style="font-size:1rem;font-weight:700;color:{TEXT_0};">Sign Your Letters</div>
            <div style="font-size:0.82rem;color:{TEXT_1};margin-top:0.2rem;">Draw your signature below.</div>
        </div>
        """, unsafe_allow_html=True)

        _existing_sig = None
        if user_id:
            try:
                _existing_sig = db.get_user_signature(user_id)
            except Exception:
                pass

        from ui.signature_pad import render_signature_pad
        _sig_result = render_signature_pad(existing_signature=_existing_sig)

        _vp_cols = st.columns([1, 1])
        with _vp_cols[0]:
            if st.button("Save & Build Letters", key="vp_save", type="primary", use_container_width=True):
                _vp_data = {
                    'tone': vp_tone,
                    'detail_level': vp_detail,
                    'closing': vp_closing,
                    'preferred_phrases': {
                        'dispute': vp_dispute,
                        'request': vp_request,
                        'verify': vp_verify,
                    },
                }
                if user_id:
                    try:
                        db.save_voice_profile(user_id, _vp_data)
                    except Exception:
                        pass
                    if _sig_result:
                        try:
                            import base64 as _sig_b64
                            _sig_raw = _sig_result
                            if isinstance(_sig_raw, str):
                                if ',' in _sig_raw:
                                    _sig_raw = _sig_raw.split(',', 1)[1]
                                _sig_bytes = _sig_b64.b64decode(_sig_raw)
                            else:
                                _sig_bytes = _sig_raw
                            db.save_user_signature(user_id, _sig_bytes)
                            st.session_state['_user_signature_bytes'] = _sig_bytes
                        except Exception:
                            pass
                    elif _existing_sig:
                        st.session_state['_user_signature_bytes'] = _existing_sig
                st.session_state._voice_profile = db.get_effective_voice_profile(user_id) if user_id else _vp_data
                advance_card("GENERATING")
                st.rerun()
        with _vp_cols[1]:
            if st.button("Skip signature", key="vp_skip", use_container_width=True):
                st.session_state._voice_profile = db.VOICE_PROFILE_DEFAULTS
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
                            creditor_display = (
                                rc_l.entities.get('account_name') or
                                rc_l.entities.get('creditor') or
                                rc_l.entities.get('_extracted_creditor') or
                                rc_l.entities.get('furnisher') or
                                rc_l.entities.get('inquirer') or
                                rc_l.entity or
                                'Account'
                            )
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
                            _vp_gen = st.session_state.get('_voice_profile')
                            letter_data = generate_round1_letter(bureau_lower_r1, consumer_info, items_r1, voice_profile=_vp_gen)
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
                    bureau_round2_items = {}
                    for candidate in final_selected:
                        target_type, creditor_norm, bureau_code = candidate.letter_key
                        bureau_lower_r2 = {"EQ": "equifax", "EX": "experian", "TU": "transunion"}.get(bureau_code, bureau_code.lower())
                        for claim_id in candidate.claims:
                            rc_r2 = rc_map.get(claim_id)
                            if rc_r2:
                                if bureau_lower_r2 not in bureau_round2_items:
                                    bureau_round2_items[bureau_lower_r2] = []
                                rt_val = rc_r2.review_type.value if hasattr(rc_r2.review_type, 'value') else str(rc_r2.review_type)
                                ct_val = ''
                                merged_fields = {}
                                if rc_r2.supporting_claim_ids:
                                    snapshot_key_ct = next(
                                        (k for k, r in st.session_state.uploaded_reports.items()
                                         if r.get('bureau', '').lower() == bureau_lower_r2), None)
                                    if snapshot_key_ct:
                                        raw_claims_ct = st.session_state.extracted_claims.get(snapshot_key_ct, [])
                                        for rc_claim in raw_claims_ct:
                                            if rc_claim.claim_id in rc_r2.supporting_claim_ids:
                                                if not ct_val:
                                                    ct_val = rc_claim.claim_type.value if hasattr(rc_claim.claim_type, 'value') else str(rc_claim.claim_type)
                                                if hasattr(rc_claim, 'fields') and rc_claim.fields:
                                                    for fk, fv in rc_claim.fields.items():
                                                        if fv and fk not in merged_fields:
                                                            merged_fields[fk] = fv
                                bureau_round2_items[bureau_lower_r2].append({
                                    'entities': dict(rc_r2.entities) if rc_r2.entities else {},
                                    'fields': merged_fields,
                                    'claim_type': ct_val,
                                    'review_type': rt_val,
                                    'rc_id': claim_id,
                                })

                    for bureau_lower_r2, items_r2 in bureau_round2_items.items():
                        if not items_r2:
                            continue
                        consumer_info = bureau_consumer_info.get(bureau_lower_r2, {})
                        try:
                            _vp_gen_r2 = st.session_state.get('_voice_profile')
                            letter_data = generate_round2_letter(bureau_lower_r2, consumer_info, items_r2, round_number=round_number_gen, voice_profile=_vp_gen_r2)
                        except Exception as r2_err:
                            print(f"[ROUND2_LETTER_ERROR] {r2_err}")
                            continue

                        letter_text = letter_data.get('letter_text', '')
                        if not forbidden_assertions_scan(letter_text):
                            continue

                        letter_data['rc_details'] = bureau_rc_details.get(bureau_lower_r2, [])
                        letters_generated[bureau_lower_r2] = letter_data

                        report_data = bureau_report_data.get(bureau_lower_r2)
                        report_id_val = (report_data or {}).get('report_id')
                        if report_id_val:
                            try:
                                uid = current_user.get('user_id')
                                db.save_letter(
                                    report_id_val,
                                    letter_data['letter_text'],
                                    bureau_lower_r2,
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
                    is_sprint_free_r3 = (round_number_gen >= 3 and db.check_free_round_eligible(user_id))
                    if is_sprint_free_r3 and not is_admin_user:
                        db.use_free_round(user_id)
                        db.log_activity(user_id, 'free_round3', 'Sprint guarantee Round 3 used', 'GENERATING')
                    elif is_free_gen and not is_admin_user:
                        if not auth.spend_free_letters(user_id, free_item_count, max_capacity=free_max_cap if free_max_cap > 0 else None):
                            st.session_state._letter_spend_failed = True
                    elif not is_admin_user and letter_deduct_count > 0:
                        if auth.spend_entitlement(user_id, 'letters', letter_deduct_count):
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
                    st.session_state._letters_generated_at = datetime.now().isoformat()
                    db.log_activity(user_id, 'generate_letters', f"{len(letters_generated)} letter(s) for {', '.join(b.title() for b in letters_generated.keys())}", 'GENERATING')

                    try:
                        from services.workflow import hooks as workflow_hooks

                        workflow_hooks.notify_letter_generation_completed(
                            user_id,
                            list(letters_generated.keys()),
                        )
                    except Exception:
                        pass

                    try:
                        _ul_token = db.get_or_create_upload_token(user_id)
                        if _ul_token and current_user.get('email'):
                            import os as _ul_os
                            _ul_host = _ul_os.environ.get('REPLIT_DEPLOYMENT_URL') or _ul_os.environ.get('REPLIT_DEV_DOMAIN', '')
                            if _ul_host and not _ul_host.startswith('http'):
                                _ul_base = f"https://{_ul_host}"
                            elif _ul_host:
                                _ul_base = _ul_host
                            else:
                                _ul_base = "https://850lab.replit.app"
                            _ul_url = f"{_ul_base}/?upload={_ul_token}"
                            st.session_state._upload_link = _ul_url
                            st.session_state._upload_token = _ul_token
                            from resend_client import send_upload_link_email
                            send_upload_link_email(
                                to_email=current_user['email'],
                                display_name=current_user.get('display_name'),
                                upload_url=_ul_url,
                                letter_count=len(letters_generated),
                                bureau_names=[b.title() for b in letters_generated.keys()],
                            )
                    except Exception as _ul_err:
                        print(f"[UPLOAD_LINK] Email send failed: {_ul_err}")

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
        _was_auto = st.session_state.pop('_auto_round1', False)
        if gen_error_msg == "exception":
            st.session_state.system_error_message = SYSTEM_ERROR_UI_STATE
            advance_card("DISPUTES")
            st.rerun()
        elif gen_error_msg == "no_letters":
            if _was_auto:
                st.session_state._report_outcome = 'clean'
                advance_card("DONE")
            else:
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
    @keyframes ready-fade {{
        0% {{ opacity: 0; transform: translateY(15px); }}
        100% {{ opacity: 1; transform: translateY(0); }}
    }}
    .ready-step {{
        display: flex; align-items: center; gap: 12px;
        padding: 14px 16px; margin: 6px 0;
        background: {BG_1}; border: 1px solid {BORDER};
        border-radius: 12px; opacity: 0;
    }}
    .ready-step-done {{
        border-color: #2ecc71;
        background: linear-gradient(135deg, rgba(46,204,113,0.08), rgba(46,204,113,0.02));
    }}
    .ready-step-next {{
        border-color: {GOLD};
        background: linear-gradient(135deg, rgba(212,160,23,0.10), rgba(212,160,23,0.04));
    }}
    .ready-step-num {{
        width: 32px; height: 32px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.85rem; font-weight: 800; flex-shrink: 0;
    }}
    .ready-step-done .ready-step-num {{ background: #2ecc71; color: #fff; }}
    .ready-step-next .ready-step-num {{ background: {GOLD}; color: #1a1a1f; }}
    .ready-step:not(.ready-step-done):not(.ready-step-next) .ready-step-num {{
        background: {BG_2}; color: {TEXT_1}; border: 1px solid {BORDER};
    }}
    .ready-step-text {{ font-size: 0.88rem; font-weight: 600; color: {TEXT_0}; }}
    .ready-step-sub {{ font-size: 0.75rem; color: {TEXT_1}; margin-top: 2px; }}
    </style>
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                min-height:55vh;text-align:center;padding:2rem 1rem;max-width:420px;margin:0 auto;">
        <div style="font-size:2.5rem;opacity:0;animation:ready-fade 0.5s ease-out 0.2s forwards;">&#x1F4E8;</div>
        <div style="font-size:1.4rem;font-weight:800;color:{TEXT_0};margin-top:0.8rem;
                    opacity:0;animation:ready-fade 0.5s ease-out 0.4s forwards;">
            {letter_count} letter{"s" if letter_count != 1 else ""} built for {bureau_display}
        </div>
        <div style="font-size:0.92rem;color:{TEXT_1};margin-top:0.5rem;line-height:1.5;
                    opacity:0;animation:ready-fade 0.5s ease-out 0.6s forwards;">
            Your letters are not sent yet. Here is what to do next.
        </div>
        <div style="width:100%;margin-top:1.2rem;text-align:left;">
            <div class="ready-step ready-step-done" style="animation:ready-fade 0.4s ease-out 0.8s forwards;">
                <div class="ready-step-num">&#x2713;</div>
                <div><div class="ready-step-text">Letters Built</div>
                <div class="ready-step-sub">{letter_count} letter{"s" if letter_count != 1 else ""} with legal citations</div></div>
            </div>
            <div class="ready-step ready-step-next" style="animation:ready-fade 0.4s ease-out 1.0s forwards;">
                <div class="ready-step-num">2</div>
                <div><div class="ready-step-text">Upload Your ID &amp; Address Proof</div>
                <div class="ready-step-sub">Bureaus need these or they can reject your dispute</div></div>
            </div>
            <div class="ready-step" style="animation:ready-fade 0.4s ease-out 1.2s forwards;">
                <div class="ready-step-num">3</div>
                <div><div class="ready-step-text">Send via Certified Mail</div>
                <div class="ready-step-sub">We print, mail, and track it for you</div></div>
            </div>
            <div class="ready-step" style="animation:ready-fade 0.4s ease-out 1.4s forwards;">
                <div class="ready-step-num">4</div>
                <div><div class="ready-step-text">Track Delivery</div>
                <div class="ready-step-sub">30-day investigation clock starts when they get it</div></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.get('_auto_round1'):
        advance_card("DONE")
        st.session_state._auto_round1 = False
        st.query_params['page'] = 'proof'
        st.rerun()
    else:
        st.markdown(f'<div style="opacity:0;animation:ready-fade 0.4s ease-out 1.6s forwards;max-width:420px;margin:8px auto 0;">', unsafe_allow_html=True)
        if st.button("Next: Upload Your Documents \u2192", type="primary", use_container_width=True, key="letters_ready_continue_btn"):
            advance_card("DONE")
            st.query_params['page'] = 'proof'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        _lr_upload_link = st.session_state.get('_upload_link')
        if _lr_upload_link:
            st.markdown(f'''
            <div style="opacity:0;animation:ready-fade 0.4s ease-out 1.8s forwards;max-width:420px;margin:12px auto 0;
                        padding:12px 16px;background:{BG_1};border:1px solid {BORDER};border-radius:10px;text-align:center;">
                <div style="font-size:0.78rem;color:{TEXT_1};margin-bottom:6px;">
                    We also sent an upload link to your email. You can share it:
                </div>
                <code style="font-size:0.7rem;color:{GOLD};word-break:break-all;">{_lr_upload_link}</code>
            </div>
            ''', unsafe_allow_html=True)
            import streamlit.components.v1 as _lr_comp
            _lr_comp.html(f'''
            <div style="max-width:420px;margin:6px auto 0;opacity:0;animation:ready-fade 0.4s ease-out 2.0s forwards;">
            <style>@keyframes ready-fade {{0%{{opacity:0;transform:translateY(15px);}}100%{{opacity:1;transform:translateY(0);}}}}</style>
            <button onclick="copyUL()" id="copyULBtn" style="width:100%;padding:10px 16px;
                background:{BG_2};border:1px solid rgba(212,160,23,0.25);color:{GOLD};
                font-weight:600;font-size:0.85rem;border-radius:8px;cursor:pointer;
                font-family:'Inter',-apple-system,sans-serif;transition:all 0.15s ease;">
                &#x1F4CB; Copy Upload Link</button>
            </div>
            <script>
            function copyUL(){{
                var link="{_lr_upload_link}";
                if(navigator.clipboard){{
                    navigator.clipboard.writeText(link).then(function(){{
                        document.getElementById('copyULBtn').innerHTML='&#x2705; Copied!';
                        setTimeout(function(){{document.getElementById('copyULBtn').innerHTML='&#x1F4CB; Copy Upload Link';}},2000);
                    }});
                }} else {{
                    var t=document.createElement('textarea');t.value=link;
                    document.body.appendChild(t);t.select();document.execCommand('copy');
                    document.body.removeChild(t);
                    document.getElementById('copyULBtn').innerHTML='&#x2705; Copied!';
                    setTimeout(function(){{document.getElementById('copyULBtn').innerHTML='&#x1F4CB; Copy Upload Link';}},2000);
                }}
            }}
            </script>
            ''', height=50)

elif st.session_state.ui_card == "DONE":
    if _is_demo:
        advance_card("DISPUTES")
        st.rerun()
    if st.session_state.get('_ui_state_restored') and not st.session_state.get('generated_letters'):
        try:
            _reload_uid = (current_user or {}).get('id') or (current_user or {}).get('user_id')
            if _reload_uid:
                _db_letters = db.get_latest_letters_for_user(_reload_uid)
                if _db_letters:
                    _restored_letters = {}
                    for _rl_b, _rl_data in _db_letters.items():
                        if _rl_data.get('letter_text'):
                            _restored_letters[_rl_b] = {
                                'letter_text': _rl_data['letter_text'],
                                'bureau': _rl_b,
                                'rc_details': [],
                            }
                    if _restored_letters:
                        st.session_state.generated_letters = _restored_letters
                        st.session_state._gen_letters_count = len(_restored_letters)
                        st.session_state._gen_bureau_names = [b.title() for b in _restored_letters.keys()]
                        st.session_state._gen_completed = True
                        st.session_state._letters_generated_at = datetime.now().isoformat()
                    else:
                        st.session_state.ui_card = "UPLOAD"
                        st.session_state._ui_state_restored = False
                        st.rerun()
                else:
                    st.session_state.ui_card = "UPLOAD"
                    st.session_state._ui_state_restored = False
                    st.rerun()
        except Exception:
            st.session_state.ui_card = "UPLOAD"
            st.session_state._ui_state_restored = False
            st.rerun()

    _report_outcome = st.session_state.get('_report_outcome', '')

    if _report_outcome == 'clean':
        st.markdown(
            f'<div style="text-align:center;padding:3rem 1rem;">'
            f'<div style="font-size:3rem;margin-bottom:1rem;">&#x2705;</div>'
            f'<div style="font-size:1.5rem;font-weight:700;color:{TEXT_0};margin-bottom:0.5rem;">Your Credit Report Looks Good</div>'
            f'<div style="font-size:1rem;color:{TEXT_1};max-width:440px;margin:0 auto;line-height:1.6;">'
            f'We analyzed your report and didn\'t find any items that need disputing. '
            f'Everything appears to be reporting accurately.'
            f'</div>'
            f'<div style="margin-top:2rem;background:{BG_1};border-radius:12px;padding:1.5rem;max-width:440px;margin-left:auto;margin-right:auto;">'
            f'<div style="font-size:1rem;font-weight:600;color:{TEXT_0};margin-bottom:0.5rem;">What you can do</div>'
            f'<div style="font-size:0.9rem;color:{TEXT_1};line-height:1.6;text-align:left;">'
            f'&#8226; Keep paying bills on time<br/>'
            f'&#8226; Keep credit utilization below 30%<br/>'
            f'&#8226; Avoid opening too many new accounts<br/>'
            f'&#8226; Check your report again in 3-6 months'
            f'</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Upload a Different Report", type="primary", use_container_width=True, key="clean_upload_again"):
            reset_analysis_state(full=True)
            advance_card("UPLOAD")
            st.rerun()

    elif _report_outcome == 'thin':
        st.markdown(
            f'<div style="text-align:center;padding:3rem 1rem;">'
            f'<div style="font-size:3rem;margin-bottom:1rem;">&#x1f4c4;</div>'
            f'<div style="font-size:1.5rem;font-weight:700;color:{TEXT_0};margin-bottom:0.5rem;">Your Credit File Is Thin</div>'
            f'<div style="font-size:1rem;color:{TEXT_1};max-width:440px;margin:0 auto;line-height:1.6;">'
            f'Your report has very few accounts, which means there isn\'t much to dispute. '
            f'The best path forward is building your credit history.'
            f'</div>'
            f'<div style="margin-top:2rem;background:{BG_1};border-radius:12px;padding:1.5rem;max-width:440px;margin-left:auto;margin-right:auto;">'
            f'<div style="font-size:1rem;font-weight:600;color:{TEXT_0};margin-bottom:0.5rem;">How to build credit</div>'
            f'<div style="font-size:0.9rem;color:{TEXT_1};line-height:1.6;text-align:left;">'
            f'&#8226; Open a secured credit card<br/>'
            f'&#8226; Become an authorized user on a family member\'s card<br/>'
            f'&#8226; Use a credit-builder loan<br/>'
            f'&#8226; Keep accounts open and active<br/>'
            f'&#8226; Check your report again in 3-6 months'
            f'</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Upload a Different Report", type="primary", use_container_width=True, key="thin_upload_again"):
            reset_analysis_state(full=True)
            advance_card("UPLOAD")
            st.rerun()

    else:
        if st.session_state.uploaded_reports:
            if st.button("\u2190 Back to Dispute Plan", key="done_back_disputes"):
                st.session_state.manual_nav_back = True
                advance_card("DISPUTES")
                st.rerun()

        if st.session_state.pop('_letter_spend_failed', False):
            st.warning("Your letters were generated, but we couldn't deduct the credits. Your balance may not reflect this usage \u2014 please contact support if it persists.")

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

        if 'panel' not in st.session_state:
            st.session_state.panel = 'home'

        def go(panel_name):
            st.session_state.panel = panel_name
            try:
                _go_uid = (st.session_state.get('auth_user') or {}).get('user_id')
                if _go_uid:
                    db.save_user_ui_state(_go_uid, st.session_state.get('ui_card', 'DONE'), panel_name)
            except Exception:
                pass
            st.rerun()

        if has_letters:
            letters = st.session_state.generated_letters
            letter_count_done = len(letters)
            bureau_names_done = [k.title() for k in letters.keys() if k != 'unknown']
            total_claims_done = sum(ld.get('claim_count', 0) if isinstance(ld, dict) else 0 for ld in letters.values())
            round_number_done = st.session_state.get('dispute_round_number', 1)
        else:
            letters = {}
            letter_count_done = 0
            bureau_names_done = []
            total_claims_done = 0
            round_number_done = st.session_state.get('dispute_round_number', 1)

        user_id_dash = user_id
        user_tier = auth.get_user_tier(user_id_dash) if not is_admin_user else 'deletion_sprint'
        tier_rank = auth.TIER_HIERARCHY.get(user_tier, 0)
        tier_label = auth.TIER_LABELS.get(user_tier, 'Free')

        tracker = db.get_dispute_tracker(user_id_dash, round_number_done)
        lob_sends = db.get_lob_sends_for_user(user_id_dash)
        round_lob_sends = [s for s in lob_sends if s.get('status') == 'mailed']

        if not tracker and round_lob_sends:
            earliest = min(s['created_at'] for s in round_lob_sends)
            db.save_dispute_tracker(user_id_dash, round_number_done, earliest, 'certified_mail')
            tracker = db.get_dispute_tracker(user_id_dash, round_number_done)

        _ws_mailed = bool(tracker and tracker.get('mailed_at'))
        _ws_days_elapsed = 0
        _ws_days_remaining = 30
        _ws_mailed_dt = None
        if _ws_mailed:
            from datetime import timedelta
            _ws_mailed_dt = tracker['mailed_at']
            _ws_days_elapsed = (datetime.now() - _ws_mailed_dt).days
            _ws_days_remaining = max(0, 30 - _ws_days_elapsed)

        if has_letters and _ws_mailed:
            _pill_letters = '<span class="ws-pill ws-pill-ok">&#x2709;&#xFE0F; SENT</span>'
        elif has_letters:
            _pill_letters = '<span class="ws-pill ws-pill-warn">&#x2709;&#xFE0F; READY</span>'
        else:
            _pill_letters = '<span class="ws-pill ws-pill-neutral">&#x2709;&#xFE0F; NO LETTERS</span>'

        if _ws_mailed and _ws_days_remaining <= 0:
            _pill_clock = '<span class="ws-pill ws-pill-ok">&#x23F0; COMPLETE</span>'
        elif _ws_mailed:
            _pill_clock = f'<span class="ws-pill ws-pill-warn">&#x23F0; DAY {_ws_days_elapsed}</span>'
        else:
            _pill_clock = '<span class="ws-pill ws-pill-alert">&#x23F0; NOT STARTED</span>'

        _proof_check_home = db.has_proof_docs(user_id_dash) if has_letters else {'has_id': False, 'has_address': False, 'both': False}
        _docs_uploaded = _proof_check_home['both']

        if not has_letters:
            _next_target = 'documents'
            _next_title = "Make Your Letters"
            _next_desc = "Upload your credit reports. We'll make your dispute letters."
            _next_cta = "Get Started"
        elif has_letters and not _docs_uploaded:
            _next_target = 'proof_upload'
            _next_title = "Upload Your ID & Address Proof"
            _next_desc = "Bureaus need these or they will reject your dispute."
            _next_cta = "Upload Now"
        elif has_letters and _docs_uploaded and not _ws_mailed:
            _next_target = 'send_mail'
            _next_title = "Mail Your Letters"
            _next_desc = "Your docs are ready. Send via certified mail to start the clock."
            _next_cta = "Send Now"
        elif _ws_mailed and _ws_days_remaining > 0:
            _next_target = 'documents'
            _next_title = f"Day {_ws_days_elapsed} of 30"
            _next_desc = f"{_ws_days_remaining} days left. Add any replies you get."
            _next_cta = "View Documents"
        else:
            _next_target = 'escalation'
            _next_title = "Ready to Escalate"
            _next_desc = "30 days are up. Time to push on items not yet fixed."
            _next_cta = "View Options"

        _panel = st.session_state.panel

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PANEL: HOME
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if _panel == 'home':

            _nac1, _nac2 = st.columns([3, 1])
            with _nac1:
                st.markdown(f'''
                <div style="padding:4px 0;">
                    <div style="font-size:0.62rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:{GOLD_DIM};margin-bottom:2px;">Next Action</div>
                    <div style="font-size:0.95rem;font-weight:800;color:{TEXT_0};margin-bottom:1px;">{_next_title}</div>
                    <div style="font-size:0.78rem;color:{TEXT_1};line-height:1.3;">{_next_desc}</div>
                </div>
                ''', unsafe_allow_html=True)
            with _nac2:
                if _next_target == 'proof_upload':
                    if st.button(f"{_next_cta} \u2192", key="ws_next_cta", type="primary", use_container_width=True):
                        st.query_params['page'] = 'proof'
                        st.rerun()
                else:
                    if st.button(f"{_next_cta} \u2192", key="ws_next_cta", type="primary", use_container_width=True):
                        go(_next_target)


            try:
                _combined_sm_nudge = {}
                _all_sm_nudge = st.session_state.get('strike_metrics', {})
                for _bsm_n, _vsm_n in _all_sm_nudge.items():
                    if isinstance(_vsm_n, dict):
                        for _ksm_n, _valsm_n in _vsm_n.items():
                            if _ksm_n == 'data_quality':
                                continue
                            if _ksm_n not in _combined_sm_nudge:
                                _combined_sm_nudge[_ksm_n] = _valsm_n
                            elif isinstance(_valsm_n, bool) and _valsm_n:
                                _combined_sm_nudge[_ksm_n] = True
                            elif isinstance(_valsm_n, (int, float)) and _valsm_n and isinstance(_combined_sm_nudge[_ksm_n], (int, float)):
                                _combined_sm_nudge[_ksm_n] = max(_combined_sm_nudge[_ksm_n], _valsm_n)

                _nudge_user_state = {
                    'has_letters': has_letters,
                    'has_mailed': _ws_mailed,
                    'letters_generated_at': st.session_state.get('_letters_generated_at'),
                    'mailed_at': _ws_mailed_dt.isoformat() if _ws_mailed_dt else None,
                    'days_elapsed': _ws_days_elapsed if _ws_mailed else 0,
                    'has_clock_started': _ws_mailed,
                    'utilization_pct': _combined_sm_nudge.get('revolving_utilization_pct', 0),
                    'critical_utilization': _combined_sm_nudge.get('critical_utilization_flag', False),
                    'high_utilization': _combined_sm_nudge.get('high_utilization_flag', False),
                    'has_balance_update': st.session_state.get('_balance_update_logged', False),
                    'escalation_opened': st.session_state.get('_escalation_opened', False),
                    'report_uploaded_at': st.session_state.get('_report_uploaded_at'),
                }
                _active_nudges = evaluate_nudge_rules(_nudge_user_state)

                if _active_nudges:
                    for _nudge in _active_nudges[:1]:
                        _ncolor = NUDGE_SEVERITY_COLORS.get(_nudge.severity, TEXT_1)
                        _nlabel = NUDGE_SEVERITY_LABELS.get(_nudge.severity, 'Notice')
                        st.markdown(f'''
                        <div class="glass-card" style="border-color:{_ncolor}40;background:{_ncolor}08;margin-top:6px;">
                            <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{_ncolor};"></span>
                                <span style="font-size:0.7rem;font-weight:800;text-transform:uppercase;letter-spacing:0.08em;color:{_ncolor};">{_nlabel}</span>
                            </div>
                            <div style="font-size:0.82rem;color:{TEXT_0};line-height:1.45;">{_nudge.message}</div>
                        </div>
                        ''', unsafe_allow_html=True)
                        if _nudge.recommended_action_route:
                            if st.button(f"{_nudge.trigger_name} \u2192", key=f"nudge_{_nudge.id}", use_container_width=True):
                                go(_nudge.recommended_action_route)
                        _nudge_logged = db.log_nudge_if_not_cooldown(
                            user_id_dash, _nudge.id, _nudge.severity,
                            _nudge.message, _nudge.cooldown_days
                        )
                        if _nudge_logged and user_email:
                            try:
                                send_nudge_email(
                                    to_email=user_email,
                                    nudge_id=_nudge.id,
                                    severity=_nudge.severity,
                                    message=_nudge.message,
                                    display_name=st.session_state.get('display_name'),
                                    days_elapsed=_ws_days_elapsed if _ws_mailed else 0,
                                )
                            except Exception:
                                pass
            except Exception:
                pass

            _all_sm = st.session_state.get('strike_metrics', {})
            if _all_sm:
                _combined_sm = {}
                for _b_sm, _v_sm in _all_sm.items():
                    for _k_sm, _val_sm in _v_sm.items():
                        if _k_sm == 'data_quality':
                            continue
                        if _k_sm not in _combined_sm:
                            _combined_sm[_k_sm] = _val_sm
                        elif isinstance(_val_sm, (int, float)) and _val_sm and isinstance(_combined_sm[_k_sm], (int, float)):
                            _combined_sm[_k_sm] = max(_combined_sm[_k_sm], _val_sm)
                        elif isinstance(_val_sm, bool) and _val_sm:
                            _combined_sm[_k_sm] = True

                _wr_plan = build_war_room_plan(
                    strike_metrics=_combined_sm,
                    has_letters=has_letters,
                    has_mailed=_ws_mailed,
                    days_elapsed=_ws_days_elapsed if _ws_mailed else 0,
                    mission_goal=st.session_state.get('mission_goal', 'General Rebuild'),
                    mission_timeline=st.session_state.get('mission_timeline', 'ASAP (7 days)'),
                )
                st.session_state['war_room_plan'] = _wr_plan.as_dict()

                if not st.session_state.get('_mission_snapshots_saved'):
                    try:
                        db.update_mission_snapshots(
                            user_id,
                            risk_level=_wr_plan.risk_level,
                            primary_lever=_wr_plan.primary_lever,
                            strike_metrics_snapshot=_combined_sm,
                            war_plan_snapshot=_wr_plan.as_dict(),
                        )
                        st.session_state['_mission_snapshots_saved'] = True
                    except Exception:
                        pass

            _cmd_saved_checks = db.get_checklist_items(user_id_dash, round_number_done)
            _cmd_done = sum(1 for v in _cmd_saved_checks.values() if v)
            _cmd_summary = f"{_cmd_done}/5 done"
            _trk_summary = f"Day {_ws_days_elapsed}/30" if _ws_mailed else "Not started"
            _doc_summary = f"{letter_count_done} letter{'s' if letter_count_done != 1 else ''}" if has_letters else "No letters yet"
            _str_summary = "Plan is live" if st.session_state.get('strike_metrics') else "Upload a report first"

            _all_user_letters = db.get_all_letters_for_user(user_id_dash)
            _lb_count = len(_all_user_letters) if _all_user_letters else 0
            _lb_summary = f"{_lb_count} saved" if _lb_count else "Empty"

            _qn1, _qn2, _qn3, _qn4, _qn5 = st.columns(5)
            with _qn1:
                st.markdown(f'<div style="text-align:center;font-size:1.2rem;">&#x1F3AF;</div><div style="text-align:center;font-size:0.68rem;color:{TEXT_1};">{_cmd_summary}</div>', unsafe_allow_html=True)
                if st.button("Command", key="go_command", use_container_width=True):
                    go('command')
            with _qn2:
                st.markdown(f'<div style="text-align:center;font-size:1.2rem;">&#x23F0;</div><div style="text-align:center;font-size:0.68rem;color:{TEXT_1};">{_trk_summary}</div>', unsafe_allow_html=True)
                if st.button("Tracker", key="go_tracker", use_container_width=True):
                    go('tracker')
            with _qn3:
                st.markdown(f'<div style="text-align:center;font-size:1.2rem;">&#x1F4C4;</div><div style="text-align:center;font-size:0.68rem;color:{TEXT_1};">{_doc_summary}</div>', unsafe_allow_html=True)
                if st.button("Documents", key="go_documents", use_container_width=True):
                    go('documents')
            with _qn4:
                st.markdown(f'<div style="text-align:center;font-size:1.2rem;">&#x1F4DC;</div><div style="text-align:center;font-size:0.68rem;color:{TEXT_1};">{_lb_summary}</div>', unsafe_allow_html=True)
                if st.button("Letters", key="go_letter_bank", use_container_width=True):
                    go('letter_bank')
            with _qn5:
                st.markdown(f'<div style="text-align:center;font-size:1.2rem;">&#x1F9E0;</div><div style="text-align:center;font-size:0.68rem;color:{TEXT_1};">{_str_summary}</div>', unsafe_allow_html=True)
                if st.button("Strategy", key="go_strategy", use_container_width=True):
                    go('strategy')

            _ev_categories = [
                ("payments", "On-Time Payments", "Bank statements, payment confirmations, receipts showing payments made on time"),
                ("balances", "Correct Balances", "Statements showing actual balance differs from what's reported"),
                ("personal", "Personal Info Corrections", "Proof of correct name, address, SSN, or date of birth"),
                ("accounts", "Account Disputes", "Letters, statements, or records proving account info is wrong"),
                ("other", "Other Evidence", "Any other supporting documentation for your disputes"),
            ]
            _ev_items = db.get_proof_uploads(user_id_dash, round_number_done)
            _ev_by_cat = {}
            for _ev in _ev_items:
                _cat = _ev.get('bureau', 'other')
                if _cat not in _ev_by_cat:
                    _ev_by_cat[_cat] = []
                _ev_by_cat[_cat].append(_ev)
            _ev_total = len(_ev_items)

            with st.expander(f"Evidence Tracker ({_ev_total} item{'s' if _ev_total != 1 else ''})", expanded=False):
                for _ev_key, _ev_label, _ev_hint in _ev_categories:
                    _cat_items = _ev_by_cat.get(_ev_key, [])
                    _cat_count = len(_cat_items)
                    if _cat_count > 0:
                        st.markdown(f'<div style="font-size:0.82rem;font-weight:700;color:{TEXT_0};margin:8px 0 4px;">{_ev_label} ({_cat_count})</div>', unsafe_allow_html=True)
                        for _ev_item in _cat_items:
                            _ev_date = _ev_item.get('created_at', '')
                            if hasattr(_ev_date, 'strftime'):
                                _ev_date = _ev_date.strftime('%b %d, %Y')
                            else:
                                _ev_date = str(_ev_date)[:10]
                            _ev_note = _ev_item.get('notes', '') or ''
                            _ev_fname = _ev_item.get('file_name', '') or ''
                            _ev_display = _ev_fname if _ev_fname else _ev_note[:80]
                            _ev_id = _ev_item.get('id')
                            _ec1, _ec2 = st.columns([5, 1])
                            with _ec1:
                                st.markdown(f'<div style="font-size:0.82rem;color:{TEXT_0};">{_ev_display} <span style="color:{TEXT_1};font-size:0.72rem;">{_ev_date}</span></div>', unsafe_allow_html=True)
                            with _ec2:
                                if st.button("x", key=f"ev_del_{_ev_id}", help="Remove"):
                                    db.delete_proof_upload(_ev_id, user_id_dash)
                                    st.rerun()
                    _ev_note_key = f"ev_note_{_ev_key}_{round_number_done}"
                    _ev_note_val = st.text_input(_ev_label, key=_ev_note_key, placeholder=_ev_hint, label_visibility="collapsed")
                    if st.button("Add", key=f"ev_add_{_ev_key}", use_container_width=True, disabled=not _ev_note_val):
                        db.save_proof_upload(user_id_dash, round_number_done, _ev_key, _ev_note_val, 'note', _ev_note_val)
                        st.rerun()

            if _ws_mailed:
                _share_ref_link = get_referral_link(user_id) if user_id else ""
                _share_bureau_list = " & ".join(bureau_names_done) if bureau_names_done else "credit bureaus"
                _share_text_encoded = f"I just found {total_claims_done} errors on my credit report and got dispute letters for {_share_bureau_list} in 60 seconds. Check yours free:"
                import urllib.parse as _urlp
                _share_tw = f"https://twitter.com/intent/tweet?text={_urlp.quote(_share_text_encoded)}&url={_urlp.quote(_share_ref_link)}"
                _share_fb = f"https://www.facebook.com/sharer/sharer.php?u={_urlp.quote(_share_ref_link)}&quote={_urlp.quote(_share_text_encoded)}"
                _share_wa = f"https://wa.me/?text={_urlp.quote(_share_text_encoded + ' ' + _share_ref_link)}"
                _share_sms = f"sms:?body={_urlp.quote(_share_text_encoded + ' ' + _share_ref_link)}"

                with st.expander("Share Your Win & Referral Link", expanded=False):
                    st.markdown(
                        f'<div style="font-size:0.85rem;color:{TEXT_1};margin-bottom:10px;">'
                        f'You found <strong style="color:{GOLD};">{total_claims_done} errors</strong> across '
                        f'<strong style="color:{GOLD};">{_share_bureau_list}</strong>. Share with friends:</div>'
                        f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">'
                        f'<a href="{_share_tw}" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:5px;'
                        f'padding:8px 14px;background:#1DA1F2;color:#fff;border-radius:8px;font-size:0.8rem;'
                        f'font-weight:600;text-decoration:none;">Post</a>'
                        f'<a href="{_share_fb}" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:5px;'
                        f'padding:8px 14px;background:#1877F2;color:#fff;border-radius:8px;font-size:0.8rem;'
                        f'font-weight:600;text-decoration:none;">Share</a>'
                        f'<a href="{_share_wa}" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:5px;'
                        f'padding:8px 14px;background:#25D366;color:#fff;border-radius:8px;font-size:0.8rem;'
                        f'font-weight:600;text-decoration:none;">WhatsApp</a>'
                        f'<a href="{_share_sms}" style="display:inline-flex;align-items:center;gap:5px;'
                        f'padding:8px 14px;background:#6C757D;color:#fff;border-radius:8px;font-size:0.8rem;'
                        f'font-weight:600;text-decoration:none;">Text</a>'
                        f'</div>'
                        f'<div style="font-size:0.78rem;color:{TEXT_1};">Your referral link:<br/>'
                        f'<code style="font-size:0.75rem;color:{GOLD};word-break:break-all;">{_share_ref_link}</code></div>',
                        unsafe_allow_html=True,
                    )
                    import streamlit.components.v1 as _share_comp
                    _share_comp.html(f'''
                    <button onclick="copyLink()" id="copyBtn" style="width:100%;padding:8px 14px;
                        background:{BG_2};border:1px solid rgba(212,160,23,0.25);color:{GOLD};
                        font-weight:600;font-size:0.82rem;border-radius:8px;cursor:pointer;
                        font-family:'Inter',-apple-system,sans-serif;">
                        Copy Referral Link</button>
                    <script>
                    function copyLink(){{
                        var link="{_share_ref_link}";
                        if(navigator.clipboard){{
                            navigator.clipboard.writeText(link).then(function(){{
                                document.getElementById('copyBtn').innerHTML='Copied!';
                                setTimeout(function(){{document.getElementById('copyBtn').innerHTML='Copy Referral Link';}},2000);
                            }});
                        }} else {{
                            var t=document.createElement('textarea');t.value=link;
                            document.body.appendChild(t);t.select();document.execCommand('copy');
                            document.body.removeChild(t);
                            document.getElementById('copyBtn').innerHTML='Copied!';
                            setTimeout(function(){{document.getElementById('copyBtn').innerHTML='Copy Referral Link';}},2000);
                        }}
                    }}
                    </script>
                    ''', height=42)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PANEL: COMMAND
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        elif _panel == 'command':
            if st.button("\u2190 Back", key="cmd_back", use_container_width=False):
                go('home')

            st.markdown(f'<div class="glass-card"><div class="glass-section-title">&#x1F3AF; Command</div>', unsafe_allow_html=True)

            CHECKLIST_ITEMS = [
                ("save_receipt", "Save your mailing receipt / tracking number"),
                ("keep_copies", "Keep copies of all letters you sent"),
                ("monitor_credit", "Check your credit report for updates"),
                ("collect_responses", "Save any bureau response letters"),
                ("prep_round2", "Prepare evidence for items not corrected"),
            ]

            saved_checks = db.get_checklist_items(user_id_dash, round_number_done)
            completed_count = sum(1 for v in saved_checks.values() if v)
            total_items = len(CHECKLIST_ITEMS)
            _pct_done = int(completed_count / total_items * 100) if total_items > 0 else 0

            st.markdown(f'''
                <div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:8px;">Progress: {completed_count}/{total_items} ({_pct_done}%)</div>
                <div class="ws-progress">
                    <div class="ws-progress-bar"><div class="ws-progress-fill" style="width:{_pct_done}%;"></div></div>
                </div>
            ''', unsafe_allow_html=True)

            for item_key, item_label in CHECKLIST_ITEMS:
                is_checked = saved_checks.get(item_key, False)
                new_val = st.checkbox(item_label, value=is_checked, key=f"cl_{item_key}_{round_number_done}")
                if new_val != is_checked:
                    db.toggle_checklist_item(user_id_dash, round_number_done, item_key, new_val)
                    st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

            _cur_goal = st.session_state.get('mission_goal', 'General Rebuild')
            _cur_tl = st.session_state.get('mission_timeline', 'ASAP (7 days)')
            _m_icons = {"Auto Purchase": "\U0001F697", "Apartment": "\U0001F3E0", "Credit Card": "\U0001F4B3", "Bank Account": "\U0001F3E6", "General Rebuild": "\U0001F527"}
            st.markdown(f'''
            <div class="glass-card" style="margin-top:8px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:{GOLD_DIM};margin-bottom:3px;">Active Mission</div>
                        <div style="font-size:0.95rem;font-weight:700;color:{TEXT_0};">{_m_icons.get(_cur_goal, "")} {_cur_goal}</div>
                        <div style="font-size:0.78rem;color:{TEXT_1};">{_cur_tl}</div>
                    </div>
                </div>
            </div>
            ''', unsafe_allow_html=True)

            with st.expander("Switch Mission", expanded=False):
                _sw_goals = ["Auto Purchase", "Apartment", "Credit Card", "Bank Account", "General Rebuild"]
                _sw_timelines = ["ASAP (7 days)", "30 days", "90 days"]
                _sw_goal = st.selectbox("New Goal", _sw_goals, index=_sw_goals.index(_cur_goal) if _cur_goal in _sw_goals else 4, key="sw_mission_goal")
                _sw_tl = st.selectbox("Timeline", _sw_timelines, index=_sw_timelines.index(_cur_tl) if _cur_tl in _sw_timelines else 0, key="sw_mission_tl")
                if _sw_goal != _cur_goal or _sw_tl != _cur_tl:
                    if st.button("Switch Mission", key="sw_mission_confirm", type="primary", use_container_width=True):
                        try:
                            db.create_mission(user_id_dash, _sw_goal, _sw_tl)
                            st.session_state['mission_goal'] = _sw_goal
                            st.session_state['mission_timeline'] = _sw_tl
                            st.session_state['_mission_snapshots_saved'] = False
                            st.session_state.pop('war_room_plan', None)
                            db.log_activity(user_id, 'switch_mission', f"{_sw_goal} / {_sw_tl}", 'command')
                            st.toast(f"Mission switched to {_sw_goal}")
                            st.rerun()
                        except Exception:
                            st.error("Could not switch mission. Please try again.")

            _mission_hist = db.get_mission_history(user_id_dash, limit=5)
            if len(_mission_hist) > 1:
                with st.expander(f"Mission History ({len(_mission_hist)})", expanded=False):
                    for _mh in _mission_hist:
                        _mh_status = _mh.get('status', 'unknown')
                        _mh_color = GOLD if _mh_status == 'active' else TEXT_1
                        _mh_risk = _mh.get('risk_level', '')
                        _mh_lever = _mh.get('primary_lever', '')
                        _mh_date = _mh.get('created_at')
                        _mh_date_str = _mh_date.strftime('%b %d, %Y') if hasattr(_mh_date, 'strftime') else str(_mh_date)[:10] if _mh_date else '—'
                        _mh_snap = ""
                        if _mh_risk and _mh_lever:
                            _mh_snap = f' &middot; <span style="color:{TEXT_1};">{_mh_risk} / {_mh_lever}</span>'
                        st.markdown(f'''
                        <div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:0.8rem;">
                            <span style="color:{_mh_color};font-weight:700;">{_mh.get("goal", "—")}</span>
                            <span style="color:{TEXT_1};"> &middot; {_mh.get("timeline", "—")} &middot; {_mh_date_str}</span>
                            {_mh_snap}
                            <span style="font-size:0.7rem;color:{_mh_color};text-transform:uppercase;margin-left:6px;">{_mh_status}</span>
                        </div>
                        ''', unsafe_allow_html=True)

            sprint_g = db.get_sprint_guarantee(user_id_dash)
            if sprint_g and not sprint_g.get('free_round_used', False):
                with st.expander("2-Round Guarantee Tracker", expanded=False):
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
                        f'If no disputed item is deleted or updated after completing 2 rounds, Round 3 is on us. '
                        f"After each round\'s 30-day window, record whether any items were deleted or corrected.</div>"
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
                            ["No changes \u2014 nothing was deleted or corrected", "Yes \u2014 at least one item was deleted or corrected"],
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
                            f'Nothing changed after 2 rounds \u2014 your guarantee is active. '
                            f'Upload your updated report and generate Round 3 letters at no charge.</div>'
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
                        f"&#x2705; Reminder set \u2014 we\'ll email <strong>{user_email}</strong> "
                        f"when it\'s time to check your results."
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown("---")

            _r2_eligible = _ws_days_elapsed >= 30 if _ws_mailed else False
            _r2_has_entitlement = tier_rank >= 1
            _next_round = round_number_done + 1

            if _r2_eligible or round_number_done >= 1:
                with st.expander(f"Start Round {_next_round}", expanded=_r2_eligible):
                    if _r2_eligible:
                        st.markdown(f'''
                        <div class="glass-card" style="border-color:{GOLD}40;background:linear-gradient(135deg, rgba(212,160,23,0.08), rgba(212,160,23,0.02));">
                            <div style="font-size:0.92rem;font-weight:700;color:{GOLD};margin-bottom:6px;">
                                Ready for Round {_next_round}
                            </div>
                            <div style="font-size:0.82rem;color:{TEXT_0};line-height:1.5;">
                                Your 30-day investigation period has ended. Upload your updated credit report to see what was deleted vs. what still needs to be disputed.
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        st.markdown(f'''
                        <div style="font-size:0.82rem;color:{TEXT_1};line-height:1.5;margin-bottom:8px;">
                            Round {_next_round} becomes available after the 30-day investigation period ends (Day {_ws_days_elapsed}/30).
                        </div>
                        ''', unsafe_allow_html=True)

                    if _r2_eligible:
                        _prev_violations = []
                        _prev_report_ids = list(set(
                            st.session_state.get('saved_report_ids', {}).values()
                        ))
                        for _pr_id in _prev_report_ids:
                            try:
                                _pv = db.get_violations_for_report(_pr_id)
                                _prev_violations.extend(_pv)
                            except Exception:
                                pass

                        if _prev_violations:
                            _pv_count = len(_prev_violations)
                            st.markdown(f'''
                            <div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:8px;">
                                {_pv_count} disputed item{"s" if _pv_count != 1 else ""} from Round {round_number_done} will be compared against your new report.
                            </div>
                            ''', unsafe_allow_html=True)

                        if st.button(f"Upload Updated Report for Round {_next_round}", key="start_round2_btn",
                                     type="primary", use_container_width=True):
                            _snapshot_items_r2 = []
                            _prev_letters = st.session_state.get('generated_letters', {})
                            _prev_claims = st.session_state.get('review_claims', [])
                            from normalization import canonicalize_creditor_name as _snap_r2_canon
                            for _rc_snap in _prev_claims:
                                _raw_c = _rc_snap.entities.get('creditor_name', '')
                                if _raw_c:
                                    _snapshot_items_r2.append({
                                        'creditor': _raw_c,
                                        'creditor_canon': _snap_r2_canon(_raw_c),
                                        'bureau': _rc_snap.entities.get('bureau', 'unknown'),
                                        'account_number': _rc_snap.entities.get('account_number_partial', ''),
                                        'violation_type': str(getattr(_rc_snap, 'review_type', '')),
                                    })
                            if not _snapshot_items_r2 and _prev_violations:
                                for _pv_item in _prev_violations:
                                    _td = _pv_item.get('triggering_data', {})
                                    if isinstance(_td, str):
                                        import json as _j_tmp
                                        try: _td = _j_tmp.loads(_td)
                                        except Exception: _td = {}
                                    _snapshot_items_r2.append({
                                        'creditor': _td.get('creditor_name', _pv_item.get('violation_type', '')),
                                        'creditor_canon': _snap_r2_canon(_td.get('creditor_name', '')),
                                        'bureau': _td.get('bureau', 'unknown'),
                                        'account_number': _td.get('account_number', ''),
                                        'violation_type': _pv_item.get('violation_type', ''),
                                    })
                            st.session_state['_prev_round_snapshot'] = {
                                'round_number': round_number_done,
                                'items': _snapshot_items_r2,
                                'bureaus': list(_prev_letters.keys()),
                            }
                            try:
                                db.archive_mission(user_id)
                            except Exception:
                                pass
                            st.session_state['_round2_mode'] = True
                            st.session_state['_round2_number'] = _next_round
                            st.session_state['dispute_round_number'] = _next_round
                            st.session_state['dispute_rounds'] = st.session_state.get('dispute_rounds', []) + [{}]
                            st.session_state['uploaded_reports'] = {}
                            st.session_state['generated_letters'] = {}
                            st.session_state['_gen_completed'] = False
                            st.session_state['_mission_snapshots_saved'] = False
                            st.session_state['current_card'] = 'UPLOAD'
                            db.log_activity(user_id, 'start_round2', f"Round {_next_round}", 'command')
                            st.rerun()

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
                        _prev_claims = st.session_state.get('review_claims', [])
                        _prev_rounds = st.session_state.get('dispute_rounds', [])
                        _prev_letters = st.session_state.get('generated_letters', {})
                        if _prev_rounds and _prev_claims:
                            from normalization import canonicalize_creditor_name as _snap_canon
                            _snapshot_items = []
                            _all_disputed_ids = set()
                            for pr in _prev_rounds:
                                _all_disputed_ids.update(pr.get('claim_ids', []))
                            for rc in _prev_claims:
                                if rc.review_claim_id in _all_disputed_ids:
                                    _raw_cred_snap = rc.entities.get('creditor_name', 'Unknown')
                                    _snapshot_items.append({
                                        'rc_id': rc.review_claim_id,
                                        'summary': rc.summary,
                                        'review_type': rc.review_type.value if hasattr(rc.review_type, 'value') else str(rc.review_type),
                                        'creditor': _raw_cred_snap,
                                        'creditor_canon': _snap_canon(_raw_cred_snap),
                                        'bureau': rc.entities.get('bureau', 'unknown'),
                                        'account_number': rc.entities.get('account_number_partial', ''),
                                    })
                            st.session_state._prev_round_snapshot = {
                                'round_number': len(_prev_rounds),
                                'items': _snapshot_items,
                                'bureaus': list(_prev_letters.keys()),
                            }
                        try:
                            db.archive_mission(user_id)
                        except Exception:
                            pass
                        reset_analysis_state(full=True)
                        st.session_state.confirm_start_over = False
                        st.session_state.reminder_email_sent = False
                        st.session_state['_mission_snapshots_saved'] = False
                        advance_card("UPLOAD")
                        st.rerun()
                with col_confirm2:
                    if st.button("Cancel", use_container_width=True, key="confirm_start_over_no"):
                        st.session_state.confirm_start_over = False
                        st.rerun()

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PANEL: TRACKER
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        elif _panel == 'tracker':
            if st.button("\u2190 Back", key="trk_back", use_container_width=False):
                go('home')

            st.markdown(f'<div class="glass-card"><div class="glass-section-title">&#x23F0; Investigation Tracker</div>', unsafe_allow_html=True)

            if has_letters:
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
                        status_label = "30-day window complete \u2014 time to check results"
                        status_color = "#66BB6A"

                    st.markdown(f"""
                    <div style="text-align:center;margin-bottom:14px;">
                        <div style="font-size:2.2rem;font-weight:900;color:{GOLD};">{days_elapsed}<span style="font-size:1rem;color:{TEXT_1};">/30</span></div>
                        <div style="font-size:0.78rem;color:{status_color};font-weight:600;">{status_label}</div>
                        <div class="ws-progress" style="margin-top:8px;">
                            <div class="ws-progress-bar"><div class="ws-progress-fill" style="width:{pct}%;"></div></div>
                        </div>
                        <div style="display:flex;justify-content:space-between;margin-top:6px;">
                            <div style="font-size:0.72rem;color:{TEXT_1};">Mailed: {mailed_dt.strftime('%b %d')}</div>
                            <div style="font-size:0.72rem;color:{TEXT_1};">Deadline: {deadline.strftime('%b %d')}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if days_remaining <= 0:
                        st.markdown(f'''
                        <div style="background:rgba(102,187,106,0.1);border:1px solid #66BB6A;border-radius:10px;padding:12px;text-align:center;margin-bottom:10px;">
                            <div style="font-size:0.88rem;font-weight:700;color:#2E7D32;">&#x2705; Investigation window complete</div>
                        </div>
                        ''', unsafe_allow_html=True)
                        if st.button("View Escalation Options \u2192", key="trk_go_esc", type="primary", use_container_width=True):
                            go('escalation')
                else:
                    st.markdown(f"""
                    <div style="background:rgba(229,115,115,0.06);border:1px solid #E57373;border-radius:10px;padding:14px;margin-bottom:12px;">
                        <div style="font-size:0.88rem;font-weight:700;color:#E57373;margin-bottom:4px;">
                            &#x23F0; Clock not started
                        </div>
                        <div style="font-size:0.82rem;color:{TEXT_1};line-height:1.4;">
                            Set your mail date to start the 30-day countdown.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    mail_date = st.date_input("Date letters were mailed", value=datetime.now().date(), key="dash_mail_date")
                    if st.button("Start My 30-Day Countdown", key="dash_start_countdown", type="primary", use_container_width=True):
                        db.save_dispute_tracker(user_id_dash, round_number_done, datetime.combine(mail_date, datetime.min.time()), 'manual')
                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)

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

                _bt_cache_key = f'_bureau_tracker_disputes_{round_number_done}'
                if _bt_cache_key not in st.session_state:
                    try:
                        from bureau_tracker import build_bureau_disputes, render_bureau_tracker_html
                        _bt_selected = st.session_state.get('_gen_selected_items', [])
                        _bt_bureaus = set()
                        for _bt_rc in _bt_selected:
                            _bt_b = (_bt_rc.entities.get('bureau') or '').lower()
                            if _bt_b:
                                _bt_bureaus.add(_bt_b)
                        if not _bt_bureaus:
                            for _letter in st.session_state.generated_letters:
                                _bt_b2 = (_letter.get('bureau', '') or '').lower()
                                if _bt_b2:
                                    _bt_bureaus.add(_bt_b2)
                        _bt_tracker_row = db.get_dispute_tracker(user_id_dash, round_number_done)
                        _bt_tracker_rows = [_bt_tracker_row] if _bt_tracker_row else []
                        _bt_lob_sends = db.get_lob_sends_for_user(user_id_dash) if hasattr(db, 'get_lob_sends_for_user') else []
                        _bt_disputes = build_bureau_disputes(
                            selected_items=_bt_selected,
                            bureaus=_bt_bureaus if _bt_bureaus else {'equifax', 'experian', 'transunion'},
                            tracker_rows=_bt_tracker_rows,
                            lob_sends=_bt_lob_sends,
                            has_generated_letters=bool(st.session_state.generated_letters),
                        )
                        st.session_state[_bt_cache_key] = _bt_disputes
                    except Exception:
                        st.session_state[_bt_cache_key] = None

                _bt_disputes = st.session_state.get(_bt_cache_key)
                if _bt_disputes:
                    from bureau_tracker import render_bureau_tracker_html
                    _bt_colors = {"TEXT_0": TEXT_0, "TEXT_1": TEXT_1, "GOLD": GOLD, "BG_1": BG_1, "BORDER": BORDER}
                    st.markdown(render_bureau_tracker_html(_bt_disputes, _bt_colors), unsafe_allow_html=True)

                if _ws_mailed:
                    if st.button("Upload Bureau Response \u2192", key="trk_go_docs", use_container_width=True):
                        go('documents')
            else:
                st.markdown(
                    f'<div style="text-align:center;padding:2rem 1rem;color:{TEXT_1};font-size:0.88rem;">'
                    f'Generate your dispute letters first to start tracking.</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PANEL: DOCUMENTS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        elif _panel == 'documents':
            if st.button("\u2190 Back", key="doc_back", use_container_width=False):
                go('home')

            if has_letters:
                if 'doc_active_letter' not in st.session_state:
                    st.session_state.doc_active_letter = None

                _bureau_keys_list = list(letters.keys())
                _active_letter_key = st.session_state.doc_active_letter

                if _active_letter_key and _active_letter_key not in _bureau_keys_list:
                    _active_letter_key = None
                    st.session_state.doc_active_letter = None

                if not _active_letter_key:
                    st.markdown(f'''
                    <div style="text-align:center;padding:8px 0 4px;">
                        <div style="font-size:1.1rem;font-weight:800;color:{TEXT_0};margin-bottom:2px;">
                            {letter_count_done} Letter{"s" if letter_count_done != 1 else ""} Ready
                        </div>
                        <div style="font-size:0.8rem;color:{TEXT_1};">Tap a letter to preview, edit, and download</div>
                    </div>
                    ''', unsafe_allow_html=True)

                    _proof_check_doc = db.has_proof_docs(user_id_dash)
                    if _proof_check_doc['both']:
                        st.markdown(
                            f'<div style="background:linear-gradient(135deg, rgba(46,204,113,0.12), rgba(46,204,113,0.04));'
                            f'border:2px solid #2ecc71;border-radius:12px;padding:12px 16px;margin:8px 0 6px 0;">'
                            f'<div style="font-size:0.88rem;font-weight:700;color:#2ecc71;">'
                            f'&#x2705; Your ID and address proof are on file</div></div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f'<div style="background:{BG_1};border:1px solid rgba(192,57,43,0.4);border-radius:10px;'
                            f'padding:10px 14px;margin:8px 0 6px 0;display:flex;align-items:center;justify-content:space-between;">'
                            f'<div style="font-size:0.82rem;color:#e74c3c;font-weight:600;">'
                            f'ID & address proof needed to download</div>'
                            f'<a href="/?page=proof" target="_self" style="color:{GOLD};font-weight:700;font-size:0.82rem;text-decoration:none;">'
                            f'Upload &rarr;</a>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                    if _proof_check_doc['both']:
                        import hashlib as _zip_hashlib_doc
                        _letter_texts_doc = {b: st.session_state.get('letter_edits', {}).get(b, ld['letter_text']) for b, ld in letters.items()}
                        _zip_hash_doc = _zip_hashlib_doc.md5("||".join(f"{b}:{t}" for b, t in sorted(_letter_texts_doc.items())).encode()).hexdigest()
                        if st.session_state.get('_cached_zip_hash') != _zip_hash_doc or '_cached_zip_b64' not in st.session_state:
                            import zipfile as _zf_doc
                            _zb_doc = BytesIO()
                            with _zf_doc.ZipFile(_zb_doc, 'w', _zf_doc.ZIP_DEFLATED) as _zf:
                                for _bk_z, _txt_z in _letter_texts_doc.items():
                                    _fn_z = format_letter_filename(_bk_z)
                                    _zf.writestr(f"{_fn_z}.txt", _txt_z)
                                    _sig_for_pdf_d = st.session_state.get('_user_signature_bytes') or (db.get_user_signature(user_id) if user_id else None)
                                    _proof_docs_d = _get_proof_docs_for_pdf(user_id)
                                    _zf.writestr(f"{_fn_z}.pdf", generate_letter_pdf(_txt_z, signature_image=_sig_for_pdf_d, proof_documents=_proof_docs_d))
                            import base64 as _b64_doc
                            st.session_state._cached_zip_b64 = _b64_doc.b64encode(_zb_doc.getvalue()).decode()
                            st.session_state._cached_zip_hash = _zip_hash_doc
                        _b64d = st.session_state._cached_zip_b64
                        _zfn_doc = f"dispute_letters_{datetime.now().strftime('%Y%m%d')}.zip"
                        import streamlit.components.v1 as _dl_doc_comp
                        _dl_doc_comp.html(
                            f'''<button onclick="dlDoc(this)" style="width:100%;padding:14px 16px;
                            background:linear-gradient(90deg,{GOLD},#f2c94c);color:#1a1a1f;
                            font-weight:700;font-size:0.95rem;border-radius:10px;border:none;cursor:pointer;
                            box-shadow:0 4px 16px rgba(212,160,23,0.25);font-family:'Inter',-apple-system,sans-serif;
                            transition:all 0.3s ease;">
                            &#x1F4E5; Download All {letter_count_done} Letters (ZIP)</button>
                            <script>
                            function dlDoc(btn){{
                              var b64="{_b64d}";
                              var bin=atob(b64);var arr=new Uint8Array(bin.length);
                              for(var i=0;i<bin.length;i++)arr[i]=bin.charCodeAt(i);
                              var blob=new Blob([arr],{{type:"application/zip"}});
                              var url=URL.createObjectURL(blob);
                              var a=document.createElement('a');a.href=url;a.download="{_zfn_doc}";
                              document.body.appendChild(a);a.click();
                              setTimeout(function(){{document.body.removeChild(a);URL.revokeObjectURL(url);}},100);
                              btn.innerHTML="&#x2705; Downloaded!";
                              btn.style.background="linear-gradient(90deg,#2ecc71,#27ae60)";
                              btn.style.color="#fff";
                              setTimeout(function(){{btn.innerHTML="&#x1F4E5; Download All {letter_count_done} Letters (ZIP)";btn.style.background="linear-gradient(90deg,{GOLD},#f2c94c)";btn.style.color="#1a1a1f";}},2500);
                            }}
                            </script>''',
                            height=55,
                        )
                    for _bk_nav in _bureau_keys_list:
                        _bt_nav = _bk_nav.title() if _bk_nav != 'unknown' else 'Credit Bureau'
                        _ld_nav = letters[_bk_nav]
                        _cc_nav = _ld_nav.get('claim_count', 0)
                        _cats_nav = _ld_nav.get('categories', [])
                        _hcats = [humanize_category(c) for c in _cats_nav[:3]]
                        _cat_text = ", ".join(_hcats) if _hcats else ""
                        _is_edited_nav = st.session_state.get('letter_edits', {}).get(_bk_nav, _ld_nav['letter_text']) != _ld_nav['letter_text']
                        _item_word = "items" if _cc_nav != 1 else "item"
                        _sub_line = f"{_cc_nav} disputed {_item_word}"
                        if _cat_text:
                            _sub_line += f" · {_cat_text}"
                        _edited_badge = ""
                        if _is_edited_nav:
                            _edited_badge = f'<span style="font-size:0.65rem;color:{GOLD};font-weight:600;">EDITED</span>'

                        st.markdown(
                            f'<div class="glass-card" style="padding:14px 16px;">'
                            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                            f'<div>'
                            f'<div style="font-size:0.95rem;font-weight:700;color:{TEXT_0};">{_bt_nav}</div>'
                            f'<div style="font-size:0.75rem;color:{TEXT_1};">{_sub_line}</div>'
                            f'</div>'
                            f'<div style="display:flex;align-items:center;gap:6px;">'
                            f'{_edited_badge}'
                            f'<span style="font-size:1.1rem;color:{TEXT_1};">&#x276F;</span>'
                            f'</div>'
                            f'</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        if st.button(f"Open {_bt_nav} Letter", key=f"open_letter_{_bk_nav}", use_container_width=True, type="primary"):
                            st.session_state.doc_active_letter = _bk_nav
                            st.rerun()


                    with st.expander("Disputed Items & Report Details", expanded=False):
                        _all_rc_details = []
                        for b_key, l_data in letters.items():
                            for rd in l_data.get('rc_details', []):
                                rd_copy = dict(rd)
                                rd_copy['bureau'] = b_key.title()
                                _all_rc_details.append(rd_copy)
                        if _all_rc_details:
                            st.markdown(f'<div style="font-size:0.78rem;font-weight:700;color:{GOLD_DIM};margin-bottom:4px;">{len(_all_rc_details)} ITEMS DISPUTED</div>', unsafe_allow_html=True)
                            _items_removed = False
                            for idx_rd, rd in enumerate(_all_rc_details):
                                _rd_cols = st.columns([6, 1])
                                with _rd_cols[0]:
                                    _rt_display = rd.get('review_type', '').replace('_', ' ').title()
                                    st.markdown(
                                        f'<div style="font-size:0.85rem;color:{TEXT_0};font-weight:500;">{rd["creditor"]}</div>'
                                        f'<div style="font-size:0.72rem;color:{TEXT_1};">{_rt_display} · {rd["bureau"]}</div>',
                                        unsafe_allow_html=True,
                                    )
                                with _rd_cols[1]:
                                    if st.button("Remove", key=f"remove_item_{idx_rd}_{rd.get('rc_id','')}",
                                                 type="secondary"):
                                        _rc_id_to_remove = rd.get('rc_id', '')
                                        if _rc_id_to_remove and 'battle_plan_items' in st.session_state:
                                            st.session_state.battle_plan_items[_rc_id_to_remove] = False
                                            _items_removed = True
                            if _items_removed:
                                _remaining = [
                                    rc for rc in st.session_state.get('_gen_selected_items', [])
                                    if st.session_state.battle_plan_items.get(rc.review_claim_id, True)
                                ]
                                if _remaining:
                                    st.session_state._gen_selected_items = _remaining
                                    st.session_state._gen_completed = False
                                    st.session_state.generated_letters = {}
                                    if not st.session_state.get('_voice_profile'):
                                        st.session_state._voice_profile = db.get_effective_voice_profile(user_id) if user_id else db.VOICE_PROFILE_DEFAULTS
                                    advance_card("GENERATING")
                                    st.rerun()
                                else:
                                    st.session_state.generated_letters = {}
                                    st.session_state._report_outcome = 'clean'
                                    st.rerun()
                        st.markdown(f'<div style="height:8px;"></div>', unsafe_allow_html=True)
                        for sk_sum, rr_sum in st.session_state.uploaded_reports.items():
                            pd_sum = rr_sum.get('parsed_data', {})
                            b_sum = rr_sum.get('bureau', 'unknown').title()
                            accts_sum = len(pd_sum.get('accounts', []))
                            neg_sum = len(pd_sum.get('negative_items', []))
                            inq_sum = len(pd_sum.get('inquiries', []))
                            st.markdown(
                                f'<div style="font-size:0.88rem;font-weight:600;color:{TEXT_0};margin-bottom:2px;">{b_sum}</div>'
                                f'<div style="font-size:0.78rem;color:{TEXT_1};margin-bottom:8px;">'
                                f'{accts_sum} accounts · {neg_sum} negative · {inq_sum} inquiries</div>',
                                unsafe_allow_html=True,
                            )

                else:
                    bureau_key_l = _active_letter_key
                    letter_data = letters[bureau_key_l]
                    bureau_title = bureau_key_l.title() if bureau_key_l != 'unknown' else 'Credit Bureau'
                    categories = letter_data.get('categories', [])
                    claim_count = letter_data.get('claim_count', 0)

                    if st.button("\u2190 Back to Letters", key="letter_back", use_container_width=False):
                        st.session_state.doc_active_letter = None
                        st.rerun()

                    human_cats = [humanize_category(c) for c in categories[:6]]
                    cat_summary = ", ".join(human_cats) if human_cats else ""
                    _item_word_d = "items" if claim_count != 1 else "item"

                    st.markdown(
                        f'<div class="glass-card glass-header" style="padding:12px 16px;">'
                        f'<div style="font-size:1.05rem;font-weight:800;color:{TEXT_0};">{bureau_title} Letter</div>'
                        f'<div style="font-size:0.78rem;color:{TEXT_1};">{claim_count} disputed {_item_word_d}'
                        f'{" · " + cat_summary if cat_summary else ""}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    if 'letter_edits' not in st.session_state:
                        st.session_state.letter_edits = {}

                    letter_text_original = letter_data['letter_text']
                    if bureau_key_l not in st.session_state.letter_edits:
                        st.session_state.letter_edits[bureau_key_l] = letter_text_original

                    if 'letter_edit_mode' not in st.session_state:
                        st.session_state.letter_edit_mode = {}

                    _edit_active = st.session_state.letter_edit_mode.get(bureau_key_l, False)
                    _current_text = st.session_state.letter_edits[bureau_key_l]
                    is_edited = _current_text != letter_text_original

                    _mode_cols = st.columns([1, 1, 1])
                    with _mode_cols[0]:
                        if _edit_active:
                            if st.button("Preview", key=f"preview_{bureau_key_l}", use_container_width=True):
                                st.session_state.letter_edit_mode[bureau_key_l] = False
                                st.rerun()
                        else:
                            if st.button("Edit Letter", key=f"editbtn_{bureau_key_l}", use_container_width=True):
                                st.session_state.letter_edit_mode[bureau_key_l] = True
                                st.rerun()
                    with _mode_cols[1]:
                        if is_edited:
                            if st.button("Reset", key=f"reset_{bureau_key_l}", use_container_width=True):
                                st.session_state.letter_edits[bureau_key_l] = letter_text_original
                                st.session_state.letter_edit_mode[bureau_key_l] = False
                                st.rerun()
                    with _mode_cols[2]:
                        if is_edited:
                            st.markdown(
                                f'<div style="font-size:0.72rem;color:{GOLD};padding-top:8px;text-align:right;">Edited</div>',
                                unsafe_allow_html=True,
                            )

                    if _edit_active:
                        edit_key = f"edit_area_{bureau_key_l}"
                        edited_text = st.text_area(
                            "Edit your letter:",
                            value=_current_text,
                            height=400,
                            key=edit_key,
                            label_visibility="collapsed",
                        )
                        st.session_state.letter_edits[bureau_key_l] = edited_text
                        _current_text = edited_text
                    else:
                        _preview_lines = _current_text.split('\n')
                        _preview_html_parts = []
                        for _pl in _preview_lines:
                            _pl_stripped = _pl.strip()
                            if not _pl_stripped:
                                _preview_html_parts.append('<div style="height:10px;"></div>')
                            elif _pl_stripped.startswith('DISPUTED ITEM') or _pl_stripped.startswith('Re:') or _pl_stripped.startswith('Subject:'):
                                _preview_html_parts.append(
                                    f'<div style="font-weight:700;color:{TEXT_0};font-size:0.88rem;margin:6px 0 2px;">{_pl_stripped}</div>'
                                )
                            elif _pl_stripped.startswith('Dispute:') or _pl_stripped.startswith('I demand:') or _pl_stripped.startswith('Applicable law:'):
                                _preview_html_parts.append(
                                    f'<div style="font-weight:600;color:{GOLD};font-size:0.82rem;margin:4px 0 1px;">{_pl_stripped}</div>'
                                )
                            else:
                                import html as _html_mod
                                _preview_html_parts.append(
                                    f'<div style="color:{TEXT_0};font-size:0.82rem;line-height:1.5;">{_html_mod.escape(_pl_stripped)}</div>'
                                )
                        _letter_preview_html = '\n'.join(_preview_html_parts)
                        st.markdown(
                            f'<div style="background:{BG_0};border:1px solid {BORDER};border-radius:10px;'
                            f'padding:20px 18px;max-height:420px;overflow-y:auto;margin-bottom:8px;'
                            f'font-family:\'Times New Roman\',Times,serif;">'
                            f'{_letter_preview_html}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                    _proof_check_detail = db.has_proof_docs(user_id_dash)
                    if not _proof_check_detail['both']:
                        st.markdown(
                            f'<div style="background:{BG_1};border:1px solid rgba(192,57,43,0.4);border-radius:10px;'
                            f'padding:10px 14px;margin:8px 0;display:flex;align-items:center;justify-content:space-between;">'
                            f'<div style="font-size:0.82rem;color:#e74c3c;font-weight:600;">'
                            f'ID & address proof needed to download</div>'
                            f'<a href="/?page=proof" target="_self" style="color:{GOLD};font-weight:700;font-size:0.82rem;text-decoration:none;">'
                            f'Upload &rarr;</a>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        letter_text_final = _current_text
                        filename = format_letter_filename(bureau_key_l)
                        _sig_for_pdf_l = st.session_state.get('_user_signature_bytes') or (db.get_user_signature(user_id) if user_id else None)
                        _proof_docs_l = _get_proof_docs_for_pdf(user_id)
                        pdf_bytes = generate_letter_pdf(letter_text_final, signature_image=_sig_for_pdf_l, proof_documents=_proof_docs_l)

                        import base64
                        _b64_pdf = base64.b64encode(pdf_bytes).decode()
                        _b64_txt = base64.b64encode(letter_text_final.encode()).decode()

                        import streamlit.components.v1 as _dl_components
                        _dl_components.html(
                            f'''<div style="display:flex;gap:8px;font-family:'Inter',-apple-system,sans-serif;">
                            <button id="dlPdfBtn" onclick="dlFile(this,'{_b64_pdf}','application/pdf','{filename}.pdf','Download PDF')"
                            style="flex:1;padding:10px 16px;background:linear-gradient(90deg,{GOLD},#f2c94c);color:#1a1a1f;
                            font-weight:600;font-size:0.88rem;border-radius:10px;border:none;cursor:pointer;
                            box-shadow:0 4px 16px rgba(212,160,23,0.25);transition:all 0.3s ease;">Download PDF</button>
                            <button id="dlTxtBtn" onclick="dlFile(this,'{_b64_txt}','text/plain','{filename}.txt','Download Text')"
                            style="flex:1;padding:10px 16px;background:{BG_2};color:{TEXT_0};
                            font-weight:500;font-size:0.88rem;border-radius:10px;border:1px solid rgba(255,215,140,0.15);cursor:pointer;
                            transition:all 0.3s ease;">Download Text</button>
                            </div>
                            <script>
                            function dlFile(btn,b64,mime,name,orig){{
                              var bin=atob(b64);var arr=new Uint8Array(bin.length);
                              for(var i=0;i<bin.length;i++)arr[i]=bin.charCodeAt(i);
                              var blob=new Blob([arr],{{type:mime}});
                              var url=URL.createObjectURL(blob);
                          var a=document.createElement('a');a.href=url;a.download=name;
                          document.body.appendChild(a);a.click();
                          setTimeout(function(){{document.body.removeChild(a);URL.revokeObjectURL(url);}},100);
                          var prevBg=btn.style.background;var prevColor=btn.style.color;
                          btn.innerHTML="&#x2705; Downloaded!";
                          btn.style.background="linear-gradient(90deg,#2ecc71,#27ae60)";
                          btn.style.color="#fff";
                              setTimeout(function(){{btn.innerHTML=orig;btn.style.background=prevBg;btn.style.color=prevColor;}},2500);
                            }}
                            </script>''',
                            height=50,
                        )

                    rc_details = letter_data.get('rc_details', [])
                    if rc_details:
                        with st.expander(f"Accounts in this letter ({len(rc_details)})", expanded=False):
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
                                        f'{creditor_d} <span style="color:{TEXT_1};opacity:0.6;">\u2014 {rtype_d}</span></div>',
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
                                    if not st.session_state.get('_voice_profile'):
                                        st.session_state._voice_profile = db.get_effective_voice_profile(user_id) if user_id else db.VOICE_PROFILE_DEFAULTS
                                    advance_card("GENERATING")
                                    st.rerun()

                _upgrade_user_has_mail = auth.has_entitlement(user_id, 'mailings') or is_admin_user
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
                    if st.button("Upgrade to Full Round \u2014 We Handle Everything", key="upgrade_full_round_post_download", type="primary", use_container_width=True):
                        result = create_checkout_session(
                            user_id, current_user.get('email', ''),
                            'full_round', _fr_pack.get('label', 'Full Round'), _fr_pack.get('price_cents', 2499),
                            ai_rounds=_fr_pack.get('ai_rounds', 1), letters=_fr_pack.get('letters', 3), mailings=_fr_pack.get('mailings', 3),
                            workflow_id=ensure_active_workflow_id(user_id),
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

                has_mail_ent = auth.has_entitlement(user_id, 'mailings') or is_admin_user
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
                        f"Skip the post office. We\'ll print, certify, and mail your letters for you \u2014 "
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

                    _saved_proof = db.has_proof_docs(current_user.get('user_id'))
                    _has_saved_id = _saved_proof['has_id']
                    _has_saved_addr = _saved_proof['has_address']

                    id_file = None
                    addr_proof_file = None

                    if _saved_proof['both']:
                        st.markdown(
                            f'<div style="background:linear-gradient(135deg, rgba(46,204,113,0.12), rgba(46,204,113,0.04));'
                            f'border:1px solid #2ecc71;border-radius:10px;padding:12px 16px;margin-bottom:10px;">'
                            f'<div style="font-size:0.88rem;font-weight:700;color:#2ecc71;margin-bottom:4px;">'
                            f'&#x2705; Your ID and address proof are on file</div>'
                            f'<div style="font-size:0.78rem;color:{TEXT_1};">'
                            f'These will be included with your certified mail. '
                            f'<a href="/?page=proof" target="_self" style="color:{GOLD};">Update documents</a></div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f'<div style="background:linear-gradient(135deg, rgba(192,57,43,0.15), rgba(192,57,43,0.05));'
                            f'border:2px solid #c0392b;border-radius:12px;padding:14px 16px;margin-bottom:10px;">'
                            f'<div style="font-size:0.92rem;font-weight:800;color:#e74c3c;margin-bottom:6px;">'
                            f'&#x1F512; Upload your documents first</div>'
                            f'<div style="font-size:0.82rem;color:{TEXT_0};line-height:1.6;margin-bottom:10px;">'
                            f'You must upload your ID and proof of address before we can send your letters.</div>'
                            f'<a href="/?page=proof" target="_self" style="display:inline-block;padding:10px 24px;'
                            f'background:linear-gradient(90deg,{GOLD},#f2c94c);color:#1a1a1f;font-weight:700;'
                            f'font-size:0.9rem;border-radius:10px;text-decoration:none;">'
                            f'Upload Documents &rarr;</a>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    max_size = 5 * 1024 * 1024
                    size_error = False
                    if id_file and len(id_file.getvalue()) > max_size:
                        st.error("ID file is too large. Please upload a file under 5 MB.")
                        size_error = True
                    if addr_proof_file and len(addr_proof_file.getvalue()) > max_size:
                        st.error("Address proof file is too large. Please upload a file under 5 MB.")
                        size_error = True
                    _id_ready = id_file is not None or _has_saved_id
                    _addr_ready = addr_proof_file is not None or _has_saved_addr
                    if not _id_ready or not _addr_ready:
                        st.warning("Both proof of ID and proof of address are required to send certified mail.")

                    if st.session_state.lob_send_results:
                        _failed_keys_inline = []
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
                                _failed_keys_inline.append(bk)
                        for _fk in _failed_keys_inline:
                            if st.button(f"Retry sending to {_fk.title()}", key=f"retry_lob_inline_{_fk}", type="primary"):
                                del st.session_state.lob_send_results[_fk]
                                st.rerun()

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
                            docs_ready = (_id_ready and _addr_ready) and not size_error

                            _dl_letter_text_m = letter_data_send.get('letter_text', '')
                            if _dl_letter_text_m:
                                _dl_fn_m = format_letter_filename(bureau_key_send)
                                _sig_for_pdf_m = st.session_state.get('_user_signature_bytes') or (db.get_user_signature(user_id) if user_id else None)
                                _proof_docs_m = _get_proof_docs_for_pdf(user_id)
                                _dl_pdf_m = generate_letter_pdf(_dl_letter_text_m, signature_image=_sig_for_pdf_m, proof_documents=_proof_docs_m)
                                import base64 as _b64m
                                _dl_b64_m = _b64m.b64encode(_dl_pdf_m).decode()
                                import streamlit.components.v1 as _dl_cm
                                _dl_cm.html(
                                    f'''<script>var _d{bureau_key_send}="{_dl_b64_m}";</script>
                                    <button id="dlCm{bureau_key_send}" onclick="var btn=this;var bin=atob(_d{bureau_key_send});var a=new Uint8Array(bin.length);
                                    for(var i=0;i<bin.length;i++)a[i]=bin.charCodeAt(i);
                                    var b=new Blob([a],{{type:'application/pdf'}});var u=URL.createObjectURL(b);
                                    var l=document.createElement('a');l.href=u;l.download='{_dl_fn_m}.pdf';
                                    document.body.appendChild(l);l.click();
                                    setTimeout(function(){{document.body.removeChild(l);URL.revokeObjectURL(u);}},100);
                                    btn.innerHTML='&#x2705; Downloaded!';btn.style.background='linear-gradient(90deg,#2ecc71,#27ae60)';
                                    setTimeout(function(){{btn.innerHTML='&#x1F4E5; Download {bureau_title_send} Letter';btn.style.background='#c0392b';}},2500);"
                                    style="width:100%;padding:12px 16px;background:#c0392b;color:#fff;
                                    font-weight:700;font-size:0.9rem;border-radius:10px;border:none;cursor:pointer;
                                    box-shadow:0 4px 16px rgba(192,57,43,0.3);font-family:'Inter',-apple-system,sans-serif;
                                    margin-bottom:4px;transition:all 0.3s ease;">
                                    &#x1F4E5; Download {bureau_title_send} Letter</button>''',
                                    height=55,
                                )

                            _confirm_key = f"confirm_send_{bureau_key_send}"
                            st.markdown(
                                f'<div style="font-size:0.78rem;color:{TEXT_1};padding:4px 0;">'
                                f'This will mail your letter to <strong style="color:{TEXT_0};">{bureau_title_send}</strong> '
                                f'via USPS Certified Mail with return receipt. Cost: <strong style="color:{GOLD};">1 mailing credit</strong>.</div>',
                                unsafe_allow_html=True,
                            )
                            if st.button(
                                f"Send to {bureau_title_send} ({cost_info['total_display']})",
                                key=send_key,
                                use_container_width=True,
                                type="primary",
                                disabled=not docs_ready,
                            ):
                                if not addr_valid['valid']:
                                    st.error(f"Please fix your return address: {addr_valid['error']}")
                                elif not is_admin_user and not auth.spend_entitlement(user_id, 'mailings', 1):
                                    st.error("You don't have any mailing entitlements remaining. Purchase more to send certified mail.")
                                else:
                                    st.session_state.lob_return_address = from_addr

                                    attachments = []
                                    if id_file is not None:
                                        attachments.append({"name": "Government-Issued ID", "data": id_file.getvalue(), "type": id_file.type or "image/png"})
                                    elif _has_saved_id:
                                        _saved_id_docs = db.get_proof_docs_for_user(current_user.get('user_id'), doc_types=['government_id'])
                                        if _saved_id_docs:
                                            _saved_id_file = db.get_proof_doc_file(_saved_id_docs[0]['id'], current_user.get('user_id'))
                                            if _saved_id_file and _saved_id_file.get('file_data'):
                                                attachments.append({"name": "Government-Issued ID", "data": bytes(_saved_id_file['file_data']), "type": _saved_id_file.get('file_type', 'image/png')})
                                    if addr_proof_file is not None:
                                        attachments.append({"name": "Proof of Address", "data": addr_proof_file.getvalue(), "type": addr_proof_file.type or "image/png"})
                                    elif _has_saved_addr:
                                        _saved_addr_docs = db.get_proof_docs_for_user(current_user.get('user_id'), doc_types=['address_proof'])
                                        if _saved_addr_docs:
                                            _saved_addr_file = db.get_proof_doc_file(_saved_addr_docs[0]['id'], current_user.get('user_id'))
                                            if _saved_addr_file and _saved_addr_file.get('file_data'):
                                                attachments.append({"name": "Proof of Address", "data": bytes(_saved_addr_file['file_data']), "type": _saved_addr_file.get('file_type', 'image/png')})

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

                                    if not result.get('success'):
                                        try:
                                            from services.workflow import hooks as workflow_hooks

                                            workflow_hooks.notify_mail_send_failed(
                                                user_id,
                                                str(result.get('error') or 'MAIL_SEND_FAILED')[:64],
                                                str(
                                                    result.get('message')
                                                    or result.get('error_message')
                                                    or 'Certified mail could not be sent.',
                                                )[:500],
                                            )
                                        except Exception:
                                            pass

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
                                            workflow_id=ensure_active_workflow_id(current_user.get('user_id')),
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
                        f"You get a tracking number and legal proof of delivery \u2014 starting the 30-day clock.</div>"
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

            else:
                st.markdown(f'''
                <div class="glass-card">
                    <div class="glass-section-title">No Letters Yet</div>
                    <div style="font-size:0.85rem;color:{TEXT_1};">
                        You currently have no dispute-ready items based on what could be confidently extracted.
                        Try a different bureau report or re-upload a clearer PDF.
                    </div>
                </div>
                ''', unsafe_allow_html=True)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PANEL: STRATEGY
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        elif _panel == 'strategy':
            if st.button("\u2190 Back", key="str_back", use_container_width=False):
                go('home')

            st.markdown(f'''
            <div class="glass-card">
                <div class="glass-section-title">&#x26A1; 72-Hour Credit Strike Protocol</div>
            </div>
            ''', unsafe_allow_html=True)

            _wr_cached = st.session_state.get('war_room_plan')
            _all_sm_wr = st.session_state.get('strike_metrics', {})

            if not _all_sm_wr:
                st.markdown(
                    f'<div style="text-align:center;padding:2rem;color:{TEXT_1};font-size:0.9rem;">'
                    f'Upload and analyze your credit reports to activate the War Room.</div>',
                    unsafe_allow_html=True,
                )
            else:
                _wr_mission_cols = st.columns(2)
                with _wr_mission_cols[0]:
                    _mg = st.selectbox(
                        "Mission Goal",
                        ["Auto Purchase", "Apartment", "Credit Card", "Bank Account", "General Rebuild"],
                        index=["Auto Purchase", "Apartment", "Credit Card", "Bank Account", "General Rebuild"].index(
                            st.session_state.get('mission_goal', 'General Rebuild')
                        ),
                        key="wr_mission_goal",
                    )
                with _wr_mission_cols[1]:
                    _mt = st.selectbox(
                        "Timeline",
                        ["ASAP (7 days)", "30 days", "90 days"],
                        index=["ASAP (7 days)", "30 days", "90 days"].index(
                            st.session_state.get('mission_timeline', 'ASAP (7 days)')
                        ),
                        key="wr_mission_timeline",
                    )

                if _mg != st.session_state.get('mission_goal') or _mt != st.session_state.get('mission_timeline'):
                    st.session_state['mission_goal'] = _mg
                    st.session_state['mission_timeline'] = _mt
                    st.session_state.pop('war_room_plan', None)
                    st.rerun()

                st.session_state['mission_goal'] = _mg
                st.session_state['mission_timeline'] = _mt

                _combined_sm_wr = {}
                for _b_sm_wr, _v_sm_wr in _all_sm_wr.items():
                    for _k_wr, _val_wr in _v_sm_wr.items():
                        if _k_wr == 'data_quality':
                            continue
                        if _k_wr not in _combined_sm_wr:
                            _combined_sm_wr[_k_wr] = _val_wr
                        elif isinstance(_val_wr, (int, float)) and _val_wr and isinstance(_combined_sm_wr[_k_wr], (int, float)):
                            _combined_sm_wr[_k_wr] = max(_combined_sm_wr[_k_wr], _val_wr)
                        elif isinstance(_val_wr, bool) and _val_wr:
                            _combined_sm_wr[_k_wr] = True

                _wr = build_war_room_plan(
                    strike_metrics=_combined_sm_wr,
                    has_letters=has_letters,
                    has_mailed=_ws_mailed,
                    days_elapsed=_ws_days_elapsed if _ws_mailed else 0,
                    mission_goal=_mg,
                    mission_timeline=_mt,
                )
                st.session_state['war_room_plan'] = _wr.as_dict()

                _wr_risk = _wr.risk_level
                _wr_lever = _wr.primary_lever
                _risk_colors_wr = {'HIGH': '#EF5350', 'MODERATE': '#FFA726', 'CONTROLLED': '#66BB6A'}
                _risk_color_wr = _risk_colors_wr.get(_wr_risk, TEXT_1)
                _lever_colors_wr = {'UTILIZATION': '#EF5350', 'DELETION': '#FFA726', 'STABILITY': '#42A5F5', 'OPTIMIZATION': '#66BB6A'}
                _lever_color_wr = _lever_colors_wr.get(_wr_lever, TEXT_1)

                st.markdown(f'''
                <div class="glass-card" style="padding:12px 16px;margin-bottom:12px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <span style="font-size:0.82rem;font-weight:700;color:{_risk_color_wr};">Risk: {_wr_risk}</span>
                            <span style="color:{TEXT_1};margin:0 6px;">&middot;</span>
                            <span style="font-size:0.82rem;font-weight:600;color:{_lever_color_wr};">Lever: {_wr_lever}</span>
                        </div>
                        <div style="font-size:0.75rem;color:{TEXT_1};">{_mg} &middot; {_mt}</div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)

                if 'war_room_done' not in st.session_state:
                    st.session_state['war_room_done'] = {}

                _all_wr_actions = []
                for _ph_key in ("0-6", "6-24", "24-48", "48-72"):
                    _all_wr_actions.extend(_wr.phases.get(_ph_key, []))
                _wr_total = len(_all_wr_actions)
                _wr_completed = sum(1 for a in _all_wr_actions if st.session_state['war_room_done'].get(a['id'], False))

                st.markdown(
                    f'<div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:12px;text-align:center;">'
                    f'<strong style="color:{GOLD};">{_wr_completed}</strong> / {_wr_total} actions complete</div>',
                    unsafe_allow_html=True,
                )

                st.markdown(f'<div style="font-size:0.78rem;font-weight:700;color:{GOLD_DIM};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;">Top Priority</div>', unsafe_allow_html=True)
                for _idx_ta, _ta_wr in enumerate(_wr.top3_actions[:3]):
                    _ta_done = st.session_state['war_room_done'].get(_ta_wr['id'], False)
                    _ta_cols = st.columns([0.08, 0.92])
                    with _ta_cols[0]:
                        if st.checkbox("", value=_ta_done, key=f"wr_top_{_idx_ta}", label_visibility="collapsed"):
                            st.session_state['war_room_done'][_ta_wr['id']] = True
                        else:
                            st.session_state['war_room_done'][_ta_wr['id']] = False
                    with _ta_cols[1]:
                        _ta_style = f"text-decoration:line-through;color:{TEXT_1};" if _ta_done else f"color:{TEXT_0};"
                        st.markdown(
                            f'<div style="font-size:0.88rem;font-weight:600;{_ta_style}">{_ta_wr["title"]}</div>'
                            f'<div style="font-size:0.75rem;color:{TEXT_1};margin-bottom:4px;">{_ta_wr["why"][:120]}</div>',
                            unsafe_allow_html=True,
                        )
                        if _ta_wr.get('primary_button_label') and _ta_wr.get('primary_route'):
                            if st.button(_ta_wr['primary_button_label'], key=f"wr_top_btn_{_idx_ta}", use_container_width=True):
                                go(_ta_wr['primary_route'])

                for _ph_key in ("0-6", "6-24", "24-48", "48-72"):
                    _ph_actions = _wr.phases.get(_ph_key, [])
                    if not _ph_actions:
                        continue
                    _ph_done_count = sum(1 for a in _ph_actions if st.session_state['war_room_done'].get(a['id'], False))
                    _ph_label = PHASE_LABELS.get(_ph_key, _ph_key)
                    _ph_suffix = f" ({_ph_done_count}/{len(_ph_actions)})"

                    with st.expander(f"{_ph_label}{_ph_suffix}", expanded=False):
                        for _a_idx, _action in enumerate(_ph_actions):
                            _a_id = _action['id']
                            _a_done = st.session_state['war_room_done'].get(_a_id, False)

                            _a_cols = st.columns([0.08, 0.92])
                            with _a_cols[0]:
                                _new_val = st.checkbox("", value=_a_done, key=f"wr_{_ph_key}_{_a_idx}", label_visibility="collapsed")
                                st.session_state['war_room_done'][_a_id] = _new_val
                            with _a_cols[1]:
                                _a_style = f"text-decoration:line-through;color:{TEXT_1};" if _new_val else f"color:{TEXT_0};"
                                st.markdown(
                                    f'<div style="font-size:0.88rem;font-weight:600;{_a_style}">{_action["title"]}</div>'
                                    f'<div style="font-size:0.75rem;color:{TEXT_1};margin-bottom:2px;">{_action["why"][:150]}</div>'
                                    f'<div style="font-size:0.7rem;color:{GOLD_DIM};margin-bottom:4px;">Done when: {_action["success_criteria"]}</div>',
                                    unsafe_allow_html=True,
                                )

                                _has_primary_btn = _action.get('primary_button_label') and _action.get('primary_route')
                                _has_secondary_btn = _action.get('secondary_route')
                                if _has_primary_btn:
                                    _btn_cols = st.columns([1, 1] if _has_secondary_btn else [1])
                                    with _btn_cols[0]:
                                        if st.button(_action['primary_button_label'], key=f"wr_btn_{_ph_key}_{_a_idx}", use_container_width=True):
                                            go(_action['primary_route'])
                                    if _has_secondary_btn and len(_btn_cols) > 1:
                                        with _btn_cols[1]:
                                            if st.button(_action.get('secondary_button_label', 'More'), key=f"wr_btn2_{_ph_key}_{_a_idx}", use_container_width=True):
                                                go(_action['secondary_route'])

                                if _action.get('script'):
                                    with st.expander("Script", expanded=False):
                                        st.code(_action['script'], language=None)

                if _wr.notes:
                    st.markdown(f'<div style="margin-top:12px;font-size:0.75rem;color:{TEXT_1};">', unsafe_allow_html=True)
                    for _note in _wr.notes:
                        st.markdown(f'<div style="margin-bottom:4px;">&#x26A0;&#xFE0F; {_note}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

            with st.expander("72-Hour Tactical Plan (Legacy)", expanded=False):
                _ccp_cache_key = '_credit_command_plan'
                if _ccp_cache_key not in st.session_state:
                    try:
                        from credit_command_plan import build_credit_command_plan
                        from review_claims import ReviewType as _RT
                        _bp_items = st.session_state.get('_gen_selected_items', [])
                        _items_by_type = {}
                        for _rc in _bp_items:
                            rt = _rc.review_type
                            if rt not in _items_by_type:
                                _items_by_type[rt] = []
                            _items_by_type[rt].append(_rc)
                        _sel_bureaus = set()
                        for _rc in _bp_items:
                            _b = (_rc.entities.get('bureau') or '').lower()
                            if _b:
                                _sel_bureaus.add(_b)
                        st.session_state[_ccp_cache_key] = build_credit_command_plan(
                            items_by_type=_items_by_type,
                            selected_count=len(_bp_items),
                            bureaus=_sel_bureaus if _sel_bureaus else {'equifax', 'experian', 'transunion'},
                            parsed_reports=st.session_state.uploaded_reports,
                        )
                    except Exception:
                        st.session_state[_ccp_cache_key] = None

                _ccp = st.session_state.get(_ccp_cache_key)
                if _ccp:
                    from credit_command_plan import render_command_plan_html
                    _ccp_colors = {"TEXT_0": TEXT_0, "TEXT_1": TEXT_1, "GOLD": GOLD, "BG_1": BG_1, "BORDER": BORDER}
                    st.markdown(render_command_plan_html(_ccp, _ccp_colors), unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div style="text-align:center;padding:1rem;color:{TEXT_1};font-size:0.88rem;">'
                        f'Generate your dispute letters first to see your strategy plan.</div>',
                        unsafe_allow_html=True,
                    )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PANEL: LETTER BANK
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        elif _panel == 'letter_bank':
            if st.button("\u2190 Back", key="lb_back", use_container_width=False):
                go('home')

            st.markdown(f'''
            <div class="glass-card">
                <div class="glass-section-title">&#x1F4DC; Letter Bank</div>
                <div style="color:{TEXT_1};font-size:0.88rem;margin-top:4px;">All your dispute letters in one place. Download anytime.</div>
            </div>
            ''', unsafe_allow_html=True)

            _lb_letters = db.get_all_letters_for_user(user_id_dash)
            if not _lb_letters:
                st.markdown(
                    f'<div style="text-align:center;padding:2rem;color:{TEXT_1};font-size:0.92rem;">'
                    f'No letters yet. Upload a credit report and generate dispute letters to see them here.</div>',
                    unsafe_allow_html=True,
                )
            else:
                _lb_sig = st.session_state.get('_user_signature_bytes') or (db.get_user_signature(user_id_dash) if user_id_dash else None)
                _lb_proof = _get_proof_docs_for_pdf(user_id_dash)

                _lb_rounds = {}
                for _lb_l in _lb_letters:
                    _rn = _lb_l.get('round_number', 1) or 1
                    if _rn not in _lb_rounds:
                        _lb_rounds[_rn] = []
                    _lb_rounds[_rn].append(_lb_l)

                if len(_lb_letters) > 1:
                    _lb_zip_buf = BytesIO()
                    import zipfile as _lb_zf
                    with _lb_zf.ZipFile(_lb_zip_buf, 'w', _lb_zf.ZIP_DEFLATED) as _lb_zip:
                        for _lb_lz in _lb_letters:
                            _lb_fn = format_letter_filename(_lb_lz.get('bureau', 'unknown'))
                            _lb_rn = _lb_lz.get('round_number', 1) or 1
                            _lb_zip.writestr(f"round{_lb_rn}/{_lb_fn}.pdf",
                                             generate_letter_pdf(_lb_lz['letter_text'], signature_image=_lb_sig, proof_documents=_lb_proof))
                            _lb_zip.writestr(f"round{_lb_rn}/{_lb_fn}.txt", _lb_lz['letter_text'])
                    import base64 as _lb_b64
                    _lb_zip_data = _lb_b64.b64encode(_lb_zip_buf.getvalue()).decode()
                    _lb_zip_fn = f"all_dispute_letters_{datetime.now().strftime('%Y%m%d')}.zip"
                    import streamlit.components.v1 as _lb_comp
                    _lb_comp.html(
                        f'''<script>var _lbzd="{_lb_zip_data}";</script>
                        <button onclick="(function(){{var b=atob(_lbzd);var a=new Uint8Array(b.length);for(var i=0;i<b.length;i++)a[i]=b.charCodeAt(i);
                        var bl=new Blob([a],{{type:'application/zip'}});var u=URL.createObjectURL(bl);var l=document.createElement('a');
                        l.href=u;l.download='{_lb_zip_fn}';l.click();URL.revokeObjectURL(u)}})()" style="width:100%;padding:12px 16px;margin-bottom:16px;
                        background:linear-gradient(135deg,{GOLD_DIM},{GOLD});border:none;color:#0f0f12;
                        font-weight:700;font-size:0.9rem;border-radius:10px;cursor:pointer;
                        font-family:'Inter',-apple-system,sans-serif;">&#x1F4E5; Download All Letters (ZIP)</button>''',
                        height=55)

                for _lb_rn_key in sorted(_lb_rounds.keys()):
                    _lb_round_letters = _lb_rounds[_lb_rn_key]
                    st.markdown(
                        f'<div style="font-size:0.72rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;'
                        f'color:{GOLD_DIM};margin:16px 0 8px;padding-bottom:4px;border-bottom:1px solid {BORDER};">'
                        f'Round {_lb_rn_key}</div>',
                        unsafe_allow_html=True,
                    )

                    for _lb_lt in _lb_round_letters:
                        _lb_bureau = (_lb_lt.get('bureau') or 'unknown').title()
                        _lb_created = _lb_lt.get('created_at')
                        if hasattr(_lb_created, 'strftime'):
                            _lb_dt = _lb_created.strftime('%b %d, %Y')
                        else:
                            _lb_dt = str(_lb_created)[:10] if _lb_created else '—'

                        _lb_text = _lb_lt.get('letter_text', '')
                        _lb_meta = _lb_lt.get('metadata')
                        if isinstance(_lb_meta, str):
                            try:
                                _lb_meta = json.loads(_lb_meta)
                            except Exception:
                                _lb_meta = {}
                        elif not isinstance(_lb_meta, dict):
                            _lb_meta = {}
                        _lb_violations = _lb_meta.get('violation_count', 0)
                        _lb_cats = _lb_meta.get('categories', [])
                        _lb_cat_str = ', '.join(_lb_cats[:3]) if _lb_cats else ''

                        _lb_snippet = (_lb_text[:150].replace('\n', ' ') + '...') if len(_lb_text) > 150 else _lb_text.replace('\n', ' ')

                        st.markdown(
                            f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;padding:14px 18px;margin-bottom:8px;">'
                            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                            f'<div style="font-size:0.95rem;font-weight:700;color:{TEXT_0};">{_lb_bureau}</div>'
                            f'<div style="font-size:0.75rem;color:{TEXT_1};">{_lb_dt}</div>'
                            f'</div>'
                            f'{"<div style=" + chr(34) + "font-size:0.78rem;color:" + GOLD + ";margin-top:4px;" + chr(34) + ">" + str(_lb_violations) + " violations cited &middot; " + _lb_cat_str + "</div>" if _lb_violations else ""}'
                            f'<div style="font-size:0.78rem;color:{TEXT_1};margin-top:6px;font-style:italic;">{_lb_snippet}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                        _lb_lid = _lb_lt.get('id', 0)
                        _lb_pdf = generate_letter_pdf(_lb_text, signature_image=_lb_sig, proof_documents=_lb_proof)
                        _lb_pdf_b64 = __import__('base64').b64encode(_lb_pdf).decode()
                        _lb_pdf_fn = f"dispute_letter_{_lb_lt.get('bureau', 'unknown')}_r{_lb_rn_key}.pdf"
                        import streamlit.components.v1 as _lb_dl_comp
                        _lb_dl_comp.html(
                            f'''<script>var _lbd{_lb_lid}="{_lb_pdf_b64}";</script>
                            <button onclick="(function(){{var b=atob(_lbd{_lb_lid});var a=new Uint8Array(b.length);for(var i=0;i<b.length;i++)a[i]=b.charCodeAt(i);
                            var bl=new Blob([a],{{type:'application/pdf'}});var u=URL.createObjectURL(bl);var l=document.createElement('a');
                            l.href=u;l.download='{_lb_pdf_fn}';l.click();URL.revokeObjectURL(u)}})()" style="width:100%;padding:8px 14px;margin-bottom:12px;
                            background:{BG_2};border:1px solid {BORDER};color:{GOLD};
                            font-weight:600;font-size:0.82rem;border-radius:8px;cursor:pointer;
                            font-family:'Inter',-apple-system,sans-serif;">&#x1F4E5; Download PDF</button>''',
                            height=48)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PANEL: SEND MAIL
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        elif _panel == 'send_mail':
            if st.button("\u2190 Back", key="mail_back", use_container_width=False):
                go('home')

            st.markdown(f'''
            <div class="glass-card">
                <div class="glass-section-title">&#x2709;&#xFE0F; Send Certified Mail</div>
                <div style="font-size:0.82rem;color:{TEXT_1};margin-top:4px;">Skip the post office \u2014 we handle everything.</div>
            </div>
            ''', unsafe_allow_html=True)

            has_mail_ent = auth.has_entitlement(user_id, 'mailings') or is_admin_user
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

                saved_addr = st.session_state.lob_return_address
                addr_name = st.text_input("Your Full Name", value=saved_addr.get('name', current_user.get('display_name', '')), key="sm_addr_name")
                addr_line1 = st.text_input("Street Address", value=saved_addr.get('address_line1', ''), key="sm_addr_line1")
                addr_line2 = st.text_input("Apt / Suite (optional)", value=saved_addr.get('address_line2', ''), key="sm_addr_line2")

                addr_col1, addr_col2, addr_col3 = st.columns([2, 1, 1])
                with addr_col1:
                    addr_city = st.text_input("City", value=saved_addr.get('address_city', ''), key="sm_addr_city")
                with addr_col2:
                    state_idx = 0
                    saved_state = saved_addr.get('address_state', '')
                    if saved_state and saved_state.upper() in lob_client.US_STATES:
                        state_idx = lob_client.US_STATES.index(saved_state.upper())
                    addr_state = st.selectbox("State", options=lob_client.US_STATES, index=state_idx, key="sm_addr_state")
                with addr_col3:
                    addr_zip = st.text_input("ZIP Code", value=saved_addr.get('address_zip', ''), key="sm_addr_zip")

                return_receipt = st.checkbox("Include Return Receipt", value=True, key="sm_return_receipt")
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

                _sm_proof = db.has_proof_docs(current_user.get('user_id'))
                _sm_has_id = _sm_proof['has_id']
                _sm_has_addr = _sm_proof['has_address']
                id_file = None
                addr_proof_file = None
                max_size = 5 * 1024 * 1024
                size_error = False

                if _sm_proof['both']:
                    st.markdown(
                        f'<div style="font-size:0.82rem;color:#2ecc71;font-weight:600;margin-bottom:8px;">'
                        f'&#x2705; ID and address proof on file &mdash; '
                        f'<a href="/?page=proof" target="_self" style="color:{GOLD};font-size:0.78rem;">update</a></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div style="background:{BG_1};border:1px solid rgba(192,57,43,0.4);border-radius:10px;'
                        f'padding:10px 14px;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;">'
                        f'<div style="font-size:0.82rem;color:#e74c3c;font-weight:600;">'
                        f'Upload ID & address proof first</div>'
                        f'<a href="/?page=proof" target="_self" style="color:{GOLD};font-weight:700;font-size:0.82rem;text-decoration:none;">'
                        f'Upload &rarr;</a>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                if st.session_state.lob_send_results:
                    _failed_keys_sm = []
                    for bk, res in st.session_state.lob_send_results.items():
                        if res.get('success'):
                            st.success(f"Letter to **{bk.title()}** sent! Tracking: {res.get('tracking_number', 'N/A')}")
                        elif res.get('error'):
                            st.error(f"Failed to send to {bk.title()}: {res['error']}")
                            _failed_keys_sm.append(bk)
                    for _fk in _failed_keys_sm:
                        if st.button(f"Retry sending to {_fk.title()}", key=f"retry_lob_sm_{_fk}", type="primary"):
                            del st.session_state.lob_send_results[_fk]
                            st.rerun()

                for bureau_key_send, letter_data_send in letters.items():
                    bureau_title_send = bureau_key_send.title() if bureau_key_send != 'unknown' else 'Credit Bureau'
                    already_sent = bureau_key_send in st.session_state.lob_send_results and st.session_state.lob_send_results[bureau_key_send].get('success')
                    current_report_id = st.session_state.get('current_report', {}).get('id') if st.session_state.get('current_report') else None
                    already_in_db = db.has_been_sent_via_lob(current_user.get('user_id'), bureau_key_send, report_id=current_report_id)

                    if already_sent or already_in_db:
                        st.markdown(
                            f'<div style="background:{BG_1};border:1px solid {BORDER};border-left:4px solid {GOLD};border-radius:10px;padding:10px 14px;margin-bottom:8px;">'
                            f'<strong>{bureau_title_send}</strong> &mdash; &#x2705; Sent</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        _sm_id_ready = id_file is not None or _sm_has_id
                        _sm_addr_ready = addr_proof_file is not None or _sm_has_addr
                        docs_ready = (_sm_id_ready and _sm_addr_ready) and not size_error
                        if st.button(f"Send to {bureau_title_send} ({cost_info['total_display']})", key=f"sm_send_{bureau_key_send}", use_container_width=True, type="primary", disabled=not docs_ready):
                            if not addr_valid['valid']:
                                st.error(f"Fix your return address: {addr_valid['error']}")
                            elif not is_admin_user and not auth.spend_entitlement(user_id, 'mailings', 1):
                                st.error("No mailing entitlements remaining.")
                            else:
                                st.session_state.lob_return_address = from_addr
                                attachments = []
                                if id_file is not None:
                                    attachments.append({"name": "Government-Issued ID", "data": id_file.getvalue(), "type": id_file.type or "image/png"})
                                elif _sm_has_id:
                                    _sm_id_docs = db.get_proof_docs_for_user(current_user.get('user_id'), doc_types=['government_id'])
                                    if _sm_id_docs:
                                        _sm_id_file = db.get_proof_doc_file(_sm_id_docs[0]['id'], current_user.get('user_id'))
                                        if _sm_id_file and _sm_id_file.get('file_data'):
                                            attachments.append({"name": "Government-Issued ID", "data": bytes(_sm_id_file['file_data']), "type": _sm_id_file.get('file_type', 'image/png')})
                                if addr_proof_file is not None:
                                    attachments.append({"name": "Proof of Address", "data": addr_proof_file.getvalue(), "type": addr_proof_file.type or "image/png"})
                                elif _sm_has_addr:
                                    _sm_addr_docs = db.get_proof_docs_for_user(current_user.get('user_id'), doc_types=['address_proof'])
                                    if _sm_addr_docs:
                                        _sm_addr_file = db.get_proof_doc_file(_sm_addr_docs[0]['id'], current_user.get('user_id'))
                                        if _sm_addr_file and _sm_addr_file.get('file_data'):
                                            attachments.append({"name": "Proof of Address", "data": bytes(_sm_addr_file['file_data']), "type": _sm_addr_file.get('file_type', 'image/png')})
                                with st.spinner(f"Sending certified letter to {bureau_title_send}..."):
                                    result = lob_client.create_certified_letter(
                                        from_address=from_addr, to_bureau=bureau_key_send,
                                        letter_text=letter_data_send['letter_text'], return_receipt=return_receipt,
                                        description=f"850 Lab dispute - {bureau_title_send}", attachments=attachments,
                                    )
                                st.session_state.lob_send_results[bureau_key_send] = result
                                if not result.get('success'):
                                    try:
                                        from services.workflow import hooks as workflow_hooks

                                        workflow_hooks.notify_mail_send_failed(
                                            user_id,
                                            str(result.get('error') or 'MAIL_SEND_FAILED')[:64],
                                            str(
                                                result.get('message')
                                                or result.get('error_message')
                                                or 'Certified mail could not be sent.',
                                            )[:500],
                                        )
                                    except Exception:
                                        pass
                                if result.get('success'):
                                    db.log_activity(user_id, 'mail_sent', f"Certified mail to {bureau_title_send}", 'DONE')
                                    report_id = None
                                    if st.session_state.get('current_report'):
                                        report_id = st.session_state.current_report.get('id')
                                    db.save_lob_send(
                                        user_id=current_user.get('user_id'), report_id=report_id, bureau=bureau_key_send,
                                        lob_id=result.get('lob_id', ''), tracking_number=result.get('tracking_number', ''),
                                        status='mailed', from_address=from_addr,
                                        to_address=lob_client.get_bureau_address(bureau_key_send) or {},
                                        cost_cents=cost_info['total_cents'], return_receipt=return_receipt,
                                        is_test=result.get('is_test', False), expected_delivery=result.get('expected_delivery', ''),
                                        workflow_id=ensure_active_workflow_id(current_user.get('user_id')),
                                    )
                                st.rerun()

            elif not has_mail_ent:
                st.markdown(
                    f'<div style="background:linear-gradient(135deg, {BG_1} 0%, rgba(212,160,23,0.06) 100%);'
                    f'border:2px solid {GOLD};border-radius:14px;padding:20px;margin:0.75rem 0 0.5rem 0;">'
                    f'<div style="font-size:1.1rem;font-weight:700;color:{GOLD};margin-bottom:6px;text-align:center;">'
                    f'&#x2709;&#xFE0F; Skip the Post Office</div>'
                    f'<div style="font-size:0.88rem;color:{TEXT_1};line-height:1.6;text-align:center;margin-bottom:12px;">'
                    f'Send your dispute letters as USPS Certified Mail directly from 850 Lab.</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                render_purchase_options(context="done_mail_sm", needed_mailings=1)
            else:
                st.markdown(
                    f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;padding:12px 16px;">'
                    f'<div style="font-size:0.86rem;color:{TEXT_1};">Certified mail service is being configured.</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PANEL: ESCALATION
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        elif _panel == 'escalation':
            st.session_state['_escalation_opened'] = True
            if st.button("\u2190 Back", key="esc_back", use_container_width=False):
                go('home')

            _esc_days = _ws_days_elapsed if _ws_mailed else 0
            st.markdown(f'''
            <div class="glass-card" style="border-color:rgba(239,83,80,0.3);background:rgba(239,83,80,0.04);">
                <div class="glass-section-title">&#x26A1; Escalation Options</div>
                <div style="font-size:0.82rem;color:{TEXT_1};margin-top:4px;">
                    {"Day " + str(_esc_days) + " — The 30-day investigation window has expired. Bureaus that have not responded are now in potential violation of FCRA §611." if _esc_days >= 31 else "Prepare your escalation materials for when the 30-day window expires."}
                </div>
            </div>
            ''', unsafe_allow_html=True)

            _esc_user_name = current_user.get('display_name', current_user.get('email', '[Your Name]'))
            _esc_letters = st.session_state.get('generated_letters', {})
            _esc_bureaus = [b.title() for b in _esc_letters.keys()] if _esc_letters else ['Equifax', 'Experian', 'TransUnion']
            _esc_mailed_str = _ws_mailed_dt.strftime('%B %d, %Y') if _ws_mailed_dt else '[Date Mailed]'

            _esc_disputed_items = []
            _esc_rcs = st.session_state.get('review_claims', [])
            for _rc in _esc_rcs:
                if hasattr(_rc, 'account_name'):
                    _esc_disputed_items.append(_rc.account_name)
                elif isinstance(_rc, dict):
                    _esc_disputed_items.append(_rc.get('account_name', 'Unknown Account'))
            _esc_disputed_items = list(set(_esc_disputed_items))[:10]
            _esc_items_str = ", ".join(_esc_disputed_items) if _esc_disputed_items else "[disputed account names]"

            from statutes import get_bureau_address

            with st.expander("Method of Verification (MOV) Letter", expanded=False):
                st.markdown(f'''
                <div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:10px;">
                    Demand that each bureau disclose exactly how they verified the disputed items — who they contacted, what documents they reviewed, and what method was used. Bureaus are required to provide this under FCRA §611(a)(6)(B)(iii) and §611(a)(7).
                </div>
                ''', unsafe_allow_html=True)

                _esc_mov_bureau = st.selectbox("Generate for", _esc_bureaus, key="mov_bureau_sel")
                _mov_bureau_key = _esc_mov_bureau.lower()
                _mov_addr = get_bureau_address(_mov_bureau_key)
                _mov_today = datetime.now().strftime('%B %d, %Y')

                _mov_text = f"""{_esc_user_name}
[Your Address]
[City, State ZIP]

{_mov_today}

{_mov_addr['name']}
{_mov_addr['address']}
{_mov_addr['city_state_zip']}

Re: Method of Verification Request — FCRA §611(a)(6)(B)(iii) and §611(a)(7)

To Whom It May Concern:

On {_esc_mailed_str}, I submitted a written dispute regarding inaccurate information on my {_esc_mov_bureau} credit report. The disputed items include: {_esc_items_str}.

More than 30 days have passed since you received my dispute. Pursuant to the Fair Credit Reporting Act, I am formally requesting that you provide me with the following:

1. The method of verification used for each disputed item, as required under 15 U.S.C. §1681i(a)(6)(B)(iii)
2. The name, address, and telephone number of each person contacted in connection with the verification, as required under 15 U.S.C. §1681i(a)(7)
3. A copy of any documents used to verify the accuracy of the disputed information

If you verified these items by simply receiving an automated response from the data furnisher without conducting a meaningful investigation, that does not satisfy your obligations under FCRA §611(a)(1)(A), which requires a "reasonable investigation."

Please provide the requested information within 15 days of receipt of this letter. Failure to comply may constitute a willful violation of the FCRA, subjecting {_mov_addr['name']} to statutory damages under 15 U.S.C. §1681n.

Sincerely,
{_esc_user_name}"""

                st.text_area("MOV Letter", _mov_text, height=420, key=f"mov_text_{_mov_bureau_key}")
                import base64 as _b64_mov
                _b64_mov_data = _b64_mov.b64encode(_mov_text.encode()).decode()
                _mov_fn = f"MOV_Letter_{_esc_mov_bureau}_{datetime.now().strftime('%Y%m%d')}.txt"
                import streamlit.components.v1 as _dl_mov_comp
                _dl_mov_comp.html(
                    f'''<button onclick="dlMov(this)" style="width:100%;padding:10px 16px;background:{BG_2};color:{TEXT_0};
                    font-weight:500;font-size:0.88rem;border-radius:10px;border:1px solid rgba(255,215,140,0.15);cursor:pointer;
                    font-family:'Inter',-apple-system,sans-serif;transition:all 0.3s ease;">Download MOV Letter ({_esc_mov_bureau})</button>
                    <script>function dlMov(btn){{var b=atob("{_b64_mov_data}");var a=new Uint8Array(b.length);
                    for(var i=0;i<b.length;i++)a[i]=b.charCodeAt(i);var bl=new Blob([a],{{type:"text/plain"}});
                    var u=URL.createObjectURL(bl);var l=document.createElement('a');l.href=u;l.download="{_mov_fn}";
                    document.body.appendChild(l);l.click();setTimeout(function(){{document.body.removeChild(l);URL.revokeObjectURL(u);}},100);
                    btn.innerHTML="&#x2705; Downloaded!";btn.style.background="linear-gradient(90deg,#2ecc71,#27ae60)";btn.style.color="#fff";
                    setTimeout(function(){{btn.innerHTML="Download MOV Letter ({_esc_mov_bureau})";btn.style.background="{BG_2}";btn.style.color="{TEXT_0}";}},2500);
                    }}</script>''',
                    height=46,
                )

            with st.expander("CFPB Complaint Narrative", expanded=False):
                st.markdown(f'''
                <div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:10px;">
                    File a complaint with the Consumer Financial Protection Bureau at <a href="https://www.consumerfinance.gov/complaint/" target="_blank" style="color:{GOLD};">consumerfinance.gov/complaint</a>. Copy the narrative below into the complaint form.
                </div>
                ''', unsafe_allow_html=True)

                _cfpb_bureau = st.selectbox("Complaint against", _esc_bureaus, key="cfpb_bureau_sel")

                _cfpb_text = f"""COMPLAINT NARRATIVE

Company: {_cfpb_bureau}
Product: Credit reporting
Issue: Incorrect information on my credit report / Investigation took more than 30 days

On {_esc_mailed_str}, I sent a written dispute to {_cfpb_bureau} via USPS Certified Mail regarding inaccurate items on my credit report. The disputed items include: {_esc_items_str}.

As of today, {datetime.now().strftime('%B %d, %Y')}, which is Day {_esc_days} since my dispute was mailed, {_cfpb_bureau} has {"not provided a response or correction" if _esc_days >= 31 else "not yet completed their investigation"}.

Under the Fair Credit Reporting Act (FCRA), 15 U.S.C. §1681i(a)(1)(A), credit reporting agencies must conduct a reasonable investigation within 30 days of receiving a consumer dispute. {"This deadline has passed without resolution." if _esc_days >= 31 else ""}

I have supporting documentation including:
- Copy of my original dispute letter sent via Certified Mail
- USPS tracking confirmation showing delivery
- Copy of my credit report showing the disputed items

I am requesting that the CFPB investigate {_cfpb_bureau}'s handling of my dispute and ensure compliance with federal law. I request that all disputed items be corrected or removed, and that {_cfpb_bureau} provide a detailed description of the method of verification used, as required under FCRA §611(a)(6)(B)(iii).

DESIRED RESOLUTION: I want {_cfpb_bureau} to correct or delete the inaccurate items from my credit report and provide written confirmation of the corrections."""

                st.text_area("CFPB Narrative", _cfpb_text, height=380, key=f"cfpb_text_{_cfpb_bureau.lower()}")
                import base64 as _b64_cfpb
                _b64_cfpb_data = _b64_cfpb.b64encode(_cfpb_text.encode()).decode()
                _cfpb_fn = f"CFPB_Complaint_{_cfpb_bureau}_{datetime.now().strftime('%Y%m%d')}.txt"
                import streamlit.components.v1 as _dl_cfpb_comp
                _dl_cfpb_comp.html(
                    f'''<button onclick="dlCfpb(this)" style="width:100%;padding:10px 16px;background:{BG_2};color:{TEXT_0};
                    font-weight:500;font-size:0.88rem;border-radius:10px;border:1px solid rgba(255,215,140,0.15);cursor:pointer;
                    font-family:'Inter',-apple-system,sans-serif;transition:all 0.3s ease;">Download CFPB Narrative ({_cfpb_bureau})</button>
                    <script>function dlCfpb(btn){{var b=atob("{_b64_cfpb_data}");var a=new Uint8Array(b.length);
                    for(var i=0;i<b.length;i++)a[i]=b.charCodeAt(i);var bl=new Blob([a],{{type:"text/plain"}});
                    var u=URL.createObjectURL(bl);var l=document.createElement('a');l.href=u;l.download="{_cfpb_fn}";
                    document.body.appendChild(l);l.click();setTimeout(function(){{document.body.removeChild(l);URL.revokeObjectURL(u);}},100);
                    btn.innerHTML="&#x2705; Downloaded!";btn.style.background="linear-gradient(90deg,#2ecc71,#27ae60)";btn.style.color="#fff";
                    setTimeout(function(){{btn.innerHTML="Download CFPB Narrative ({_cfpb_bureau})";btn.style.background="{BG_2}";btn.style.color="{TEXT_0}";}},2500);
                    }}</script>''',
                    height=46,
                )
                st.markdown(f'''
                <div style="font-size:0.75rem;color:{TEXT_1};margin-top:8px;padding:8px 12px;background:{BG_1};border-radius:8px;">
                    File at <a href="https://www.consumerfinance.gov/complaint/" target="_blank" style="color:{GOLD};">consumerfinance.gov/complaint</a> &middot; Select "Credit reporting" &middot; Paste narrative &middot; Attach your dispute letter and tracking receipt
                </div>
                ''', unsafe_allow_html=True)

            with st.expander("Executive Escalation Letter", expanded=False):
                st.markdown(f'''
                <div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:10px;">
                    Escalate directly to bureau executive offices. These letters bypass standard dispute processing and are reviewed by compliance teams.
                </div>
                ''', unsafe_allow_html=True)

                _exec_bureau = st.selectbox("Escalate to", _esc_bureaus, key="exec_bureau_sel")
                _exec_bureau_key = _exec_bureau.lower()
                _exec_addr = get_bureau_address(_exec_bureau_key)

                _exec_offices = {
                    "equifax": {"exec": "Office of Consumer Affairs", "addr": "1550 Peachtree Street NW", "csz": "Atlanta, GA 30309"},
                    "experian": {"exec": "Office of Consumer Affairs", "addr": "475 Anton Blvd", "csz": "Costa Mesa, CA 92626"},
                    "transunion": {"exec": "Office of the President", "addr": "555 West Adams Street", "csz": "Chicago, IL 60661"},
                }
                _exec_office = _exec_offices.get(_exec_bureau_key, {"exec": "Office of Consumer Affairs", "addr": _exec_addr['address'], "csz": _exec_addr['city_state_zip']})

                _exec_text = f"""{_esc_user_name}
[Your Address]
[City, State ZIP]

{datetime.now().strftime('%B %d, %Y')}

{_exec_office['exec']}
{_exec_addr['name']}
{_exec_office['addr']}
{_exec_office['csz']}

Re: Executive Escalation — Unresolved Credit Report Dispute

Dear {_exec_office['exec']}:

I am writing to escalate an unresolved dispute that was not properly handled through your standard dispute process.

On {_esc_mailed_str}, I submitted a detailed written dispute via USPS Certified Mail to {_exec_addr['name']} regarding the following inaccurate items on my credit report: {_esc_items_str}.

As of today, Day {_esc_days} since my dispute was mailed, {"the 30-day investigation period required under FCRA §611(a)(1)(A) has expired without adequate resolution" if _esc_days >= 31 else "I am writing to ensure this matter receives proper executive attention"}.

I am concerned that my dispute was not given a "reasonable investigation" as required by the FCRA. A reasonable investigation requires more than simply passing my dispute to the data furnisher and accepting an automated verification response. The FTC and courts have consistently held that CRAs must go beyond a superficial review when consumers provide specific information about inaccuracies.

I respectfully request that your office:

1. Conduct a thorough, manual review of each disputed item
2. Contact the data furnishers directly and request supporting documentation
3. Provide me with the method of verification for each item per FCRA §611(a)(6)(B)(iii)
4. Correct or remove any items that cannot be independently verified
5. Provide written confirmation of all actions taken

I have filed, or intend to file, a complaint with the Consumer Financial Protection Bureau regarding this matter. I am hopeful that executive intervention will resolve this without the need for further action.

Please respond within 15 business days. I can be reached at the address above.

Sincerely,
{_esc_user_name}

Enclosures:
- Copy of original dispute letter
- USPS Certified Mail tracking receipt
- Relevant credit report pages"""

                st.text_area("Executive Letter", _exec_text, height=480, key=f"exec_text_{_exec_bureau_key}")
                import base64 as _b64_exec
                _b64_exec_data = _b64_exec.b64encode(_exec_text.encode()).decode()
                _exec_fn = f"Executive_Escalation_{_exec_bureau}_{datetime.now().strftime('%Y%m%d')}.txt"
                import streamlit.components.v1 as _dl_exec_comp
                _dl_exec_comp.html(
                    f'''<button onclick="dlExec(this)" style="width:100%;padding:10px 16px;background:{BG_2};color:{TEXT_0};
                    font-weight:500;font-size:0.88rem;border-radius:10px;border:1px solid rgba(255,215,140,0.15);cursor:pointer;
                    font-family:'Inter',-apple-system,sans-serif;transition:all 0.3s ease;">Download Executive Letter ({_exec_bureau})</button>
                    <script>function dlExec(btn){{var b=atob("{_b64_exec_data}");var a=new Uint8Array(b.length);
                    for(var i=0;i<b.length;i++)a[i]=b.charCodeAt(i);var bl=new Blob([a],{{type:"text/plain"}});
                    var u=URL.createObjectURL(bl);var l=document.createElement('a');l.href=u;l.download="{_exec_fn}";
                    document.body.appendChild(l);l.click();setTimeout(function(){{document.body.removeChild(l);URL.revokeObjectURL(u);}},100);
                    btn.innerHTML="&#x2705; Downloaded!";btn.style.background="linear-gradient(90deg,#2ecc71,#27ae60)";btn.style.color="#fff";
                    setTimeout(function(){{btn.innerHTML="Download Executive Letter ({_exec_bureau})";btn.style.background="{BG_2}";btn.style.color="{TEXT_0}";}},2500);
                    }}</script>''',
                    height=46,
                )

            st.markdown("---")
            _esc_nav = st.columns(2)
            with _esc_nav[0]:
                if st.button("View Tracker", key="esc_go_trk", use_container_width=True):
                    go('tracker')
            with _esc_nav[1]:
                if st.button("View Documents", key="esc_go_doc", use_container_width=True):
                    go('documents')

    
st.markdown('</div>', unsafe_allow_html=True)

