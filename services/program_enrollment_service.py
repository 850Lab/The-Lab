"""
Phase 1 S2 — organization program enrollment (participant lifecycle).

Requires an active ``org_user`` membership for the same org (S1).
Each enrollment links to an ``org_program_v1`` row in ``workflow_sessions`` (``program_workflow_id``).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from database import get_db

_log = logging.getLogger(__name__)

from services.org_service import (
    get_active_membership_for_user,
    get_organization,
    org_allows_participant_program_access,
    user_is_org_user_for_org,
)

ENROLLMENT_STATUSES = frozenset(
    {"enrolled", "active", "paused", "completed", "withdrawn"}
)


def get_program_workflow_id_for_enrollment(enrollment_id: int) -> Optional[str]:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT program_workflow_id
            FROM organization_program_enrollments
            WHERE id = %s
            """,
            (enrollment_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    raw = row.get("program_workflow_id")
    return str(raw) if raw is not None else None


def get_enrollment(org_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, organization_id, user_id, status, session_id,
                   session_checked_in_at, session_workshop_complete_at,
                   program_workflow_id,
                   enrolled_at, activated_at, completed_at, created_at, updated_at
            FROM organization_program_enrollments
            WHERE organization_id = %s AND user_id = %s
            LIMIT 1
            """,
            (org_id, user_id),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def list_enrollments_for_org(org_id: int) -> List[Dict[str, Any]]:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT e.id, e.organization_id, e.user_id, e.status, e.session_id,
                   e.session_checked_in_at, e.session_workshop_complete_at,
                   e.enrolled_at, e.activated_at, e.completed_at,
                   e.created_at, e.updated_at,
                   u.email, u.display_name
            FROM organization_program_enrollments e
            JOIN users u ON u.id = e.user_id
            WHERE e.organization_id = %s
            ORDER BY e.enrolled_at DESC, e.id DESC
            """,
            (org_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def create_program_enrollment(
    org_id: int,
    user_id: int,
    status: str = "enrolled",
) -> Dict[str, Any]:
    st = (status or "enrolled").strip()
    if st not in ENROLLMENT_STATUSES:
        return {
            "error": f"status must be one of: {', '.join(sorted(ENROLLMENT_STATUSES))}",
        }

    if not get_organization(org_id):
        return {"error": "Organization not found."}

    if not user_is_org_user_for_org(user_id, org_id):
        return {
            "error": "User must have an active org_user membership in this organization.",
        }

    if get_enrollment(org_id, user_id):
        return {"error": "An enrollment already exists for this user in this organization."}

    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO organization_program_enrollments (
                organization_id, user_id, status, session_id,
                enrolled_at, activated_at, completed_at
            )
            VALUES (
                %s, %s, %s, NULL,
                CURRENT_TIMESTAMP,
                CASE WHEN %s IN ('active', 'completed') THEN CURRENT_TIMESTAMP ELSE NULL END,
                CASE WHEN %s = 'completed' THEN CURRENT_TIMESTAMP ELSE NULL END
            )
            RETURNING id, organization_id, user_id, status, session_id,
                      enrolled_at, activated_at, completed_at, created_at, updated_at
            """,
            (org_id, user_id, st, st, st),
        )
        row = dict(cur.fetchone())
        conn.commit()
    from services.program_progress_service import initialize_progress_for_enrollment

    initialize_progress_for_enrollment(int(row["id"]), int(row["user_id"]))
    try:
        from services.org_program_workflow_service import ensure_org_program_workflow

        ensure_org_program_workflow(int(row["user_id"]), org_id, int(row["id"]))
    except Exception:
        _log.warning(
            "ensure_org_program_workflow failed after enrollment eid=%s",
            row["id"],
            exc_info=True,
        )
    return row


def build_me_org_program_payload(user_id: int) -> Dict[str, Any]:
    """
    Participant-safe / instructor-safe context for GET /api/me/org-program.
    No other users' data; no internal admin fields.
    """
    m = get_active_membership_for_user(user_id)
    if not m:
        return {
            "organization": None,
            "membership": None,
            "enrollment": None,
        }

    org_id = int(m["organization_id"])
    org = get_organization(org_id)
    org_public = None
    if org:
        org_public = {
            "id": org["id"],
            "name": org["name"],
            "status": org["status"],
            "contactEmail": org.get("contact_email"),
            "contactPhone": org.get("contact_phone"),
            "programCode": org.get("program_code"),
            "onboardingStage": org.get("onboarding_stage"),
            "paymentAccess": org.get("payment_access"),
            "programAccessAllowed": org_allows_participant_program_access(org),
            "programAccessActivatedAt": org.get("program_access_activated_at"),
        }

    membership_public = {
        "organizationId": org_id,
        "role": m["role"],
        "status": m["status"],
    }

    enrollment_public = None
    org_bundle_eid: Optional[int] = None
    if m.get("role") == "org_user":
        enr = get_enrollment(org_id, user_id)
        if enr:
            try:
                from services.org_program_workflow_service import ensure_org_program_workflow

                ensure_org_program_workflow(user_id, org_id, int(enr["id"]))
                enr = get_enrollment(org_id, user_id) or enr
            except Exception:
                _log.warning("ensure_org_program_workflow in org-program payload failed", exc_info=True)
            eid = int(enr["id"])
            org_bundle_eid = eid
            enrollment_public = {
                "id": eid,
                "enrollmentId": eid,
                "status": enr["status"],
                "enrolledAt": enr["enrolled_at"],
                "activatedAt": enr["activated_at"],
                "completedAt": enr["completed_at"],
            }
            pw = enr.get("program_workflow_id")
            if pw:
                enrollment_public["programWorkflowId"] = str(pw)

    out: Dict[str, Any] = {
        "organization": org_public,
        "membership": membership_public,
        "enrollment": enrollment_public,
    }
    if org_bundle_eid is not None:
        from services.workflow.progression_api import build_org_participant_progression_bundle

        bundle = build_org_participant_progression_bundle(user_id, org_bundle_eid)
        if bundle:
            out.update(bundle)
    return out
