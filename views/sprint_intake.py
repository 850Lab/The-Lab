import streamlit as st
import re


GOLD = "#D4A017"
TEXT_0 = "#1A1A1A"
TEXT_1 = "#666666"
BORDER = "#E0E0E0"


def render_sprint_intake():
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    [data-testid="stAppViewContainer"] { margin-left: 0 !important; padding-left: 0 !important; }
    [data-testid="stMain"] { margin-left: 0 !important; width: 100% !important; }
    </style>
    """, unsafe_allow_html=True)

    if st.session_state.get('_sprint_submitted'):
        _render_confirmation()
        return

    _render_form()


def _render_confirmation():
    st.markdown(f"""
    <div style="max-width:560px;margin:3rem auto;text-align:center;padding:2rem 1.5rem;">
        <div style="font-size:2.5rem;margin-bottom:1rem;">&#x2705;</div>
        <h1 style="color:{TEXT_0};font-size:1.6rem;font-weight:800;margin-bottom:0.5rem;">
            You're in.
        </h1>
        <p style="color:{TEXT_1};font-size:1rem;line-height:1.6;margin-bottom:1.5rem;">
            Jaylan will contact you within 24 hours to review your credit situation
            and get your Sprint started.
        </p>
        <div style="background:linear-gradient(135deg, rgba(212,175,55,0.10), rgba(212,175,55,0.03));
                    border:1px solid {GOLD};border-radius:12px;padding:1.2rem 1.5rem;
                    margin-bottom:1.5rem;text-align:left;">
            <div style="font-weight:700;color:{GOLD};margin-bottom:0.5rem;">What happens next:</div>
            <div style="font-size:0.9rem;color:{TEXT_0};line-height:1.8;">
                <strong>1.</strong> Personal review of your situation<br/>
                <strong>2.</strong> We pull your reports together and identify the strongest disputes<br/>
                <strong>3.</strong> Round 1 letters go out certified within days
            </div>
        </div>
        <p style="color:{TEXT_1};font-size:0.8rem;">
            Questions? Reply to the confirmation email or reach out anytime.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("\u2190 Back to home", key="sprint_back_home"):
        st.session_state._sprint_submitted = False
        st.session_state.auth_page = 'landing'
        st.rerun()


def _render_form():
    st.markdown(f"""
    <div style="max-width:560px;margin:1.5rem auto 0;text-align:center;">
        <div style="display:inline-block;background:linear-gradient(135deg, {GOLD}, #e8c848);
                    color:#1a1a1a;font-size:0.7rem;font-weight:700;text-transform:uppercase;
                    letter-spacing:1px;padding:0.3rem 1rem;border-radius:20px;margin-bottom:1rem;">
            Work With Me Directly
        </div>
        <h1 style="color:{TEXT_0};font-size:1.5rem;font-weight:800;margin-bottom:0.3rem;letter-spacing:-0.02em;">
            30-Day Deletion Sprint Intake
        </h1>
        <p style="color:{TEXT_1};font-size:0.95rem;line-height:1.6;margin-bottom:0.3rem;">
            Fill this out in about 2 minutes. Jaylan will contact you within 24 hours to get started.
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div style="max-width:480px;margin:0 auto;">', unsafe_allow_html=True)

        name = st.text_input("Full name", key="sprint_name", placeholder="Your full name")
        email = st.text_input("Email", key="sprint_email", placeholder="you@example.com")
        phone = st.text_input("Phone number", key="sprint_phone", placeholder="(555) 123-4567")

        col1, col2 = st.columns(2)
        with col1:
            preferred_contact = st.radio(
                "Preferred contact method",
                ["Text", "Call"],
                key="sprint_contact_method",
                horizontal=True,
            )
        with col2:
            best_time = st.selectbox(
                "Best time to reach you",
                ["Anytime", "Morning", "Lunch", "After 5"],
                key="sprint_best_time",
            )

        goal = st.text_area(
            "What's your main goal?",
            key="sprint_goal",
            placeholder="e.g., Remove collections before applying for a mortgage, clean up old accounts, raise my score for an auto loan...",
            height=100,
        )

        timeline = st.selectbox(
            "How soon do you need results?",
            ["As soon as possible", "Within 30 days", "Within 60 days", "No rush — just want it done right"],
            key="sprint_timeline",
        )

        st.markdown(f"""
        <div style="background:linear-gradient(135deg, rgba(212,175,55,0.08), rgba(212,175,55,0.02));
                    border:1px solid {GOLD};border-radius:10px;padding:1rem 1.2rem;margin:1rem 0;">
            <div style="font-size:0.85rem;font-weight:700;color:{GOLD};margin-bottom:0.4rem;">
                &#x1f6e1;&#xfe0f; 2-Round Guarantee
            </div>
            <div style="font-size:0.82rem;color:{TEXT_0};line-height:1.6;">
                If no disputed item changes after 2 rounds, Round 3 is on us.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Start 30-Day Sprint", key="sprint_submit", use_container_width=True, type="primary"):
            errors = []
            if not name or not name.strip():
                errors.append("Please enter your name.")
            if not email or not re.match(r'^[^@]+@[^@]+\.[^@]+$', email.strip()):
                errors.append("Please enter a valid email address.")
            if not phone or len(re.sub(r'\D', '', phone)) < 7:
                errors.append("Please enter a valid phone number.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                try:
                    import database as db
                    db.insert_sprint_lead(
                        name=name.strip(),
                        email=email.strip().lower(),
                        phone=phone.strip(),
                        goal=(goal or '').strip(),
                        timeline=timeline,
                        preferred_contact=preferred_contact.lower(),
                        best_time=best_time.lower(),
                    )
                    st.session_state._sprint_submitted = True
                    st.rerun()
                except Exception:
                    st.error("Something went wrong. Please try again.")

        st.markdown(f"""
        <div style="text-align:center;margin-top:0.8rem;">
            <p style="font-size:0.75rem;color:{TEXT_1};line-height:1.5;">
                No outcome is promised; you're purchasing a structured dispute process.<br/>
                Payment is collected after your intake call &mdash; not now.
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    if st.button("\u2190 Back to home", key="sprint_form_back"):
        st.session_state.auth_page = 'landing'
        st.rerun()
