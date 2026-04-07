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


def ensure_workflow_events_table(conn) -> None:
    """Append-only observability log: what happened, when, to which workflow."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id UUID NOT NULL REFERENCES workflow_sessions(workflow_id) ON DELETE CASCADE,
            event_type VARCHAR(80) NOT NULL,
            step_id VARCHAR(64),
            previous_state JSONB,
            new_state JSONB,
            actor VARCHAR(64) NOT NULL DEFAULT 'system',
            source VARCHAR(64) NOT NULL DEFAULT 'engine',
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflow_events_wf_created ON workflow_events(workflow_id, created_at ASC)"
    )
    cur.close()


def ensure_workflow_jobs_table(conn) -> None:
    """Background job queue: heavy work outside HTTP request/response (in-process worker)."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id UUID NOT NULL REFERENCES workflow_sessions(workflow_id) ON DELETE CASCADE,
            job_type VARCHAR(64) NOT NULL,
            status VARCHAR(24) NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            payload JSONB NOT NULL DEFAULT '{}',
            result JSONB,
            error TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            run_at TIMESTAMP
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflow_jobs_wf ON workflow_jobs(workflow_id, created_at DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflow_jobs_pending ON workflow_jobs(status, run_at, created_at)"
    )
    cur.close()


def ensure_report_upload_sessions_table(conn) -> None:
    """
    Direct-to-object-storage ingest: one row per presigned upload before finalize → job.

    ``organization_id`` / ``organization_program_enrollment_id`` are set for org-program
    uploads; optional FKs omitted so this table can be ensured early in bootstrap.
    """
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS report_upload_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            workflow_id UUID NOT NULL REFERENCES workflow_sessions(workflow_id) ON DELETE CASCADE,
            kind VARCHAR(24) NOT NULL DEFAULT 'retail',
            organization_id INTEGER,
            organization_program_enrollment_id INTEGER,
            bucket TEXT NOT NULL,
            object_key TEXT NOT NULL UNIQUE,
            status VARCHAR(32) NOT NULL DEFAULT 'pending_upload',
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finalized_at TIMESTAMP NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_upload_sessions_user "
        "ON report_upload_sessions(user_id, created_at DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_upload_sessions_wf "
        "ON report_upload_sessions(workflow_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_upload_sessions_status_expires "
        "ON report_upload_sessions(status, expires_at)"
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


