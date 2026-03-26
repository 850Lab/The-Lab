"""
Persistence for workflow_sessions and workflow_steps (Postgres or SQLite dev).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.workflow.registry import (
    DEFINITION_VERSION,
    ENGINE_VERSION,
    LINEAR_STEP_ORDER,
    WORKFLOW_TYPE_DEFAULT,
)

_UNSET = object()


def _uuid_str(u: Any) -> str:
    if isinstance(u, uuid.UUID):
        return str(u)
    return str(u)


def fetch_session(workflow_id: str) -> Optional[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT workflow_id, user_id, workflow_type, current_step, overall_status,
                   started_at, updated_at, completed_at,
                   last_error_code, last_error_message_safe, metadata,
                   definition_version, engine_version
            FROM workflow_sessions
            WHERE workflow_id = %s
            """,
            (workflow_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    meta = d.get("metadata")
    if isinstance(meta, str):
        try:
            d["metadata"] = json.loads(meta)
        except Exception:
            d["metadata"] = {}
    return d


def fetch_steps(workflow_id: str) -> List[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    order = {s: i for i, s in enumerate(LINEAR_STEP_ORDER)}
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT workflow_step_id, workflow_id, step_id, status, attempt_count,
                   started_at, completed_at, failed_at,
                   last_error_code, last_error_message_safe,
                   completion_payload_summary, async_task_state
            FROM workflow_steps
            WHERE workflow_id = %s
            """,
            (workflow_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    rows.sort(key=lambda r: order.get(r["step_id"], 999))
    return rows


def fetch_latest_active_workflow_id(
    user_id: int,
    workflow_type: Optional[str] = None,
) -> Optional[str]:
    """Most recently touched active/failed workflow for user (not completed)."""
    from services.workflow.workflow_db import get_workflow_db

    wt = workflow_type or WORKFLOW_TYPE_DEFAULT
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT workflow_id AS workflow_id
            FROM workflow_sessions
            WHERE user_id = %s AND workflow_type = %s
              AND overall_status IN ('active', 'failed')
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (user_id, wt),
        )
        row = cur.fetchone()
    return row["workflow_id"] if row else None


def create_workflow_with_steps(
    *,
    user_id: int,
    workflow_type: str,
    metadata: Optional[Dict[str, Any]] = None,
    first_step_id: str,
    overall_status: str = "active",
) -> str:
    """Atomically create session + all step rows (single transaction)."""
    from services.workflow.workflow_db import get_workflow_db

    meta = metadata or {}
    wid = str(uuid.uuid4())
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_sessions (
                workflow_id, user_id, workflow_type, current_step, overall_status,
                metadata, definition_version, engine_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                wid,
                user_id,
                workflow_type,
                first_step_id,
                overall_status,
                json.dumps(meta),
                DEFINITION_VERSION,
                ENGINE_VERSION,
            ),
        )
        seed_steps_for_workflow(conn, cur, wid, first_step_id)
        conn.commit()
    return wid


def ensure_active_workflow_id(
    user_id: int,
    workflow_type: Optional[str] = None,
) -> str:
    """Return existing active/failed workflow id or create a new session + steps."""
    wid = fetch_latest_active_workflow_id(user_id, workflow_type)
    if wid:
        return wid
    wt = workflow_type or WORKFLOW_TYPE_DEFAULT
    first = LINEAR_STEP_ORDER[0]
    return create_workflow_with_steps(
        user_id=user_id,
        workflow_type=wt,
        metadata={},
        first_step_id=first,
    )


def insert_step_row(
    conn,
    cur,
    *,
    workflow_id: str,
    step_id: str,
    status: str,
) -> None:
    cur.execute(
        """
        INSERT INTO workflow_steps (workflow_step_id, workflow_id, step_id, status)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (workflow_id, step_id) DO NOTHING
        """,
        (str(uuid.uuid4()), workflow_id, step_id, status),
    )


def seed_steps_for_workflow(conn, cur, workflow_id: str, first_available: str) -> None:
    for sid in LINEAR_STEP_ORDER:
        st = "available" if sid == first_available else "not_started"
        insert_step_row(conn, cur, workflow_id=workflow_id, step_id=sid, status=st)


def update_session_fields(
    conn,
    cur,
    workflow_id: str,
    *,
    current_step: Any = _UNSET,
    overall_status: Any = _UNSET,
    completed_at: Any = _UNSET,
    last_error_code: Any = _UNSET,
    last_error_message_safe: Any = _UNSET,
    metadata_patch: Optional[Dict[str, Any]] = None,
) -> None:
    parts = ["updated_at = CURRENT_TIMESTAMP"]
    args: List[Any] = []
    if current_step is not _UNSET:
        parts.append("current_step = %s")
        args.append(current_step)
    if overall_status is not _UNSET:
        parts.append("overall_status = %s")
        args.append(overall_status)
    if completed_at is not _UNSET:
        parts.append("completed_at = %s")
        args.append(completed_at)
    if last_error_code is not _UNSET:
        parts.append("last_error_code = %s")
        args.append(last_error_code)
    if last_error_message_safe is not _UNSET:
        parts.append("last_error_message_safe = %s")
        args.append(last_error_message_safe)
    if metadata_patch:
        from services.workflow.workflow_db_config import should_use_workflow_sqlite

        if should_use_workflow_sqlite():
            cur.execute(
                "SELECT metadata FROM workflow_sessions WHERE workflow_id = %s",
                (workflow_id,),
            )
            row = cur.fetchone()
            mraw = row[0] if row else "{}"
            if isinstance(mraw, dict):
                merged = dict(mraw)
            else:
                try:
                    merged = json.loads(mraw or "{}")
                except Exception:
                    merged = {}
            if not isinstance(merged, dict):
                merged = {}
            merged.update(metadata_patch)
            parts.append("metadata = %s")
            args.append(json.dumps(merged))
        else:
            parts.append("metadata = metadata || %s::jsonb")
            args.append(json.dumps(metadata_patch))
    args.append(workflow_id)
    cur.execute(
        f"UPDATE workflow_sessions SET {', '.join(parts)} WHERE workflow_id = %s",
        tuple(args),
    )


def update_step_fields(
    conn,
    cur,
    workflow_id: str,
    step_id: str,
    *,
    status: Optional[str] = None,
    attempt_count_delta: int = 0,
    started_at: Any = False,  # False = skip, None = clear
    completed_at: Any = False,
    failed_at: Any = False,
    last_error_code: Any = _UNSET,
    last_error_message_safe: Any = _UNSET,
    completion_payload_summary: Optional[Dict[str, Any]] = None,
    async_task_state: Any = False,
) -> None:
    sets = []
    args: List[Any] = []
    if status is not None:
        sets.append("status = %s")
        args.append(status)
    if attempt_count_delta:
        sets.append("attempt_count = attempt_count + %s")
        args.append(attempt_count_delta)
    if started_at is not False:
        sets.append("started_at = %s")
        args.append(started_at)
    if completed_at is not False:
        sets.append("completed_at = %s")
        args.append(completed_at)
    if failed_at is not False:
        sets.append("failed_at = %s")
        args.append(failed_at)
    if last_error_code is not _UNSET:
        sets.append("last_error_code = %s")
        args.append(last_error_code)
    if last_error_message_safe is not _UNSET:
        sets.append("last_error_message_safe = %s")
        args.append(last_error_message_safe)
    if completion_payload_summary is not None:
        sets.append("completion_payload_summary = %s")
        args.append(json.dumps(completion_payload_summary))
    if async_task_state is not False:
        sets.append("async_task_state = %s")
        args.append(
            json.dumps(async_task_state) if async_task_state is not None else None
        )
    if not sets:
        return
    args.extend([workflow_id, step_id])
    cur.execute(
        f"""
        UPDATE workflow_steps
        SET {", ".join(sets)}
        WHERE workflow_id = %s AND step_id = %s
        """,
        tuple(args),
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
