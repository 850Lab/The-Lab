"""
database.py | 850 Lab Parser Machine
Minimal persistence layer for reports, violations, and letters
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from datetime import datetime
import json

import logging

_logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL')

_pool = None
_pool_lock = __import__('threading').Lock()

def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        try:
            _pool = ThreadedConnectionPool(
                minconn=1, maxconn=10, dsn=DATABASE_URL,
                keepalives=1, keepalives_idle=30,
                keepalives_interval=10, keepalives_count=3,
                connect_timeout=5,
                options='-c statement_timeout=30000',
            )
            _logger.info("Database pool created successfully")
        except Exception as e:
            _logger.error(f"DB pool creation failed: {e}")
            raise
    return _pool

def _get_pool_with_retry(max_retries=5):
    global _pool
    if _pool is not None:
        return _pool
    for attempt in range(max_retries):
        try:
            return _get_pool()
        except Exception as e:
            if attempt < max_retries - 1:
                import time
                wait = min(2 ** attempt, 5)
                _logger.warning(f"DB pool retry {attempt+1}/{max_retries}: {e}. Waiting {wait}s...")
                time.sleep(wait)
            else:
                _logger.error(f"DB pool creation failed after {max_retries} attempts")
                raise
    return _pool

def _check_conn(pool, conn):
    if conn.closed:
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
        return pool.getconn()
    try:
        conn.autocommit = True
        with conn.cursor() as c:
            c.execute('SELECT 1')
        conn.autocommit = False
        return conn
    except (psycopg2.InterfaceError, psycopg2.OperationalError):
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
        return pool.getconn()

def _reset_pool():
    global _pool
    try:
        if _pool:
            _pool.closeall()
    except Exception:
        pass
    _pool = None

@contextmanager
def get_db(dict_cursor=False):
    pool = _get_pool()
    conn = None
    try:
        conn = pool.getconn()
        conn = _check_conn(pool, conn)
        cur = conn.cursor(cursor_factory=RealDictCursor) if dict_cursor else conn.cursor()
        try:
            yield (conn, cur)
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                cur.close()
            except Exception:
                pass
    except (psycopg2.InterfaceError, psycopg2.OperationalError):
        _reset_pool()
        pool2 = _get_pool()
        conn2 = pool2.getconn()
        cur2 = conn2.cursor(cursor_factory=RealDictCursor) if dict_cursor else conn2.cursor()
        try:
            yield (conn2, cur2)
        except Exception:
            try:
                conn2.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                cur2.close()
            except Exception:
                pass
            try:
                pool2.putconn(conn2)
            except Exception:
                pass
        return
    finally:
        if conn is not None:
            try:
                pool.putconn(conn)
            except Exception:
                pass

def init_database():
    """Create tables if they don't exist, and migrate schema if needed"""
    import time as _time
    for _attempt in range(3):
        try:
            return _init_database_inner()
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            _logger.warning(f"init_database attempt {_attempt+1}/3 failed: {e}")
            _reset_pool()
            if _attempt < 2:
                _time.sleep(1)
            else:
                raise

def _init_database_inner():
    from services.workflow.workflow_db_config import should_use_workflow_sqlite

    if should_use_workflow_sqlite():
        from services.workflow import workflow_sqlite

        workflow_sqlite.ensure_schema()
        return

    pool = _get_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'users'")
        if cur.fetchone():
            cur.close()
            try:
                from workflow_schema import (
                    ensure_operations_tables,
                    ensure_response_intake_tables,
                    ensure_workflow_tables,
                )

                ensure_workflow_tables(conn)
                ensure_response_intake_tables(conn)
                ensure_operations_tables(conn)
                conn.commit()
            except Exception as _wf_e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                _logger.warning("workflow schema ensure failed (non-fatal): %s", _wf_e)
            pool.putconn(conn)
            return
        cur.close()
        return _init_database_ddl(pool, conn)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
        raise

