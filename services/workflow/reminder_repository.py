"""
Persistence for workflow_reminders and workflow_admin_audit.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

REMINDER_STATUSES = frozenset(
    {"eligible", "queued", "sent", "skipped", "failed"}
)


def _uuid_str(u: Any) -> str:
    if isinstance(u, uuid.UUID):
        return str(u)
    return str(u)


def has_active_or_recent_reminder(
    workflow_id: str,
    reminder_type: str,
    *,
    cooldown_hours: int = 48,
) -> bool:
    """Dedupe: block if eligible/queued exists, or same type sent within cooldown."""
    from services.workflow.workflow_db import get_workflow_db
    from services.workflow.workflow_db_config import should_use_workflow_sqlite

    rt = reminder_type[:64]
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            SELECT 1 FROM workflow_reminders
            WHERE workflow_id = %s AND reminder_type = %s
              AND status IN ('eligible', 'queued')
            LIMIT 1
            """,
            (workflow_id, rt),
        )
        if cur.fetchone():
            return True
        if should_use_workflow_sqlite():
            cur.execute(
                """
                SELECT 1 FROM workflow_reminders
                WHERE workflow_id = %s AND reminder_type = %s
                  AND status = 'sent'
                  AND sent_at IS NOT NULL
                  AND datetime(sent_at) > datetime('now', ?)
                LIMIT 1
                """,
                (workflow_id, rt, f"-{int(cooldown_hours)} hours"),
            )
        else:
            cur.execute(
                """
                SELECT 1 FROM workflow_reminders
                WHERE workflow_id = %s AND reminder_type = %s
                  AND status = 'sent'
                  AND sent_at IS NOT NULL
                  AND sent_at > NOW() - CAST(%s AS INTERVAL)
                LIMIT 1
                """,
                (workflow_id, rt, f"{int(cooldown_hours)} hours"),
            )
        return bool(cur.fetchone())


