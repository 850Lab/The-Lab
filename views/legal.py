import streamlit as st
import os
from ui.css import inject_css, BG_0, BG_1, BG_2, TEXT_0, TEXT_1, GOLD, GOLD_DIM, BORDER


def _legal_page_wrapper(title, sections):
    inject_css()
    st.markdown(f"""
    <style>
    [data-testid="stSidebar"] {{ display: none !important; }}
    [data-testid="collapsedControl"] {{ display: none !important; }}
    .legal-wrap {{ max-width:760px;margin:0 auto;padding:2rem 1.5rem; }}
    .legal-wrap h1 {{ color:{GOLD};font-size:2rem;font-weight:700;margin-bottom:0.5rem; }}
    .legal-wrap .legal-date {{ color:{TEXT_1};font-size:0.85rem;margin-bottom:2rem; }}
    .legal-wrap h2 {{ color:{TEXT_0};font-size:1.3rem;margin-top:1.5rem;margin-bottom:0.5rem; }}
    .legal-wrap p {{ color:{TEXT_0};font-size:0.95rem;line-height:1.8;margin-bottom:0.8rem; }}
    .legal-wrap ul {{ color:{TEXT_0};margin-left:1.5rem;font-size:0.95rem;line-height:1.8; }}
    .legal-wrap li {{ margin-bottom:0.3rem; }}
    .legal-wrap a {{ color:{GOLD}; }}
    .legal-footer {{ text-align:center;margin-top:3rem;padding-top:1.5rem;border-top:1px solid {BORDER}; }}
    .legal-footer a {{ color:{GOLD};text-decoration:none;font-size:0.9rem; }}
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f'<div class="legal-wrap"><h1>{title}</h1><div class="legal-date">Last updated: February 25, 2026</div>', unsafe_allow_html=True)

    for section in sections:
        st.markdown(section, unsafe_allow_html=True)

    st.markdown('<div class="legal-footer"><a href="/" target="_self">&larr; Back to 850 Lab</a></div></div>', unsafe_allow_html=True)


def render_privacy_policy():
    sections = [
        f"""<h2>Introduction</h2>
<p>850 Lab ("we", "us", "our") operates the 850 Lab credit report analysis platform.
This Privacy Policy explains how we collect, use, and protect your information.</p>""",

        f"""<h2>Information We Collect</h2>
<p>We collect the following types of information:</p>
<ul>
<li><strong>Account Information:</strong> Email address, display name, and password (securely hashed)</li>
<li><strong>Credit Report Data:</strong> When you upload a credit report PDF, we extract and analyze its contents. We store structured data (account names, statuses, balances) but <strong>never store the raw PDF text</strong>, which may contain sensitive identifiers.</li>
<li><strong>Proof Documents:</strong> Government-issued ID and proof of address images, used exclusively for dispute letter enclosures</li>
<li><strong>Payment Information:</strong> Processed securely through Stripe. We never store your full card number.</li>
<li><strong>Usage Data:</strong> Pages visited, features used, and device information for improving our service</li>
</ul>""",

        f"""<h2>How We Use Your Information</h2>
<ul>
<li>To analyze your credit report and identify potential errors</li>
<li>To generate personalized dispute letters citing applicable laws</li>
<li>To include your proof documents with dispute letters sent to credit bureaus</li>
<li>To process payments and manage your account</li>
<li>To send service-related communications (dispute status, account updates)</li>
<li>To improve our platform and develop new features</li>
</ul>""",

        f"""<h2>Data Security</h2>
<p>We implement industry-standard security measures including:</p>
<ul>
<li>Passwords hashed with bcrypt</li>
<li>All data transmitted over HTTPS/TLS</li>
<li>User-scoped data access (you can only see your own data)</li>
<li>Rate limiting on sensitive endpoints</li>
<li>Webhook signature validation for payment processing</li>
</ul>""",

        f"""<h2>Data Retention & Deletion</h2>
<p>You may delete all your data at any time using the "Delete All My Data" feature in your account settings.
This permanently removes your account, reports, letters, proof documents, and all associated data.</p>""",

        f"""<h2>Third-Party Services</h2>
<ul>
<li><strong>Stripe:</strong> Payment processing (<a href="https://stripe.com/privacy" target="_blank">Stripe Privacy Policy</a>)</li>
<li><strong>Lob:</strong> Certified mail delivery (<a href="https://www.lob.com/privacy" target="_blank">Lob Privacy Policy</a>)</li>
<li><strong>OpenAI:</strong> AI-powered analysis (data is not used for model training)</li>
<li><strong>Resend:</strong> Transactional email delivery</li>
</ul>""",

        f"""<h2>Your Rights</h2>
<p>You have the right to access, correct, or delete your personal information.
Contact us at <a href="mailto:850creditlab@gmail.com">850creditlab@gmail.com</a> with any privacy-related requests.</p>""",

        f"""<h2>Cookies</h2>
<p>We use essential cookies to maintain your session and remember your preferences.
We do not use third-party advertising cookies.</p>""",

        f"""<h2>Contact</h2>
<p>For privacy questions or concerns, contact us at <a href="mailto:850creditlab@gmail.com">850creditlab@gmail.com</a>.</p>""",
    ]
    _legal_page_wrapper("Privacy Policy", sections)


def render_terms_of_service():
    sections = [
        f"""<h2>Acceptance of Terms</h2>
<p>By accessing or using 850 Lab, you agree to be bound by these Terms of Service.
If you do not agree, please do not use the service.</p>""",

        f"""<h2>Service Description</h2>
<p>850 Lab provides credit report analysis tools and generates dispute letters based on your uploaded credit reports.
We help you identify potential errors and exercise your rights under the Fair Credit Reporting Act (FCRA).</p>""",

        f"""<h2>Important Disclaimers</h2>
<ul>
<li><strong>Not Legal Advice:</strong> 850 Lab is a software tool, not a law firm. The information and letters generated are for informational purposes and do not constitute legal advice.</li>
<li><strong>No Guarantee of Results:</strong> While our tools cite applicable laws and identify potential errors, we cannot guarantee that credit bureaus will correct any items on your report.</li>
<li><strong>Accuracy of Uploads:</strong> You are responsible for ensuring the accuracy of information you upload and confirming your identity before submitting disputes.</li>
</ul>""",

        f"""<h2>User Accounts</h2>
<ul>
<li>You must provide accurate information when creating an account</li>
<li>You are responsible for maintaining the security of your password</li>
<li>You must be at least 18 years old to use this service</li>
<li>One account per person; accounts are non-transferable</li>
</ul>""",

        f"""<h2>Payments & Refunds</h2>
<p>Paid features are billed through Stripe. All purchases are final unless otherwise required by law.
If you believe you were charged in error, contact us at <a href="mailto:850creditlab@gmail.com">850creditlab@gmail.com</a>.</p>""",

        f"""<h2>Acceptable Use</h2>
<p>You agree not to:</p>
<ul>
<li>Upload credit reports belonging to others without authorization</li>
<li>Use the service for fraudulent purposes</li>
<li>Attempt to reverse-engineer, scrape, or abuse the platform</li>
<li>Submit false or misleading dispute information</li>
</ul>""",

        f"""<h2>Termination</h2>
<p>We reserve the right to suspend or terminate accounts that violate these terms.
You may delete your account and data at any time.</p>""",

        f"""<h2>Limitation of Liability</h2>
<p>850 Lab is provided "as is" without warranties of any kind. We are not liable for any damages
arising from your use of the service, including but not limited to changes (or lack thereof) to your credit report.</p>""",

        f"""<h2>Contact</h2>
<p>Questions about these terms? Contact us at <a href="mailto:850creditlab@gmail.com">850creditlab@gmail.com</a>.</p>""",
    ]
    _legal_page_wrapper("Terms of Service", sections)


def render_proof_upload_page(current_user=None, via_token=False):
    inject_css()
    import database as db

    st.markdown(f"""
    <style>
    [data-testid="stSidebar"] {{ display: none !important; }}
    [data-testid="collapsedControl"] {{ display: none !important; }}
    .proof-wrap {{ max-width:520px;margin:0 auto;padding:1.5rem 1rem; }}
    </style>
    """, unsafe_allow_html=True)

    if not current_user:
        st.markdown(f'<div class="proof-wrap">', unsafe_allow_html=True)
        st.markdown(f'<div style="text-align:center;padding:2rem 0;"><div style="font-size:1.4rem;font-weight:800;color:{TEXT_0};">Upload Your Documents</div></div>', unsafe_allow_html=True)
        st.warning("You need to sign in to upload your documents.")
        st.markdown(f'<div style="text-align:center;margin-top:1rem;"><a href="/" target="_self" style="color:{GOLD};text-decoration:none;font-size:0.9rem;">&larr; Sign in to 850 Lab</a></div></div>', unsafe_allow_html=True)
        st.stop()
        return

    user_id = current_user.get('user_id')
    proof_status = db.has_proof_docs(user_id)
    existing_docs = db.get_proof_docs_for_user(user_id)

    has_id = proof_status['has_id']
    has_addr = proof_status['has_address']
    both_done = proof_status['both']
    steps_done = (1 if has_id else 0) + (1 if has_addr else 0)

    id_check = f'<span style="color:#2ecc71;font-size:1.1rem;">&#x2705;</span>' if has_id else f'<span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;border:2px solid {TEXT_1};font-size:0.7rem;font-weight:800;color:{TEXT_1};">1</span>'
    addr_check = f'<span style="color:#2ecc71;font-size:1.1rem;">&#x2705;</span>' if has_addr else f'<span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;border:2px solid {TEXT_1};font-size:0.7rem;font-weight:800;color:{TEXT_1};">2</span>'

    st.markdown(f'<div class="proof-wrap">', unsafe_allow_html=True)

    if both_done:
        st.markdown(f'''
        <div style="text-align:center;padding:0.5rem 0 1rem;">
            <div style="font-size:2rem;margin-bottom:4px;">&#x2705;</div>
            <div style="font-size:1.2rem;font-weight:800;color:#2ecc71;">You're all set</div>
            <div style="font-size:0.85rem;color:{TEXT_1};margin-top:4px;">Both documents are on file and will be included with your letters.</div>
        </div>
        ''', unsafe_allow_html=True)
    else:
        st.markdown(f'''
        <div style="text-align:center;padding:0.5rem 0 1rem;">
            <div style="font-size:1.3rem;font-weight:800;color:{TEXT_0};margin-bottom:4px;">{steps_done} of 2 uploaded</div>
            <div style="font-size:0.85rem;color:{TEXT_1};">Bureaus need your ID and address proof with every dispute.</div>
            <div style="display:flex;gap:16px;justify-content:center;margin-top:12px;">
                <div style="display:flex;align-items:center;gap:6px;">{id_check} <span style="font-size:0.82rem;color:{TEXT_0 if has_id else TEXT_1};font-weight:{'600' if not has_id else '400'};">ID</span></div>
                <div style="display:flex;align-items:center;gap:6px;">{addr_check} <span style="font-size:0.82rem;color:{TEXT_0 if has_addr else TEXT_1};font-weight:{'600' if not has_addr else '400'};">Address</span></div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

    if not has_id or st.session_state.get('_proof_replace_id'):
        st.markdown(f'''
        <div style="background:{BG_1};border:1px solid {BORDER};border-radius:12px;padding:14px 16px;margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                {id_check}
                <div>
                    <div style="font-size:0.9rem;font-weight:700;color:{TEXT_0};">Government ID</div>
                    <div style="font-size:0.75rem;color:{TEXT_1};">License, passport, or state ID</div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        id_file = st.file_uploader(
            "Upload your ID",
            type=["png", "jpg", "jpeg", "pdf"],
            key="proof_page_id_upload",
            label_visibility="collapsed",
        )

        if id_file:
            file_data = id_file.getvalue()
            max_size = 5 * 1024 * 1024
            if len(file_data) > max_size:
                st.error("File too large. Max 5 MB.")
            elif st.button("Save ID", key="save_proof_id", type="primary", use_container_width=True):
                from doc_validator import validate_proof_document
                with st.spinner("Checking..."):
                    _val = validate_proof_document(file_data, 'government_id', id_file.type or 'image/png')
                if not _val['valid']:
                    st.error(f"This doesn't look right: {_val['reason']}")
                else:
                    db.save_proof_upload(
                        user_id=user_id,
                        round_number=1,
                        bureau='government_id',
                        file_name=id_file.name,
                        file_type=id_file.type or 'image/png',
                        notes='Government-issued ID',
                        file_data=file_data,
                        doc_type='government_id',
                    )
                    if _val.get('checked'):
                        st.success(f"ID saved. {_val['reason']}")
                    else:
                        st.success("ID saved.")
                    db.log_activity(user_id, 'proof_upload', 'Government ID uploaded', None)
                    if st.session_state.get('_proof_replace_id'):
                        del st.session_state['_proof_replace_id']
                    st.rerun()
    else:
        id_docs = [d for d in existing_docs if d.get('doc_type') == 'government_id']
        _id_name = id_docs[0]['file_name'] if id_docs else 'uploaded'
        _id_date = ''
        if id_docs and hasattr(id_docs[0]['created_at'], 'strftime'):
            _id_date = id_docs[0]['created_at'].strftime('%b %d')
        st.markdown(f'''
        <div style="background:{BG_1};border:1px solid rgba(46,204,113,0.25);border-radius:12px;padding:12px 16px;margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:8px;">
                {id_check}
                <div style="flex:1;">
                    <div style="font-size:0.88rem;font-weight:600;color:{TEXT_0};">Government ID</div>
                    <div style="font-size:0.72rem;color:{TEXT_1};">{_id_name} {("· " + _id_date) if _id_date else ""}</div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        if st.button("Replace ID", key="replace_id_btn", use_container_width=True):
            st.session_state['_proof_replace_id'] = True
            st.rerun()

    if not has_addr or st.session_state.get('_proof_replace_addr'):
        st.markdown(f'''
        <div style="background:{BG_1};border:1px solid {BORDER};border-radius:12px;padding:14px 16px;margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                {addr_check}
                <div>
                    <div style="font-size:0.9rem;font-weight:700;color:{TEXT_0};">Proof of Address</div>
                    <div style="font-size:0.75rem;color:{TEXT_1};">Utility bill, bank statement, or insurance doc</div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        addr_file = st.file_uploader(
            "Upload proof of address",
            type=["png", "jpg", "jpeg", "pdf"],
            key="proof_page_addr_upload",
            label_visibility="collapsed",
        )

        if addr_file:
            file_data = addr_file.getvalue()
            max_size = 5 * 1024 * 1024
            if len(file_data) > max_size:
                st.error("File too large. Max 5 MB.")
            elif st.button("Save Address Proof", key="save_proof_addr", type="primary", use_container_width=True):
                from doc_validator import validate_proof_document
                with st.spinner("Checking..."):
                    _val = validate_proof_document(file_data, 'address_proof', addr_file.type or 'image/png')
                if not _val['valid']:
                    st.error(f"This doesn't look right: {_val['reason']}")
                else:
                    db.save_proof_upload(
                        user_id=user_id,
                        round_number=1,
                        bureau='address_proof',
                        file_name=addr_file.name,
                        file_type=addr_file.type or 'image/png',
                        notes='Proof of current address',
                        file_data=file_data,
                        doc_type='address_proof',
                    )
                    if _val.get('checked'):
                        st.success(f"Address proof saved. {_val['reason']}")
                    else:
                        st.success("Address proof saved.")
                    db.log_activity(user_id, 'proof_upload', 'Address proof uploaded', None)
                    if st.session_state.get('_proof_replace_addr'):
                        del st.session_state['_proof_replace_addr']
                    st.rerun()
    else:
        addr_docs = [d for d in existing_docs if d.get('doc_type') == 'address_proof']
        _addr_name = addr_docs[0]['file_name'] if addr_docs else 'uploaded'
        _addr_date = ''
        if addr_docs and hasattr(addr_docs[0]['created_at'], 'strftime'):
            _addr_date = addr_docs[0]['created_at'].strftime('%b %d')
        st.markdown(f'''
        <div style="background:{BG_1};border:1px solid rgba(46,204,113,0.25);border-radius:12px;padding:12px 16px;margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:8px;">
                {addr_check}
                <div style="flex:1;">
                    <div style="font-size:0.88rem;font-weight:600;color:{TEXT_0};">Proof of Address</div>
                    <div style="font-size:0.72rem;color:{TEXT_1};">{_addr_name} {("· " + _addr_date) if _addr_date else ""}</div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        if st.button("Replace Address Proof", key="replace_addr_btn", use_container_width=True):
            st.session_state['_proof_replace_addr'] = True
            st.rerun()

    _replacing = st.session_state.get('_proof_replace_id') or st.session_state.get('_proof_replace_addr')
    if both_done and not via_token and not _replacing:
        if st.button("Continue to Mail Your Letters \u2192", type="primary", use_container_width=True, key="proof_continue_mail"):
            st.query_params.clear()
            st.session_state.panel = 'send_mail'
            st.rerun()

    with st.expander("Why do I need these?", expanded=False):
        st.markdown(f'''
        <div style="font-size:0.82rem;color:{TEXT_1};line-height:1.6;">
        Credit bureaus can ask for proof that you are who you say you are. Sending your ID and a recent bill
        with your address keeps them from delaying your dispute. Your documents are stored securely and only
        used for your dispute letters.
        </div>
        ''', unsafe_allow_html=True)

    if via_token:
        st.markdown(f'''
        <div style="text-align:center;margin-top:12px;font-size:0.82rem;color:{TEXT_1};">
            You can close this page when done. Your documents will be attached to your letters automatically.
        </div>
        ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if not via_token:
        if st.button("\u2190 Back", key="proof_back_home", use_container_width=True):
            st.query_params.clear()
            st.session_state.panel = 'home'
            st.rerun()
