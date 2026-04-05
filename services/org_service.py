"""
Phase 1 S1 — minimal organizations + memberships for multi-tenant foundation.

Rules:
- ``users.role == 'admin'`` → platform operator (create orgs, attach members).
- Org roles: org_instructor | org_user | org_admin (buyer / org visibility, no participant seat).
- At most one *active* membership per user (any org / any org role).
- Multiple active org_instructors per organization are allowed (delivery teams).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from database import get_db

# Seats org operators may assign without platform admin (participant + co-guide).
ORG_MEMBER_ROLES_SELF_SERVE = frozenset({"org_instructor", "org_user"})
# Billing / buyer seat — only platform admin may attach via API.
ORG_MEMBER_ROLE_ADMIN_SEAT = "org_admin"


def create_organization(name: str, status: str = "active") -> Dict[str, Any]:
    name = (name or "").strip()
    if not name:
        return {"error": "Organization name is required."}
    st = (status or "active").strip() or "active"
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO organizations (name, status)
            VALUES (%s, %s)
            RETURNING id, name, status, created_at, updated_at
            """,
            (name[:255], st[:32]),
        )
        row = dict(cur.fetchone())
        conn.commit()
    return row


def get_organization(org_id: int) -> Optional[Dict[str, Any]]:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, name, status,
                   contact_email, contact_phone, program_code, onboarding_stage, payment_access,
                   program_access_activated_at, program_access_last_stripe_session_id,
                   program_access_unlock_error_safe,
                   created_at, updated_at
            FROM organizations WHERE id = %s
            """,
            (org_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_active_membership_for_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Single active org context for this user, if any."""
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT m.id, m.organization_id, m.user_id, m.role, m.status,
                   m.created_at, m.updated_at
            FROM organization_memberships m
            WHERE m.user_id = %s AND m.status = 'active'
            LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def user_is_active_instructor_for_org(user_id: int, org_id: int) -> bool:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT 1 FROM organization_memberships
            WHERE user_id = %s AND organization_id = %s
              AND role = 'org_instructor' AND status = 'active'
            LIMIT 1
            """,
            (user_id, org_id),
        )
        return cur.fetchone() is not None


def user_is_active_org_admin_for_org(user_id: int, org_id: int) -> bool:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT 1 FROM organization_memberships
            WHERE user_id = %s AND organization_id = %s
              AND role = 'org_admin' AND status = 'active'
            LIMIT 1
            """,
            (user_id, org_id),
        )
        return cur.fetchone() is not None


def user_is_org_user_for_org(user_id: int, org_id: int) -> bool:
    """Active org_user membership for this org (program participant seat)."""
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT 1 FROM organization_memberships
            WHERE user_id = %s AND organization_id = %s
              AND role = 'org_user' AND status = 'active'
            LIMIT 1
            """,
            (user_id, org_id),
        )
        return cur.fetchone() is not None


def list_organization_members(org_id: int) -> List[Dict[str, Any]]:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT m.id, m.organization_id, m.user_id, m.role, m.status,
                   m.created_at, m.updated_at,
                   u.email, u.display_name
            FROM organization_memberships m
            JOIN users u ON u.id = m.user_id
            WHERE m.organization_id = %s AND m.status = 'active'
            ORDER BY m.role, m.id
            """,
            (org_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def add_organization_member(
    org_id: int,
    user_id: int,
    role: str,
    *,
    allow_org_admin_seat: bool = False,
) -> Dict[str, Any]:
    """
    Attach a user to an org. API layer decides who may call (org admin/instructor vs platform).

    ``allow_org_admin_seat``: when True, ``org_admin`` (buyer) role is allowed; otherwise only
    org_user and org_instructor (self-serve roster).

    Enforces single active org per user (V1).
    """
    role = (role or "").strip()
    allowed = (
        ORG_MEMBER_ROLES_SELF_SERVE | frozenset({ORG_MEMBER_ROLE_ADMIN_SEAT})
        if allow_org_admin_seat
        else ORG_MEMBER_ROLES_SELF_SERVE
    )
    if role not in allowed:
        return {"error": f"role must be one of: {', '.join(sorted(allowed))}"}

    import auth

    user = auth.get_user_by_id(user_id)
    if not user:
        return {"error": "User not found."}

    org = get_organization(org_id)
    if not org:
        return {"error": "Organization not found."}

    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            "SELECT id FROM organization_memberships WHERE user_id = %s LIMIT 1",
            (user_id,),
        )
        if cur.fetchone():
            conn.rollback()
            return {"error": "User already has an organization membership (V1: one org per user)."}

        cur.execute(
            """
            INSERT INTO organization_memberships (organization_id, user_id, role, status)
            VALUES (%s, %s, %s, 'active')
            RETURNING id, organization_id, user_id, role, status, created_at, updated_at
            """,
            (org_id, user_id, role),
        )
        row = dict(cur.fetchone())
        conn.commit()
    row["email"] = user.get("email")
    row["display_name"] = user.get("display_name")
    return row


PAYMENT_ACCESS_VALUES = frozenset({"full", "locked", "trial"})


def org_allows_participant_program_access(org: Optional[Dict[str, Any]]) -> bool:
    """When payment_access is ``locked``, participants should not advance the program."""
    if not org:
        return False
    pa = (org.get("payment_access") or "full").strip().lower()
    return pa != "locked"


def update_organization(org_id: int, **fields: Any) -> Dict[str, Any]:
    """
    Patch organization profile / delivery fields. Unknown keys ignored.
    Returns row dict or {"error": "..."}.
    """
    col_map = {
        "name": "name",
        "contact_email": "contact_email",
        "contact_phone": "contact_phone",
        "program_code": "program_code",
        "onboarding_stage": "onboarding_stage",
        "payment_access": "payment_access",
        "status": "status",
    }
    sets: List[str] = []
    vals: List[Any] = []
    for key, col in col_map.items():
        if key not in fields or fields[key] is None:
            continue
        v = fields[key]
        if key == "name":
            v = str(v).strip()[:255]
            if not v:
                return {"error": "Organization name cannot be empty."}
        elif key == "payment_access":
            s = str(v).strip().lower()[:24]
            if s not in PAYMENT_ACCESS_VALUES:
                return {
                    "error": f"payment_access must be one of: {', '.join(sorted(PAYMENT_ACCESS_VALUES))}",
                }
            v = s
        elif key == "status":
            v = str(v).strip()[:32]
        else:
            v = str(v).strip()[:255] if key != "contact_phone" else str(v).strip()[:80]
        sets.append(f"{col} = %s")
        vals.append(v)
    if not sets:
        return {"error": "No valid fields to update."}
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(org_id)
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            f"""
            UPDATE organizations
            SET {", ".join(sets)}
            WHERE id = %s
            RETURNING id, name, status,
                      contact_email, contact_phone, program_code, onboarding_stage, payment_access,
                      program_access_activated_at, program_access_last_stripe_session_id,
                      created_at, updated_at
            """,
            tuple(vals),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return {"error": "Organization not found."}
        conn.commit()
    return dict(row)