def insert_reminder(
    *,
    workflow_id: str,
    user_id: int,
    reminder_type: str,
    reason: str,
    payload_summary: Dict[str, Any],
    delivery_channel: Optional[str] = None,
    eligible_at: Optional[datetime] = None,
) -> str:
    from services.workflow.workflow_db import get_workflow_db

    ps = json.dumps(payload_summary or {})
    rid = str(uuid.uuid4())
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_reminders (
                reminder_id, workflow_id, user_id, reminder_type, reason, eligible_at,
                status, delivery_channel, payload_summary
            )
            VALUES (%s, %s, %s, %s, %s, COALESCE(%s, CURRENT_TIMESTAMP),
                    'eligible', %s, %s)
            """,
            (
                rid,
                workflow_id,
                user_id,
                reminder_type[:64],
                (reason or "")[:2000],
                eligible_at,
                (delivery_channel or "")[:32] or None,
                ps,
            ),
        )
        conn.commit()
    return rid


def update_reminder_status(
    reminder_id: str,
    *,
    status: str,
    sent_at: Any = False,
    delivery_channel: Any = False,
    payload_patch: Optional[Dict[str, Any]] = None,
) -> None:
    from services.workflow.workflow_db import get_workflow_db
    from services.workflow.workflow_db_config import should_use_workflow_sqlite

    st = status[:24]
    sets = ["status = %s", "updated_at = CURRENT_TIMESTAMP"]
    args: List[Any] = [st]
    if sent_at is not False:
        sets.append("sent_at = %s")
        args.append(sent_at)
    if delivery_channel is not False:
        sets.append("delivery_channel = %s")
        args.append(delivery_channel)
    if payload_patch:
        if should_use_workflow_sqlite():
            with get_workflow_db(dict_cursor=True) as (conn, cur):
                cur.execute(
                    "SELECT payload_summary FROM workflow_reminders WHERE reminder_id = %s",
                    (reminder_id,),
                )
                row = cur.fetchone()
                praw = row["payload_summary"] if row else "{}"
                if isinstance(praw, dict):
                    merged = dict(praw)
                else:
                    try:
                        merged = json.loads(praw or "{}")
                    except Exception:
                        merged = {}
                if not isinstance(merged, dict):
                    merged = {}
                merged.update(payload_patch)
                sets.append("payload_summary = %s")
                args.append(json.dumps(merged))
        else:
            sets.append("payload_summary = payload_summary || %s::jsonb")
            args.append(json.dumps(payload_patch))
    args.append(reminder_id)
    with get_workflow_db() as (conn, cur):
        cur.execute(
            f"UPDATE workflow_reminders SET {', '.join(sets)} WHERE reminder_id = %s",
            tuple(args),
        )
        conn.commit()


def fetch_reminder(reminder_id: str) -> Optional[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT reminder_id::text AS reminder_id, workflow_id::text AS workflow_id, user_id,
                   reminder_type, reason, eligible_at, sent_at, status, delivery_channel,
                   payload_summary, created_at, updated_at
            FROM workflow_reminders
            WHERE reminder_id = %s
            """,
            (reminder_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    v = d.get("payload_summary")
    if isinstance(v, str):
        try:
            d["payload_summary"] = json.loads(v)
        except Exception:
            d["payload_summary"] = {}
    return d


def list_reminders_for_workflow(
    workflow_id: str,
    *,
    statuses: Optional[List[str]] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    statuses = statuses or ["eligible", "queued", "sent", "skipped", "failed"]
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT reminder_id::text AS reminder_id, reminder_type, reason, status,
                   eligible_at, sent_at, delivery_channel, payload_summary, created_at
            FROM workflow_reminders
            WHERE workflow_id = %s AND status = ANY(%s)
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (workflow_id, statuses, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
    for d in rows:
        v = d.get("payload_summary")
        if isinstance(v, str):
            try:
                d["payload_summary"] = json.loads(v)
            except Exception:
                d["payload_summary"] = {}
    return rows


def list_queued_reminders(limit: int = 100) -> List[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT reminder_id::text AS reminder_id, workflow_id::text AS workflow_id, user_id,
                   reminder_type, reason, eligible_at, sent_at, delivery_channel, payload_summary
            FROM workflow_reminders
            WHERE status = 'queued'
            ORDER BY updated_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    for d in rows:
        v = d.get("payload_summary")
        if isinstance(v, str):
            try:
                d["payload_summary"] = json.loads(v)
            except Exception:
                d["payload_summary"] = {}
    return rows


def list_eligible_reminders(limit: int = 100) -> List[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT reminder_id::text AS reminder_id, workflow_id::text AS workflow_id, user_id,
                   reminder_type, reason, eligible_at, payload_summary
            FROM workflow_reminders
            WHERE status = 'eligible' AND eligible_at <= CURRENT_TIMESTAMP
            ORDER BY eligible_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    for d in rows:
        v = d.get("payload_summary")
        if isinstance(v, str):
            try:
                d["payload_summary"] = json.loads(v)
            except Exception:
                d["payload_summary"] = {}
    return rows


def insert_admin_audit(
    *,
    workflow_id: Optional[str],
    user_id: Optional[int],
    actor_source: str,
    action_type: str,
    reason_safe: str,
    payload_before: Optional[Dict[str, Any]],
    payload_after: Optional[Dict[str, Any]],
    reminder_id: Optional[str] = None,
    response_id: Optional[str] = None,
) -> str:
    from services.workflow.workflow_db import get_workflow_db

    aid = str(uuid.uuid4())
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_admin_audit (
                audit_id, workflow_id, user_id, actor_source, action_type, reason_safe,
                payload_before, payload_after, reminder_id, response_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                aid,
                workflow_id,
                user_id,
                actor_source[:128],
                action_type[:64],
                (reason_safe or "")[:4000],
                json.dumps(payload_before or {}),
                json.dumps(payload_after or {}),
                reminder_id,
                response_id,
            ),
        )
        conn.commit()
    return aid


def merge_session_admin_override_metadata(
    workflow_id: str,
    entry: Dict[str, Any],
) -> None:
    """Append one entry to metadata.adminOverrideHistory (bounded)."""
    from services.workflow.repository import fetch_session, update_session_fields

    from services.workflow.workflow_db import get_workflow_db

    session = fetch_session(workflow_id)
    if not session:
        return
    meta = session.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    hist = list(meta.get("adminOverrideHistory") or [])
    if not isinstance(hist, list):
        hist = []
    hist.append(entry)
    with get_workflow_db() as (conn, cur):
        update_session_fields(
            conn,
            cur,
            workflow_id,
            metadata_patch={
                "adminOverrideHistory": hist[-25:],
                "adminOverridePresent": True,
            },
        )
        conn.commit()
