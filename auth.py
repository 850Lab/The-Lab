"""
auth.py | 850 Lab
Authentication, session management, and tier entitlements
"""

import os
import bcrypt
import secrets
from datetime import datetime, timedelta
import json
import logging
import random
import string

from database import get_db

logger = logging.getLogger(__name__)

TIERS = {
    'free': {
        'label': 'Free',
        'ai_strategy': False,
        'enhanced_letters': False,
    },
    'glow': {
        'label': 'Glow',
        'ai_strategy': True,
        'enhanced_letters': True,
    },
}

PACKS = {
    'deletion_sprint': {
        'label': '30-Day Deletion Sprint',
        'description': '2 Full Rounds + 6 Certified Mailings + Escalation + Free Round 3 Guarantee',
        'price_cents': 19900,
        'ai_rounds': 2,
        'letters': 6,
        'mailings': 6,
    },
    'full_round': {
        'label': 'Full Round',
        'description': '1 Full Dispute Round + 3 Certified Mailings',
        'price_cents': 2499,
        'ai_rounds': 1,
        'letters': 3,
        'mailings': 3,
    },
    'digital_only': {
        'label': 'Digital Only',
        'description': 'AI Strategy + 3 Enhanced Letters',
        'price_cents': 499,
        'ai_rounds': 1,
        'letters': 3,
        'mailings': 0,
    },
}

ALA_CARTE = {
    'ai_round': {
        'label': 'AI Strategy Round',
        'price_cents': 299,
        'type': 'ai_rounds',
        'qty': 1,
    },
    'letter': {
        'label': 'Enhanced Letter',
        'price_cents': 149,
        'type': 'letters',
        'qty': 1,
    },
    'mailing': {
        'label': 'Certified Mailing',
        'price_cents': 799,
        'type': 'mailings',
        'qty': 1,
    },
}

ROLES = ['consumer', 'admin']

SESSION_DURATION_DAYS = 30


