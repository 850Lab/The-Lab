import html
import os
import requests

_resend = None

def _get_resend():
    global _resend
    if _resend is None:
        import resend
        _resend = resend
    return _resend


def _resolve_resend_credentials():
    """
    Prefer explicit env (local / CI); fall back to Replit connector when configured.
    """
    api_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    from_email = (os.environ.get("RESEND_FROM_EMAIL") or "").strip()
    if api_key and from_email:
        return {"api_key": api_key, "from_email": from_email}
    return _get_resend_credentials()


def _get_resend_credentials():
    hostname = os.environ.get("REPLIT_CONNECTORS_HOSTNAME")
    repl_identity = os.environ.get("REPL_IDENTITY")
    web_repl_renewal = os.environ.get("WEB_REPL_RENEWAL")

    if repl_identity:
        token = "repl " + repl_identity
    elif web_repl_renewal:
        token = "depl " + web_repl_renewal
    else:
        raise RuntimeError("Resend connector: no Replit token found")

    resp = requests.get(
        f"https://{hostname}/api/v2/connection?include_secrets=true&connector_names=resend",
        headers={"Accept": "application/json", "X_REPLIT_TOKEN": token},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    item = data.get("items", [None])[0]
    if not item or not item.get("settings", {}).get("api_key"):
        raise RuntimeError("Resend not connected")
    from_email = os.environ.get("RESEND_FROM_EMAIL") or item["settings"].get("from_email", "")
    if not from_email:
        raise RuntimeError("Resend from_email not configured")
    return {
        "api_key": item["settings"]["api_key"],
        "from_email": from_email,
    }


def send_workflow_reminder_email(
    to_email: str,
    *,
    reminder_type: str,
    reason_plain: str,
    display_name: str = None,
) -> dict:
    """
    Lifecycle reminder (workflow worker). Raises on misconfiguration or send failure.
    Returns a small dict safe to log (provider id only).
    """
    creds = _resolve_resend_credentials()
    _get_resend().api_key = creds["api_key"]
    from_email = creds["from_email"]

    greeting = f"Hi {html.escape(display_name)}," if display_name else "Hi,"
    rtype = html.escape((reminder_type or "reminder")[:80])
    body = html.escape((reason_plain or "")[:2000])

    html_body = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #121212; padding: 40px 32px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #F5C542; font-size: 28px; margin: 0; letter-spacing: -0.02em;">850 Lab</h1>
        </div>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
        <p style="color: #999; font-size: 12px; line-height: 1.5; margin-bottom: 12px;">Reminder type: {rtype}</p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 24px;">{body}</p>
        <div style="text-align: center; margin-top: 24px;">
            <a href="https://850.life" style="display: inline-block; background: linear-gradient(90deg, #D4A017, #f2c94c); color: #121212; font-weight: 700; font-size: 14px; padding: 12px 32px; border-radius: 8px; text-decoration: none;">Open 850 Lab</a>
        </div>
        <p style="color: #666; font-size: 12px; line-height: 1.5; text-align: center; margin-top: 24px;">
            You are receiving this because you have an active dispute workflow.
        </p>
    </div>
    """

    resend_mod = _get_resend()
    params: resend_mod.Emails.SendParams = {
        "from": f"850 Lab <{from_email}>",
        "to": [to_email],
        "subject": f"850 Lab — Action needed ({reminder_type[:40]})",
        "html": html_body,
    }

    raw = resend_mod.Emails.send(params)
    mid = ""
    if isinstance(raw, dict):
        mid = str(raw.get("id") or "")[:120]
    else:
        mid = str(raw)[:120]
    return {"provider": "resend", "message_id": mid or "sent"}


def send_verification_email(to_email: str, code: str, display_name: str = None):
    creds = _get_resend_credentials()
    _get_resend().api_key = creds["api_key"]
    from_email = creds["from_email"]

    greeting = f"Hi {display_name}," if display_name else "Hi,"

    html_body = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #121212; padding: 40px 32px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #F5C542; font-size: 28px; margin: 0; letter-spacing: -0.02em;">850 Lab</h1>
        </div>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 24px;">
            Enter this code to verify your email and activate your account:
        </p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="display: inline-block; background: #1B1B1B; border: 2px solid #F5C542; border-radius: 12px; padding: 16px 40px; font-size: 32px; font-weight: 700; letter-spacing: 0.3em; color: #F5C542;">{code}</span>
        </div>
        <p style="color: #999; font-size: 13px; line-height: 1.5; margin-top: 24px; text-align: center;">
            This code expires in 30 minutes.<br>
            If you didn't create an account, you can safely ignore this email.
        </p>
    </div>
    """

    resend_mod = _get_resend()
    params: resend_mod.Emails.SendParams = {
        "from": f"850 Lab <{from_email}>",
        "to": [to_email],
        "subject": f"{code} — Verify your 850 Lab account",
        "html": html_body,
    }

    return resend_mod.Emails.send(params)


def send_password_reset_email(to_email: str, code: str, display_name: str = None):
    creds = _get_resend_credentials()
    _get_resend().api_key = creds["api_key"]
    from_email = creds["from_email"]

    greeting = f"Hi {display_name}," if display_name else "Hi,"

    html_body = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #121212; padding: 40px 32px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #F5C542; font-size: 28px; margin: 0; letter-spacing: -0.02em;">850 Lab</h1>
        </div>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 24px;">
            Enter this code to reset your password:
        </p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="display: inline-block; background: #1B1B1B; border: 2px solid #F5C542; border-radius: 12px; padding: 16px 40px; font-size: 32px; font-weight: 700; letter-spacing: 0.3em; color: #F5C542;">{code}</span>
        </div>
        <p style="color: #999; font-size: 13px; line-height: 1.5; margin-top: 24px; text-align: center;">
            This code expires in 30 minutes.<br>
            If you didn't request a password reset, you can safely ignore this email.
        </p>
    </div>
    """

    resend_mod = _get_resend()
    params: resend_mod.Emails.SendParams = {
        "from": f"850 Lab <{from_email}>",
        "to": [to_email],
        "subject": f"{code} — Reset your 850 Lab password",
        "html": html_body,
    }

    return resend_mod.Emails.send(params)


def send_reminder_email(to_email: str, display_name: str = None, round_number: int = 1, bureau_names: list = None):
    creds = _get_resend_credentials()
    _get_resend().api_key = creds["api_key"]
    from_email = creds["from_email"]

    greeting = f"Hi {display_name}," if display_name else "Hi,"

    if bureau_names:
        bureau_text = " & ".join(bureau_names)
    else:
        bureau_text = "the credit bureaus"

    html_body = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #121212; padding: 40px 32px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #F5C542; font-size: 28px; margin: 0; letter-spacing: -0.02em;">850 Lab</h1>
        </div>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
            Your Round {round_number} dispute letters have been sent to {bureau_text}. Under the Fair Credit Reporting Act (FCRA § 611), credit bureaus have 30 days to respond and investigate your disputes.
        </p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
            In 30–45 days, pull your updated credit report from the bureaus and upload it to 850 Lab for Round {round_number + 1} analysis. This gives us the data we need to drive your next round of disputes.
        </p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 24px;">
            Every dispute round brings you closer to building the financial record you deserve. Let's keep pushing toward your 850 score.
        </p>
        <p style="color: #999; font-size: 13px; line-height: 1.5; text-align: center;">
            Questions? We're here to help every step of the way.
        </p>
    </div>
    """

    resend_mod = _get_resend()
    params: resend_mod.Emails.SendParams = {
        "from": f"850 Lab <{from_email}>",
        "to": [to_email],
        "subject": f"850 Lab — Time to check your results (Round {round_number})",
        "html": html_body,
    }

    try:
        return resend_mod.Emails.send(params)
    except Exception:
        return None


def send_founder_welcome_email(to_email: str, display_name: str = None):
    creds = _get_resend_credentials()
    _get_resend().api_key = creds["api_key"]
    from_email = creds["from_email"]

    greeting = f"Hi {display_name}," if display_name else "Hi,"

    html_body = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #121212; padding: 40px 32px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #F5C542; font-size: 28px; margin: 0; letter-spacing: -0.02em;">850 Lab</h1>
        </div>
        <div style="text-align: center; margin-bottom: 24px;">
            <span style="display: inline-block; background: linear-gradient(135deg, #F5C542, #D4A017); color: #1a1a1a; padding: 6px 20px; border-radius: 20px; font-size: 13px; font-weight: 700; letter-spacing: 0.04em;">FOUNDING MEMBER</span>
        </div>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 20px;">
            Welcome to the founding team. You're one of the first 100 members of 850 Lab, and your account has been activated with the full Founding Member package:
        </p>
        <div style="background: #1B1B1B; border: 1px solid #333; border-radius: 12px; padding: 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
                <div style="text-align: center; flex: 1;">
                    <div style="font-size: 28px; font-weight: 700; color: #F5C542;">9</div>
                    <div style="font-size: 12px; color: #999; margin-top: 2px;">AI Strategy Rounds</div>
                </div>
                <div style="text-align: center; flex: 1;">
                    <div style="font-size: 28px; font-weight: 700; color: #F5C542;">9</div>
                    <div style="font-size: 12px; color: #999; margin-top: 2px;">Enhanced Letters</div>
                </div>
                <div style="text-align: center; flex: 1;">
                    <div style="font-size: 28px; font-weight: 700; color: #F5C542;">3</div>
                    <div style="font-size: 12px; color: #999; margin-top: 2px;">Bureaus Covered</div>
                </div>
            </div>
            <div style="text-align: center; font-size: 13px; color: #999; border-top: 1px solid #333; padding-top: 12px;">
                Estimated value: <strong style="color: #F5C542;">$500&ndash;$800</strong>
            </div>
        </div>
        <p style="color: #E0E0E0; font-size: 14px; line-height: 1.7; margin-bottom: 16px;">
            <strong style="color: #F5C542;">What you can do now:</strong>
        </p>
        <p style="color: #E0E0E0; font-size: 14px; line-height: 1.8; margin-bottom: 20px;">
            &#x2714; Upload your credit report from any bureau<br>
            &#x2714; Get AI-powered dispute strategy and enhanced letters<br>
            &#x2714; Transfer unused rounds to a friend from your sidebar<br>
            &#x2714; Only pay if you want us to mail letters certified for you
        </p>
        <p style="color: #999; font-size: 13px; line-height: 1.5; text-align: center; margin-top: 24px;">
            Thank you for believing in what we're building. Let's get your credit right.
        </p>
    </div>
    """

    resend_mod = _get_resend()
    params: resend_mod.Emails.SendParams = {
        "from": f"850 Lab <{from_email}>",
        "to": [to_email],
        "subject": "Welcome, Founding Member — Your 850 Lab account is ready",
        "html": html_body,
    }

    try:
        return resend_mod.Emails.send(params)
    except Exception:
        return None


def send_transfer_notification_email(to_email: str, from_display_name: str = None,
                                      ai_rounds: int = 0, letters: int = 0,
                                      recipient_name: str = None):
    creds = _get_resend_credentials()
    _get_resend().api_key = creds["api_key"]
    from_email = creds["from_email"]

    greeting = f"Hi {recipient_name}," if recipient_name else "Hi,"
    sender = from_display_name or "Another 850 Lab member"

    items = []
    if ai_rounds > 0:
        items.append(f"<strong style='color:#F5C542;'>{ai_rounds}</strong> AI Strategy Round{'s' if ai_rounds != 1 else ''}")
    if letters > 0:
        items.append(f"<strong style='color:#F5C542;'>{letters}</strong> Enhanced Letter{'s' if letters != 1 else ''}")
    items_html = " and ".join(items)

    html_body = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #121212; padding: 40px 32px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #F5C542; font-size: 28px; margin: 0; letter-spacing: -0.02em;">850 Lab</h1>
        </div>
        <div style="text-align: center; margin-bottom: 24px;">
            <span style="font-size: 36px;">&#x1f381;</span>
        </div>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 20px;">
            <strong>{sender}</strong> just sent you {items_html} on 850 Lab.
        </p>
        <div style="background: #1B1B1B; border: 1px solid #333; border-radius: 12px; padding: 20px; margin-bottom: 20px; text-align: center;">
            <div style="font-size: 14px; color: #999; margin-bottom: 8px;">You received</div>
            <div style="font-size: 18px; color: #E0E0E0; font-weight: 600;">{items_html}</div>
            <div style="font-size: 13px; color: #999; margin-top: 12px; border-top: 1px solid #333; padding-top: 12px;">
                These have already been added to your account balance.
            </div>
        </div>
        <p style="color: #E0E0E0; font-size: 14px; line-height: 1.7; margin-bottom: 20px;">
            Log in to 850 Lab to use them. Upload your credit report and we'll help you find errors, build a dispute strategy, and generate legally-cited letters.
        </p>
        <p style="color: #999; font-size: 13px; line-height: 1.5; text-align: center; margin-top: 24px;">
            Questions? We're here to help every step of the way.
        </p>
    </div>
    """

    resend_mod = _get_resend()
    params: resend_mod.Emails.SendParams = {
        "from": f"850 Lab <{from_email}>",
        "to": [to_email],
        "subject": f"{sender} sent you a gift on 850 Lab",
        "html": html_body,
    }

    try:
        return resend_mod.Emails.send(params)
    except Exception:
        return None


NUDGE_SUBJECTS = {
    'letters_not_mailed_48h': 'Your dispute letters are ready to send',
    'clock_not_started': 'Start your 30-day investigation clock',
    'utilization_no_update_72h': 'Action needed: High credit utilization',
    'approaching_day_28': 'Day {days} — Bureau deadline approaching',
    'day31_escalation_ready': 'Day {days} — Escalation authorized',
}

NUDGE_CTA = {
    'letters_not_mailed_48h': ('Send Your Letters', 'send_mail'),
    'clock_not_started': ('Start Tracking', 'tracker'),
    'utilization_no_update_72h': ('View Strategy', 'strategy'),
    'approaching_day_28': ('Prepare Escalation', 'escalation'),
    'day31_escalation_ready': ('Begin Escalation', 'escalation'),
}

SEVERITY_COLORS_EMAIL = {
    'info': '#42A5F5',
    'warn': '#FFA726',
    'critical': '#EF5350',
}


def send_nudge_email(to_email: str, nudge_id: str, severity: str, message: str, display_name: str = None, days_elapsed: int = 0):
    try:
        creds = _get_resend_credentials()
    except Exception:
        return None
    _get_resend().api_key = creds["api_key"]
    from_email = creds["from_email"]

    greeting = f"Hi {display_name}," if display_name else "Hi,"
    subject_template = NUDGE_SUBJECTS.get(nudge_id, 'Action needed on your credit dispute')
    subject = subject_template.format(days=days_elapsed) if '{days}' in subject_template else subject_template

    cta_label, _ = NUDGE_CTA.get(nudge_id, ('Open 850 Lab', 'home'))
    sev_color = SEVERITY_COLORS_EMAIL.get(severity, '#FFA726')
    sev_label = severity.upper()

    html_body = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #121212; padding: 40px 32px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #F5C542; font-size: 28px; margin: 0; letter-spacing: -0.02em;">850 Lab</h1>
        </div>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
        <div style="border-left: 3px solid {sev_color}; padding: 12px 16px; margin: 16px 0; background: rgba(255,255,255,0.03); border-radius: 0 8px 8px 0;">
            <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; color: {sev_color}; margin-bottom: 6px;">{sev_label}</div>
            <p style="color: #E0E0E0; font-size: 14px; line-height: 1.6; margin: 0;">{message}</p>
        </div>
        <div style="text-align: center; margin-top: 24px;">
            <a href="https://850.life" style="display: inline-block; background: linear-gradient(90deg, #D4A017, #f2c94c); color: #121212; font-weight: 700; font-size: 14px; padding: 12px 32px; border-radius: 8px; text-decoration: none;">{cta_label}</a>
        </div>
        <p style="color: #666; font-size: 12px; line-height: 1.5; text-align: center; margin-top: 24px;">
            You're receiving this because you have an active dispute in progress.
        </p>
    </div>
    """

    resend_mod = _get_resend()
    params: resend_mod.Emails.SendParams = {
        "from": f"850 Lab <{from_email}>",
        "to": [to_email],
        "subject": f"850 Lab — {subject}",
        "html": html_body,
    }

    try:
        return resend_mod.Emails.send(params)
    except Exception:
        return None


def send_upload_link_email(to_email: str, display_name: str = None, upload_url: str = "", letter_count: int = 0, bureau_names: list = None):
    creds = _get_resend_credentials()
    _get_resend().api_key = creds["api_key"]
    from_email = creds["from_email"]

    greeting = f"Hi {display_name}," if display_name else "Hi,"
    bureau_text = " & ".join(bureau_names) if bureau_names else "the credit bureaus"

    html_body = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #121212; padding: 40px 32px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #F5C542; font-size: 28px; margin: 0; letter-spacing: -0.02em;">850 Lab</h1>
        </div>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
            Your {letter_count} dispute letter{"s" if letter_count != 1 else ""} for {bureau_text} {"are" if letter_count != 1 else "is"} built and ready to go.
        </p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 20px;">
            Before we can mail them, we need a copy of your <strong style="color: #F5C542;">government ID</strong> and
            <strong style="color: #F5C542;">proof of address</strong> (like a utility bill or bank statement).
            The credit bureaus require these with every dispute.
        </p>
        <div style="text-align: center; margin-bottom: 24px;">
            <a href="{upload_url}" style="display: inline-block; padding: 14px 36px;
                background: linear-gradient(90deg, #F5C542, #D4A017); color: #1a1a1a;
                font-weight: 700; font-size: 16px; border-radius: 10px; text-decoration: none;
                box-shadow: 0 4px 16px rgba(212,160,23,0.3);">
                Upload Your Documents
            </a>
        </div>
        <p style="color: #999; font-size: 13px; line-height: 1.5; text-align: center; margin-bottom: 4px;">
            This link is good for 7 days. Once you upload, we handle the rest.
        </p>
        <p style="color: #666; font-size: 11px; line-height: 1.4; text-align: center;">
            If you did not request this, you can ignore this email.
        </p>
    </div>
    """

    resend_mod = _get_resend()
    params: resend_mod.Emails.SendParams = {
        "from": f"850 Lab <{from_email}>",
        "to": [to_email],
        "subject": "850 Lab \u2014 Upload your ID to get your letters sent",
        "html": html_body,
    }

    try:
        return resend_mod.Emails.send(params)
    except Exception:
        return None
