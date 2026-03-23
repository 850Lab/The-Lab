import streamlit as st
import time

def lab_card_open():
    st.markdown('<div class="lab-card">', unsafe_allow_html=True)


def lab_card_close():
    st.markdown('</div>', unsafe_allow_html=True)


def lab_exact_banner():
    st.markdown("""
    <div class="lab-banner">
      <div class="lab-banner-title">✅ Exact match confirmed</div>
      <div class="lab-banner-body">
        We were able to extract all major sections from your credit report, and the counts match exactly.<br/>
        You're seeing a complete and accurate translation of this report.
      </div>
    </div>
    """, unsafe_allow_html=True)


def lab_partial_banner():
    st.markdown("""
    <div class="lab-banner">
      <div class="lab-banner-title">⚠️ Partial translation — review before continuing</div>
      <div class="lab-banner-body">
        We were able to extract some information from your credit report, but not everything.<br/>
        Below is a comparison of what your report likely contains and what we were able to confidently extract.
      </div>
    </div>
    """, unsafe_allow_html=True)


def lab_system_error_banner():
    st.markdown("""
    <div class="lab-banner lab-banner-error">
      <div class="lab-banner-title">Something went wrong</div>
      <div class="lab-banner-body">
        We ran into an error while generating your letters.<br/>
        Nothing was sent. You can try again, or stop here and reach out for help.
      </div>
    </div>
    """, unsafe_allow_html=True)


CARD_ORDER = ["UPLOAD", "SUMMARY", "DISPUTES", "DONE"]


def render_card_progress():
    current = st.session_state.ui_card
    if current == "PREPARING":
        current_idx = CARD_ORDER.index("DISPUTES")
    elif current in ("VOICE_PROFILE", "GENERATING", "LETTERS_READY"):
        current_idx = CARD_ORDER.index("DONE")
    else:
        current_idx = CARD_ORDER.index(current) if current in CARD_ORDER else 0
    dots = []
    for i, c in enumerate(CARD_ORDER):
        if i < current_idx:
            dots.append('<div class="card-progress-dot done"></div>')
        elif i == current_idx:
            dots.append('<div class="card-progress-dot active"></div>')
        else:
            dots.append('<div class="card-progress-dot"></div>')
    st.markdown(f'<div class="card-progress">{"".join(dots)}</div>', unsafe_allow_html=True)