def init_auth_tables():
    with get_db() as (conn, cur):
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'users'")
        if cur.fetchone():
            return
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                display_name VARCHAR(255),
                role VARCHAR(20) DEFAULT 'consumer',
                tier VARCHAR(20) DEFAULT 'free',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code VARCHAR(6)")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code_expires TIMESTAMP")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_founder BOOLEAN DEFAULT FALSE")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS founder_granted_at TIMESTAMP")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS utm_source VARCHAR(255)")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS utm_medium VARCHAR(255)")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS utm_campaign VARCHAR(255)")

        cur.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                session_token VARCHAR(255) UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS device_sessions (
                device_id VARCHAR(255) PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                session_token VARCHAR(255) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                amount INTEGER NOT NULL,
                currency VARCHAR(10) DEFAULT 'usd',
                stripe_session_id VARCHAR(255),
                stripe_payment_intent VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def create_user(email: str, password: str, display_name: str = None, role: str = 'consumer',
                utm_source: str = None, utm_medium: str = None, utm_campaign: str = None) -> dict:
    email_key = email.lower().strip()
    rl = _check_and_increment_rate_limit('signup', email_key)
    if not rl['allowed']:
        return {'error': 'Too many signup attempts. Please wait 15 minutes and try again.'}

    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT id FROM users WHERE email = %s', (email_key,))
        if cur.fetchone():
            return {'error': 'Could not create account. Please try a different email or sign in.'}

        pw_hash = hash_password(password)
        cur.execute('''
            INSERT INTO users (email, password_hash, display_name, role, utm_source, utm_medium, utm_campaign)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, email, display_name, role, tier, created_at
        ''', (email.lower().strip(), pw_hash, display_name, role,
              utm_source[:255] if utm_source else None,
              utm_medium[:255] if utm_medium else None,
              utm_campaign[:255] if utm_campaign else None))

        user = dict(cur.fetchone())
        conn.commit()
        return user


def _check_and_increment_rate_limit(action: str, identifier: str, max_attempts: int = 5, window_seconds: int = 900) -> dict:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            INSERT INTO rate_limits (action, identifier, attempt_count, window_start)
            VALUES (%s, %s, 1, NOW())
            ON CONFLICT (action, identifier)
            DO UPDATE SET
                attempt_count = CASE
                    WHEN EXTRACT(EPOCH FROM (NOW() - rate_limits.window_start)) > %s
                    THEN 1
                    ELSE rate_limits.attempt_count + 1
                END,
                window_start = CASE
                    WHEN EXTRACT(EPOCH FROM (NOW() - rate_limits.window_start)) > %s
                    THEN NOW()
                    ELSE rate_limits.window_start
                END
            RETURNING attempt_count
        ''', (action, identifier, window_seconds, window_seconds))
        row = cur.fetchone()
        conn.commit()
        count = row['attempt_count'] if row else 1
        return {'allowed': count <= max_attempts, 'count': count}


def _clear_rate_limit(action: str, identifier: str):
    with get_db() as (conn, cur):
        cur.execute('DELETE FROM rate_limits WHERE action = %s AND identifier = %s', (action, identifier))
        conn.commit()


def authenticate_user(email: str, password: str) -> dict:
    email_key = email.lower().strip()
    rl = _check_and_increment_rate_limit('login', email_key)
    if not rl['allowed']:
        return {'error': 'Too many login attempts. Please wait 15 minutes and try again.'}

    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT * FROM users WHERE email = %s', (email_key,))
        user = cur.fetchone()

    if not user:
        return {'error': 'Invalid email or password'}

    if not verify_password(password, user['password_hash']):
        return {'error': 'Invalid email or password'}

    _clear_rate_limit('login', email_key)
    user = dict(user)
    del user['password_hash']
    return user


def create_session(user_id: int, device_id: str = None) -> str:
    token = secrets.token_urlsafe(48)
    expires_at = datetime.utcnow() + timedelta(days=SESSION_DURATION_DAYS)

    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO sessions (user_id, session_token, expires_at)
            VALUES (%s, %s, %s)
        ''', (user_id, token, expires_at))
        if device_id:
            cur.execute('''
                INSERT INTO device_sessions (device_id, user_id, session_token, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (device_id) DO UPDATE
                SET user_id = EXCLUDED.user_id,
                    session_token = EXCLUDED.session_token,
                    updated_at = NOW()
            ''', (device_id, user_id, token))
        conn.commit()

    return token


