"""
Read-only SQL for Mission Control (operator dashboards). No business rules — use mission_control_service.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

MANUAL_REVIEW_ACTIONS = (
    "manual_review_required",
    "request_manual_review_or_more_detail",
)


def _parse_meta(val: Any) -> Dict[str, Any]:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    return {}


def overview_sql_counts() -> Dict[str, int]:
    from services.workflow.workflow_db import get_workflow_db

    out: Dict[str, int] = {}
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT overall_status, COUNT(*)::int AS c
            FROM workflow_sessions
            GROUP BY overall_status
            """
        )
        for r in cur.fetchall():
            out[f"workflows_{r['overall_status']}"] = r["c"]

        cur.execute(
            """
            SELECT status, COUNT(*)::int AS c
            FROM workflow_reminders
            GROUP BY status
            """
        )
        for r in cur.fetchall():
            out[f"reminders_{r['status']}"] = r["c"]

        cur.execute(
            """
            SELECT COUNT(*)::int AS c FROM workflow_response_intake
            WHERE classification_status = 'failed'
               OR response_classification = 'insufficient_to_classify'
               OR recommended_next_action = ANY(%s)
            """,
            (list(MANUAL_REVIEW_ACTIONS),),
        )
        out["responses_needing_review"] = cur.fetchone()["c"]

        cur.execute(
            """
            SELECT COUNT(DISTINCT workflow_id)::int AS c
            FROM workflow_steps
            WHERE status = 'failed'
            """
        )
        out["workflows_with_any_failed_step"] = cur.fetchone()["c"]

    return out


def list_sessions_scan(
    *,
    overall_status: Optional[str] = None,
    current_step: Optional[str] = None,
    has_failed_step: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    clauses = ["1=1"]
    args: List[Any] = []
    if overall_status:
        clauses.append("s.overall_status = %s")
        args.append(overall_status[:24])
    if current_step:
        clauses.append("s.current_step = %s")
        args.append(current_step[:64])
    if has_failed_step is True:
        clauses.append(
            """EXISTS (
            SELECT 1 FROM workflow_steps st
            WHERE st.workflow_id = s.workflow_id AND st.status = 'failed'
        )"""
        )
    elif has_failed_step is False:
        clauses.append(
            """NOT EXISTS (
            SELECT 1 FROM workflow_steps st
            WHERE st.workflow_id = s.workflow_id AND st.status = 'failed'
        )"""
        )

    sql = f"""
        SELECT s.workflow_id::text AS workflow_id, s.user_id, s.workflow_type,
               s.current_step, s.overall_status, s.updated_at, s.started_at,
               s.metadata, s.last_error_code, s.last_error_message_safe
        FROM workflow_sessions s
        WHERE {' AND '.join(clauses)}
        ORDER BY s.updated_at DESC NULLS LAST
        LIMIT %s OFFSET %s
    """
    args.extend([limit, offset])
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(sql, tuple(args))
        rows = [dict(r) for r in cur.fetchall()]
    for d in rows:
        d["metadata"] = _parse_meta(d.get("metadata"))
    return rows


def list_reminders_global(
    *,
    statuses: Optional[List[str]] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    st = statuses or ["eligible", "queued", "sent", "failed", "skipped"]
    st = [x[:24] for x in st if x]
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT reminder_id::text AS reminder_id, workflow_id::text AS workflow_id,
                   user_id, reminder_type, status, eligible_at, sent_at, created_at,
                   delivery_channel, reason
            FROM workflow_reminders
            WHERE status = ANY(%s)
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (st, limit, offset),
        )
        rows = [dict(r) for r in cur.fetchall()]
    return rows


def list_responses_recent(
    *,
    limit: int = 100,
    offset: int = 0,
    needs_review_only: bool = False,
    workflow_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    clauses = ["1=1"]
    args: List[Any] = []
    if workflow_id:
        clauses.append("workflow_id = %s")
        args.append(workflow_id)
    if needs_review_only:
        clauses.append(
            """(
            classification_status = 'failed'
            OR response_classification = 'insufficient_to_classify'
            OR recommended_next_action = ANY(%s)
        )"""
        )
        args.append(list(MANUAL_REVIEW_ACTIONS))

    sql = f"""
        SELECT response_id::text AS response_id, workflow_id::text AS workflow_id, user_id,
               source_type, response_channel, received_at,
               classification_status, response_classification,
               classification_reasoning_safe, classification_confidence,
               recommended_next_action, escalation_recommendation,
               created_at
        FROM workflow_response_intake
        WHERE {' AND '.join(clauses)}
        ORDER BY received_at DESC NULLS LAST, created_at DESC
        LIMIT %s OFFSET %s
    """
    args.extend([limit, offset])
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(sql, tuple(args))
        rows = [dict(r) for r in cur.fetchall()]
    for d in rows:
        v = d.get("escalation_recommendation")
        if isinstance(v, str):
            try:
                d["escalation_recommendation"] = json.loads(v)
            except Exception:
                d["escalation_recommendation"] = {}
    return rows


def list_admin_audit(
    *,
    workflow_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    clauses = ["1=1"]
    args: List[Any] = []
    if workflow_id:
        clauses.append("workflow_id = %s")
        args.append(workflow_id)
    sql = f"""
        SELECT audit_id::text AS audit_id, workflow_id::text AS workflow_id, user_id,
               actor_source, action_type, reason_safe,
               payload_before, payload_after, reminder_id::text AS reminder_id,
               response_id::text AS response_id, created_at
        FROM workflow_admin_audit
        WHERE {' AND '.join(clauses)}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    args.extend([limit, offset])
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(sql, tuple(args))
        rows = [dict(r) for r in cur.fetchall()]
    for d in rows:
        for k in ("payload_before", "payload_after"):
            v = d.get(k)
            if isinstance(v, str):
                try:
                    d[k] = json.loads(v)
                except Exception:
                    d[k] = {}
    return rows


def distinct_workflow_ids_for_exceptions(limit: int = 300) -> List[str]:
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT workflow_id::text AS workflow_id FROM (
                SELECT DISTINCT workflow_id FROM workflow_steps WHERE status = 'failed'
                UNION
                SELECT workflow_id FROM workflow_sessions WHERE overall_status = 'failed'
                UNION
                SELECT workflow_id FROM workflow_reminders WHERE status = 'failed'
            ) x
            LIMIT %s
            """,
            (limit,),
        )
        return [r["workflow_id"] for r in cur.fetchall()]


def fetch_steps_for_workflow(workflow_id: str) -> List[Dict[str, Any]]:
    from services.workflow.repository import fetch_steps

    return fetch_steps(workflow_id)


def has_failed_reminder(workflow_id: str) -> bool:
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            SELECT 1 FROM workflow_reminders
            WHERE workflow_id = %s AND status = 'failed'
            LIMIT 1
            """,
            (workflow_id,),
        )
        return cur.fetchone() is not None
