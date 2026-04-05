"""
Durable workflow event log (observability foundation).

All inserts MUST go through this module — no direct INSERT INTO workflow_events elsewhere.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.workflow.workflow_db import get_workflow_db

_log = logging.getLogger(__name__)


def _coerce_json_field(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def _json_val(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return json.dumps(v)


def _ts_iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def record_event_tx(
    conn,
    cur,
    workflow_id: str,
    event_type: str,
    *,
    step_id: Optional[str] = None,
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
    actor: str = "system",
    source: str = "engine",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert one row in the caller's transaction (Postgres or SQLite workflow DB)."""
    meta = metadata if isinstance(metadata, dict) else {}
    et = (event_type or "").strip()[:80] or "unknown"
    act = (actor or "system").strip()[:64] or "system"
    src = (source or "engine").strip()[:64] or "engine"
    sid = (step_id or "").strip()[:64] or None
    if not sid:
        sid = None
    eid = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO workflow_events (
            id, workflow_id, event_type, step_id,
            previous_state, new_state, actor, source, metadata
        )
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb)
        """,
        (
            eid,
            workflow_id,
            et,
            sid,
            _json_val(previous_state),
            _json_val(new_state),
            act,
            src,
            _json_val(meta),
        ),
    )


def record_event(
    workflow_id: str,
    event_type: str,
    *,
    step_id: Optional[str] = None,
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
    actor: str = "system",
    source: str = "engine",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Standalone insert + commit."""
    try:
        with get_workflow_db() as (conn, cur):
            record_event_tx(
                conn,
                cur,
                workflow_id,
                event_type,
                step_id=step_id,
                previous_state=previous_state,
                new_state=new_state,
                actor=actor,
                source=source,
                metadata=metadata,
            )
            conn.commit()
    except Exception:
        _log.warning(
            "workflow event insert failed wf=%s type=%s", workflow_id, event_type, exc_info=True
        )


def record_transition(
    workflow_id: str,
    transition_kind: str,
    *,
    step_id: Optional[str] = None,
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
    actor: str = "system",
    source: str = "engine",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Convenience: event_type ``transition.<kind>`` (standalone transaction)."""
    kind = (transition_kind or "").strip()[:64] or "unknown"
    record_event(
        workflow_id,
        f"transition.{kind}",
        step_id=step_id,
        previous_state=previous_state,
        new_state=new_state,
        actor=actor,
        source=source,
        metadata=metadata,
    )


def record_system_event(
    workflow_id: str,
    event_type: str,
    *,
    step_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    actor: str = "system",
    source: str = "system",
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
) -> None:
    """High-level system/product events (demo, letters, plans, etc.)."""
    record_event(
        workflow_id,
        event_type,
        step_id=step_id,
        previous_state=previous_state,
        new_state=new_state,
        actor=actor,
        source=source,
        metadata=metadata,
    )


def list_workflow_events(
    workflow_id: str,
    *,
    limit: int = 500,
    oldest_first: bool = True,
) -> List[Dict[str, Any]]:
    """Return serialized rows for admin read APIs."""
    cap = max(1, min(2000, limit))
    order = "ASC" if oldest_first else "DESC"
    out: List[Dict[str, Any]] = []
    try:
        with get_workflow_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                f"""
                SELECT id, workflow_id, event_type, step_id,
                       previous_state, new_state, actor, source, metadata, created_at
                FROM workflow_events
                WHERE workflow_id = %s
                ORDER BY created_at {order}, id {order}
                LIMIT %s
                """,
                (workflow_id, cap),
            )
            rows = cur.fetchall()
    except Exception:
        _log.warning("list_workflow_events failed wf=%s", workflow_id, exc_info=True)
        return []

    for r in rows:
        if isinstance(r, dict):
            d = r
        elif hasattr(r, "keys"):
            d = {k: r[k] for k in r.keys()}
        else:
            d = dict(r)
        meta_raw = d.get("metadata")
        meta = _coerce_json_field(meta_raw)
        if not isinstance(meta, dict):
            meta = {}
        out.append(
            {
                "id": str(d.get("id", "")),
                "workflowId": str(d.get("workflow_id", "")),
                "eventType": d.get("event_type"),
                "stepId": d.get("step_id"),
                "previousState": _coerce_json_field(d.get("previous_state")),
                "newState": _coerce_json_field(d.get("new_state")),
                "actor": d.get("actor"),
                "source": d.get("source"),
                "metadata": meta,
                "createdAt": _ts_iso(d.get("created_at")),
            }
        )
    return out