def validate_session(token: str) -> dict:
    if not token:
        return None

    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT s.*, u.id as user_id, u.email, u.display_name, u.role, u.tier, u.email_verified
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_token = %s AND s.expires_at > NOW()
        ''', (token,))
        result = cur.fetchone()

    if not result:
        return None

    return {
        'user_id': result['user_id'],
        'email': result['email'],
        'display_name': result['display_name'],
        'role': result['role'],
        'tier': result['tier'],
        'email_verified': bool(result.get('email_verified')),
    }


def recover_session_by_device(device_id: str) -> dict:
    if not device_id:
        return None
    try:
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute('''
                SELECT ds.session_token
                FROM device_sessions ds
                JOIN sessions s ON ds.session_token = s.session_token
                WHERE ds.device_id = %s AND s.expires_at > NOW()
                ORDER BY ds.updated_at DESC LIMIT 1
            ''', (device_id,))
            row = cur.fetchone()
            if row:
                return validate_session(row['session_token'])
    except Exception:
        pass
    return None

def get_device_session_token(device_id: str) -> str:
    if not device_id:
        return None
    try:
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute('''
                SELECT ds.session_token
                FROM device_sessions ds
                JOIN sessions s ON ds.session_token = s.session_token
                WHERE ds.device_id = %s AND s.expires_at > NOW()
                ORDER BY ds.updated_at DESC LIMIT 1
            ''', (device_id,))
            row = cur.fetchone()
            return row['session_token'] if row else None
    except Exception:
        return None

def delete_session(token: str):
    with get_db() as (conn, cur):
        cur.execute('DELETE FROM sessions WHERE session_token = %s', (token,))
        cur.execute('DELETE FROM device_sessions WHERE session_token = %s', (token,))
        conn.commit()


def cleanup_expired_sessions():
    with get_db() as (conn, cur):
        cur.execute('DELETE FROM sessions WHERE expires_at < NOW()')
        deleted = cur.rowcount
        conn.commit()
    return deleted


def upgrade_user_tier(user_id: int, tier: str):
    with get_db() as (conn, cur):
        cur.execute('UPDATE users SET tier = %s WHERE id = %s', (tier, user_id))
        conn.commit()


def payment_already_processed(stripe_session_id: str) -> bool:
    with get_db() as (conn, cur):
        cur.execute(
            'SELECT id FROM payments WHERE stripe_session_id = %s AND status = %s',
            (stripe_session_id, 'completed'),
        )
        exists = cur.fetchone() is not None
    return exists


def record_payment(user_id: int, amount: int, stripe_session_id: str = None,
                   stripe_payment_intent: str = None, status: str = 'pending'):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            INSERT INTO payments (user_id, amount, stripe_session_id, stripe_payment_intent, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        ''', (user_id, amount, stripe_session_id, stripe_payment_intent, status))
        result = dict(cur.fetchone())
        conn.commit()
    return result


def update_payment_status(stripe_session_id: str, status: str):
    with get_db() as (conn, cur):
        cur.execute('''
            UPDATE payments SET status = %s WHERE stripe_session_id = %s
        ''', (status, stripe_session_id))
        conn.commit()


def get_user_by_id(user_id: int) -> dict:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT id, email, display_name, role, tier, created_at FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()
    return dict(user) if user else None


def get_all_users() -> list:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT id, email, display_name, role, tier, created_at FROM users ORDER BY created_at DESC')
        users = cur.fetchall()
    return [dict(u) for u in users]


def update_display_name(user_id: int, new_name: str):
    with get_db() as (conn, cur):
        cur.execute('UPDATE users SET display_name = %s WHERE id = %s', (new_name.strip(), user_id))
        conn.commit()


def invalidate_user_sessions(user_id: int, except_token: str = None):
    with get_db() as (conn, cur):
        if except_token:
            cur.execute('DELETE FROM sessions WHERE user_id = %s AND session_token != %s', (user_id, except_token))
        else:
            cur.execute('DELETE FROM sessions WHERE user_id = %s', (user_id,))
        conn.commit()


def update_password(user_id: int, current_password: str, new_password: str, except_token: str = None) -> dict:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT password_hash FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()

    if not user:
        return {'error': 'User not found'}
    if not verify_password(current_password, user['password_hash']):
        return {'error': 'Current password is incorrect'}

    with get_db() as (conn, cur):
        cur.execute('UPDATE users SET password_hash = %s WHERE id = %s', (hash_password(new_password), user_id))
        conn.commit()

    invalidate_user_sessions(user_id, except_token=except_token)
    return {'success': True}


def get_user_payments(user_id: int) -> list:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT amount, status, created_at FROM payments WHERE user_id = %s ORDER BY created_at DESC', (user_id,))
        payments = cur.fetchall()
    return [dict(p) for p in payments]


def reset_password_by_email(email: str, new_password: str) -> dict:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT id FROM users WHERE email = %s', (email.lower().strip(),))
        user = cur.fetchone()
        if not user:
            return {'error': 'No account found with this email'}
        cur.execute('UPDATE users SET password_hash = %s WHERE id = %s', (hash_password(new_password), user['id']))
        conn.commit()
    return {'success': True}


