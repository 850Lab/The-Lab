"""
PostgreSQL DDL for authoritative workflow sessions and per-step state.

Called from database.init path so existing deployments pick up tables.
"""

from __future__ import annotations


def ensure_workflow_tables(conn) -> None:
    """CREATE IF NOT EXISTS workflow_sessions + workflow_steps. Commits via caller."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_sessions (
            workflow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            workflow_type VARCHAR(80) NOT NULL DEFAULT 'dispute_linear_v1',
            current_step VARCHAR(64),
            overall_status VARCHAR(32) NOT NULL DEFAULT 'active',
            started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            last_error_code VARCHAR(64),
            last_error_message_safe TEXT,
            metadata JSONB NOT NULL DEFAULT '{}',
            definition_version INTEGER NOT NULL DEFAULT 1,
            engine_version INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflow_sessions_user ON workflow_sessions(user_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflow_sessions_user_type ON workflow_sessions(user_id, workflow_type)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflow_sessions_status ON workflow_sessions(overall_status)"
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_steps (
            workflow_step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id UUID NOT NULL REFERENCES workflow_sessions(workflow_id) ON DELETE CASCADE,
            step_id VARCHAR(64) NOT NULL,
            status VARCHAR(24) NOT NULL DEFAULT 'not_started',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            failed_at TIMESTAMP,
            last_error_code VARCHAR(64),
            last_error_message_safe TEXT,
            completion_payload_summary JSONB,
            async_task_state JSONB,
            UNIQUE(workflow_id, step_id)
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflow_steps_workflow ON workflow_steps(workflow_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflow_steps_status ON workflow_steps(workflow_id, status)"
    )

    cur.close()


def ensure_response_intake_tables(conn) -> None:
    """
    Persistent bureau/furnisher response records + classification outputs.
    linked_mailing_id is an application-level reference to lob_sends.id (no FK:
    workflow DDL may run before lob_sends on some init paths).
    """
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_response_intake (
            response_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id UUID NOT NULL REFERENCES workflow_sessions(workflow_id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            source_type VARCHAR(40) NOT NULL DEFAULT 'unknown',
            response_channel VARCHAR(40) NOT NULL DEFAULT 'upload',
            received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            linked_mailing_id INTEGER,
            linked_letter_id INTEGER,
            storage_ref TEXT,
            parsed_summary JSONB NOT NULL DEFAULT '{}',
            classification_status VARCHAR(32) NOT NULL DEFAULT 'pending',
            response_classification VARCHAR(64),
            classification_reasoning_safe TEXT,
            classification_confidence REAL,
            recommended_next_action VARCHAR(64),
            escalation_recommendation JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wf_response_intake_workflow ON workflow_response_intake(workflow_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wf_response_intake_user ON workflow_response_intake(user_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wf_response_intake_received ON workflow_response_intake(workflow_id, received_at DESC)"
    )
    cur.close()


def ensure_operations_tables(conn) -> None:
    """Reminders execution records + admin override audit (Phase 3A)."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_reminders (
            reminder_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id UUID NOT NULL REFERENCES workflow_sessions(workflow_id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reminder_type VARCHAR(64) NOT NULL,
            reason TEXT,
            eligible_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            sent_at TIMESTAMP,
            status VARCHAR(24) NOT NULL DEFAULT 'eligible',
            delivery_channel VARCHAR(32),
            payload_summary JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wf_reminders_workflow ON workflow_reminders(workflow_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wf_reminders_user ON workflow_reminders(user_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wf_reminders_status ON workflow_reminders(status, eligible_at)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wf_reminders_type_wf ON workflow_reminders(workflow_id, reminder_type)"
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_admin_audit (
            audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id UUID REFERENCES workflow_sessions(workflow_id) ON DELETE SET NULL,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            actor_source VARCHAR(128) NOT NULL,
            action_type VARCHAR(64) NOT NULL,
            reason_safe TEXT,
            payload_before JSONB,
            payload_after JSONB,
            reminder_id UUID,
            response_id UUID,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wf_admin_audit_workflow ON workflow_admin_audit(workflow_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wf_admin_audit_created ON workflow_admin_audit(created_at DESC)"
    )
    cur.close()
