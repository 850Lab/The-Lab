import streamlit as st
import re
import base64
import os
import auth
import database as db
from views.landing import render_landing_page
from drip_emails import process_drip_emails, mark_drip_sent, has_drip_been_sent, _welcome_email, _send_drip
from referral import record_referral, fulfill_referral_reward

@st.cache_data
def get_logo_b64():
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "logo.png")
    with open(logo_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def _auth_transition():
    logo_b64 = get_logo_b64()
    st.markdown(
        '<div class="auth-container">'
        '<div class="auth-logo">'
        f'<img src="data:image/png;base64,{logo_b64}" style="width: 120px; height: auto;" alt="850 Lab">'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="text-align:center; color:#999; margin-top:1rem;">Signing in\u2026</p>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

def _send_verification_email(user_id, email, display_name=None):
    try:
        from resend_client import send_verification_email
        code = auth.set_verification_code(user_id)
        if code is None:
            st.warning("Please wait a few minutes before requesting another code.")
            return False
        send_verification_email(email, code, display_name)
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        st.error("Could not send verification email. Please try again.")
        return False

def render_auth_page():
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    [data-testid="stAppViewContainer"] {
        margin-left: 0 !important;
        padding-left: 0 !important;
    }
    [data-testid="stMain"] {
        margin-left: 0 !important;
        width: 100% !important;
    }
    .auth-links {
        text-align: center;
        margin-top: 1rem;
        display: flex;
        justify-content: center;
        gap: 1.5rem;
        flex-wrap: wrap;
    }
    .auth-links .stButton > button {
        background: none !important;
        border: none !important;
        box-shadow: none !important;
        color: #666666 !important;
        font-size: 0.85rem !important;
        padding: 4px 8px !important;
        min-height: auto !important;
        text-decoration: underline;
    }
    .auth-links .stButton > button:hover {
        color: #D4A017 !important;
    }
    .auth-back-link {
        text-align: center;
        margin-top: 0.5rem;
    }
    .auth-back-link .stButton > button {
        background: none !important;
        border: none !important;
        box-shadow: none !important;
        color: #999 !important;
        font-size: 0.8rem !important;
        padding: 4px 8px !important;
        min-height: auto !important;
    }
    .auth-back-link .stButton > button:hover {
        color: #D4A017 !important;
    }
    .verify-code-input input {
        text-align: center !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.3em !important;
        padding: 12px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    nav = st.query_params.get('nav', '')
    if nav == 'sprint':
        st.query_params.clear()
        from views.sprint_intake import render_sprint_intake
        render_sprint_intake()
        return

    if nav == 'signup':
        st.query_params.clear()
        st.session_state.auth_page = 'signup'

    if st.session_state.auth_page == 'landing':
        render_landing_page()
        return

    if st.session_state.get('_auth_transition'):
        del st.session_state._auth_transition
        _auth_transition()
        return

    logo_b64 = get_logo_b64()
    st.markdown(
        '<div class="auth-container">'
        '<div class="auth-logo">'
        f'<img src="data:image/png;base64,{logo_b64}" style="width: 120px; height: auto;" alt="850 Lab">'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.auth_page == 'login':
        st.markdown("#### Welcome back")
        login_email = st.text_input("Email", key="login_email")
        login_password = st.text_input("Password", type="password", key="login_password")
        login_clicked = st.button("Sign In", use_container_width=True, type="primary", key="login_submit")
        if login_clicked:
            if not login_email or not login_password:
                st.error("Please enter your email and password.")
            else:
                result = auth.authenticate_user(login_email, login_password)
                if 'error' in result:
                    st.error(result['error'])
                else:
                    _dev_id = None
                    try:
                        import hashlib
                        _hdrs = st.context.headers
                        _parts = [_hdrs.get('User-Agent',''), _hdrs.get('Accept-Language',''), _hdrs.get('X-Forwarded-For', _hdrs.get('X-Real-Ip',''))]
                        _dev_id = hashlib.sha256('|'.join(_parts).encode()).hexdigest()[:32] if any(_parts) else None
                    except Exception:
                        pass
                    token = auth.create_session(result['id'], device_id=_dev_id)
                    st.session_state.auth_token = token
                    st.session_state.auth_user = result
                    st.session_state._set_auth_cookie_pending = token
                    user_id = result.get('id') or result.get('user_id')
                    db.log_activity(user_id, 'login', result.get('email', ''))
                    if not auth.is_email_verified(user_id):
                        st.session_state.auth_page = 'verify_email'
                        st.session_state._pending_verify_email = True
                        st.rerun()
                    else:
                        st.session_state._auth_transition = True
                        st.rerun()

        col_create, col_forgot = st.columns(2)
        with col_create:
            if st.button("Create account", key="goto_signup", use_container_width=True):
                st.session_state.auth_page = 'signup'
                st.rerun()
        with col_forgot:
            if st.button("Forgot password?", key="goto_reset", use_container_width=True):
                st.session_state.auth_page = 'reset_password'
                st.rerun()

        if st.button("\u2190 Back to home", key="back_to_landing_login"):
            st.session_state.auth_page = 'landing'
            st.rerun()

        st.markdown("""<div style="text-align:center;margin-top:1.5rem;padding-top:1rem;border-top:1px solid rgba(255,215,140,0.1);">
<a href="?page=terms" style="color:#888;text-decoration:none;font-size:0.75rem;" target="_self">Terms</a>
&nbsp;&middot;&nbsp;
<a href="?page=privacy" style="color:#888;text-decoration:none;font-size:0.75rem;" target="_self">Privacy</a>
&nbsp;&middot;&nbsp;
<a href="?page=refund" style="color:#888;text-decoration:none;font-size:0.75rem;" target="_self">Refund Policy</a>
</div>""", unsafe_allow_html=True)

    elif st.session_state.auth_page == 'signup':
        st.markdown("#### Create your account")
        display_name = st.text_input("Your Name", key="signup_name")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        password2 = st.text_input("Confirm Password", type="password", key="signup_password2")
        _preloaded_ref = st.session_state.get('_referral_code', '')
        ref_code_input = st.text_input("Referral Code (optional)", value=_preloaded_ref, key="signup_ref_code",
                                        help="Have a friend's referral code? Enter it here.")
        if ref_code_input and ref_code_input.strip():
            st.session_state._referral_code = ref_code_input.strip()
        if st.button("Create Account", use_container_width=True, type="primary", key="signup_submit"):
            if not email or not password or not display_name:
                st.error("Please fill in all fields.")
            elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email.strip()):
                st.error("Please enter a valid email address.")
            elif password != password2:
                st.error("Passwords don't match.")
            elif len(password) < 8:
                st.error("Password must be at least 8 characters.")
            elif not any(c.isupper() for c in password):
                st.error("Password must include at least one uppercase letter.")
            elif not any(c.islower() for c in password):
                st.error("Password must include at least one lowercase letter.")
            elif not any(c.isdigit() for c in password):
                st.error("Password must include at least one number.")
            else:
                utm_source = st.session_state.pop('_utm_source', None)
                utm_medium = st.session_state.pop('_utm_medium', None)
                utm_campaign = st.session_state.pop('_utm_campaign', None)
                result = auth.create_user(email, password, display_name,
                                          utm_source=utm_source, utm_medium=utm_medium, utm_campaign=utm_campaign)
                if 'error' in result:
                    st.error(result['error'])
                else:
                    _dev_id_s = None
                    try:
                        import hashlib as _hl_s
                        _hdrs_s = st.context.headers
                        _parts_s = [_hdrs_s.get('User-Agent',''), _hdrs_s.get('Accept-Language',''), _hdrs_s.get('X-Forwarded-For', _hdrs_s.get('X-Real-Ip',''))]
                        _dev_id_s = _hl_s.sha256('|'.join(_parts_s).encode()).hexdigest()[:32] if any(_parts_s) else None
                    except Exception:
                        pass
                    token = auth.create_session(result['id'], device_id=_dev_id_s)
                    st.session_state.auth_token = token
                    st.session_state.auth_user = result
                    st.session_state._set_auth_cookie_pending = token
                    db.log_activity(result['id'], 'signup', email)
                    _conv_js = ""
                    _meta_px = os.environ.get('META_PIXEL_ID', '')
                    _tt_px = os.environ.get('TIKTOK_PIXEL_ID', '')
                    if _meta_px:
                        _conv_js += f"try{{window.parent.fbq('track','CompleteRegistration');}}catch(e){{}}"
                    if _tt_px:
                        _conv_js += f"try{{window.parent.ttq.track('CompleteRegistration');}}catch(e){{}}"
                    if _conv_js:
                        import streamlit.components.v1 as _conv_comp
                        _conv_comp.html(f'<script>{_conv_js}</script>', height=0, width=0)
                    ref_code = st.session_state.pop('_referral_code', None)
                    if ref_code:
                        try:
                            record_referral(result['id'], ref_code)
                        except Exception:
                            pass
                    st.session_state.auth_page = 'verify_email'
                    st.session_state._pending_verify_email = True
                    st.rerun()

        if st.button("Already have an account? Sign in", key="goto_login_from_signup", use_container_width=True):
            st.session_state.auth_page = 'login'
            st.rerun()

        if st.button("\u2190 Back to home", key="back_to_landing_signup"):
            st.session_state.auth_page = 'landing'
            st.rerun()

        st.markdown("""<div style="text-align:center;margin-top:1.5rem;padding-top:1rem;border-top:1px solid rgba(255,215,140,0.1);">
<a href="?page=terms" style="color:#888;text-decoration:none;font-size:0.75rem;" target="_self">Terms</a>
&nbsp;&middot;&nbsp;
<a href="?page=privacy" style="color:#888;text-decoration:none;font-size:0.75rem;" target="_self">Privacy</a>
&nbsp;&middot;&nbsp;
<a href="?page=refund" style="color:#888;text-decoration:none;font-size:0.75rem;" target="_self">Refund Policy</a>
</div>""", unsafe_allow_html=True)

    elif st.session_state.auth_page == 'verify_email':
        user = st.session_state.auth_user
        user_email = user.get('email', '') if user else ''
        user_id = user.get('id') or user.get('user_id') if user else None

        if st.session_state.pop('_pending_verify_email', False) and user_id:
            _send_verification_email(user_id, user_email, user.get('display_name') if user else None)

        st.markdown("#### Verify your email")
        st.markdown(
            f'<p style="color:#999; font-size:0.95rem;">We sent a 6-digit code to <strong style="color:#E0E0E0;">{user_email}</strong></p>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="verify-code-input">', unsafe_allow_html=True)
        code = st.text_input("Enter code", max_chars=6, label_visibility="collapsed", placeholder="000000", key="verify_code")
        st.markdown('</div>', unsafe_allow_html=True)
        if st.button("Verify", use_container_width=True, type="primary", key="verify_submit"):
            if not code or len(code.strip()) != 6:
                st.error("Please enter the 6-digit code.")
            elif user_id:
                result = auth.verify_email_code(user_id, code)
                if 'error' in result:
                    st.error(result['error'])
                else:
                    try:
                        if not has_drip_been_sent(user_id, 'welcome'):
                            subj, body = _welcome_email(user.get('display_name'))
                            if _send_drip(user_email, subj, body):
                                mark_drip_sent(user_id, 'welcome')
                    except Exception:
                        pass
                    if result.get('founder_granted'):
                        try:
                            from resend_client import send_founder_welcome_email
                            send_founder_welcome_email(user_email, user.get('display_name'))
                        except Exception as _fw_err:
                            import logging
                            logging.getLogger(__name__).warning(f"Founder welcome email failed for {user_email}: {_fw_err}")
                    try:
                        fulfill_referral_reward(user_id)
                    except Exception:
                        pass
                    st.session_state._email_verified_cached = True
                    st.session_state._auth_transition = True
                    st.rerun()
            else:
                st.error("Session expired. Please sign in again.")

        st.markdown('<div class="auth-links">', unsafe_allow_html=True)
        if st.button("Resend code", key="resend_code"):
            if user_id:
                if _send_verification_email(user_id, user_email, user.get('display_name')):
                    st.success("New code sent! Check your email.")
            else:
                st.error("Session expired. Please sign in again.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="auth-back-link">', unsafe_allow_html=True)
        if st.button("Sign out", key="verify_signout"):
            if st.session_state.auth_token:
                auth.delete_session(st.session_state.auth_token)
            st.session_state.auth_token = None
            st.session_state.auth_user = None
            st.session_state.auth_page = 'login'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.auth_page == 'reset_password':
        reset_step = st.session_state.get('_reset_step', 'email')

        if reset_step == 'email':
            st.markdown("#### Reset Password")
            st.markdown(
                '<p style="color:#999; font-size:0.95rem;">Enter your email and we\'ll send you a code to reset your password.</p>',
                unsafe_allow_html=True,
            )
            email = st.text_input("Email", key="reset_email")
            if st.button("Send Reset Code", use_container_width=True, type="primary", key="reset_send_code"):
                if not email or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email.strip()):
                    st.error("Please enter a valid email address.")
                else:
                    result = auth.send_password_reset_code(email)
                    if result.get('success'):
                        st.session_state._reset_email = email.lower().strip()
                        if result.get('code') and result.get('user_id'):
                            try:
                                from resend_client import send_password_reset_email
                                send_password_reset_email(email, result['code'], result.get('display_name'))
                            except Exception:
                                import traceback
                                traceback.print_exc()
                        st.session_state._reset_step = 'code'
                        st.rerun()
                    else:
                        st.session_state._reset_email = email.lower().strip()
                        st.session_state._reset_step = 'code'
                        st.rerun()

        elif reset_step == 'code':
            reset_email = st.session_state.get('_reset_email', '')
            st.markdown("#### Reset Password")
            st.markdown(
                f'<p style="color:#999; font-size:0.95rem;">If an account exists for <strong style="color:#E0E0E0;">{reset_email}</strong>, we sent a 6-digit code.</p>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="verify-code-input">', unsafe_allow_html=True)
            code = st.text_input("Enter code", max_chars=6, label_visibility="collapsed", placeholder="000000", key="reset_code")
            st.markdown('</div>', unsafe_allow_html=True)
            new_pw = st.text_input("New Password", type="password", key="reset_new_pw")
            new_pw2 = st.text_input("Confirm New Password", type="password", key="reset_new_pw2")
            if st.button("Reset Password", use_container_width=True, type="primary", key="reset_submit"):
                if not code or len(code.strip()) != 6:
                    st.error("Please enter the 6-digit code.")
                elif not new_pw:
                    st.error("Please enter a new password.")
                elif new_pw != new_pw2:
                    st.error("Passwords don't match.")
                elif len(new_pw) < 8:
                    st.error("Password must be at least 8 characters.")
                elif not any(c.isupper() for c in new_pw):
                    st.error("Password must include at least one uppercase letter.")
                elif not any(c.islower() for c in new_pw):
                    st.error("Password must include at least one lowercase letter.")
                elif not any(c.isdigit() for c in new_pw):
                    st.error("Password must include at least one number.")
                else:
                    result = auth.verify_reset_code_and_set_password(reset_email, code, new_pw)
                    if 'error' in result:
                        st.error(result['error'])
                    else:
                        st.session_state._reset_step = 'email'
                        st.session_state._reset_email = None
                        st.success("Password reset successfully! You can now sign in.")
                        st.session_state.auth_page = 'login'

            st.markdown('<div class="auth-links">', unsafe_allow_html=True)
            if st.button("Resend code", key="reset_resend_code"):
                result = auth.send_password_reset_code(reset_email)
                if result.get('code') and result.get('user_id'):
                    try:
                        from resend_client import send_password_reset_email
                        send_password_reset_email(reset_email, result['code'], result.get('display_name'))
                    except Exception:
                        pass
                st.success("If an account exists, a new code has been sent.")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="auth-links">', unsafe_allow_html=True)
        if st.button("\u2190 Back to Sign In", key="back_to_login_from_reset"):
            st.session_state._reset_step = 'email'
            st.session_state._reset_email = None
            st.session_state.auth_page = 'login'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
