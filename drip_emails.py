import logging
from database import get_db
from resend_client import _get_resend_credentials
import resend

logger = logging.getLogger(__name__)

DRIP_SEQUENCE = [
    {"type": "welcome", "delay_hours": 0},
    {"type": "nudge_upload", "delay_hours": 24},
    {"type": "final_push", "delay_hours": 72},
]


def has_drip_been_sent(user_id: int, email_type: str) -> bool:
    with get_db() as (conn, cur):
        cur.execute(
            'SELECT id FROM drip_emails WHERE user_id = %s AND email_type = %s',
            (user_id, email_type),
        )
        return cur.fetchone() is not None


def mark_drip_sent(user_id: int, email_type: str):
    with get_db() as (conn, cur):
        cur.execute(
            '''INSERT INTO drip_emails (user_id, email_type)
               VALUES (%s, %s)
               ON CONFLICT (user_id, email_type) DO NOTHING''',
            (user_id, email_type),
        )
        conn.commit()


def user_has_purchased(user_id: int) -> bool:
    with get_db() as (conn, cur):
        cur.execute(
            "SELECT id FROM entitlement_transactions WHERE user_id = %s AND transaction_type = 'credit' LIMIT 1",
            (user_id,),
        )
        return cur.fetchone() is not None


def user_has_uploaded(user_id: int) -> bool:
    with get_db() as (conn, cur):
        cur.execute(
            'SELECT id FROM reports WHERE user_id = %s LIMIT 1',
            (user_id,),
        )
        return cur.fetchone() is not None


def get_user_age_hours(user_id: int) -> float:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            "SELECT EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0 AS hours FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    if row:
        return float(row['hours'])
    return 0.0


