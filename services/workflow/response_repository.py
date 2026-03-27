"""
Persistence for workflow_response_intake rows.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


def _uuid_str(u: Any) -> str:
    if isinstance(u, uuid.UUID):
        return str(u)
    return str(u)


def insert_response_intake(
    *,
    workflow_id: str,
    user_id: int,
    source_type: str,
    response_channel: str,
    parsed_summary: Dict[str, Any],
    storage_ref: Optional[str] = None,
    linked_mailing_id: Optional[int] = None,
    linked_letter_id: Optional[int] = None,
    received_at: Optional[datetime] = None,
) -> str:
    from services.workflow.workflow_db import get_workflow_db

    ps = json.dumps(parsed_summary or {})
    rid = str(uuid.uuid4())
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_response_intake (
                response_id, workflow_id, user_id, source_type, response_channel,
                received_at, linked_mailing_id, linked_letter_id,
                storage_ref, parsed_summary, classification_status
            )
            VALUES (%s, %s, %s, %s, %s, COALESCE(%s, CURRENT_TIMESTAMP), %s, %s, %s, %s, 'pending')
            """,
            (
                rid,
                workflow_id,
                user_id,
                source_type[:40],
                response_channel[:40],
                received_at,
                linked_mailing_id,
                linked_letter_id,
                storage_ref,
                ps,
            ),
        )
        conn.commit()
    return rid


def fetch_response_by_id(response_id: str) -> Optional[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT response_id::text AS response_id, workflow_id::text AS workflow_id, user_id,
                   source_type, response_channel, received_at,
                   linked_mailing_id, linked_letter_id, storage_ref,
                   parsed_summary, classification_status, response_classification,
                   classification_reasoning_safe, classification_confidence,
                   recommended_next_action, escalation_recommendation,
                   created_at, updated_at
            FROM workflow_response_intake
            WHERE response_id = %s
            """,
            (response_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    for k in ("parsed_summary", "escalation_recommendation"):
        v = d.get(k)
        if isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except Exception:
                d[k] = {}
    return d


def update_response_classification(
    response_id: str,
    *,
    classification_status: str,
    response_classification: Optional[str],
    classification_reasoning_safe: str,
    classification_confidence: Optional[float],
    recommended_next_action: str,
    escalation_recommendation: Dict[str, Any],
) -> None:
    from services.workflow.workflow_db import get_workflow_db

    esc = json.dumps(escalation_recommendation or {})
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            UPDATE workflow_response_intake
            SET classification_status = %s,
                response_classification = %s,
                classification_reasoning_safe = %s,
                classification_confidence = %s,
                recommended_next_action = %s,
                escalation_recommendation = %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE response_id = %s
            """,
            (
                classification_status[:32],
                response_classification[:64] if response_classification else None,
                classification_reasoning_safe[:4000] if classification_reasoning_safe else None,
                classification_confidence,
                recommended_next_action[:64] if recommended_next_action else None,
                esc,
                response_id,
            ),
        )
        conn.commit()


def fetch_latest_response_for_workflow(workflow_id: str) -> Optional[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT response_id::text AS response_id, workflow_id::text AS workflow_id, user_id,
                   source_type, response_channel, received_at,
                   linked_mailing_id, linked_letter_id, storage_ref,
                   parsed_summary, classification_status, response_classification,
                   classification_reasoning_safe, classification_confidence,
                   recommended_next_action, escalation_recommendation,
                   created_at, updated_at
            FROM workflow_response_intake
            WHERE workflow_id = %s
            ORDER BY received_at DESC, created_at DESC
            LIMIT 1
            """,
            (workflow_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    for k in ("parsed_summary", "escalation_recommendation"):
        v = d.get(k)
        if isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except Exception:
                d[k] = {}
    return d


def list_response_intake_metric_rows(workflow_id: str) -> List[Dict[str, Any]]:
    """
    Minimal columns for workflow-scoped response metrics (all rows; typically small per workflow).
    """
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT classification_status, escalation_recommendation, received_at,
                   source_type, response_channel, recommended_next_action
            FROM workflow_response_intake
            WHERE workflow_id = %s
            ORDER BY received_at DESC, created_at DESC
            """,
            (workflow_id,),
        )
        rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        v = d.get("escalation_recommendation")
        if isinstance(v, str):
            try:
                d["escalation_recommendation"] = json.loads(v)
            except Exception:
                d["escalation_recommendation"] = {}
        out.append(d)
    return out


def list_responses_detailed_for_workflow(
    workflow_id: str, limit: int = 30
) -> List[Dict[str, Any]]:
    """Full rows for customer / operator UI (JSON fields parsed)."""
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT response_id::text AS response_id, workflow_id::text AS workflow_id, user_id,
                   source_type, response_channel, received_at,
                   linked_mailing_id, linked_letter_id, storage_ref,
                   parsed_summary, classification_status, response_classification,
                   classification_reasoning_safe, classification_confidence,
                   recommended_next_action, escalation_recommendation,
                   created_at, updated_at
            FROM workflow_response_intake
            WHERE workflow_id = %s
            ORDER BY received_at DESC, created_at DESC
            LIMIT %s
            """,
            (workflow_id, limit),
        )
        rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        for k in ("parsed_summary", "escalation_recommendation"):
            v = d.get(k)
            if isinstance(v, str):
                try:
                    d[k] = json.loads(v)
                except Exception:
                    d[k] = {}
        out.append(d)
    return out


def list_responses_for_workflow(workflow_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT response_id::text AS response_id, classification_status, response_classification,
                   received_at, source_type, response_channel
            FROM workflow_response_intake
            WHERE workflow_id = %s
            ORDER BY received_at DESC
            LIMIT %s
            """,
            (workflow_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]
