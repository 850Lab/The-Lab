"""
S6 — org + instructor visibility (API-only aggregates, no PII-heavy fields).

S5B participant listing / detail helpers (enrollment-scoped, no email).

``program_current_step`` and progress aggregates use **milestone / instructor-effective**
buckets for cohort UX — **not** the canonical workflow head. Use ``canonicalProgression``
on participant detail (and ``GET /api/me/progress``) for engine truth.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from database import get_db

from services.program_enrollment_service import get_enrollment
from services.program_progress_service import (
    PROGRAM_STEPS,
    build_instructor_participant_progress_view,
    build_effective_milestone_flags,
    refresh_program_progress,
)


def list_org_program_participants(org_id: int) -> List[Dict[str, Any]]:
    """Enrolled org_users; names/email for instructor desk (no report payloads)."""
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT e.id AS enrollment_id, e.user_id, e.status,
                   e.enrolled_at, e.activated_at, e.completed_at,
                   e.session_id, e.session_checked_in_at, e.session_workshop_complete_at,
                   u.email, u.display_name
            FROM organization_program_enrollments e
            JOIN users u ON u.id = e.user_id
            JOIN organization_memberships m
              ON m.user_id = e.user_id AND m.organization_id = e.organization_id
            WHERE e.organization_id = %s
              AND m.role = 'org_user' AND m.status = 'active'
            ORDER BY e.enrolled_at DESC NULLS LAST, e.id DESC
            """,
            (org_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["program_current_step"] = _participant_current_step_bucket(
            int(r["user_id"]),
            int(r["enrollment_id"]),
        )
    return rows


def get_org_program_participant_detail(org_id: int, participant_user_id: int) -> Optional[Dict[str, Any]]:
    enr = get_enrollment(org_id, participant_user_id)
    if not enr:
        return None
    eid = int(enr["id"])
    uid = int(participant_user_id)
    view = build_instructor_participant_progress_view(uid, eid)
    from services.workflow.progression_api import build_org_participant_progression_bundle

    out: Dict[str, Any] = {
        "organizationId": int(enr["organization_id"]),
        "userId": uid,
        "enrollmentId": eid,
        "enrollmentStatus": enr.get("status"),
        "enrolledAt": enr.get("enrolled_at"),
        "progress": view,
    }
    canon = build_org_participant_progression_bundle(uid, eid)
    if canon:
        out.update(canon)
    return out


def _participant_current_step_bucket(user_id: int, enrollment_id: int) -> str:
    """First incomplete effective step, or ``complete`` when all milestones satisfied."""
    st = refresh_program_progress(user_id, enrollment_id)
    ef = build_effective_milestone_flags(st["flags"], st["row"])
    if all(bool(ef.get(s)) for s in PROGRAM_STEPS):
        return "complete"
    for step in PROGRAM_STEPS:
        if not ef.get(step):
            return step
    return "complete"


def build_org_progress_aggregate(org_id: int) -> Dict[str, Any]:
    parts = list_org_program_participants(org_id)
    total = len(parts)
    step_counts: Dict[str, int] = {s: 0 for s in PROGRAM_STEPS}
    complete = 0
    for p in parts:
        uid = int(p["user_id"])
        eid = int(p["enrollment_id"])
        bucket = _participant_current_step_bucket(uid, eid)
        if bucket == "complete":
            complete += 1
        else:
            step_counts[bucket] = step_counts.get(bucket, 0) + 1
    pct_steps: Dict[str, Optional[float]] = {}
    if total > 0:
        for s in PROGRAM_STEPS:
            pct_steps[s] = round(100.0 * float(step_counts[s]) / float(total), 1)
        pct_complete = round(100.0 * float(complete) / float(total), 1)
    else:
        for s in PROGRAM_STEPS:
            pct_steps[s] = None
        pct_complete = None
    return {
        "organizationId": org_id,
        "totalParticipants": total,
        "countAtStep": step_counts,
        "completedAllStepsCount": complete,
        "percentAtStep": pct_steps,
        "percentCompletedAll": pct_complete,
        "aggregationBasis": "delivery_milestone_effective_state",
        "authoritativeProgressionNote": (
            "Buckets reflect instructor-effective milestones, not workflow engine head; "
            "use per-participant canonicalProgression for engine truth."
        ),
    }


def build_org_outcomes_aggregate(org_id: int) -> Dict[str, Any]:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT COUNT(*)::int AS c FROM reports
            WHERE organization_id = %s
            """,
            (org_id,),
        )
        reports_uploaded = int(cur.fetchone()["c"])
        cur.execute(
            """
            SELECT COUNT(DISTINCT s.id)::int AS c
            FROM organization_program_dispute_selections s
            JOIN reports r ON r.id = s.report_id
            WHERE r.organization_id = %s
              AND COALESCE(jsonb_array_length(s.selected_review_claim_ids), 0) > 0
            """,
            (org_id,),
        )
        dispute_selections_saved = int(cur.fetchone()["c"])
        cur.execute(
            """
            SELECT COUNT(*)::int AS c
            FROM letters l
            JOIN reports r ON r.id = l.report_id
            WHERE r.organization_id = %s
            """,
            (org_id,),
        )
        letters_generated = int(cur.fetchone()["c"])
        cur.execute(
            """
            SELECT COUNT(*)::int AS c
            FROM organization_program_enrollments
            WHERE organization_id = %s
            """,
            (org_id,),
        )
        enrollments = int(cur.fetchone()["c"])
    return {
        "organizationId": org_id,
        "programEnrollments": enrollments,
        "reportsUploaded": reports_uploaded,
        "disputeSelectionsSaved": dispute_selections_saved,
        "lettersGenerated": letters_generated,
    }
