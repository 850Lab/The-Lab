"""
Workshop / live session records for org program delivery.

State machine: draft → scheduled → active → completed.
Participants link via ``organization_program_enrollments.session_id``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from database import get_db

from services.org_service import get_organization

SESSION_STATES = frozenset({"draft", "scheduled", "active", "completed"})


def create_program_session(org_id: int, name: str) -> Dict[str, Any]:
    name = (name or "").strip()[:255]
    if not name:
        return {"error": "Session name is required."}
    if not get_organization(org_id):
        return {"error": "Organization not found."}
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO organization_program_sessions (organization_id, name, state)
            VALUES (%s, %s, 'draft')
            RETURNING id, organization_id, name, state,
                      scheduled_starts_at, started_at, ended_at, created_at, updated_at
            """,
            (org_id, name),
        )
        row = dict(cur.fetchone())
        conn.commit()
    return row


def list_program_sessions(org_id: int) -> List[Dict[str, Any]]:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, organization_id, name, state,
                   scheduled_starts_at, started_at, ended_at, created_at, updated_at
            FROM organization_program_sessions
            WHERE organization_id = %s
            ORDER BY created_at DESC, id DESC
            """,
            (org_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_program_session(org_id: int, session_id: int) -> Optional[Dict[str, Any]]:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, organization_id, name, state,
                   scheduled_starts_at, started_at, ended_at, created_at, updated_at
            FROM organization_program_sessions
            WHERE id = %s AND organization_id = %s
            LIMIT 1
            """,
            (session_id, org_id),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def update_program_session(
    org_id: int,
    session_id: int,
    *,
    name: Optional[str] = None,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    sess = get_program_session(org_id, session_id)
    if not sess:
        return {"error": "Session not found."}
    st = (state or "").strip().lower() if state is not None else None
    if st is not None and st not in SESSION_STATES:
        return {
            "error": f"state must be one of: {', '.join(sorted(SESSION_STATES))}",
        }
    nm = None
    if name is not None:
        nm = str(name).strip()[:255]
        if not nm:
            return {"error": "Session name cannot be empty."}
    sets: List[str] = []
    vals: List[Any] = []
    if nm is not None:
        sets.append("name = %s")
        vals.append(nm)
    if st is not None:
        sets.append("state = %s")
        vals.append(st)
        if st == "active":
            sets.append(
                "started_at = COALESCE(started_at, CURRENT_TIMESTAMP)"
            )
        if st == "completed":
            sets.append("ended_at = COALESCE(ended_at, CURRENT_TIMESTAMP)")
    if not sets:
        return {"error": "No changes."}
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.extend([session_id, org_id])
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            f"""
            UPDATE organization_program_sessions
            SET {", ".join(sets)}
            WHERE id = %s AND organization_id = %s
            RETURNING id, organization_id, name, state,
                      scheduled_starts_at, started_at, ended_at, created_at, updated_at
            """,
            tuple(vals),
        )
        row = dict(cur.fetchone())
        conn.commit()
    return row


def set_enrollment_session(
    org_id: int,
    enrollment_id: int,
    session_id: Optional[int],
) -> Dict[str, Any]:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, organization_id, session_id FROM organization_program_enrollments
            WHERE id = %s LIMIT 1
            """,
            (enrollment_id,),
        )
        enr = cur.fetchone()
        if not enr or int(enr["organization_id"]) != org_id:
            conn.rollback()
            return {"error": "Enrollment not found for this organization."}
        old_sid = enr.get("session_id")
        old_norm = int(old_sid) if old_sid is not None else None
        new_norm = int(session_id) if session_id is not None else None
        reassigned = old_norm != new_norm
        if session_id is not None:
            cur.execute(
                """
                SELECT 1 FROM organization_program_sessions
                WHERE id = %s AND organization_id = %s LIMIT 1
                """,
                (session_id, org_id),
            )
            if not cur.fetchone():
                conn.rollback()
                return {"error": "Session not found for this organization."}
        set_parts = ["session_id = %s", "updated_at = CURRENT_TIMESTAMP"]
        if reassigned:
            set_parts.extend(
                [
                    "session_checked_in_at = NULL",
                    "session_workshop_complete_at = NULL",
                ]
            )
        cur.execute(
            f"""
            UPDATE organization_program_enrollments
            SET {", ".join(set_parts)}
            WHERE id = %s
            RETURNING id, organization_id, user_id, status, session_id,
                      session_checked_in_at, session_workshop_complete_at,
                      enrolled_at, activated_at, completed_at, created_at, updated_at
            """,
            (session_id, enrollment_id),
        )
        row = dict(cur.fetchone())
        conn.commit()
    return row


def patch_enrollment_workshop(
    org_id: int,
    enrollment_id: int,
    *,
    checked_in: Optional[bool] = None,
    workshop_complete: Optional[bool] = None,
) -> Dict[str, Any]:
    if checked_in is None and workshop_complete is None:
        return {"error": "No changes."}
    sets: List[str] = []
    if checked_in is not None:
        if checked_in:
            sets.append("session_checked_in_at = CURRENT_TIMESTAMP")
        else:
            sets.append("session_checked_in_at = NULL")
    if workshop_complete is not None:
        if workshop_complete:
            sets.append("session_workshop_complete_at = CURRENT_TIMESTAMP")
        else:
            sets.append("session_workshop_complete_at = NULL")
    sets.append("updated_at = CURRENT_TIMESTAMP")
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, organization_id FROM organization_program_enrollments
            WHERE id = %s LIMIT 1
            """,
            (enrollment_id,),
        )
        enr = cur.fetchone()
        if not enr or int(enr["organization_id"]) != org_id:
            conn.rollback()
            return {"error": "Enrollment not found for this organization."}
        cur.execute(
            f"""
            UPDATE organization_program_enrollments
            SET {", ".join(sets)}
            WHERE id = %s
            RETURNING id, organization_id, user_id, status, session_id,
                      session_checked_in_at, session_workshop_complete_at,
                      enrolled_at, activated_at, completed_at, created_at, updated_at
            """,
            (enrollment_id,),
        )
        row = dict(cur.fetchone())
        conn.commit()
    return row