def send_password_reset_code(email: str) -> dict:
    email = email.lower().strip()
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT id, display_name FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        if not user:
            return {'success': True, 'user_id': None}
    rl = _check_and_increment_rate_limit('email_send', email, max_attempts=3, window_seconds=300)
    if not rl['allowed']:
        return {'success': True, 'user_id': None}
    with get_db(dict_cursor=True) as (conn, cur):
        code = generate_verification_code()
        expires = datetime.utcnow() + timedelta(minutes=30)
        cur.execute(
            'UPDATE users SET verification_code = %s, verification_code_expires = %s WHERE id = %s',
            (code, expires, user['id']),
        )
        conn.commit()
    return {'success': True, 'user_id': user['id'], 'code': code, 'display_name': user.get('display_name')}


def verify_reset_code_and_set_password(email: str, code: str, new_password: str) -> dict:
    email = email.lower().strip()
    rl = _check_and_increment_rate_limit('reset_verify', email)
    if not rl['allowed']:
        return {'error': 'Too many attempts. Please request a new code.'}

    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            'SELECT id, verification_code, verification_code_expires FROM users WHERE email = %s',
            (email,),
        )
        user = cur.fetchone()
        if not user:
            return {'error': 'No account found with this email.'}
        if not user['verification_code'] or user['verification_code'] != code.strip():
            return {'error': 'Invalid code. Please check and try again.'}
        if user['verification_code_expires'] and user['verification_code_expires'] < datetime.utcnow():
            return {'error': 'Code has expired. Please request a new one.'}
        cur.execute(
            'UPDATE users SET password_hash = %s, verification_code = NULL, verification_code_expires = NULL WHERE id = %s',
            (hash_password(new_password), user['id']),
        )
        conn.commit()
        user_id = user['id']

    invalidate_user_sessions(user_id)
    _clear_rate_limit('reset_verify', email)
    return {'success': True}


def is_admin(user: dict) -> bool:
    return user and user.get('role') == 'admin'


def has_glow(user: dict) -> bool:
    return user and user.get('tier') == 'glow'


def can_use_ai(user: dict) -> bool:
    return has_glow(user) or is_admin(user)


FREE_DISPUTE_ITEM_LIMIT = 2
FREE_PER_BUREAU_LIMIT = 2


def get_entitlements(user_id: int) -> dict:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT ai_rounds, letters, mailings, free_letters_used FROM entitlements WHERE user_id = %s', (user_id,))
        row = cur.fetchone()
    if row:
        return dict(row)
    return {'ai_rounds': 0, 'letters': 0, 'mailings': 0, 'free_letters_used': 0}


def get_free_items_remaining(user_id: int) -> int:
    ent = get_entitlements(user_id)
    return max(0, FREE_DISPUTE_ITEM_LIMIT - ent.get('free_letters_used', 0))


def has_used_free_letters(user_id: int) -> bool:
    ent = get_entitlements(user_id)
    return ent.get('free_letters_used', 0) > 0


def spend_free_letters(user_id: int, item_count: int, max_capacity: int = None) -> bool:
    cap = max_capacity if max_capacity is not None else FREE_DISPUTE_ITEM_LIMIT
    with get_db() as (conn, cur):
        cur.execute('''
            UPDATE entitlements
            SET free_letters_used = free_letters_used + %s, updated_at = NOW()
            WHERE user_id = %s AND free_letters_used + %s <= %s
        ''', (item_count, user_id, item_count, cap))
        if cur.rowcount == 0:
            cur.execute('''
                INSERT INTO entitlements (user_id, free_letters_used, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    free_letters_used = entitlements.free_letters_used + EXCLUDED.free_letters_used,
                    updated_at = NOW()
                WHERE entitlements.free_letters_used + EXCLUDED.free_letters_used <= %s
            ''', (user_id, item_count, cap))
            success = cur.rowcount > 0
        else:
            success = True
        conn.commit()
    return success


