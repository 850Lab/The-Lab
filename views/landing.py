import streamlit as st
import base64
import os
from referral import get_reports_analyzed_count
import database as db

@st.cache_data
def _get_logo_b64():
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "logo_small.png")
    if not os.path.exists(logo_path):
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "logo.png")
    with open(logo_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def _safe_db_call(fn, default=None, timeout=5):
    import threading
    result = [default]
    exc = [None]
    def _run():
        try:
            result[0] = fn()
        except Exception as e:
            exc[0] = e
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return default
    return result[0]

@st.cache_data(ttl=300, show_spinner=False)
def _get_report_count():
    try:
        count = _safe_db_call(get_reports_analyzed_count, default=0)
        if not count or count < 50:
            return None
        return f"{count:,}"
    except Exception:
        return None

@st.cache_data(ttl=300, show_spinner=False)
def _get_user_count():
    try:
        count = _safe_db_call(lambda: db.get_total_user_count(), default=0)
        if not count or count < 10:
            return None
        return count
    except Exception:
        return None

@st.cache_data(ttl=30, show_spinner=False)
def _get_founders_remaining():
    try:
        from auth import founders_remaining
        return _safe_db_call(founders_remaining, default=100)
    except Exception:
        return 100

def render_landing_page():
    logo_b64 = _get_logo_b64()
    report_count = _get_report_count()
    user_count = _get_user_count()
    spots_left = _get_founders_remaining()

    qp = st.query_params
    ref_code = qp.get('ref')
    if ref_code:
        st.session_state['_referral_code'] = ref_code
    for utm_key in ('utm_source', 'utm_medium', 'utm_campaign'):
        val = qp.get(utm_key)
        if val:
            st.session_state[f'_{utm_key}'] = val
        elif not val and st.session_state.get(f'_{utm_key}'):
            try:
                st.query_params[utm_key] = st.session_state[f'_{utm_key}']
            except Exception:
                pass
    nav = qp.get('nav')
    if nav == 'signup':
        st.query_params.clear()
        st.session_state.auth_page = 'signup'
        st.rerun()
    elif nav == 'login':
        st.query_params.clear()
        st.session_state.auth_page = 'login'
        st.rerun()
    elif nav == 'demo':
        st.query_params.clear()
        st.session_state.auth_page = 'demo'
        st.rerun()

    social_proof_html = ""
    if user_count and user_count >= 10:
        social_proof_html = f'<div class="lp-social-proof">{user_count:,} people have joined the beta</div>'

    # --- HERO ---
    st.markdown(f"""<div class="lp-hero">
<img src="data:image/png;base64,{logo_b64}" class="lp-logo" alt="850 Lab">
<h1 class="lp-headline">Find Errors on<br/>Your Credit Report.<br/><span class="lp-accent">Fix Them Fast.</span></h1>
<p class="lp-subheadline">Upload your report. We find mistakes. You get dispute letters. Done in under a minute.</p>
<div class="lp-cta-row">
<a href="?nav=demo" class="lp-btn-primary" target="_self">Try It Free &mdash; No Sign Up</a>
<a href="?nav=signup" class="lp-btn-secondary" target="_self">Create Account</a>
<a href="?nav=login" class="lp-btn-login-link" target="_self">Already have an account? Sign In</a>
</div>
{social_proof_html}
</div>""", unsafe_allow_html=True)

    # --- WHAT 850 LAB DOES ---
    st.markdown("""<div class="lp-section">
<h2 class="lp-section-title lp-how-title">How it works.</h2>
<div class="lp-steps">
<div class="lp-step"><span class="lp-step-num">1</span><span class="lp-step-word">Upload</span><span class="lp-step-detail">Send us your PDF from TransUnion, Equifax, or Experian</span></div>
<div class="lp-step-divider"></div>
<div class="lp-step"><span class="lp-step-num">2</span><span class="lp-step-word">Scan</span><span class="lp-step-detail">AI checks every account for errors and wrong info</span></div>
<div class="lp-step-divider"></div>
<div class="lp-step"><span class="lp-step-num">3</span><span class="lp-step-word">Get Letters</span><span class="lp-step-detail">Dispute letters with legal backing, ready to send</span></div>
</div>
</div>""", unsafe_allow_html=True)

    # --- SEE IT IN ACTION ---
    st.markdown(f"""<div class="lp-section"><div class="lp-demo-callout">
<div class="lp-demo-callout-icon">&#x1F50D;</div>
<div class="lp-demo-callout-title">See what we find on a real report.</div>
<div class="lp-demo-callout-text">Try the demo with sample data. No sign up needed. Takes 30 seconds.</div>
<a href="?nav=demo" class="lp-demo-callout-btn" target="_self">Try the Demo &rarr;</a>
</div></div>""", unsafe_allow_html=True)

    # --- WHAT YOU RECEIVE ---
    st.markdown(f"""<div class="lp-section"><div class="lp-founder-hero">
<div class="lp-founder-badge">What You Get</div>
<div class="lp-founder-title" style="font-size:1.3rem;">Real Results.<br/>Not Guesses.</div>
<div class="lp-founder-subtitle">Each upload gives you a full review and letters you can use right away.</div>

<div class="lp-founder-value">
<div class="lp-founder-value-item"><div class="lp-founder-value-num" style="font-size:1.2rem;">&#x1F50D;</div><div class="lp-founder-value-label">Each Account Checked</div></div>
<div class="lp-founder-value-item"><div class="lp-founder-value-num" style="font-size:1.2rem;">&#x1F4DD;</div><div class="lp-founder-value-label">Dispute Letters</div></div>
<div class="lp-founder-value-item"><div class="lp-founder-value-num" style="font-size:1.2rem;">&#x2696;</div><div class="lp-founder-value-label">Legal References</div></div>
<div class="lp-founder-value-item"><div class="lp-founder-value-num" style="font-size:1.2rem;">&#x1F4CA;</div><div class="lp-founder-value-label">Bureau-to-Bureau Check</div></div>
</div>

<div class="lp-founder-note">Each letter cites the exact law that applies to the error we found.</div>
</div>
</div>""", unsafe_allow_html=True)

    # --- WHO IT'S FOR ---
    st.markdown(f"""<div class="lp-section">
<h2 class="lp-section-title">Who this is for.</h2>
<div class="lp-testimonial-grid">
<div class="lp-testimonial"><div class="lp-testimonial-text">You want to buy a home, a car, or get a loan. You need to make sure your report is right before you apply.</div></div>
<div class="lp-testimonial"><div class="lp-testimonial-text">You think your credit report has old, wrong, or repeated info. You want a clear way to fix it.</div></div>
</div>
</div>""", unsafe_allow_html=True)

    # --- WHY 850 LAB IS DIFFERENT ---
    st.markdown(f"""<div class="lp-section">
<h2 class="lp-section-title">Why 850 Lab is different.</h2>
<div class="lp-testimonial-grid">
<div class="lp-testimonial"><div class="lp-testimonial-text"><strong style="color:#D4A017;">Facts, not promises.</strong><br/>We find errors on your report. We don't promise things will be removed.</div></div>
<div class="lp-testimonial"><div class="lp-testimonial-text"><strong style="color:#D4A017;">Made for you, not generic.</strong><br/>Each letter is built from your report. It cites the exact law that applies.</div></div>
<div class="lp-testimonial"><div class="lp-testimonial-text"><strong style="color:#D4A017;">Your data, your call.</strong><br/>We never save your credit report. It's kept safe. Delete it all with one click.</div></div>
<div class="lp-testimonial"><div class="lp-testimonial-text"><strong style="color:#D4A017;">Clear and simple.</strong><br/>No monthly fees. No tricks. No pressure. You see what we found and why.</div></div>
</div>
</div>""", unsafe_allow_html=True)

    # --- PRIVATE BETA ACCESS ---
    st.markdown(f"""<div class="lp-section"><div class="lp-founder-hero">
<div class="lp-founder-badge">Private Beta</div>
<div class="lp-founder-title" style="font-size:1.3rem;">Free Right Now.<br/>Try It Today.</div>
<div class="lp-founder-subtitle">We're still making it better. It's free while we do. Join now before we launch to the public.</div>

<div class="lp-founder-value">
<div class="lp-founder-value-item"><div class="lp-founder-value-num">$0</div><div class="lp-founder-value-label">During Beta</div></div>
<div class="lp-founder-value-item"><div class="lp-founder-value-num" style="font-size:1.2rem;">&#x2714;</div><div class="lp-founder-value-label">Full Review</div></div>
<div class="lp-founder-value-item"><div class="lp-founder-value-num" style="font-size:1.2rem;">&#x2714;</div><div class="lp-founder-value-label">Dispute Letters</div></div>
<div class="lp-founder-value-item"><div class="lp-founder-value-num" style="font-size:1.2rem;">&#x2714;</div><div class="lp-founder-value-label">All 3 Bureaus</div></div>
</div>

<a href="?nav=signup" class="lp-founder-cta" target="_self">Request Beta Access</a>
<div class="lp-founder-note">No credit card needed. Your feedback helps us get better.</div>
</div>
</div>""", unsafe_allow_html=True)

    # --- GET YOUR REPORTS (accordion) ---
    st.markdown("""<div class="lp-section lp-get-reports">
<h2 class="lp-section-title">Get your credit report.</h2>
<p class="lp-section-sub">You can get free copies every week. It's the law.</p>
<div class="lp-guide-tip">&#x1F4C4; Download it as a <strong>PDF</strong>. That's the file you upload here.</div>
<div class="lp-guide-card lp-guide-featured">
<div class="lp-guide-card-badge">Recommended</div>
<div class="lp-guide-card-name">AnnualCreditReport.com</div>
<div class="lp-guide-card-desc">The official site. Free reports from all 3 bureaus every week. This is the one most people use.</div>
<a href="https://www.annualcreditreport.com" target="_blank" rel="noopener noreferrer" class="lp-guide-card-link">Go to site &rarr;</a>
</div>
<details class="lp-guide-more">
<summary class="lp-guide-more-toggle">See more options</summary>
<div class="lp-guide-more-list">
<div class="lp-guide-row"><span class="lp-guide-row-name">Equifax</span><span class="lp-guide-row-desc">Direct from their site</span><a href="https://www.equifax.com/personal/credit-report-services/" target="_blank" rel="noopener noreferrer" class="lp-guide-row-link">Visit &rarr;</a></div>
<div class="lp-guide-row"><span class="lp-guide-row-name">Experian</span><span class="lp-guide-row-desc">Free membership available</span><a href="https://www.experian.com/consumer-products" target="_blank" rel="noopener noreferrer" class="lp-guide-row-link">Visit &rarr;</a></div>
<div class="lp-guide-row"><span class="lp-guide-row-name">TransUnion</span><span class="lp-guide-row-desc">Free options available</span><a href="https://www.transunion.com/credit" target="_blank" rel="noopener noreferrer" class="lp-guide-row-link">Visit &rarr;</a></div>
<div class="lp-guide-row"><span class="lp-guide-row-name">Credit Karma</span><span class="lp-guide-row-desc">Free TransUnion &amp; Equifax</span><a href="https://www.creditkarma.com" target="_blank" rel="noopener noreferrer" class="lp-guide-row-link">Visit &rarr;</a></div>
<div class="lp-guide-row"><span class="lp-guide-row-name">Your Bank / Card</span><span class="lp-guide-row-desc">Many offer free reports in their app</span></div>
</div>
</details>
</div>""", unsafe_allow_html=True)

    # --- TRUST & SECURITY ---
    st.markdown(f"""<div class="lp-section">
<h2 class="lp-section-title">Safe and private.</h2>
<div class="lp-testimonial-grid">
<div class="lp-testimonial"><div class="lp-testimonial-text"><strong style="color:#D4A017;">We don't save your report.</strong> We read it, scan it, and that's it. Nothing is stored.</div></div>
<div class="lp-testimonial"><div class="lp-testimonial-text"><strong style="color:#D4A017;">Your data is locked down.</strong> Everything is sent safely. We never share your info with anyone.</div></div>
<div class="lp-testimonial"><div class="lp-testimonial-text"><strong style="color:#D4A017;">Delete it all.</strong> One click removes all your data for good. You'll find it in your settings.</div></div>
</div>
</div>""", unsafe_allow_html=True)

    # --- FAQ ---
    st.markdown("""<div class="lp-section lp-faq-section">
<h2 class="lp-section-title">Common questions.</h2>
<div class="lp-faq-list">
<details class="lp-faq-item"><summary class="lp-faq-q">What does 850 Lab do?</summary><div class="lp-faq-a">You upload your credit report PDF. Our AI reads it and looks for errors &mdash; wrong amounts, accounts that aren't yours, old info, and more. Then it writes dispute letters for you, ready to send.</div></details>
<details class="lp-faq-item"><summary class="lp-faq-q">Is it legal to dispute errors?</summary><div class="lp-faq-a">Yes. The law says you can dispute wrong info on your report. The bureaus must look into it within 30 days.</div></details>
<details class="lp-faq-item"><summary class="lp-faq-q">Will this hurt my credit score?</summary><div class="lp-faq-a">No. A dispute does not lower your score. If a mistake gets fixed or removed, your score could go up.</div></details>
<details class="lp-faq-item"><summary class="lp-faq-q">Do I need all 3 bureau reports?</summary><div class="lp-faq-a">No. You can upload one, two, or all three. If you upload all three, we can compare them and find more errors.</div></details>
<details class="lp-faq-item"><summary class="lp-faq-q">Is my data safe?</summary><div class="lp-faq-a">Yes. We never save your credit report. We read it, scan it, and that's it. You can delete all your data any time from your settings.</div></details>
<details class="lp-faq-item"><summary class="lp-faq-q">What does &ldquo;private beta&rdquo; mean?</summary><div class="lp-faq-a">We're still making things better. Right now, it's all free. Once we're done, we'll open it to everyone. No credit card needed.</div></details>
<details class="lp-faq-item"><summary class="lp-faq-q">Is 850 Lab a law firm?</summary><div class="lp-faq-a">No. 850 Lab is a tool. It helps you use your rights under the law. We don't give legal advice. We don't promise any results.</div></details>
</div>
</div>""", unsafe_allow_html=True)

    # --- FINAL CTA ---
    st.markdown(f"""<div class="lp-section" style="text-align:center;padding-bottom:2rem;">
<h2 class="lp-section-title">See what's on your report.</h2>
<p class="lp-section-sub" style="margin-bottom:1.2rem;">Try the demo first or jump right in. No credit card needed.</p>
<div class="lp-cta-row">
<a href="?nav=demo" class="lp-btn-primary" target="_self">Try It Free &mdash; No Sign Up</a>
<a href="?nav=signup" class="lp-btn-secondary" target="_self">Create Account</a>
</div>
</div>""", unsafe_allow_html=True)

    # --- FOOTER ---
    st.markdown("""<div style="text-align:center;padding:1.5rem 0 2.5rem;border-top:1px solid rgba(255,215,140,0.1);margin-top:1rem;">
<span style="color:#666;font-size:0.8rem;">
<a href="?page=guide" style="color:#888;text-decoration:none;" target="_self">How It Works</a>
&nbsp;&middot;&nbsp;
<a href="?page=terms" style="color:#888;text-decoration:none;" target="_self">Terms</a>
&nbsp;&middot;&nbsp;
<a href="?page=privacy" style="color:#888;text-decoration:none;" target="_self">Privacy</a>
&nbsp;&middot;&nbsp;
<a href="?page=refund" style="color:#888;text-decoration:none;" target="_self">Refund Policy</a>
</span>
</div>""", unsafe_allow_html=True)

    # --- SCROLL FADE-IN ANIMATIONS ---
    import streamlit.components.v1 as _anim_comp
    _anim_comp.html("""<script>
(function(){
  var root = window.parent.document;
  var sections = root.querySelectorAll('.lp-section');
  if(!sections.length) return;
  sections.forEach(function(s){ s.classList.add('lp-animate'); });
  if('IntersectionObserver' in window.parent){
    var obs = new window.parent.IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if(e.isIntersecting){
          e.target.classList.add('lp-visible');
          obs.unobserve(e.target);
        }
      });
    },{root:null, threshold:0.12});
    sections.forEach(function(s){ obs.observe(s); });
  } else {
    sections.forEach(function(s){ s.classList.add('lp-visible'); });
  }
})();
</script>""", height=0, width=0)


def render_ad_landing():
    logo_b64 = _get_logo_b64()
    report_count = _get_report_count()
    user_count = _get_user_count()

    qp = st.query_params
    ref_code = qp.get('ref')
    if ref_code:
        st.session_state['_referral_code'] = ref_code
    for utm_key in ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'):
        val = qp.get(utm_key)
        if val:
            st.session_state[f'_{utm_key}'] = val

    _pixel_js = ""
    _meta_pixel_id = os.environ.get('META_PIXEL_ID', '')
    _tt_pixel_id = os.environ.get('TIKTOK_PIXEL_ID', '')
    if _meta_pixel_id:
        _pixel_js += f"""
        !function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
        n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;
        n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
        t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}
        (window.parent,window.parent.document,'script','https://connect.facebook.net/en_US/fbevents.js');
        window.parent.fbq('init','{_meta_pixel_id}');
        window.parent.fbq('track','PageView');
        """
    if _tt_pixel_id:
        _pixel_js += f"""
        !function(w,d,t){{w.TiktokAnalyticsObject=t;var ttq=w[t]=w[t]||[];
        ttq.methods=["page","track","identify","instances","debug","on","off","once","ready","alias",
        "group","enableCookie","disableCookie"];ttq.setAndDefer=function(t,e){{t[e]=function(){{
        t.push([e].concat(Array.prototype.slice.call(arguments,0)));}}}};for(var i=0;i<ttq.methods.length;i++)
        ttq.setAndDefer(ttq,ttq.methods[i]);ttq.instance=function(t){{for(var e=ttq._i[t]||[],n=0;
        n<ttq.methods.length;n++)ttq.setAndDefer(e,ttq.methods[n]);return e}};ttq.load=function(e,n){{
        var i="https://analytics.tiktok.com/i18n/pixel/events.js";ttq._i=ttq._i||{{}};ttq._i[e]=[];
        ttq._i[e]._u=i;ttq._t=ttq._t||{{}};ttq._t[e]=+new Date;ttq._o=ttq._o||{{}};ttq._o[e]=n||{{}};
        var o=d.createElement("script");o.type="text/javascript";o.async=!0;o.src=i+"?sdkid="+e+"&lib="+t;
        var a=d.getElementsByTagName("script")[0];a.parentNode.insertBefore(o,a)}};
        ttq.load('{_tt_pixel_id}');ttq.page();}}(window.parent,window.parent.document,'ttq');
        """
    if _pixel_js:
        import streamlit.components.v1 as _px_comp
        _px_comp.html(f'<script>{_pixel_js}</script>', height=0, width=0)

    social_proof_html = ""
    if report_count:
        social_proof_html = f'<div style="font-size:0.82rem;color:#a0a0a8;margin-top:0.8rem;">{report_count} reports checked so far</div>'
    elif user_count and user_count >= 10:
        social_proof_html = f'<div style="font-size:0.82rem;color:#a0a0a8;margin-top:0.8rem;">{user_count:,} people have signed up</div>'

    st.markdown(f"""
<div style="text-align:center;padding:2.5rem 1rem 1.5rem;max-width:480px;margin:0 auto;">
<img src="data:image/png;base64,{logo_b64}" style="width:80px;height:auto;margin-bottom:1.2rem;" alt="850 Lab">

<div style="font-size:2.4rem;font-weight:900;color:#f5f5f5;line-height:1.1;letter-spacing:-0.04em;margin-bottom:0.8rem;">
Your Credit Report<br/>May Have Errors.<br/><span style="color:#D4A017;">Find Out in 60 Seconds.</span>
</div>

<div style="font-size:1rem;color:#a0a0a8;margin-bottom:1.5rem;line-height:1.5;">
Upload your report. Our AI finds errors and writes dispute letters for you. It takes less than a minute.
</div>

<a href="?nav=demo" target="_self" style="display:block;padding:16px 32px;
    background:linear-gradient(90deg,#D4A017,#f2c94c);color:#1a1a1f;
    font-weight:800;font-size:1.1rem;border-radius:12px;text-decoration:none;
    box-shadow:0 6px 24px rgba(212,160,23,0.35);margin-bottom:0.8rem;
    letter-spacing:0.01em;">
    Try It Free &mdash; No Sign Up &rarr;
</a>
<a href="?nav=signup" target="_self" style="display:block;padding:12px 28px;
    background:transparent;color:#f5f5f5;
    font-weight:600;font-size:0.95rem;border-radius:10px;text-decoration:none;
    border:2px solid rgba(255,215,140,0.15);margin-bottom:0.8rem;">
    Create Account
</a>
<div style="font-size:0.82rem;color:#a0a0a8;">Free right now. No credit card needed.</div>
{social_proof_html}
</div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
<div style="max-width:440px;margin:1rem auto 0;padding:0 1rem;">

<div style="background:#1a1a1f;border:1px solid rgba(255,215,140,0.12);border-radius:14px;padding:20px;margin-bottom:16px;">
<div style="font-size:0.92rem;font-weight:800;color:#f5f5f5;margin-bottom:14px;text-align:center;">How it works</div>
<div style="display:flex;flex-direction:column;gap:14px;">
<div style="display:flex;align-items:center;gap:12px;">
<div style="min-width:36px;height:36px;background:linear-gradient(135deg,#D4A017,#B8860B);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:0.9rem;color:#1a1a1f;">1</div>
<div><div style="font-size:0.88rem;font-weight:700;color:#f5f5f5;">Upload your PDF</div>
<div style="font-size:0.78rem;color:#a0a0a8;">From TransUnion, Equifax, or Experian</div></div>
</div>
<div style="display:flex;align-items:center;gap:12px;">
<div style="min-width:36px;height:36px;background:linear-gradient(135deg,#D4A017,#B8860B);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:0.9rem;color:#1a1a1f;">2</div>
<div><div style="font-size:0.88rem;font-weight:700;color:#f5f5f5;">AI checks every account</div>
<div style="font-size:0.78rem;color:#a0a0a8;">Balances, payments, status, and dates</div></div>
</div>
<div style="display:flex;align-items:center;gap:12px;">
<div style="min-width:36px;height:36px;background:linear-gradient(135deg,#D4A017,#B8860B);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:0.9rem;color:#1a1a1f;">3</div>
<div><div style="font-size:0.88rem;font-weight:700;color:#f5f5f5;">Get your results and letters</div>
<div style="font-size:0.78rem;color:#a0a0a8;">Dispute letters ready to send, with legal backing</div></div>
</div>
</div>
</div>

<div style="background:linear-gradient(135deg,rgba(212,160,23,0.10),rgba(212,160,23,0.04));
    border:1px solid rgba(212,160,23,0.2);border-radius:14px;padding:18px;margin-bottom:16px;">
<div style="font-size:0.88rem;color:#f5f5f5;font-weight:700;margin-bottom:10px;text-align:center;">Errors the AI looks for</div>
<div style="display:flex;flex-direction:column;gap:8px;">
<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,215,140,0.08);">
<span style="font-size:0.82rem;color:#a0a0a8;">Wrong balance amounts</span>
<span style="font-size:0.82rem;color:#D4A017;font-weight:600;">Changes how much you owe</span>
</div>
<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,215,140,0.08);">
<span style="font-size:0.82rem;color:#a0a0a8;">Wrong payment history</span>
<span style="font-size:0.82rem;color:#D4A017;font-weight:600;">Hurts your pay record</span>
</div>
<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,215,140,0.08);">
<span style="font-size:0.82rem;color:#a0a0a8;">Accounts that aren't yours</span>
<span style="font-size:0.82rem;color:#D4A017;font-weight:600;">Doesn't belong to you</span>
</div>
<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;">
<span style="font-size:0.82rem;color:#a0a0a8;">Old account status</span>
<span style="font-size:0.82rem;color:#D4A017;font-weight:600;">Should show the latest info</span>
</div>
</div>
</div>

<div style="background:#1a1a1f;border:1px solid rgba(255,215,140,0.12);border-radius:14px;padding:16px;margin-bottom:16px;">
<div style="font-size:0.88rem;font-weight:700;color:#f5f5f5;margin-bottom:8px;text-align:center;">Need your credit report?</div>
<div style="font-size:0.82rem;color:#a0a0a8;text-align:center;margin-bottom:10px;line-height:1.5;">
You can get free copies every week from the official site. It takes about 2 minutes.
</div>
<div style="text-align:center;">
<a href="https://www.annualcreditreport.com" target="_blank" rel="noopener noreferrer"
    style="display:inline-block;padding:10px 20px;background:rgba(212,160,23,0.12);
    border:1px solid rgba(212,160,23,0.3);color:#D4A017;font-weight:600;font-size:0.85rem;
    border-radius:8px;text-decoration:none;">AnnualCreditReport.com &rarr;</a>
</div>
</div>

<div style="background:#1a1a1f;border:1px solid rgba(255,215,140,0.12);border-radius:14px;padding:16px;margin-bottom:16px;">
<div style="font-size:0.88rem;font-weight:700;color:#f5f5f5;margin-bottom:10px;text-align:center;">Your data stays private</div>
<div style="font-size:0.82rem;color:#a0a0a8;line-height:1.6;text-align:center;">
We never save your report. Your data is safe in transit. Delete it all with one click.
</div>
</div>

<div style="text-align:center;padding:1rem 0 0.5rem;">
<a href="?nav=demo" target="_self" style="display:block;padding:16px 32px;
    background:linear-gradient(90deg,#D4A017,#f2c94c);color:#1a1a1f;
    font-weight:800;font-size:1.05rem;border-radius:12px;text-decoration:none;
    box-shadow:0 6px 24px rgba(212,160,23,0.35);margin-bottom:0.5rem;">
    Try It Free &mdash; No Sign Up &rarr;
</a>
<a href="?nav=signup" target="_self" style="display:block;padding:10px 24px;
    background:transparent;color:#f5f5f5;font-weight:600;font-size:0.9rem;
    border-radius:8px;text-decoration:none;border:1px solid rgba(255,215,140,0.15);
    margin-bottom:0.5rem;">Create Account</a>
<div style="font-size:0.78rem;color:#a0a0a8;">Free right now. No credit card. Your data stays private.</div>
</div>

</div>

<div style="text-align:center;padding:1.5rem 0 2.5rem;border-top:1px solid rgba(255,215,140,0.1);margin-top:1rem;">
<span style="color:#666;font-size:0.75rem;">
<a href="?page=guide" style="color:#888;text-decoration:none;" target="_self">How It Works</a>
&nbsp;&middot;&nbsp;
<a href="?page=terms" style="color:#888;text-decoration:none;" target="_self">Terms</a>
&nbsp;&middot;&nbsp;
<a href="?page=privacy" style="color:#888;text-decoration:none;" target="_self">Privacy</a>
&nbsp;&middot;&nbsp;
<a href="?page=refund" style="color:#888;text-decoration:none;" target="_self">Refund Policy</a>
</span>
</div>
    """, unsafe_allow_html=True)
