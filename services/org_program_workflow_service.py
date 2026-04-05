"""
Organization program: one ``workflow_sessions`` row per enrollment (``org_program_v1``).

**Single engine:** ``WorkflowEngine.service_complete_step`` on ``workflow_steps``.
``organization_program_progress`` holds instructor pause/override plus **mirrored**
milestone timestamps (see ``sync_org_progress_row_from_org_workflow``); it does not
own head/next-step logic.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from database import get_db

from services.program_enrollment_service import get_program_workflow_id_for_enrollment
from services.workflow.engine import WorkflowEngine
from services.workflow.registry import ORG_PROGRAM_WORKFLOW_TYPE, linear_order_for
from services.workflow.repository import create_workflow_with_steps, fetch_session

_log = logging.getLogger(__name__)


def set_program_workflow_id(enrollment_id: int, workflow_id: str) -> None:
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            UPDATE organization_program_enrollments
            SET program_workflow_id = %s::uuid, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (workflow_id, enrollment_id),
        )
        conn.commit()


def ensure_org_program_workflow(user_id: int, organization_id: int, enrollment_id: int) -> str:
    """
    Return the org program workflow id, creating ``org_program_v1`` + steps if needed.
    Completes ``orgprog_enrollment`` immediately so the participant head is upload.
    """
    wid = get_program_workflow_id_for_enrollment(enrollment_id)
    if wid:
        sess = fetch_session(wid)
        if sess and int(sess.get("user_id") or 0) == int(user_id):
            return wid
        _log.warning(
            "Enrollment %s had stale program_workflow_id %s; recreating",
            enrollment_id,
            wid,
        )

    meta: Dict[str, Any] = {
        "programContext": "org",
        "organizationProgramEnrollmentId": enrollment_id,
        "organizationId": organization_id,
    }
    first = linear_order_for(ORG_PROGRAM_WORKFLOW_TYPE)[0]
    wid = create_workflow_with_steps(
        user_id=user_id,
        workflow_type=ORG_PROGRAM_WORKFLOW_TYPE,
        metadata=meta,
        first_step_id=first,
    )
    set_program_workflow_id(enrollment_id, wid)
    eng = WorkflowEngine()
    eng.service_complete_step(
        wid,
        "orgprog_enrollment",
        {"source": "org_program_bootstrap"},
        audit_source="org_program_bootstrap",
        audit_user_id=user_id,
    )
    return wid


def advance_org_program_steps(
    user_id: int,
    organization_id: int,
    enrollment_id: int,
    step_ids: list[str],
    *,
    audit_source: str = "api:me_program",
) -> str:
    """
    Complete each step in order via ``WorkflowEngine.service_complete_step`` (authoritative).
    Then mirror timestamps into ``organization_program_progress`` (non-authoritative).
    """
    from services.program_progress_service import sync_org_progress_row_from_org_workflow

    wid = ensure_org_program_workflow(user_id, organization_id, enrollment_id)
    eng = WorkflowEngine()
    for sid in step_ids:
        eng.service_complete_step(
            wid,
            sid,
            {"source": audit_source[:80]},
            audit_source=audit_source,
            audit_user_id=user_id,
        )
    sync_org_progress_row_from_org_workflow(enrollment_id, user_id, wid)
    return wid