def add_entitlements(user_id: int, ai_rounds: int = 0, letters: int = 0, mailings: int = 0,
                     source: str = 'manual', stripe_session_id: str = None, note: str = None):
    with get_db() as (conn, cur):
        if stripe_session_id:
            lock_key = hash(stripe_session_id) & 0x7FFFFFFFFFFFFFFF
            cur.execute('SELECT pg_advisory_xact_lock(%s)', (lock_key,))
            cur.execute(
                'SELECT id FROM entitlement_transactions WHERE stripe_session_id = %s AND transaction_type = %s',
                (stripe_session_id, 'credit'),
            )
            if cur.fetchone() is not None:
                conn.commit()
                return
        cur.execute('''
            INSERT INTO entitlements (user_id, ai_rounds, letters, mailings, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                ai_rounds = entitlements.ai_rounds + EXCLUDED.ai_rounds,
                letters = entitlements.letters + EXCLUDED.letters,
                mailings = entitlements.mailings + EXCLUDED.mailings,
                updated_at = NOW()
        ''', (user_id, ai_rounds, letters, mailings))
        cur.execute('''
            INSERT INTO entitlement_transactions (user_id, transaction_type, source, ai_rounds, letters, mailings, stripe_session_id, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        ''', (user_id, 'credit', source, ai_rounds, letters, mailings, stripe_session_id, note))
        conn.commit()


def spend_entitlement(user_id: int, entitlement_type: str, amount: int = 1) -> bool:
    if entitlement_type not in ('ai_rounds', 'letters', 'mailings'):
        return False
    with get_db() as (conn, cur):
        cur.execute(f'''
            UPDATE entitlements
            SET {entitlement_type} = {entitlement_type} - %s, updated_at = NOW()
            WHERE user_id = %s AND {entitlement_type} >= %s
        ''', (amount, user_id, amount))
        success = cur.rowcount > 0
        if success:
            kwargs = {'ai_rounds': 0, 'letters': 0, 'mailings': 0}
            kwargs[entitlement_type] = amount
            cur.execute('''
                INSERT INTO entitlement_transactions (user_id, transaction_type, source, ai_rounds, letters, mailings, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (user_id, 'debit', 'usage', kwargs['ai_rounds'], kwargs['letters'], kwargs['mailings'],
                  f'Used {amount} {entitlement_type}'))
        conn.commit()
    return success


def has_entitlement(user_id: int, entitlement_type: str, amount: int = 1) -> bool:
    ent = get_entitlements(user_id)
    return ent.get(entitlement_type, 0) >= amount


TIER_HIERARCHY = {
    'free': 0,
    'digital_only': 1,
    'full_round': 2,
    'deletion_sprint': 3,
}

TIER_LABELS = {
    'free': 'Free',
    'digital_only': 'Digital Only',
    'full_round': 'Full Round',
    'deletion_sprint': 'Deletion Sprint',
}

def get_user_tier(user_id: int) -> str:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT source FROM entitlement_transactions
            WHERE user_id = %s AND transaction_type = 'credit'
            ORDER BY created_at DESC
        ''', (user_id,))
        txns = cur.fetchall()
    best_tier = 'free'
    best_rank = 0
    for t in txns:
        src = t.get('source', '')
        for pack_key in ('deletion_sprint', 'full_round', 'digital_only'):
            if pack_key in src:
                rank = TIER_HIERARCHY.get(pack_key, 0)
                if rank > best_rank:
                    best_tier = pack_key
                    best_rank = rank
                break
    if best_rank == 0:
        ent = get_entitlements(user_id)
        total_ever_credited = 0
        for t in txns:
            total_ever_credited += 1
        if total_ever_credited > 0:
            has_mailings = ent.get('mailings', 0) > 0 or any('mailing' in (t.get('source', '') or '') for t in txns)
            has_letters = ent.get('letters', 0) > 0 or any('letter' in (t.get('source', '') or '') for t in txns)
            has_ai = ent.get('ai_rounds', 0) > 0 or any('ai' in (t.get('source', '') or '') for t in txns)
            if has_mailings and has_letters and has_ai:
                best_tier = 'full_round'
            elif has_letters or has_ai:
                best_tier = 'digital_only'
    return best_tier