def _send_drip(to_email: str, subject: str, html_body: str) -> bool:
    try:
        creds = _get_resend_credentials()
        resend.api_key = creds["api_key"]
        from_email = creds["from_email"]
        params: resend.Emails.SendParams = {
            "from": f"850 Lab <{from_email}>",
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        logger.warning(f"Drip email send failed: {e}")
        return False


def _email_wrapper(content: str) -> str:
    return f'''
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #121212; padding: 40px 32px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #F5C542; font-size: 28px; margin: 0; letter-spacing: -0.02em;">850 Lab</h1>
        </div>
        {content}
        <div style="text-align: center; margin-top: 32px; padding-top: 20px; border-top: 1px solid #333;">
            <p style="color: #666; font-size: 11px; margin: 0;">
                You received this because you signed up for 850 Lab.<br/>
                Questions? Reply to this email anytime.
            </p>
        </div>
    </div>
    '''


def _welcome_email(display_name: str) -> tuple:
    greeting = f"Hi {display_name}," if display_name else "Hi,"
    subject = "Welcome to 850 Lab — here's what to do next"
    body = _email_wrapper(f'''
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
            You're in. 850 Lab is ready to scan your credit report for errors and generate
            dispute letters backed by real legal citations.
        </p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
            <strong style="color: #F5C542;">Here's how to get started:</strong>
        </p>
        <ol style="color: #E0E0E0; font-size: 15px; line-height: 1.8; margin-bottom: 20px; padding-left: 20px;">
            <li>Go to <strong>AnnualCreditReport.com</strong> and download your free report from any bureau</li>
            <li>Upload the PDF to 850 Lab</li>
            <li>Review the errors we find and generate your dispute letters</li>
        </ol>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 24px;">
            The upload and analysis are completely free. You'll see exactly what's on your
            report and what could be hurting your score before you spend anything.
        </p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="display: inline-block; background: #F5C542; color: #121212; font-weight: 700; font-size: 15px; padding: 12px 32px; border-radius: 8px;">
                Upload Your Report Now
            </span>
        </div>
    ''')
    return subject, body


def _nudge_upload_email(display_name: str, has_uploaded: bool) -> tuple:
    greeting = f"Hi {display_name}," if display_name else "Hi,"

    if has_uploaded:
        subject = "Your report is ready — next step inside"
        body = _email_wrapper(f'''
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                You uploaded your credit report — nice work. We found items that could
                be hurting your score and are ready to generate your dispute letters.
            </p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                For <strong style="color: #F5C542;">$4.99</strong>, you get AI-powered strategy that picks
                your strongest disputes, plus 3 enhanced letters with deeper legal reasoning.
                That's less than a cup of coffee for letters that could save you thousands
                in interest over time.
            </p>
            <div style="text-align: center; margin: 24px 0;">
                <span style="display: inline-block; background: #F5C542; color: #121212; font-weight: 700; font-size: 15px; padding: 12px 32px; border-radius: 8px;">
                    Get Your Dispute Letters — $4.99
                </span>
            </div>
            <p style="color: #999; font-size: 13px; line-height: 1.5; text-align: center;">
                No subscription. No monthly fees. One-time purchase.
            </p>
        ''')
    else:
        subject = "Don't let credit errors cost you — upload your report"
        body = _email_wrapper(f'''
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                Quick reminder: 1 in 5 credit reports contain errors that could be
                costing you higher interest rates and denied applications.
            </p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                You signed up for 850 Lab but haven't uploaded a report yet.
                The scan is completely free — you'll see exactly what's on your report
                and whether anything needs to be disputed.
            </p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                Get your free report from <strong>AnnualCreditReport.com</strong>,
                then upload the PDF. It takes about 2 minutes.
            </p>
            <div style="text-align: center; margin: 24px 0;">
                <span style="display: inline-block; background: #F5C542; color: #121212; font-weight: 700; font-size: 15px; padding: 12px 32px; border-radius: 8px;">
                    Upload My Report Free
                </span>
            </div>
        ''')
    return subject, body


def _final_push_email(display_name: str, has_uploaded: bool) -> tuple:
    greeting = f"Hi {display_name}," if display_name else "Hi,"

    if has_uploaded:
        subject = "Your disputes are waiting — $4.99 before they expire"
        body = _email_wrapper(f'''
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                We analyzed your credit report and found items you can dispute.
                Your analysis is still saved — all you need to do is generate the letters.
            </p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                People who dispute errors on their reports often see improvements within
                30-45 days. The longer you wait, the longer those errors stay on your record.
            </p>
            <div style="background: #1B1B1B; border: 1px solid #333; border-radius: 10px; padding: 20px; margin: 20px 0; text-align: center;">
                <p style="color: #F5C542; font-size: 20px; font-weight: 700; margin: 0 0 4px 0;">$4.99</p>
                <p style="color: #999; font-size: 13px; margin: 0;">AI strategy + 3 enhanced dispute letters</p>
            </div>
            <div style="text-align: center; margin: 24px 0;">
                <span style="display: inline-block; background: #F5C542; color: #121212; font-weight: 700; font-size: 15px; padding: 12px 32px; border-radius: 8px;">
                    Generate My Letters Now
                </span>
            </div>
            <p style="color: #999; font-size: 13px; line-height: 1.5; text-align: center;">
                No subscription. No monthly fees. Just $4.99 one-time.
            </p>
        ''')
    else:
        subject = "Last chance: your free credit scan is waiting"
        body = _email_wrapper(f'''
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                Just a final reminder — your 850 Lab account is set up and ready to go.
                Upload your credit report to find out if errors are dragging down your score.
            </p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                Credit repair companies charge $79-$149/month for the same dispute letters
                you can generate here. 850 Lab does it for $4.99 — or you can just use the
                free scan to see what's there.
            </p>
            <div style="text-align: center; margin: 24px 0;">
                <span style="display: inline-block; background: #F5C542; color: #121212; font-weight: 700; font-size: 15px; padding: 12px 32px; border-radius: 8px;">
                    Scan My Report Free
                </span>
            </div>
        ''')
    return subject, body


FOUNDER_DRIP_SEQUENCE = [
    {"type": "founder_welcome", "delay_hours": 0},
    {"type": "founder_nudge_upload", "delay_hours": 24},
    {"type": "founder_transfer_cta", "delay_hours": 72},
]


def _founder_welcome_drip(display_name: str) -> tuple:
    greeting = f"Hi {display_name}," if display_name else "Hi,"
    subject = "Your Founding Member account is loaded — here's your game plan"
    body = _email_wrapper(f'''
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
            Your Founding Member account is fully activated. Here's what's loaded and ready for you:
        </p>
        <div style="background: #1B1B1B; border: 1px solid #333; border-radius: 12px; padding: 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; text-align: center;">
                <div style="flex: 1;">
                    <div style="font-size: 28px; font-weight: 700; color: #F5C542;">9</div>
                    <div style="font-size: 12px; color: #999; margin-top: 2px;">AI Strategy Rounds</div>
                </div>
                <div style="flex: 1;">
                    <div style="font-size: 28px; font-weight: 700; color: #F5C542;">9</div>
                    <div style="font-size: 12px; color: #999; margin-top: 2px;">Enhanced Letters</div>
                </div>
            </div>
        </div>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
            <strong style="color: #F5C542;">Step 1:</strong> Go to <strong>AnnualCreditReport.com</strong>
            and pull your free report from any bureau (TransUnion, Equifax, or Experian).
        </p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
            <strong style="color: #F5C542;">Step 2:</strong> Upload the PDF to 850 Lab. We'll scan it
            and show you every error and inconsistency.
        </p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 24px;">
            <strong style="color: #F5C542;">Step 3:</strong> Generate your dispute letters &mdash;
            your 9 rounds mean you can dispute across multiple reports and follow up if bureaus don't respond.
        </p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="display: inline-block; background: #F5C542; color: #121212; font-weight: 700; font-size: 15px; padding: 12px 32px; border-radius: 8px;">
                Upload My First Report
            </span>
        </div>
    ''')
    return subject, body


def _founder_nudge_upload_drip(display_name: str, has_uploaded: bool) -> tuple:
    greeting = f"Hi {display_name}," if display_name else "Hi,"
    if has_uploaded:
        subject = "Nice work — your report is ready for dispute letters"
        body = _email_wrapper(f'''
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                You uploaded your report &mdash; you're ahead of most people already. As a Founding Member,
                your AI strategy rounds and enhanced letters are ready to go. No payment needed.
            </p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                Head back to 850 Lab, review the errors we found, and generate your dispute letters.
                Bureaus have <strong style="color: #F5C542;">30 days to respond by law</strong> &mdash;
                the sooner you send, the sooner things start moving.
            </p>
            <div style="text-align: center; margin: 24px 0;">
                <span style="display: inline-block; background: #F5C542; color: #121212; font-weight: 700; font-size: 15px; padding: 12px 32px; border-radius: 8px;">
                    Generate My Letters Free
                </span>
            </div>
        ''')
    else:
        subject = "Your 9 free rounds are waiting — have you pulled your report yet?"
        body = _email_wrapper(f'''
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                Quick check-in: you've got 9 AI strategy rounds and 9 enhanced letters loaded
                in your Founding Member account, but you haven't uploaded a report yet.
            </p>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
                The hardest part is getting started. Here's all you need to do:
            </p>
            <ol style="color: #E0E0E0; font-size: 15px; line-height: 1.8; margin-bottom: 20px; padding-left: 20px;">
                <li>Visit <strong>AnnualCreditReport.com</strong> (it's the official free source)</li>
                <li>Download your report as a PDF</li>
                <li>Upload it to 850 Lab &mdash; takes about 2 minutes</li>
            </ol>
            <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 24px;">
                1 in 5 reports have errors. Let's find out if yours does.
            </p>
            <div style="text-align: center; margin: 24px 0;">
                <span style="display: inline-block; background: #F5C542; color: #121212; font-weight: 700; font-size: 15px; padding: 12px 32px; border-radius: 8px;">
                    Upload My Report
                </span>
            </div>
        ''')
    return subject, body


def _founder_transfer_cta_drip(display_name: str) -> tuple:
    greeting = f"Hi {display_name}," if display_name else "Hi,"
    subject = "Know someone with credit problems? You can help them for free."
    body = _email_wrapper(f'''
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">{greeting}</p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
            As a Founding Member, you have <strong style="color: #F5C542;">unused rounds you can transfer</strong>
            to anyone &mdash; a friend, family member, or anyone who could use help cleaning up their credit.
        </p>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
            Here's how it works:
        </p>
        <ol style="color: #E0E0E0; font-size: 15px; line-height: 1.8; margin-bottom: 20px; padding-left: 20px;">
            <li>Open 850 Lab and look for <strong>"Transfer Rounds"</strong> in the sidebar</li>
            <li>Enter their email and choose how many rounds to send</li>
            <li>They get notified instantly and can start using them right away</li>
        </ol>
        <p style="color: #E0E0E0; font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
            You also have a personal <strong style="color: #F5C542;">referral link</strong> in
            your sidebar. When someone signs up through your link, you earn a free AI round.
        </p>
        <p style="color: #999; font-size: 13px; line-height: 1.5; text-align: center; margin-top: 24px;">
            Credit problems are stressful. Having someone share a tool like this can make a real difference.
        </p>
    ''')
    return subject, body


def _is_founder(user_id: int) -> bool:
    try:
        from auth import is_user_founder
        return is_user_founder(user_id)
    except Exception:
        return False


def process_drip_emails(user_id: int, email: str, display_name: str = None):
    if not email or not email.strip():
        return

    is_founder = _is_founder(user_id)

    if is_founder:
        age_hours = get_user_age_hours(user_id)
        has_uploaded = user_has_uploaded(user_id)
        for step in FOUNDER_DRIP_SEQUENCE:
            email_type = step["type"]
            delay = step["delay_hours"]
            if age_hours < delay:
                break
            if has_drip_been_sent(user_id, email_type):
                continue
            if email_type == "founder_welcome":
                subject, body = _founder_welcome_drip(display_name)
            elif email_type == "founder_nudge_upload":
                subject, body = _founder_nudge_upload_drip(display_name, has_uploaded)
            elif email_type == "founder_transfer_cta":
                subject, body = _founder_transfer_cta_drip(display_name)
            else:
                continue
            if _send_drip(email, subject, body):
                mark_drip_sent(user_id, email_type)
                logger.info(f"Founder drip '{email_type}' sent to user {user_id}")
        return

    if user_has_purchased(user_id):
        return

    age_hours = get_user_age_hours(user_id)
    has_uploaded = user_has_uploaded(user_id)

    for step in DRIP_SEQUENCE:
        email_type = step["type"]
        delay = step["delay_hours"]

        if age_hours < delay:
            break

        if has_drip_been_sent(user_id, email_type):
            continue

        if email_type == "welcome":
            subject, body = _welcome_email(display_name)
        elif email_type == "nudge_upload":
            subject, body = _nudge_upload_email(display_name, has_uploaded)
        elif email_type == "final_push":
            subject, body = _final_push_email(display_name, has_uploaded)
        else:
            continue

        if _send_drip(email, subject, body):
            mark_drip_sent(user_id, email_type)
            logger.info(f"Drip '{email_type}' sent to user {user_id}")
