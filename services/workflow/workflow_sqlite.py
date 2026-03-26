"""
SQLite file storage for workflow + Mission Control tables (local dev).

Schema mirrors workflow_schema.py / operations tables; JSON stored as TEXT.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from typing import Optional

from services.workflow.workflow_db_config import workflow_sqlite_path

_lock = threading.RLock()
sqlite_write_lock = _lock
_conn: Optional[sqlite3.Connection] = None


def _connect() -> sqlite3.Connection:
    path = workflow_sqlite_path()
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level="DEFERRED")
    conn.row_factory = sqlite3.Row
    return conn


def get_connection() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = _connect()
        return _conn


def ensure_schema() -> None:
    """CREATE IF NOT EXISTS all workflow / ops tables + stub users row."""
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        );
        INSERT OR IGNORE INTO users (id) VALUES (1);

        CREATE TABLE IF NOT EXISTS workflow_sessions (
            workflow_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            workflow_type TEXT NOT NULL DEFAULT 'dispute_linear_v1',
            current_step TEXT,
            overall_status TEXT NOT NULL DEFAULT 'active',
            started_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            completed_at TEXT,
            last_error_code TEXT,
            last_error_message_safe TEXT,
            metadata TEXT NOT NULL DEFAULT '{}',
            definition_version INTEGER NOT NULL DEFAULT 1,
            engine_version INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_workflow_sessions_user ON workflow_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_workflow_sessions_status ON workflow_sessions(overall_status);

        CREATE TABLE IF NOT EXISTS workflow_steps (
            workflow_step_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL REFERENCES workflow_sessions(workflow_id) ON DELETE CASCADE,
            step_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'not_started',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            failed_at TEXT,
            last_error_code TEXT,
            last_error_message_safe TEXT,
            completion_payload_summary TEXT,
            async_task_state TEXT,
            UNIQUE(workflow_id, step_id)
        );
        CREATE INDEX IF NOT EXISTS idx_workflow_steps_workflow ON workflow_steps(workflow_id);

        CREATE TABLE IF NOT EXISTS workflow_response_intake (
            response_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL REFERENCES workflow_sessions(workflow_id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            source_type TEXT NOT NULL DEFAULT 'unknown',
            response_channel TEXT NOT NULL DEFAULT 'upload',
            received_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            linked_mailing_id INTEGER,
            linked_letter_id INTEGER,
            storage_ref TEXT,
            parsed_summary TEXT NOT NULL DEFAULT '{}',
            classification_status TEXT NOT NULL DEFAULT 'pending',
            response_classification TEXT,
            classification_reasoning_safe TEXT,
            classification_confidence REAL,
            recommended_next_action TEXT,
            escalation_recommendation TEXT,
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
        );
        CREATE INDEX IF NOT EXISTS idx_wf_response_intake_workflow ON workflow_response_intake(workflow_id);

        CREATE TABLE IF NOT EXISTS workflow_reminders (
            reminder_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL REFERENCES workflow_sessions(workflow_id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reminder_type TEXT NOT NULL,
            reason TEXT,
            eligible_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            sent_at TEXT,
            status TEXT NOT NULL DEFAULT 'eligible',
            delivery_channel TEXT,
            payload_summary TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
        );
        CREATE INDEX IF NOT EXISTS idx_wf_reminders_workflow ON workflow_reminders(workflow_id);
        CREATE INDEX IF NOT EXISTS idx_wf_reminders_status ON workflow_reminders(status, eligible_at);

        CREATE TABLE IF NOT EXISTS workflow_admin_audit (
            audit_id TEXT PRIMARY KEY,
            workflow_id TEXT REFERENCES workflow_sessions(workflow_id) ON DELETE SET NULL,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            actor_source TEXT NOT NULL,
            action_type TEXT NOT NULL,
            reason_safe TEXT,
            payload_before TEXT,
            payload_after TEXT,
            reminder_id TEXT,
            response_id TEXT,
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
        );
        CREATE INDEX IF NOT EXISTS idx_wf_admin_audit_workflow ON workflow_admin_audit(workflow_id);
        """
    )
    conn.commit()
    cur.close()
