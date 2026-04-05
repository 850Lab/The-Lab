"""
Instructor-facing workshop desk: roster for a session, names, program step, coach cues.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from database import get_db

from services.org_program_session_service import get_program_session
from services.org_program_visibility_service import _participant_current_step_bucket
from services.program_progress_service import PROGRAM_STEPS


def _recommended_coach_step(count_at_step: Dict[str, int]) -> str:
    """Dominant incomplete step in the room (excluding terminal complete)."""
    best_step = "upload"
    best_n = -1
    for s in PROGRAM_STEPS:
        if s == "enrollment":
            continue
        n = int(count_at_step.get(s) or 0)
        if n > best_n:
            best_n = n
            best_step = s
    if best_n <= 0:
        return "enrollment"
    return best_step


def _focus_copy(session_state: str, guide_step: str) -> Tuple[str, str, str]:
    """
    Returns (flow_phase, headline, say_this).
    flow_phase: prepare | start | guide | wrap
    """
    st = (session_state or "draft").strip().lower()
    if st == "completed":
        return (
            "wrap",
            "Session wrapped",
            "Thank the cohort and remind them to finish mail + tracking on their own time. "
            "They can pick up exactly where they left off in the app.",
        )
    if st == "draft":
        return (
            "prepare",
            "Before you go live",
            "Name this workshop, assign everyone to it from the roster, and confirm people can sign in. "
            "When you are ready, move the session to Scheduled or open the room.",
        )
    if st == "scheduled":
        return (
            "start",
            "Opening the room",
            "Welcome people by name when you can. Ask everyone to open the program on their device. "
            "You will move through upload → findings → disputes → letters together; pause if the room needs air.",
        )
    # active
    step_lines = {
        "upload": (
            "Coach upload together",
            "Have everyone on the upload step submit a report now. Watch for privacy consent and file errors — "
            "pair people up if someone is blocked.",
        ),
        "findings_ready": (
            "Findings pass",
            "Walk through what changed on the report after analysis. Answer questions before you send them to disputes.",
        ),
        "selections_saved": (
            "Dispute selections",
            "Help people choose review items they will actually mail. Save selections before letters.",
        ),
        "letters_generated": (
            "Letters & mail",
            "Generate letters together, preview addresses, and set expectations for printing and certified mail.",
        ),
        "enrollment": (
            "Get everyone seated in-app",
            "Confirm accounts and enrollment show active. Resolve login issues before you push upload.",
        ),
    }
    headline, say = step_lines.get(
        guide_step,
        (
            "Guide the cohort",
            "Check the roster for who is behind and stand next to them while they complete the current step.",
        ),
    )
    return ("guide", headline, say)


def build_workshop_desk(org_id: int, session_id: int) -> Dict[str, Any]:
    sess = get_program_session(org_id, session_id)
    if not sess:
        return {"error": "Session not found."}

    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT e.id AS enrollment_id, e.user_id, e.status,
                   e.session_checked_in_at, e.session_workshop_complete_at,
                   u.email, u.display_name
            FROM organization_program_enrollments e
            JOIN users u ON u.id = e.user_id
            JOIN organization_memberships m
              ON m.user_id = e.user_id AND m.organization_id = e.organization_id
            WHERE e.organization_id = %s
              AND e.session_id = %s
              AND m.role = 'org_user' AND m.status = 'active'
            ORDER BY COALESCE(NULLIF(TRIM(u.display_name), ''), u.email) ASC, e.id ASC
            """,
            (org_id, session_id),
        )
        rows = [dict(r) for r in cur.fetchall()]

    count_at_step: Dict[str, int] = {s: 0 for s in PROGRAM_STEPS}
    program_complete_n = 0
    roster: List[Dict[str, Any]] = []
    stuck: List[Dict[str, Any]] = []

    for r in rows:
        uid = int(r["user_id"])
        eid = int(r["enrollment_id"])
        bucket = _participant_current_step_bucket(uid, eid)
        prog_done = bucket == "complete"
        if prog_done:
            program_complete_n += 1
        else:
            count_at_step[bucket] = count_at_step.get(bucket, 0) + 1

        checked_in = r.get("session_checked_in_at") is not None
        marked = r.get("session_workshop_complete_at") is not None
        name = (r.get("display_name") or "").strip() or None
        email = (r.get("email") or "").strip() or None
        display = name or email or f"User #{uid}"

        entry = {
            "userId": uid,
            "enrollmentId": eid,
            "displayName": name,
            "email": email,
            "displayLabel": display,
            "enrollmentStatus": r.get("status"),
            "programCurrentStep": bucket,
            "programComplete": prog_done,
            "checkedIn": checked_in,
            "workshopMarkedComplete": marked,
            "sessionCheckedInAt": r.get("session_checked_in_at"),
            "sessionWorkshopCompleteAt": r.get("session_workshop_complete_at"),
        }
        roster.append(entry)
        if not prog_done and bucket in ("upload", "findings_ready"):
            stuck.append(
                {
                    "userId": uid,
                    "displayLabel": display,
                    "programCurrentStep": bucket,
                }
            )

    guide_step = _recommended_coach_step(count_at_step)
    flow_phase, focus_headline, say_this = _focus_copy(sess.get("state") or "draft", guide_step)

    checked_in_n = sum(1 for x in roster if x["checkedIn"])
    marked_n = sum(1 for x in roster if x["workshopMarkedComplete"])

    return {
        "organizationId": org_id,
        "session": {
            "id": int(sess["id"]),
            "name": sess.get("name"),
            "state": sess.get("state"),
            "scheduledStartsAt": sess.get("scheduled_starts_at"),
            "startedAt": sess.get("started_at"),
            "endedAt": sess.get("ended_at"),
        },
        "roster": roster,
        "totals": {
            "rosterCount": len(roster),
            "checkedInCount": checked_in_n,
            "workshopMarkedCompleteCount": marked_n,
            "programCompleteCount": program_complete_n,
            "countAtStep": count_at_step,
        },
        "instructorFocus": {
            "flowPhase": flow_phase,
            "headline": focus_headline,
            "sayThis": say_this,
            "recommendedGuideStep": guide_step,
            "stuck": stuck,
        },
    }
