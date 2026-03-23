import os
import secrets
import string
from database import get_db


def _generate_code(length=8):
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(chars) for _ in range(length))
        with get_db() as (conn, cur):
            cur.execute('SELECT 1 FROM referral_codes WHERE code = %s', (code,))
            if not cur.fetchone():
                return code


def get_or_create_referral_code(user_id):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT code FROM referral_codes WHERE user_id = %s', (user_id,))
        row = cur.fetchone()
        if row:
            return row['code']
        code = _generate_code()
        cur.execute(
            'INSERT INTO referral_codes (user_id, code) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING RETURNING code',
            (user_id, code)
        )
        result = cur.fetchone()
        if result:
            conn.commit()
            return result['code']
        conn.commit()
        cur.execute('SELECT code FROM referral_codes WHERE user_id = %s', (user_id,))
        return cur.fetchone()['code']


def get_referral_link(user_id):
    code = get_or_create_referral_code(user_id)
    base = os.environ.get('REPLIT_DEV_DOMAIN', '')
    if not base:
        base = os.environ.get('REPLIT_DOMAINS', '').split(',')[0] if os.environ.get('REPLIT_DOMAINS') else 'localhost:5000'
    scheme = 'https' if base != 'localhost:5000' else 'http'
    return f"{scheme}://{base}/?ref={code}"


def record_referral(referee_user_id, referral_code):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT user_id FROM referral_codes WHERE code = %s', (referral_code,))
        row = cur.fetchone()
        if not row:
            return False
        referrer_id = row['user_id']
        if referrer_id == referee_user_id:
            return False
        cur.execute(
            'SELECT 1 FROM referrals WHERE referee_id = %s',
            (referee_user_id,)
        )
        if cur.fetchone():
            return False
        cur.execute('''
            INSERT INTO referrals (referrer_id, referee_id, referral_code, status)
            VALUES (%s, %s, %s, 'signed_up')
        ''', (referrer_id, referee_user_id, referral_code))
        conn.commit()
        return True


def fulfill_referral_reward(referee_user_id):
    import auth
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT id, referrer_id FROM referrals
            WHERE referee_id = %s AND status = 'signed_up'
        ''', (referee_user_id,))
        row = cur.fetchone()
        if not row:
            return False
        referrer_id = row['referrer_id']
        referral_id = row['id']
        cur.execute('''
            UPDATE referrals SET status = 'rewarded', rewarded_at = NOW()
            WHERE id = %s
        ''', (referral_id,))
        conn.commit()
    auth.add_entitlements(
        referrer_id,
        ai_rounds=1,
        source='referral',
        note=f'Referral reward: user {referee_user_id} signed up'
    )
    return True


def get_referral_stats(user_id):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT
                COUNT(*) FILTER (WHERE status IN ('signed_up', 'rewarded')) as total_referrals,
                COUNT(*) FILTER (WHERE status = 'rewarded') as rewards_earned
            FROM referrals WHERE referrer_id = %s
        ''', (user_id,))
        row = cur.fetchone()
        return {
            'total_referrals': row['total_referrals'] if row else 0,
            'rewards_earned': row['rewards_earned'] if row else 0,
        }


def get_reports_analyzed_count():
    try:
        with get_db() as (conn, cur):
            cur.execute('SELECT COUNT(*) FROM reports')
            count = cur.fetchone()[0] or 0
            return count
    except Exception:
        return 0