def ensure_org_tables(conn) -> None:
    """
    Phase 1 S1: organizations + organization_memberships (Postgres only).
    One active org context per user. Additional delivery fields and multi-instructor
    support are applied in ``ensure_org_program_delivery_schema``.
    """
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS organization_memberships (
            id SERIAL PRIMARY KEY,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role VARCHAR(32) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT organization_memberships_role_chk CHECK (
                role IN ('org_instructor', 'org_user')
            ),
            CONSTRAINT organization_memberships_org_user_uniq UNIQUE (organization_id, user_id)
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_org_memberships_org ON organization_memberships(organization_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_org_memberships_user ON organization_memberships(user_id)"
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_org_single_active_instructor "
        "ON organization_memberships (organization_id) "
        "WHERE role = 'org_instructor' AND status = 'active'"
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_org_memberships_one_row_per_user "
        "ON organization_memberships (user_id)"
    )
    cur.close()


def ensure_organization_program_enrollment_tables(conn) -> None:
    """
    Phase 1 S2: program enrollment lifecycle per org user.
    One row per (organization_id, user_id); participants only (org_user).
    """
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS organization_program_enrollments (
            id SERIAL PRIMARY KEY,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(32) NOT NULL DEFAULT 'enrolled',
            enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            activated_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT org_prog_enroll_status_chk CHECK (
                status IN ('enrolled', 'active', 'paused', 'completed', 'withdrawn')
            ),
            CONSTRAINT org_prog_enroll_org_user_uniq UNIQUE (organization_id, user_id)
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_org_prog_enrollments_org "
        "ON organization_program_enrollments(organization_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_org_prog_enrollments_user "
        "ON organization_program_enrollments(user_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_org_prog_enrollments_org_status "
        "ON organization_program_enrollments(organization_id, status)"
    )
    cur.execute(
        "ALTER TABLE organization_program_enrollments ADD COLUMN IF NOT EXISTS "
        "program_workflow_id UUID REFERENCES workflow_sessions(workflow_id) ON DELETE SET NULL"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_org_prog_enrollments_program_workflow "
        "ON organization_program_enrollments(program_workflow_id)"
    )
    cur.close()


def ensure_reports_program_link_columns(conn) -> None:
    """S3: optional org + enrollment FK on reports (nullable for legacy consumer rows)."""
    cur = conn.cursor()
    cur.execute(
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS organization_id INTEGER "
        "REFERENCES organizations(id) ON DELETE SET NULL"
    )
    cur.execute(
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS organization_program_enrollment_id INTEGER "
        "REFERENCES organization_program_enrollments(id) ON DELETE SET NULL"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_reports_user_org ON reports(user_id, organization_id)"
    )
    cur.close()


def ensure_organization_program_dispute_selections_table(conn) -> None:
    """S4: persisted review-claim ids for org program participants (per user + report)."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS organization_program_dispute_selections (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            organization_program_enrollment_id INTEGER
                REFERENCES organization_program_enrollments(id) ON DELETE SET NULL,
            selected_review_claim_ids JSONB NOT NULL DEFAULT '[]',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT org_prog_dispute_sel_user_report_uniq UNIQUE (user_id, report_id)
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_org_prog_dispute_sel_user "
        "ON organization_program_dispute_selections(user_id)"
    )
    cur.close()


def ensure_organization_program_progress_table(conn) -> None:
    """S5A: monotonic milestone timestamps per program enrollment (participant path)."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS organization_program_progress (
            id SERIAL PRIMARY KEY,
            organization_program_enrollment_id INTEGER NOT NULL UNIQUE
                REFERENCES organization_program_enrollments(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            upload_completed_at TIMESTAMP,
            findings_ready_at TIMESTAMP,
            selections_saved_at TIMESTAMP,
            letters_generated_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_org_prog_progress_user "
        "ON organization_program_progress(user_id)"
    )
    # S5B: instructor dual-state (optional override; no audit/versioning)
    for ddl in (
        "ALTER TABLE organization_program_progress ADD COLUMN IF NOT EXISTS "
        "instructor_paused BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE organization_program_progress ADD COLUMN IF NOT EXISTS "
        "instructor_override_kind VARCHAR(24)",
        "ALTER TABLE organization_program_progress ADD COLUMN IF NOT EXISTS "
        "instructor_override_step VARCHAR(64)",
        "ALTER TABLE organization_program_progress ADD COLUMN IF NOT EXISTS "
        "instructor_override_at TIMESTAMP",
        "ALTER TABLE organization_program_progress ADD COLUMN IF NOT EXISTS "
        "instructor_override_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
        "ALTER TABLE organization_program_progress ADD COLUMN IF NOT EXISTS "
        "instructor_override_reason_safe TEXT",
    ):
        cur.execute(ddl)
    cur.close()


def ensure_demo_leads_table(conn) -> None:
    """Public React /demo lead capture (workshops / outreach). No FK to users."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS demo_leads (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            phone VARCHAR(80),
            source VARCHAR(40) NOT NULL DEFAULT 'react_demo',
            scenario_id VARCHAR(64),
            workflow_id VARCHAR(80),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            meta JSONB NOT NULL DEFAULT '{}'
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_demo_leads_created ON demo_leads(created_at DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_demo_leads_source ON demo_leads(source)"
    )
    cur.close()


def ensure_org_program_delivery_schema(conn) -> None:
    """
    Full program delivery layer (Postgres): org profile + onboarding fields,
    workshop/session records, demo→org linkage, org_admin role, multiple instructors.
    Safe to run repeatedly (IF NOT EXISTS / DROP IF EXISTS).
    """
    cur = conn.cursor()
    for ddl in (
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255)",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(80)",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS program_code VARCHAR(64) NOT NULL DEFAULT '850_lab_core'",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS onboarding_stage VARCHAR(32) NOT NULL DEFAULT 'draft'",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS payment_access VARCHAR(24) NOT NULL DEFAULT 'full'",
    ):
        cur.execute(ddl)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS organization_program_sessions (
            id SERIAL PRIMARY KEY,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            state VARCHAR(24) NOT NULL DEFAULT 'draft',
            scheduled_starts_at TIMESTAMP,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT org_prog_session_state_chk CHECK (
                state IN ('draft', 'scheduled', 'active', 'completed')
            )
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_org_prog_sessions_org "
        "ON organization_program_sessions(organization_id, state)"
    )
    cur.execute(
        "ALTER TABLE organization_program_enrollments ADD COLUMN IF NOT EXISTS "
        "session_id INTEGER REFERENCES organization_program_sessions(id) ON DELETE SET NULL"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_org_prog_enrollments_session "
        "ON organization_program_enrollments(session_id)"
    )
    for ddl in (
        "ALTER TABLE organization_program_enrollments ADD COLUMN IF NOT EXISTS "
        "session_checked_in_at TIMESTAMP",
        "ALTER TABLE organization_program_enrollments ADD COLUMN IF NOT EXISTS "
        "session_workshop_complete_at TIMESTAMP",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS "
        "program_access_activated_at TIMESTAMP",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS "
        "program_access_last_stripe_session_id VARCHAR(255)",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS "
        "program_access_unlock_error_safe VARCHAR(500)",
    ):
        cur.execute(ddl)
    cur.execute(
        "ALTER TABLE organizations ALTER COLUMN payment_access SET DEFAULT 'locked'"
    )
    cur.execute(
        "ALTER TABLE demo_leads ADD COLUMN IF NOT EXISTS converted_organization_id INTEGER "
        "REFERENCES organizations(id) ON DELETE SET NULL"
    )
    cur.execute(
        "ALTER TABLE demo_leads ADD COLUMN IF NOT EXISTS lead_disposition VARCHAR(32) NOT NULL DEFAULT 'open'"
    )
    cur.execute("DROP INDEX IF EXISTS idx_org_single_active_instructor")
    cur.execute(
        "ALTER TABLE organization_memberships DROP CONSTRAINT IF EXISTS organization_memberships_role_chk"
    )
    cur.execute(
        """
        ALTER TABLE organization_memberships
        ADD CONSTRAINT organization_memberships_role_chk CHECK (
            role IN ('org_instructor', 'org_user', 'org_admin')
        )
        """
    )
    cur.close()