def get_entitlement_transactions(user_id: int, limit: int = 20) -> list:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT transaction_type, source, ai_rounds, letters, mailings, note, created_at
            FROM entitlement_transactions
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        ''', (user_id, limit))
        txns = cur.fetchall()
    return [dict(t) for t in txns]


def entitlement_purchase_processed(stripe_session_id: str) -> bool:
    with get_db() as (conn, cur):
        cur.execute(
            'SELECT id FROM entitlement_transactions WHERE stripe_session_id = %s AND transaction_type = %s',
            (stripe_session_id, 'credit'),
        )
        exists = cur.fetchone() is not None
    return exists


def generate_verification_code() -> str:
    return ''.join(random.choices(string.digits, k=6))


def set_verification_code(user_id: int) -> str:
    rl = _check_and_increment_rate_limit('email_send', f'user:{user_id}', max_attempts=3, window_seconds=300)
    if not rl['allowed']:
        return None
    code = generate_verification_code()
    expires = datetime.utcnow() + timedelta(minutes=30)
    with get_db() as (conn, cur):
        cur.execute(
            'UPDATE users SET verification_code = %s, verification_code_expires = %s WHERE id = %s',
            (code, expires, user_id),
        )
        conn.commit()
    return code


def verify_email_code(user_id: int, code: str) -> dict:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            'SELECT verification_code, verification_code_expires, email_verified FROM users WHERE id = %s',
            (user_id,),
        )
        user = cur.fetchone()
        if not user:
            return {'error': 'User not found'}

        if user['email_verified']:
            return {'success': True, 'already_verified': True}

        if not user['verification_code']:
            return {'error': 'No verification code found. Please request a new one.'}

        if user['verification_code_expires'] and user['verification_code_expires'] < datetime.utcnow():
            return {'error': 'Code expired. Please request a new one.'}

        if user['verification_code'] != code.strip():
            return {'error': 'Incorrect code. Please try again.'}

        cur.execute(
            'UPDATE users SET email_verified = TRUE, verification_code = NULL, verification_code_expires = NULL WHERE id = %s',
            (user_id,),
        )
        conn.commit()
    founder_granted = try_auto_grant_founder(user_id)
    return {'success': True, 'founder_granted': founder_granted}


def is_email_verified(user_id: int) -> bool:
    with get_db() as (conn, cur):
        cur.execute('SELECT email_verified FROM users WHERE id = %s', (user_id,))
        row = cur.fetchone()
    return bool(row and row[0])


def mark_email_verified(user_id: int):
    with get_db() as (conn, cur):
        cur.execute(
            'UPDATE users SET email_verified = TRUE, verification_code = NULL, verification_code_expires = NULL WHERE id = %s',
            (user_id,),
        )
        conn.commit()


FOUNDER_LIMIT = 100
FOUNDER_AI_ROUNDS = 9
FOUNDER_LETTERS = 9


def count_founders() -> int:
    with get_db() as (conn, cur):
        cur.execute("SELECT COUNT(*) FROM users WHERE is_founder = TRUE")
        row = cur.fetchone()
    return row[0] if row else 0


def founders_remaining() -> int:
    return max(0, FOUNDER_LIMIT - count_founders())


def is_user_founder(user_id: int) -> bool:
    with get_db() as (conn, cur):
        cur.execute("SELECT is_founder FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
    return bool(row and row[0])


def grant_founder_status(user_id: int) -> bool:
    with get_db() as (conn, cur):
        try:
            cur.execute("SAVEPOINT founder_grant")

            cur.execute(
                """
                UPDATE users SET is_founder = TRUE, founder_granted_at = NOW()
                WHERE id = %s AND is_founder = FALSE
                  AND (SELECT COUNT(*) FROM users WHERE is_founder = TRUE) < %s
                """,
                (user_id, FOUNDER_LIMIT),
            )
            if cur.rowcount == 0:
                cur.execute("ROLLBACK TO SAVEPOINT founder_grant")
                logger.info(f"Founder grant skipped for user {user_id}: already founder or limit reached")
                return False

            cur.execute('''
                INSERT INTO entitlements (user_id, ai_rounds, letters, mailings, updated_at)
                VALUES (%s, %s, %s, 0, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    ai_rounds = entitlements.ai_rounds + EXCLUDED.ai_rounds,
                    letters = entitlements.letters + EXCLUDED.letters,
                    updated_at = NOW()
            ''', (user_id, FOUNDER_AI_ROUNDS, FOUNDER_LETTERS))

            cur.execute('''
                INSERT INTO entitlement_transactions (user_id, transaction_type, source, ai_rounds, letters, mailings, note)
                VALUES (%s, %s, %s, %s, %s, 0, %s)
            ''', (user_id, 'credit', 'founder_grant', FOUNDER_AI_ROUNDS, FOUNDER_LETTERS,
                  'Founding Member — 9 AI rounds + 9 letters granted'))

            cur.execute("RELEASE SAVEPOINT founder_grant")
            conn.commit()
            logger.info(f"Founder status granted to user {user_id}: {FOUNDER_AI_ROUNDS} AI rounds + {FOUNDER_LETTERS} letters")
            return True
        except Exception as e:
            try:
                cur.execute("ROLLBACK TO SAVEPOINT founder_grant")
            except Exception:
                pass
            conn.rollback()
            logger.error(f"Founder grant failed for user {user_id}: {e}", exc_info=True)
            return False


def try_auto_grant_founder(user_id: int) -> bool:
    if is_user_founder(user_id):
        return False
    return grant_founder_status(user_id)


def transfer_rounds(from_user_id: int, to_email: str, ai_rounds: int = 0, letters: int = 0) -> dict:
    if ai_rounds <= 0 and letters <= 0:
        return {'error': 'Nothing to transfer'}
    if not is_user_founder(from_user_id):
        return {'error': 'Only Founding Members can transfer rounds'}
    with get_db(dict_cursor=True) as (conn, cur):
        try:
            cur.execute("SELECT id, display_name, email FROM users WHERE email = %s", (to_email.lower().strip(),))
            recipient = cur.fetchone()
            if not recipient:
                conn.rollback()
                return {'error': 'No account found with that email address'}
            to_user_id = recipient['id']
            recipient_name = recipient.get('display_name')
            recipient_email = recipient['email']
            if to_user_id == from_user_id:
                conn.rollback()
                return {'error': 'You cannot transfer rounds to yourself'}
            cur.execute("SELECT display_name FROM users WHERE id = %s", (from_user_id,))
            sender_row = cur.fetchone()
            sender_name = sender_row['display_name'] if sender_row else None
            if ai_rounds > 0:
                cur.execute(
                    "UPDATE entitlements SET ai_rounds = ai_rounds - %s, updated_at = NOW() WHERE user_id = %s AND ai_rounds >= %s",
                    (ai_rounds, from_user_id, ai_rounds),
                )
                if cur.rowcount == 0:
                    conn.rollback()
                    return {'error': 'Not enough AI rounds to transfer'}
            if letters > 0:
                cur.execute(
                    "UPDATE entitlements SET letters = letters - %s, updated_at = NOW() WHERE user_id = %s AND letters >= %s",
                    (letters, from_user_id, letters),
                )
                if cur.rowcount == 0:
                    conn.rollback()
                    return {'error': 'Not enough letters to transfer'}
            cur.execute('''
                INSERT INTO entitlements (user_id, ai_rounds, letters, mailings, updated_at)
                VALUES (%s, %s, %s, 0, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    ai_rounds = entitlements.ai_rounds + EXCLUDED.ai_rounds,
                    letters = entitlements.letters + EXCLUDED.letters,
                    updated_at = NOW()
            ''', (to_user_id, ai_rounds, letters))
            cur.execute('''
                INSERT INTO entitlement_transactions (user_id, transaction_type, source, ai_rounds, letters, mailings, note)
                VALUES (%s, %s, %s, %s, %s, 0, %s)
            ''', (from_user_id, 'debit', 'transfer_sent', ai_rounds, letters,
                  f'Transferred to user #{to_user_id}'))
            cur.execute('''
                INSERT INTO entitlement_transactions (user_id, transaction_type, source, ai_rounds, letters, mailings, note)
                VALUES (%s, %s, %s, %s, %s, 0, %s)
            ''', (to_user_id, 'credit', 'transfer_received', ai_rounds, letters,
                  f'Transferred from user #{from_user_id}'))
            cur.execute('''
                INSERT INTO round_transfers (from_user_id, to_user_id, ai_rounds, letters)
                VALUES (%s, %s, %s, %s)
            ''', (from_user_id, to_user_id, ai_rounds, letters))
            conn.commit()
        except Exception:
            conn.rollback()
            return {'error': 'Transfer failed. Please try again.'}
    try:
        from resend_client import send_transfer_notification_email
        send_transfer_notification_email(
            to_email=recipient_email,
            from_display_name=sender_name,
            ai_rounds=ai_rounds,
            letters=letters,
            recipient_name=recipient_name,
        )
    except Exception as _tn_err:
        logger.warning(f"Transfer notification email failed for {recipient_email}: {_tn_err}")
    return {'success': True, 'to_user_id': to_user_id}


def get_all_users_with_entitlements() -> list:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT u.id, u.email, u.display_name, u.role, u.tier, u.created_at, u.email_verified,
                   COALESCE(u.is_founder, FALSE) as is_founder,
                   COALESCE(e.ai_rounds, 0) as ai_rounds,
                   COALESCE(e.letters, 0) as letters,
                   COALESCE(e.mailings, 0) as mailings
            FROM users u
            LEFT JOIN entitlements e ON u.id = e.user_id
            ORDER BY u.created_at DESC
        ''')
        users = cur.fetchall()
    return [dict(u) for u in users]


def update_user_role(user_id: int, new_role: str) -> bool:
    if new_role not in ('consumer', 'admin'):
        return False
    with get_db() as (conn, cur):
        cur.execute('UPDATE users SET role = %s WHERE id = %s', (new_role, user_id))
        success = cur.rowcount > 0
        conn.commit()
    return success


def get_platform_stats() -> dict:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT COUNT(*) as total FROM users')
        total_users = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as total FROM users WHERE created_at > NOW() - INTERVAL '7 days'")
        new_users_7d = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as total FROM users WHERE role = 'admin'")
        admin_count = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as total FROM users WHERE email_verified = TRUE")
        verified_count = cur.fetchone()['total']
        cur.execute('SELECT COALESCE(SUM(ai_rounds), 0) as ai, COALESCE(SUM(letters), 0) as letters, COALESCE(SUM(mailings), 0) as mailings FROM entitlements')
        ent_totals = cur.fetchone()
        cur.execute("SELECT COUNT(*) as total FROM entitlement_transactions WHERE transaction_type = 'debit'")
        total_usage = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as total FROM entitlement_transactions WHERE transaction_type = 'credit' AND source = 'stripe'")
        total_purchases = cur.fetchone()['total']
    return {
        'total_users': total_users,
        'new_users_7d': new_users_7d,
        'admin_count': admin_count,
        'verified_count': verified_count,
        'total_ai_rounds': ent_totals['ai'],
        'total_letters': ent_totals['letters'],
        'total_mailings': ent_totals['mailings'],
        'total_usage_events': total_usage,
        'total_purchases': total_purchases,
    }