def _init_database_ddl(pool, conn):
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            bureau VARCHAR(50),
            file_name VARCHAR(255),
            parsed_data JSONB,
            full_text TEXT
        )
    ''')

    cur.execute('''
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'reports' AND column_name = 'user_id'
    ''')
    if not cur.fetchone():
        cur.execute('ALTER TABLE reports ADD COLUMN user_id INTEGER')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id)')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS violations (
            id SERIAL PRIMARY KEY,
            report_id INTEGER REFERENCES reports(id) ON DELETE CASCADE,
            violation_type VARCHAR(100),
            fcra_section VARCHAR(50),
            triggering_data JSONB,
            explanation TEXT,
            consumer_confirmed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'letters' AND column_name = 'violation_id'
    ''')
    old_schema = cur.fetchone()
    
    if old_schema:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS letters_new (
                id SERIAL PRIMARY KEY,
                report_id INTEGER REFERENCES reports(id) ON DELETE CASCADE,
                bureau VARCHAR(50),
                letter_text TEXT,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cur.execute('''
            INSERT INTO letters_new (report_id, bureau, letter_text, metadata, created_at)
            SELECT v.report_id, r.bureau, 
                   string_agg(l.letter_text, E'\n\n---\n\n' ORDER BY l.created_at),
                   jsonb_build_object('violation_count', COUNT(*), 'categories', '[]'::jsonb),
                   MAX(l.created_at)
            FROM letters l
            JOIN violations v ON l.violation_id = v.id
            JOIN reports r ON v.report_id = r.id
            WHERE v.report_id IS NOT NULL
            GROUP BY v.report_id, r.bureau
        ''')
        
        cur.execute('DROP TABLE letters CASCADE')
        cur.execute('ALTER TABLE letters_new RENAME TO letters')
    else:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS letters (
                id SERIAL PRIMARY KEY,
                report_id INTEGER REFERENCES reports(id) ON DELETE CASCADE,
                bureau VARCHAR(50),
                letter_text TEXT,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS analytics_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            session_id VARCHAR(100),
            event_type VARCHAR(50) NOT NULL,
            page VARCHAR(100),
            detail VARCHAR(255),
            duration_ms INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_analytics_user ON analytics_events(user_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_analytics_created ON analytics_events(created_at)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_analytics_page ON analytics_events(page)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS lob_sends (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            report_id INTEGER,
            bureau VARCHAR(50) NOT NULL,
            lob_id VARCHAR(100),
            tracking_number VARCHAR(100),
            status VARCHAR(50) DEFAULT 'pending',
            from_address JSONB DEFAULT '{}',
            to_address JSONB DEFAULT '{}',
            cost_cents INTEGER DEFAULT 0,
            return_receipt BOOLEAN DEFAULT TRUE,
            is_test BOOLEAN DEFAULT FALSE,
            expected_delivery VARCHAR(50),
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_lob_sends_user ON lob_sends(user_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_lob_sends_bureau ON lob_sends(bureau)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS entitlements (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE UNIQUE,
            ai_rounds INTEGER DEFAULT 0,
            letters INTEGER DEFAULT 0,
            mailings INTEGER DEFAULT 0,
            free_letters_used INTEGER DEFAULT 0 NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_entitlements_user ON entitlements(user_id)')
    try:
        cur.execute('ALTER TABLE entitlements ADD COLUMN IF NOT EXISTS free_letters_used INTEGER DEFAULT 0 NOT NULL')
    except Exception:
        pass

    cur.execute('''
        CREATE TABLE IF NOT EXISTS entitlement_transactions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            transaction_type VARCHAR(20) NOT NULL,
            source VARCHAR(50) NOT NULL,
            ai_rounds INTEGER DEFAULT 0,
            letters INTEGER DEFAULT 0,
            mailings INTEGER DEFAULT 0,
            stripe_session_id VARCHAR(255),
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_ent_tx_user ON entitlement_transactions(user_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_ent_tx_stripe ON entitlement_transactions(stripe_session_id)')
    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_ent_tx_stripe_unique ON entitlement_transactions(stripe_session_id) WHERE stripe_session_id IS NOT NULL')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS rate_limits (
            id SERIAL PRIMARY KEY,
            action VARCHAR(50) NOT NULL,
            identifier VARCHAR(255) NOT NULL,
            attempt_count INTEGER DEFAULT 1,
            window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(action, identifier)
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_rate_limits_action_id ON rate_limits(action, identifier)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS drip_emails (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            email_type VARCHAR(50) NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, email_type)
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_drip_emails_user ON drip_emails(user_id)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS referral_codes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE UNIQUE,
            code VARCHAR(20) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_referral_codes_code ON referral_codes(code)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id SERIAL PRIMARY KEY,
            referrer_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            referee_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            referral_code VARCHAR(20) NOT NULL,
            status VARCHAR(20) DEFAULT 'signed_up',
            rewarded_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(referee_id)
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS dispute_tracker (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            round_number INTEGER NOT NULL DEFAULT 1,
            mailed_at TIMESTAMP,
            mailed_method VARCHAR(50) DEFAULT 'manual',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, round_number)
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_dispute_tracker_user ON dispute_tracker(user_id)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS proof_uploads (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            round_number INTEGER NOT NULL DEFAULT 1,
            bureau VARCHAR(50),
            file_name VARCHAR(255),
            file_type VARCHAR(50),
            notes TEXT,
            file_data BYTEA,
            doc_type VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_proof_uploads_user ON proof_uploads(user_id)')
    try:
        cur.execute('ALTER TABLE proof_uploads ADD COLUMN IF NOT EXISTS file_data BYTEA')
        cur.execute('ALTER TABLE proof_uploads ADD COLUMN IF NOT EXISTS doc_type VARCHAR(50)')
    except Exception:
        pass

    cur.execute('''
        CREATE TABLE IF NOT EXISTS mail_approvals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            approved_by VARCHAR(100) NOT NULL DEFAULT 'admin',
            reason VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_ui_state (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            ui_card VARCHAR(50) NOT NULL DEFAULT 'UPLOAD',
            active_panel VARCHAR(50),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS checklist_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            round_number INTEGER NOT NULL DEFAULT 1,
            item_key VARCHAR(100) NOT NULL,
            completed BOOLEAN DEFAULT FALSE,
            completed_at TIMESTAMP,
            UNIQUE(user_id, round_number, item_key)
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_checklist_user ON checklist_items(user_id)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_activity (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            action VARCHAR(50) NOT NULL,
            detail VARCHAR(255),
            current_card VARCHAR(30),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_user_activity_user ON user_activity(user_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_user_activity_created ON user_activity(created_at DESC)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS sprint_guarantee (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            rounds_completed INTEGER NOT NULL DEFAULT 0,
            round1_change_detected BOOLEAN DEFAULT FALSE,
            round2_change_detected BOOLEAN DEFAULT FALSE,
            free_round_available BOOLEAN DEFAULT FALSE,
            free_round_used BOOLEAN DEFAULT FALSE,
            stripe_session_id VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id)
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sprint_guarantee_user ON sprint_guarantee(user_id)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS sprint_leads (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            phone VARCHAR(50),
            goal TEXT,
            timeline VARCHAR(100),
            preferred_contact VARCHAR(20) DEFAULT 'text',
            best_time VARCHAR(50) DEFAULT 'anytime',
            contacted BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sprint_leads_created ON sprint_leads(created_at DESC)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS round_transfers (
            id SERIAL PRIMARY KEY,
            from_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            ai_rounds INTEGER DEFAULT 0,
            letters INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_round_transfers_from ON round_transfers(from_user_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_round_transfers_to ON round_transfers(to_user_id)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS voice_profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE UNIQUE,
            tone VARCHAR(50) DEFAULT 'Calm & Professional',
            detail_level VARCHAR(50) DEFAULT 'Standard',
            reading_level VARCHAR(50) DEFAULT 'Standard',
            closing VARCHAR(50) DEFAULT 'Sincerely,',
            preferred_phrases JSONB DEFAULT '{}',
            punctuation_style VARCHAR(50) DEFAULT 'Standard',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_voice_profiles_user ON voice_profiles(user_id)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS missions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            goal VARCHAR(100) NOT NULL,
            timeline VARCHAR(100) NOT NULL,
            status VARCHAR(20) DEFAULT 'active',
            risk_level VARCHAR(20),
            primary_lever VARCHAR(30),
            strike_metrics_snapshot JSONB DEFAULT '{}',
            war_plan_snapshot JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            archived_at TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_missions_user ON missions(user_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(user_id, status)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS nudge_log (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            nudge_id VARCHAR(100) NOT NULL,
            severity VARCHAR(20),
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_nudge_log_user ON nudge_log(user_id)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS upload_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            token VARCHAR(64) NOT NULL UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_upload_tokens_token ON upload_tokens(token)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_upload_tokens_user ON upload_tokens(user_id)')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_signatures (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE UNIQUE,
            signature_data BYTEA NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_user_signatures_user ON user_signatures(user_id)')

    try:
        from workflow_schema import (
            ensure_operations_tables,
            ensure_response_intake_tables,
            ensure_workflow_tables,
        )

        ensure_workflow_tables(conn)
        ensure_response_intake_tables(conn)
        ensure_operations_tables(conn)
    except Exception as _wf_e:
        _logger.warning(
            "workflow schema ensure after full DDL failed (non-fatal): %s", _wf_e
        )

    conn.commit()
    cur.close()
    pool.putconn(conn)

def save_report(bureau, file_name, parsed_data, full_text=None, user_id=None):
    """Save a parsed report. Raw full_text is never persisted — only structured
    parsed_data is stored. This is intentional: credit reports contain SSNs,
    full account numbers, and other PII that should not sit in the database."""
    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO reports (bureau, file_name, parsed_data, full_text, user_id)
            VALUES (%s, %s, %s, NULL, %s)
            RETURNING id
        ''', (bureau, file_name, json.dumps(parsed_data), user_id))
        
        result = cur.fetchone()
        report_id = result[0] if result else None
        conn.commit()
    
    return report_id

def get_report(report_id, user_id=None):
    """Get a report by ID, optionally verifying ownership"""
    with get_db(dict_cursor=True) as (conn, cur):
        if user_id:
            cur.execute('SELECT * FROM reports WHERE id = %s AND user_id = %s', (report_id, user_id))
        else:
            cur.execute('SELECT * FROM reports WHERE id = %s', (report_id,))
        report = cur.fetchone()
    
    return dict(report) if report else None

def get_all_reports(user_id=None):
    """Get all reports, optionally filtered by user_id"""
    with get_db(dict_cursor=True) as (conn, cur):
        if user_id:
            cur.execute('SELECT id, upload_date, bureau, file_name FROM reports WHERE user_id = %s ORDER BY upload_date DESC', (user_id,))
        else:
            cur.execute('SELECT id, upload_date, bureau, file_name FROM reports ORDER BY upload_date DESC')
        reports = cur.fetchall()
    
    return [dict(r) for r in reports]


def get_recent_reports_with_parsed_for_user(user_id: int, limit: int = 25):
    """
    Latest reports for a user including parsed_data (for React intake / analyze UI).
    parsed_data is returned as a dict (JSON decoded if needed).
    """
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, upload_date, bureau, file_name, parsed_data
            FROM reports
            WHERE user_id = %s
            ORDER BY upload_date DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        pd = d.get("parsed_data")
        if isinstance(pd, str):
            try:
                d["parsed_data"] = json.loads(pd)
            except Exception:
                d["parsed_data"] = {}
        elif pd is None:
            d["parsed_data"] = {}
        out.append(d)
    return out

def save_violation(report_id, violation_type, fcra_section, triggering_data, explanation):
    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO violations (report_id, violation_type, fcra_section, triggering_data, explanation)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        ''', (report_id, violation_type, fcra_section, json.dumps(triggering_data), explanation))
        result = cur.fetchone()
        violation_id = result[0] if result else None
        conn.commit()
    return violation_id


def get_violations_for_report(report_id):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT * FROM violations
            WHERE report_id = %s
            ORDER BY created_at
        ''', (report_id,))
        violations = cur.fetchall()
    return [dict(v) for v in violations]


def confirm_violation(violation_id, confirmed=True):
    with get_db() as (conn, cur):
        cur.execute('''
            UPDATE violations
            SET consumer_confirmed = %s
            WHERE id = %s
        ''', (confirmed, violation_id))
        conn.commit()


def get_confirmed_violations_for_report(report_id):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT * FROM violations
            WHERE report_id = %s AND consumer_confirmed = TRUE
            ORDER BY created_at
        ''', (report_id,))
        violations = cur.fetchall()
    return [dict(v) for v in violations]


def save_letter(report_id, letter_text, bureau, violation_count=0, categories=None, user_id=None):
    """Save a generated letter for a report and bureau, verifying ownership"""
    with get_db() as (conn, cur):
        if user_id:
            cur.execute('SELECT id FROM reports WHERE id = %s AND user_id = %s', (report_id, user_id))
            if not cur.fetchone():
                return None
            cur.execute('''
                DELETE FROM letters WHERE report_id = %s AND bureau = %s
                AND report_id IN (SELECT id FROM reports WHERE user_id = %s)
            ''', (report_id, bureau, user_id))
        else:
            cur.execute('DELETE FROM letters WHERE report_id = %s AND bureau = %s', (report_id, bureau))
        
        metadata = json.dumps({
            'violation_count': violation_count,
            'categories': categories or []
        })
        
        cur.execute('''
            INSERT INTO letters (report_id, bureau, letter_text, metadata)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        ''', (report_id, bureau, letter_text, metadata))
        
        result = cur.fetchone()
        letter_id = result[0] if result else None
        conn.commit()
    
    return letter_id


def get_letters_for_report(report_id, user_id=None):
    with get_db(dict_cursor=True) as (conn, cur):
        if user_id:
            cur.execute('''
                SELECT l.* FROM letters l
                JOIN reports r ON l.report_id = r.id
                WHERE l.report_id = %s AND r.user_id = %s
                ORDER BY l.created_at
            ''', (report_id, user_id))
        else:
            cur.execute('SELECT * FROM letters WHERE report_id = %s ORDER BY created_at', (report_id,))
        letters = cur.fetchall()
    return [dict(letter) for letter in letters]


def get_latest_letters_for_user(user_id):
    try:
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute('''
                SELECT l.* FROM letters l
                JOIN reports r ON l.report_id = r.id
                WHERE r.user_id = %s
                ORDER BY l.created_at DESC
            ''', (user_id,))
            rows = cur.fetchall()
            seen = {}
            for row in rows:
                bureau = (row.get('bureau') or '').lower()
                if bureau and bureau not in seen:
                    seen[bureau] = dict(row)
            return seen
    except Exception:
        return {}


def get_all_letters_for_user(user_id):
    try:
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute('''
                SELECT l.id, l.report_id, l.bureau, l.letter_text, l.metadata, l.created_at
                FROM letters l
                JOIN reports r ON l.report_id = r.id
                WHERE r.user_id = %s
                ORDER BY l.created_at DESC
            ''', (user_id,))
            rows = [dict(row) for row in cur.fetchall()]
            for row in rows:
                if 'round_number' not in row:
                    row['round_number'] = 1
            return rows
    except Exception:
        return []


def get_letter_by_bureau(report_id, bureau, user_id=None):
    with get_db(dict_cursor=True) as (conn, cur):
        if user_id:
            cur.execute('''
                SELECT l.* FROM letters l
                JOIN reports r ON l.report_id = r.id
                WHERE l.report_id = %s AND l.bureau = %s AND r.user_id = %s
            ''', (report_id, bureau, user_id))
        else:
            cur.execute('SELECT * FROM letters WHERE report_id = %s AND bureau = %s', (report_id, bureau))
        letter = cur.fetchone()
    return dict(letter) if letter else None


def log_analytics_event(user_id, session_id, event_type, page, detail=None, duration_ms=0):
    try:
        with get_db() as (conn, cur):
            cur.execute('''
                INSERT INTO analytics_events (user_id, session_id, event_type, page, detail, duration_ms)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (user_id, session_id, event_type, page, detail, duration_ms))
            conn.commit()
    except Exception:
        pass

def get_analytics_summary(days=30):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT page, COUNT(*) as views, COUNT(DISTINCT user_id) as unique_users,
                   AVG(duration_ms) as avg_duration_ms
            FROM analytics_events
            WHERE event_type = 'page_view' AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY page ORDER BY views DESC
        ''', (days,))
        page_views = [dict(r) for r in cur.fetchall()]

        cur.execute('''
            SELECT page, event_type, COUNT(*) as count
            FROM analytics_events
            WHERE created_at > NOW() - INTERVAL '%s days'
            GROUP BY page, event_type ORDER BY count DESC
        ''', (days,))
        event_breakdown = [dict(r) for r in cur.fetchall()]

        cur.execute('''
            SELECT DATE(created_at) as day, COUNT(DISTINCT user_id) as active_users,
                   COUNT(*) as total_events
            FROM analytics_events
            WHERE created_at > NOW() - INTERVAL '%s days'
            GROUP BY DATE(created_at) ORDER BY day DESC
        ''', (days,))
        daily_activity = [dict(r) for r in cur.fetchall()]

        cur.execute('''
            SELECT u.email, u.display_name, u.tier, 
                   COUNT(ae.id) as event_count,
                   MAX(ae.created_at) as last_active
            FROM analytics_events ae
            JOIN users u ON ae.user_id = u.id
            WHERE ae.created_at > NOW() - INTERVAL '%s days'
            GROUP BY u.id, u.email, u.display_name, u.tier
            ORDER BY event_count DESC LIMIT 20
        ''', (days,))
        top_users = [dict(r) for r in cur.fetchall()]

        cur.execute('''
            SELECT 
                SUM(CASE WHEN page = 'UPLOAD' THEN 1 ELSE 0 END) as upload,
                SUM(CASE WHEN page = 'SUMMARY' THEN 1 ELSE 0 END) as summary,
                SUM(CASE WHEN page = 'DISPUTES' THEN 1 ELSE 0 END) as disputes,
                SUM(CASE WHEN page = 'DONE' THEN 1 ELSE 0 END) as done
            FROM analytics_events
            WHERE event_type = 'page_view' AND created_at > NOW() - INTERVAL '%s days'
        ''', (days,))
        funnel = dict(cur.fetchone() or {})

        signup_stats = {}
        upload_stats = {}
        purchase_stats = {}
        referral_stats = {}
        try:
            cur.execute('''
                SELECT COUNT(*) as total_signups,
                       COUNT(*) FILTER (WHERE email_verified = TRUE) as verified,
                       COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '%s days') as recent_signups
                FROM users WHERE role = 'consumer'
            ''', (days,))
            signup_stats = dict(cur.fetchone() or {})
        except Exception:
            conn.rollback()
        try:
            cur.execute('''
                SELECT COUNT(DISTINCT user_id) as uploaders
                FROM reports WHERE upload_date > NOW() - INTERVAL '%s days'
            ''', (days,))
            upload_stats = dict(cur.fetchone() or {})
        except Exception:
            conn.rollback()
        try:
            cur.execute('''
                SELECT COUNT(*) as total_purchases, COALESCE(SUM(amount), 0) as total_revenue
                FROM payments WHERE status = 'completed' AND created_at > NOW() - INTERVAL '%s days'
            ''', (days,))
            purchase_stats = dict(cur.fetchone() or {})
        except Exception:
            conn.rollback()
        try:
            cur.execute('''
                SELECT COUNT(*) as total_referrals,
                       COUNT(*) FILTER (WHERE status = 'rewarded') as rewarded
                FROM referrals WHERE created_at > NOW() - INTERVAL '%s days'
            ''', (days,))
            referral_stats = dict(cur.fetchone() or {})
        except Exception:
            conn.rollback()

    return {
        'page_views': page_views,
        'event_breakdown': event_breakdown,
        'daily_activity': daily_activity,
        'top_users': top_users,
        'funnel': funnel,
        'signup_stats': signup_stats,
        'upload_stats': upload_stats,
        'purchase_stats': purchase_stats,
        'referral_stats': referral_stats,
    }

def save_lob_send(user_id, report_id, bureau, lob_id, tracking_number, status,
                  from_address, to_address, cost_cents, return_receipt, is_test,
                  expected_delivery=None, error_message=None, workflow_id=None):
    try:
        with get_db() as (conn, cur):
            cur.execute('''
                INSERT INTO lob_sends (user_id, report_id, bureau, lob_id, tracking_number,
                    status, from_address, to_address, cost_cents, return_receipt, is_test,
                    expected_delivery, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (user_id, report_id, bureau, lob_id, tracking_number, status,
                  json.dumps(from_address), json.dumps(to_address), cost_cents,
                  return_receipt, is_test, expected_delivery, error_message))
            result = cur.fetchone()
            conn.commit()
            send_id = result[0] if result else None
        if send_id and status == 'mailed' and user_id:
            try:
                from services.workflow import hooks as workflow_hooks

                workflow_hooks.notify_certified_mail_sent(
                    int(user_id),
                    str(bureau or ''),
                    str(tracking_number or ''),
                    lob_id=str(lob_id or ''),
                    report_id=int(report_id) if report_id is not None else None,
                    workflow_id=str(workflow_id).strip() if workflow_id else None,
                )
            except Exception:
                pass
        return send_id
    except Exception:
        return None


def get_lob_sends_for_user(user_id):
    try:
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute('''
                SELECT * FROM lob_sends WHERE user_id = %s ORDER BY created_at DESC
            ''', (user_id,))
            rows = [dict(r) for r in cur.fetchall()]
            return rows
    except Exception:
        return []


def has_been_sent_via_lob(user_id, bureau, report_id=None):
    try:
        with get_db() as (conn, cur):
            if report_id:
                cur.execute('''
                    SELECT COUNT(*) FROM lob_sends
                    WHERE user_id = %s AND bureau = %s AND report_id = %s AND status = 'mailed'
                ''', (user_id, bureau, report_id))
            else:
                cur.execute('''
                    SELECT COUNT(*) FROM lob_sends
                    WHERE user_id = %s AND bureau = %s AND status = 'mailed'
                ''', (user_id, bureau))
            count = cur.fetchone()[0]
            return count > 0
    except Exception:
        return False


def delete_user_reports(user_id):
    """Delete all reports, violations, and letters for a specific user"""
    with get_db() as (conn, cur):
        cur.execute('SELECT id FROM reports WHERE user_id = %s', (user_id,))
        report_ids = [r[0] for r in cur.fetchall()]
        if report_ids:
            placeholders = ','.join(['%s'] * len(report_ids))
            cur.execute(f'DELETE FROM lob_sends WHERE report_id IN ({placeholders})', report_ids)
            cur.execute(f'DELETE FROM letters WHERE report_id IN ({placeholders})', report_ids)
            cur.execute(f'DELETE FROM violations WHERE report_id IN ({placeholders})', report_ids)
            cur.execute(f'DELETE FROM reports WHERE id IN ({placeholders})', report_ids)
        conn.commit()


def save_dispute_tracker(user_id, round_number, mailed_at, mailed_method='manual', notes=None):
    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO dispute_tracker (user_id, round_number, mailed_at, mailed_method, notes)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, round_number) DO UPDATE SET
                mailed_at = EXCLUDED.mailed_at,
                mailed_method = EXCLUDED.mailed_method,
                notes = EXCLUDED.notes
        ''', (user_id, round_number, mailed_at, mailed_method, notes))
        conn.commit()


def get_dispute_tracker(user_id, round_number=None):
    with get_db(dict_cursor=True) as (conn, cur):
        if round_number:
            cur.execute('SELECT * FROM dispute_tracker WHERE user_id = %s AND round_number = %s', (user_id, round_number))
            row = cur.fetchone()
            return dict(row) if row else None
        else:
            cur.execute('SELECT * FROM dispute_tracker WHERE user_id = %s ORDER BY round_number DESC', (user_id,))
            return [dict(r) for r in cur.fetchall()]


def save_proof_upload(
    user_id,
    round_number,
    bureau,
    file_name,
    file_type,
    notes=None,
    file_data=None,
    doc_type=None,
    workflow_id=None,
):
    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO proof_uploads (user_id, round_number, bureau, file_name, file_type, notes, file_data, doc_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (user_id, round_number, bureau, file_name, file_type, notes,
              psycopg2.Binary(file_data) if file_data else None, doc_type))
        result = cur.fetchone()
        conn.commit()
        proof_id = result[0] if result else None
        if proof_id and user_id:
            try:
                from services.workflow import hooks as workflow_hooks

                workflow_hooks.maybe_notify_proof_attachment_completed(
                    int(user_id), workflow_id=workflow_id
                )
            except Exception:
                pass
        return proof_id


def is_mail_approved(user_id):
    try:
        with get_db() as (conn, cur):
            cur.execute(
                "SELECT 1 FROM mail_approvals WHERE user_id = %s", (user_id,)
            )
            return cur.fetchone() is not None
    except Exception:
        return False


def approve_mail_for_user(user_id, approved_by="admin", reason=None):
    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO mail_approvals (user_id, approved_by, reason)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                approved_by = EXCLUDED.approved_by,
                reason = EXCLUDED.reason,
                created_at = CURRENT_TIMESTAMP
        ''', (user_id, approved_by, reason))
        conn.commit()
        return True


def revoke_mail_approval(user_id):
    with get_db() as (conn, cur):
        cur.execute("DELETE FROM mail_approvals WHERE user_id = %s", (user_id,))
        deleted = cur.rowcount
        conn.commit()
        return deleted > 0


def reassign_orphaned_proof_uploads(proof_ids, target_user_id):
    if not proof_ids:
        return 0
    deduped = list(dict.fromkeys(proof_ids))
    with get_db() as (conn, cur):
        placeholders = ','.join(['%s'] * len(deduped))
        cur.execute(f'''
            UPDATE proof_uploads
            SET user_id = %s
            WHERE id IN ({placeholders}) AND user_id IS NULL
        ''', (target_user_id, *deduped))
        updated = cur.rowcount
        conn.commit()
        return updated


def get_proof_docs_for_user(user_id, doc_types=None):
    with get_db(dict_cursor=True) as (conn, cur):
        if doc_types:
            placeholders = ','.join(['%s'] * len(doc_types))
            cur.execute(f'''
                SELECT id, user_id, file_name, file_type, doc_type, created_at
                FROM proof_uploads
                WHERE user_id = %s AND doc_type IN ({placeholders})
                ORDER BY created_at DESC
            ''', [user_id] + list(doc_types))
        else:
            cur.execute('''
                SELECT id, user_id, file_name, file_type, doc_type, created_at
                FROM proof_uploads
                WHERE user_id = %s AND doc_type IS NOT NULL
                ORDER BY created_at DESC
            ''', (user_id,))
        return [dict(r) for r in cur.fetchall()]


def has_proof_docs(user_id):
    with get_db() as (conn, cur):
        cur.execute('''
            SELECT
                COUNT(*) FILTER (WHERE doc_type = 'government_id') as id_count,
                COUNT(*) FILTER (WHERE doc_type = 'address_proof') as addr_count
            FROM proof_uploads
            WHERE user_id = %s AND doc_type IN ('government_id', 'address_proof') AND file_data IS NOT NULL
        ''', (user_id,))
        row = cur.fetchone()
        return {'has_id': row[0] > 0, 'has_address': row[1] > 0, 'both': row[0] > 0 and row[1] > 0}


def get_proof_doc_file(proof_id, user_id):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT file_data, file_name, file_type FROM proof_uploads
            WHERE id = %s AND user_id = %s AND file_data IS NOT NULL
        ''', (proof_id, user_id))
        row = cur.fetchone()
        return dict(row) if row else None


def update_lob_send_status(lob_send_id, status, tracking_events=None):
    try:
        with get_db() as (conn, cur):
            cur.execute('''
                UPDATE lob_sends SET status = %s WHERE id = %s
            ''', (status, lob_send_id))
            conn.commit()
            return True
    except Exception:
        return False


def get_pending_lob_sends():
    try:
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute('''
                SELECT id, lob_id, status, user_id, bureau
                FROM lob_sends
                WHERE lob_id IS NOT NULL AND lob_id != ''
                AND status NOT IN ('delivered', 'returned_to_sender', 'error')
                ORDER BY created_at DESC
                LIMIT 50
            ''')
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def get_proof_uploads(user_id, round_number=None):
    with get_db(dict_cursor=True) as (conn, cur):
        if round_number:
            cur.execute('SELECT * FROM proof_uploads WHERE user_id = %s AND round_number = %s ORDER BY created_at DESC', (user_id, round_number))
        else:
            cur.execute('SELECT * FROM proof_uploads WHERE user_id = %s ORDER BY created_at DESC', (user_id,))
        return [dict(r) for r in cur.fetchall()]


def delete_proof_upload(proof_id, user_id):
    with get_db() as (conn, cur):
        cur.execute('DELETE FROM proof_uploads WHERE id = %s AND user_id = %s', (proof_id, user_id))
        conn.commit()
        return cur.rowcount > 0


def toggle_checklist_item(user_id, round_number, item_key, completed):
    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO checklist_items (user_id, round_number, item_key, completed, completed_at)
            VALUES (%s, %s, %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END)
            ON CONFLICT (user_id, round_number, item_key) DO UPDATE SET
                completed = EXCLUDED.completed,
                completed_at = CASE WHEN EXCLUDED.completed THEN NOW() ELSE NULL END
        ''', (user_id, round_number, item_key, completed, completed))
        conn.commit()


def get_checklist_items(user_id, round_number):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT item_key, completed FROM checklist_items WHERE user_id = %s AND round_number = %s', (user_id, round_number))
        return {row['item_key']: row['completed'] for row in cur.fetchall()}


def log_activity(user_id, action, detail=None, current_card=None):
    try:
        with get_db() as (conn, cur):
            cur.execute('''
                INSERT INTO user_activity (user_id, action, detail, current_card)
                VALUES (%s, %s, %s, %s)
            ''', (user_id, action, detail[:255] if detail and len(detail) > 255 else detail, current_card))
            conn.commit()
    except Exception:
        pass


def get_active_users(minutes=30):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT ua.user_id,
                   u.email,
                   u.display_name,
                   ua.action AS last_action,
                   ua.detail AS last_detail,
                   ua.current_card,
                   ua.created_at AS last_seen,
                   EXTRACT(EPOCH FROM (NOW() - ua.created_at)) AS idle_seconds
            FROM user_activity ua
            JOIN users u ON u.id = ua.user_id
            WHERE ua.created_at > NOW() - make_interval(mins => %s)
              AND ua.id = (
                  SELECT MAX(ua2.id) FROM user_activity ua2
                  WHERE ua2.user_id = ua.user_id
              )
            ORDER BY ua.created_at DESC
        ''', (minutes,))
        return [dict(r) for r in cur.fetchall()]


def get_recent_activity(limit=50):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT ua.user_id, u.email, u.display_name,
                   ua.action, ua.detail, ua.current_card, ua.created_at
            FROM user_activity ua
            JOIN users u ON u.id = ua.user_id
            ORDER BY ua.created_at DESC
            LIMIT %s
        ''', (limit,))
        return [dict(r) for r in cur.fetchall()]


def get_activity_stats():
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT
                COUNT(DISTINCT CASE WHEN created_at > NOW() - INTERVAL '5 minutes' THEN user_id END) AS active_now,
                COUNT(DISTINCT CASE WHEN created_at > NOW() - INTERVAL '30 minutes' AND created_at <= NOW() - INTERVAL '5 minutes' THEN user_id END) AS idle,
                COUNT(DISTINCT CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN user_id END) AS active_today
            FROM user_activity
        ''')
        row = cur.fetchone()
        return dict(row) if row else {'active_now': 0, 'idle': 0, 'active_today': 0}


def cleanup_old_activity(days=7):
    try:
        with get_db() as (conn, cur):
            cur.execute('DELETE FROM user_activity WHERE created_at < NOW() - make_interval(days => %s)', (days,))
            conn.commit()
    except Exception:
        pass


def get_funnel_analytics(days=30):
    with get_db(dict_cursor=True) as (conn, cur):
        interval = f'{days} days'

        cur.execute("SELECT COUNT(*) as n FROM users WHERE role = 'consumer'")
        total_signups = cur.fetchone()['n']

        cur.execute("SELECT COUNT(*) as n FROM users WHERE role = 'consumer' AND email_verified = TRUE")
        total_verified = cur.fetchone()['n']

        cur.execute("SELECT COUNT(DISTINCT user_id) as n FROM reports")
        total_uploaders = cur.fetchone()['n']

        cur.execute("""
            SELECT COUNT(DISTINCT user_id) as n
            FROM entitlement_transactions
            WHERE transaction_type = 'credit' AND source LIKE 'stripe%%'
        """)
        total_buyers = cur.fetchone()['n']

        cur.execute("""
            SELECT COUNT(DISTINCT user_id) as n
            FROM lob_sends WHERE status != 'error'
        """)
        total_mailers = cur.fetchone()['n']

        cur.execute(f"""
            SELECT COUNT(*) as n FROM users
            WHERE role = 'consumer' AND created_at > NOW() - INTERVAL '{interval}'
        """)
        period_signups = cur.fetchone()['n']

        cur.execute(f"""
            SELECT COUNT(DISTINCT u.id) as n FROM users u
            JOIN analytics_events ae ON ae.user_id = u.id
            WHERE u.role = 'consumer' AND u.email_verified = TRUE
              AND ae.created_at > NOW() - INTERVAL '{interval}'
        """)
        try:
            period_verified = cur.fetchone()['n']
        except Exception:
            conn.rollback()
            period_verified = 0

        try:
            cur.execute(f"""
                SELECT COUNT(DISTINCT r.user_id) as n FROM reports r
                WHERE r.upload_date > NOW() - INTERVAL '{interval}'
            """)
            period_uploaders = cur.fetchone()['n']
        except Exception:
            conn.rollback()
            period_uploaders = 0

        cur.execute(f"""
            SELECT COUNT(DISTINCT user_id) as n
            FROM payments WHERE status = 'completed'
              AND created_at > NOW() - INTERVAL '{interval}'
        """)
        period_buyers = cur.fetchone()['n']

        cur.execute("""
            SELECT user_id, COUNT(*) as purchase_count,
                   COALESCE(SUM(amount), 0) as total_spent
            FROM payments WHERE status = 'completed'
            GROUP BY user_id
        """)
        buyer_rows = [dict(r) for r in cur.fetchall()]
        repeat_buyers = sum(1 for b in buyer_rows if b['purchase_count'] >= 2)
        total_revenue_cents = sum(b['total_spent'] for b in buyer_rows)

        cur.execute(f"""
            SELECT COALESCE(SUM(amount), 0) as rev
            FROM payments WHERE status = 'completed'
              AND created_at > NOW() - INTERVAL '{interval}'
        """)
        period_revenue_cents = cur.fetchone()['rev']

        cur.execute("""
            SELECT et.source, COUNT(*) as cnt,
                   COALESCE(SUM(p.amount), 0) as tier_rev
            FROM entitlement_transactions et
            LEFT JOIN payments p ON p.user_id = et.user_id
              AND p.stripe_session_id = et.stripe_session_id
              AND p.status = 'completed'
            WHERE et.transaction_type = 'credit' AND et.source LIKE 'stripe%%'
            GROUP BY et.source
        """)
        source_rows = [dict(r) for r in cur.fetchall()]
        tier_purchases = {'digital_only': 0, 'full_round': 0, 'deletion_sprint': 0}
        tier_revenue = {'digital_only': 0, 'full_round': 0, 'deletion_sprint': 0}
        for s in source_rows:
            src = s.get('source', '')
            for tier_key in ('deletion_sprint', 'full_round', 'digital_only'):
                if tier_key in src:
                    tier_purchases[tier_key] += s['cnt']
                    tier_revenue[tier_key] += s.get('tier_rev', 0)
                    break

        cur.execute("""
            SELECT u.id, u.tier,
                   (SELECT COUNT(*) FROM entitlement_transactions et
                    WHERE et.user_id = u.id AND et.transaction_type = 'credit'
                      AND et.source LIKE 'stripe%%') as purchase_count
            FROM users u WHERE u.role = 'consumer'
        """)
        user_tiers = [dict(r) for r in cur.fetchall()]
        tier_dist = {'free': 0, 'digital_only': 0, 'full_round': 0, 'deletion_sprint': 0}
        for ut in user_tiers:
            t = ut.get('tier', 'free') or 'free'
            if t in tier_dist:
                tier_dist[t] += 1
            else:
                tier_dist['free'] += 1

        upgraders = 0
        cur.execute("""
            SELECT user_id FROM entitlement_transactions
            WHERE transaction_type = 'credit' AND source LIKE 'stripe%%'
            GROUP BY user_id
            HAVING COUNT(DISTINCT source) >= 2
        """)
        upgraders = len(cur.fetchall())

        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as rev, COUNT(*) as cnt
            FROM payments WHERE status = 'completed'
        """)
        rev_row = cur.fetchone()
        total_revenue_all = rev_row['rev']
        total_txn_count = rev_row['cnt']

        cur.execute(f"""
            SELECT DATE(created_at) as day,
                   COALESCE(SUM(amount), 0) as daily_rev,
                   COUNT(*) as daily_txns
            FROM payments WHERE status = 'completed'
              AND created_at > NOW() - INTERVAL '{interval}'
            GROUP BY DATE(created_at) ORDER BY day
        """)
        daily_revenue = [dict(r) for r in cur.fetchall()]

        arpu = round(total_revenue_all / len(buyer_rows) / 100, 2) if buyer_rows else 0

    return {
        'click_to_close': {
            'all_time': {
                'signups': total_signups,
                'verified': total_verified,
                'uploaded': total_uploaders,
                'purchased': total_buyers,
                'mailed': total_mailers,
            },
            'period': {
                'signups': period_signups,
                'verified': period_verified,
                'uploaded': period_uploaders,
                'purchased': period_buyers,
            },
        },
        'close_to_resell': {
            'first_time_buyers': len(buyer_rows),
            'repeat_buyers': repeat_buyers,
            'upgraders': upgraders,
            'tier_purchases': tier_purchases,
            'tier_revenue': tier_revenue,
        },
        'revenue': {
            'total_cents': total_revenue_all,
            'period_cents': period_revenue_cents,
            'arpu': arpu,
            'total_transactions': total_txn_count,
            'daily': daily_revenue,
        },
        'tier_distribution': tier_dist,
    }


def create_sprint_guarantee(user_id, stripe_session_id=None):
    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO sprint_guarantee (user_id, stripe_session_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                rounds_completed = 0,
                round1_change_detected = FALSE,
                round2_change_detected = FALSE,
                free_round_available = FALSE,
                free_round_used = FALSE,
                stripe_session_id = EXCLUDED.stripe_session_id,
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, stripe_session_id))
        conn.commit()


def get_sprint_guarantee(user_id):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT * FROM sprint_guarantee WHERE user_id = %s', (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_sprint_round(user_id, round_number, change_detected):
    with get_db() as (conn, cur):
        if round_number == 1:
            cur.execute('''
                UPDATE sprint_guarantee
                SET rounds_completed = GREATEST(rounds_completed, 1),
                    round1_change_detected = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            ''', (change_detected, user_id))
        elif round_number == 2:
            cur.execute('''
                UPDATE sprint_guarantee
                SET rounds_completed = GREATEST(rounds_completed, 2),
                    round2_change_detected = %s,
                    free_round_available = CASE
                        WHEN round1_change_detected = FALSE AND %s = FALSE THEN TRUE
                        ELSE FALSE
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            ''', (change_detected, change_detected, user_id))
        conn.commit()


def check_free_round_eligible(user_id):
    g = get_sprint_guarantee(user_id)
    if not g:
        return False
    return (
        g.get('rounds_completed', 0) >= 2
        and not g.get('round1_change_detected', True)
        and not g.get('round2_change_detected', True)
        and g.get('free_round_available', False)
        and not g.get('free_round_used', False)
    )


def use_free_round(user_id):
    with get_db() as (conn, cur):
        cur.execute('''
            UPDATE sprint_guarantee
            SET free_round_used = TRUE, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND free_round_available = TRUE AND free_round_used = FALSE
            RETURNING id
        ''', (user_id,))
        result = cur.fetchone()
        conn.commit()
        return result is not None


def get_founder_health_metrics():
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute("SELECT COUNT(*) as total FROM users WHERE is_founder = TRUE")
        total_founders = cur.fetchone()['total']

        cur.execute("""
            SELECT COUNT(DISTINCT u.id) as active
            FROM users u
            JOIN user_activity ua ON u.id = ua.user_id
            WHERE u.is_founder = TRUE
            AND ua.created_at > NOW() - INTERVAL '30 days'
        """)
        active_founders_30d = cur.fetchone()['active']

        cur.execute("""
            SELECT COUNT(DISTINCT u.id) as uploaded
            FROM users u
            JOIN reports r ON u.id = r.user_id
            WHERE u.is_founder = TRUE
        """)
        founders_uploaded = cur.fetchone()['uploaded']

        cur.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN et.transaction_type = 'debit' AND et.source LIKE 'usage%%' THEN et.ai_rounds ELSE 0 END), 0) as ai_used,
                COALESCE(SUM(CASE WHEN et.transaction_type = 'debit' AND et.source LIKE 'usage%%' THEN et.letters ELSE 0 END), 0) as letters_used
            FROM entitlement_transactions et
            JOIN users u ON et.user_id = u.id
            WHERE u.is_founder = TRUE
        """)
        usage = cur.fetchone()
        ai_rounds_used = usage['ai_used']
        letters_used = usage['letters_used']

        cur.execute("""
            SELECT COUNT(*) as total_transfers,
                   COALESCE(SUM(ai_rounds), 0) as ai_transferred,
                   COALESCE(SUM(letters), 0) as letters_transferred
            FROM round_transfers rt
            JOIN users u ON rt.from_user_id = u.id
            WHERE u.is_founder = TRUE
        """)
        transfers = cur.fetchone()

        cur.execute("""
            SELECT COUNT(DISTINCT u.id) as converted
            FROM users u
            JOIN entitlement_transactions et ON u.id = et.user_id
            WHERE u.is_founder = TRUE
            AND et.source LIKE 'stripe:%%'
        """)
        founder_to_paid = cur.fetchone()['converted']

        cur.execute("""
            SELECT COUNT(*) as recent
            FROM round_transfers rt
            JOIN users u ON rt.from_user_id = u.id
            WHERE u.is_founder = TRUE
            AND rt.created_at > NOW() - INTERVAL '7 days'
        """)
        transfers_7d = cur.fetchone()['recent']

        return {
            'total_founders': total_founders,
            'spots_remaining': max(0, 100 - total_founders),
            'active_founders_30d': active_founders_30d,
            'founders_uploaded': founders_uploaded,
            'ai_rounds_used': ai_rounds_used,
            'letters_used': letters_used,
            'total_transfers': transfers['total_transfers'],
            'ai_transferred': transfers['ai_transferred'],
            'letters_transferred': transfers['letters_transferred'],
            'transfers_7d': transfers_7d,
            'founder_to_paid': founder_to_paid,
        }


def get_signup_sources(days=30):
    with get_db(dict_cursor=True) as (conn, cur):
        interval = f'{days} days' if days else None
        date_filter = f"AND created_at > NOW() - INTERVAL '{interval}'" if interval else ""

        cur.execute(f"""
            SELECT COALESCE(utm_source, 'direct') as source,
                   COUNT(*) as signups,
                   SUM(CASE WHEN email_verified THEN 1 ELSE 0 END) as verified,
                   SUM(CASE WHEN is_founder THEN 1 ELSE 0 END) as founders
            FROM users WHERE role = 'consumer' {date_filter}
            GROUP BY COALESCE(utm_source, 'direct')
            ORDER BY signups DESC
        """)
        by_source = [dict(r) for r in cur.fetchall()]

        cur.execute(f"""
            SELECT COALESCE(utm_medium, 'none') as medium,
                   COUNT(*) as signups
            FROM users WHERE role = 'consumer' {date_filter}
            GROUP BY COALESCE(utm_medium, 'none')
            ORDER BY signups DESC
        """)
        by_medium = [dict(r) for r in cur.fetchall()]

        cur.execute(f"""
            SELECT COALESCE(utm_campaign, 'none') as campaign,
                   COUNT(*) as signups
            FROM users WHERE role = 'consumer' {date_filter}
            GROUP BY COALESCE(utm_campaign, 'none')
            ORDER BY signups DESC
        """)
        by_campaign = [dict(r) for r in cur.fetchall()]

        cur.execute(f"""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN utm_source IS NOT NULL THEN 1 ELSE 0 END) as tracked,
                   SUM(CASE WHEN utm_source IS NULL THEN 1 ELSE 0 END) as direct
            FROM users WHERE role = 'consumer' {date_filter}
        """)
        summary = dict(cur.fetchone())

        cur.execute(f"""
            SELECT DATE(created_at) as day,
                   COALESCE(utm_source, 'direct') as source,
                   COUNT(*) as signups
            FROM users WHERE role = 'consumer' {date_filter}
            GROUP BY DATE(created_at), COALESCE(utm_source, 'direct')
            ORDER BY day DESC
            LIMIT 200
        """)
        daily = [dict(r) for r in cur.fetchall()]

        return {
            'by_source': by_source,
            'by_medium': by_medium,
            'by_campaign': by_campaign,
            'summary': summary,
            'daily': daily,
        }


def get_total_user_count():
    with get_db() as (conn, cur):
        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'consumer'")
        return cur.fetchone()[0]


def insert_sprint_lead(name, email, phone, goal, timeline, preferred_contact, best_time):
    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO sprint_leads (name, email, phone, goal, timeline, preferred_contact, best_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (name, email, phone, goal, timeline, preferred_contact, best_time))
        result = cur.fetchone()
        conn.commit()
        return result[0] if result else None


def get_sprint_leads(limit=50):
    with get_db() as (conn, cur):
        cur.execute('''
            SELECT id, name, email, phone, goal, timeline, preferred_contact, best_time, contacted, created_at
            FROM sprint_leads
            ORDER BY created_at DESC
            LIMIT %s
        ''', (limit,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def mark_sprint_lead_contacted(lead_id):
    with get_db() as (conn, cur):
        cur.execute('''
            UPDATE sprint_leads SET contacted = TRUE WHERE id = %s
        ''', (lead_id,))
        conn.commit()


def log_round_transfer(from_user_id, to_user_id, ai_rounds, letters):
    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO round_transfers (from_user_id, to_user_id, ai_rounds, letters)
            VALUES (%s, %s, %s, %s)
        ''', (from_user_id, to_user_id, ai_rounds, letters))
        conn.commit()


def get_round_transfers(user_id, direction='both', limit=20):
    with get_db(dict_cursor=True) as (conn, cur):
        if direction == 'sent':
            cur.execute('''
                SELECT rt.*, u.email as recipient_email, u.display_name as recipient_name
                FROM round_transfers rt
                JOIN users u ON rt.to_user_id = u.id
                WHERE rt.from_user_id = %s
                ORDER BY rt.created_at DESC LIMIT %s
            ''', (user_id, limit))
        elif direction == 'received':
            cur.execute('''
                SELECT rt.*, u.email as sender_email, u.display_name as sender_name
                FROM round_transfers rt
                JOIN users u ON rt.from_user_id = u.id
                WHERE rt.to_user_id = %s
                ORDER BY rt.created_at DESC LIMIT %s
            ''', (user_id, limit))
        else:
            cur.execute('''
                SELECT rt.*,
                    CASE WHEN rt.from_user_id = %s THEN 'sent' ELSE 'received' END as direction,
                    u_from.email as from_email, u_to.email as to_email
                FROM round_transfers rt
                JOIN users u_from ON rt.from_user_id = u_from.id
                JOIN users u_to ON rt.to_user_id = u_to.id
                WHERE rt.from_user_id = %s OR rt.to_user_id = %s
                ORDER BY rt.created_at DESC LIMIT %s
            ''', (user_id, user_id, user_id, limit))
        return [dict(r) for r in cur.fetchall()]


VOICE_PROFILE_DEFAULTS = {
    'tone': 'Calm & Professional',
    'detail_level': 'Standard',
    'reading_level': 'Standard',
    'closing': 'Sincerely,',
    'preferred_phrases': {
        'dispute': 'I dispute the accuracy of…',
        'request': 'Please investigate and correct or delete…',
        'verify': 'Provide the method of verification…',
    },
    'punctuation_style': 'Standard',
}


def load_voice_profile(user_id):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('SELECT * FROM voice_profiles WHERE user_id = %s', (user_id,))
        row = cur.fetchone()
        if row:
            result = dict(row)
            if isinstance(result.get('preferred_phrases'), str):
                import json
                try:
                    result['preferred_phrases'] = json.loads(result['preferred_phrases'])
                except Exception:
                    result['preferred_phrases'] = dict(VOICE_PROFILE_DEFAULTS['preferred_phrases'])
            return result
        return None


def save_voice_profile(user_id, profile_dict):
    import json
    phrases = profile_dict.get('preferred_phrases', VOICE_PROFILE_DEFAULTS['preferred_phrases'])
    if isinstance(phrases, dict):
        phrases_json = json.dumps(phrases)
    else:
        phrases_json = phrases

    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO voice_profiles (user_id, tone, detail_level, reading_level, closing, preferred_phrases, punctuation_style, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id)
            DO UPDATE SET
                tone = EXCLUDED.tone,
                detail_level = EXCLUDED.detail_level,
                reading_level = EXCLUDED.reading_level,
                closing = EXCLUDED.closing,
                preferred_phrases = EXCLUDED.preferred_phrases,
                punctuation_style = EXCLUDED.punctuation_style,
                updated_at = CURRENT_TIMESTAMP
        ''', (
            user_id,
            profile_dict.get('tone', VOICE_PROFILE_DEFAULTS['tone']),
            profile_dict.get('detail_level', VOICE_PROFILE_DEFAULTS['detail_level']),
            profile_dict.get('reading_level', VOICE_PROFILE_DEFAULTS['reading_level']),
            profile_dict.get('closing', VOICE_PROFILE_DEFAULTS['closing']),
            phrases_json,
            profile_dict.get('punctuation_style', VOICE_PROFILE_DEFAULTS['punctuation_style']),
        ))
        conn.commit()


def get_effective_voice_profile(user_id):
    profile = load_voice_profile(user_id)
    if profile:
        result = dict(VOICE_PROFILE_DEFAULTS)
        for key in ('tone', 'detail_level', 'reading_level', 'closing', 'preferred_phrases', 'punctuation_style'):
            if profile.get(key):
                result[key] = profile[key]
        return result
    return dict(VOICE_PROFILE_DEFAULTS)


def create_mission(user_id, goal, timeline):
    with get_db() as (conn, cur):
        cur.execute('''
            UPDATE missions SET status = 'archived', archived_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND status = 'active'
        ''', (user_id,))
        cur.execute('''
            INSERT INTO missions (user_id, goal, timeline, status)
            VALUES (%s, %s, %s, 'active')
            RETURNING id
        ''', (user_id, goal, timeline))
        result = cur.fetchone()
        conn.commit()
    return result[0] if result else None


def get_active_mission(user_id):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT * FROM missions WHERE user_id = %s AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def update_mission_snapshots(user_id, risk_level=None, primary_lever=None,
                              strike_metrics_snapshot=None, war_plan_snapshot=None):
    with get_db() as (conn, cur):
        updates = []
        params = []
        if risk_level is not None:
            updates.append("risk_level = %s")
            params.append(risk_level)
        if primary_lever is not None:
            updates.append("primary_lever = %s")
            params.append(primary_lever)
        if strike_metrics_snapshot is not None:
            updates.append("strike_metrics_snapshot = %s")
            params.append(json.dumps(strike_metrics_snapshot))
        if war_plan_snapshot is not None:
            updates.append("war_plan_snapshot = %s")
            params.append(json.dumps(war_plan_snapshot))
        if not updates:
            return
        params.append(user_id)
        cur.execute(f'''
            UPDATE missions SET {", ".join(updates)}
            WHERE user_id = %s AND status = 'active'
        ''', params)
        conn.commit()


def archive_mission(user_id, mission_id=None):
    with get_db() as (conn, cur):
        if mission_id:
            cur.execute('''
                UPDATE missions SET status = 'archived', archived_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
            ''', (mission_id, user_id))
        else:
            cur.execute('''
                UPDATE missions SET status = 'archived', archived_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND status = 'active'
            ''', (user_id,))
        conn.commit()


def get_mission_history(user_id, limit=10):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT * FROM missions WHERE user_id = %s
            ORDER BY created_at DESC LIMIT %s
        ''', (user_id, limit))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def log_nudge(user_id, nudge_id, severity, message):
    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO nudge_log (user_id, nudge_id, severity, message)
            VALUES (%s, %s, %s, %s)
        ''', (user_id, nudge_id, severity, message))
        conn.commit()


def log_nudge_if_not_cooldown(user_id, nudge_id, severity, message, cooldown_days=1):
    try:
        with get_db(dict_cursor=True) as (conn, cur):
            cur.execute('''
                SELECT created_at FROM nudge_log
                WHERE user_id = %s AND nudge_id = %s
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id, nudge_id))
            last = cur.fetchone()
            if last:
                from datetime import datetime, timedelta
                last_at = last['created_at']
                if isinstance(last_at, str):
                    last_at = datetime.fromisoformat(last_at)
                if datetime.now() - last_at < timedelta(days=cooldown_days):
                    return False
            cur.execute('''
                INSERT INTO nudge_log (user_id, nudge_id, severity, message)
                VALUES (%s, %s, %s, %s)
            ''', (user_id, nudge_id, severity, message))
            conn.commit()
            return True
    except Exception:
        return False


def get_nudge_history(user_id, limit=20):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT * FROM nudge_log WHERE user_id = %s
            ORDER BY created_at DESC LIMIT %s
        ''', (user_id, limit))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_user_detail_for_admin(user_id):
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT u.id, u.email, u.display_name, u.role, u.created_at, u.email_verified,
                   e.ai_rounds, e.letters, e.mailings
            FROM users u
            LEFT JOIN entitlements e ON e.user_id = u.id
            WHERE u.id = %s
        ''', (user_id,))
        user = cur.fetchone()
        if not user:
            return None
        user = dict(user)

        cur.execute('''
            SELECT * FROM missions WHERE user_id = %s AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id,))
        mission = cur.fetchone()
        user['active_mission'] = dict(mission) if mission else None

        cur.execute('''
            SELECT * FROM missions WHERE user_id = %s
            ORDER BY created_at DESC LIMIT 10
        ''', (user_id,))
        user['mission_history'] = [dict(r) for r in cur.fetchall()]

        cur.execute('''
            SELECT * FROM voice_profiles WHERE user_id = %s
        ''', (user_id,))
        vp = cur.fetchone()
        user['voice_profile'] = dict(vp) if vp else None

        cur.execute('''
            SELECT * FROM nudge_log WHERE user_id = %s
            ORDER BY created_at DESC LIMIT 10
        ''', (user_id,))
        user['nudge_history'] = [dict(r) for r in cur.fetchall()]

        cur.execute('''
            SELECT * FROM dispute_tracker WHERE user_id = %s
            ORDER BY round_number DESC LIMIT 1
        ''', (user_id,))
        tracker = cur.fetchone()
        user['tracker'] = dict(tracker) if tracker else None

        cur.execute('''
            SELECT * FROM lob_sends WHERE user_id = %s
            ORDER BY created_at DESC LIMIT 5
        ''', (user_id,))
        user['lob_sends'] = [dict(r) for r in cur.fetchall()]

        cur.execute('''
            SELECT * FROM reports WHERE user_id = %s
            ORDER BY upload_date DESC LIMIT 1
        ''', (user_id,))
        report = cur.fetchone()
        user['latest_report'] = dict(report) if report else None

    return user


def save_user_ui_state(user_id, card, panel=None):
    try:
        with get_connection() as (conn, cur):
            cur.execute('''
                INSERT INTO user_ui_state (user_id, ui_card, active_panel, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET ui_card = EXCLUDED.ui_card,
                    active_panel = COALESCE(EXCLUDED.active_panel, user_ui_state.active_panel),
                    updated_at = NOW()
            ''', (user_id, card, panel))
            conn.commit()
    except Exception:
        pass


def get_user_ui_state(user_id):
    try:
        with get_connection(dict_cursor=True) as (conn, cur):
            cur.execute('''
                SELECT ui_card, active_panel FROM user_ui_state
                WHERE user_id = %s
            ''', (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def create_upload_token(user_id, expiry_days=7):
    import secrets
    from datetime import timedelta
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=expiry_days)
    try:
        with get_db() as (conn, cur):
            cur.execute('''
                INSERT INTO upload_tokens (user_id, token, expires_at)
                VALUES (%s, %s, %s)
                RETURNING token
            ''', (user_id, token, expires_at))
            conn.commit()
            return token
    except Exception:
        return None


def get_active_upload_token(user_id):
    try:
        with get_connection(dict_cursor=True) as (conn, cur):
            cur.execute('''
                SELECT token, expires_at FROM upload_tokens
                WHERE user_id = %s AND expires_at > NOW()
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id,))
            row = cur.fetchone()
            return row['token'] if row else None
    except Exception:
        return None


def validate_upload_token(token):
    try:
        with get_connection(dict_cursor=True) as (conn, cur):
            cur.execute('''
                SELECT user_id, expires_at FROM upload_tokens
                WHERE token = %s AND expires_at > NOW()
            ''', (token,))
            row = cur.fetchone()
            return row['user_id'] if row else None
    except Exception:
        return None


def mark_upload_token_used(token):
    try:
        with get_db() as (conn, cur):
            cur.execute('''
                UPDATE upload_tokens SET used_at = NOW()
                WHERE token = %s
            ''', (token,))
            conn.commit()
    except Exception:
        pass


def get_or_create_upload_token(user_id, expiry_days=7):
    existing = get_active_upload_token(user_id)
    if existing:
        return existing
    return create_upload_token(user_id, expiry_days)


def save_user_signature(user_id, signature_bytes, workflow_id=None):
    with get_db() as (conn, cur):
        cur.execute('''
            INSERT INTO user_signatures (user_id, signature_data, created_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET signature_data = EXCLUDED.signature_data,
                          created_at = NOW()
        ''', (user_id, psycopg2.Binary(signature_bytes)))
        conn.commit()
    try:
        from services.workflow import hooks as workflow_hooks

        workflow_hooks.maybe_notify_proof_attachment_completed(
            int(user_id), workflow_id=workflow_id
        )
    except Exception:
        pass


def get_user_signature(user_id):
    with get_db() as (conn, cur):
        cur.execute('''
            SELECT signature_data FROM user_signatures
            WHERE user_id = %s
        ''', (user_id,))
        row = cur.fetchone()
        if row:
            data = row[0]
            return bytes(data) if data else None
        return None
