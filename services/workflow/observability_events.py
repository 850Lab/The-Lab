"""
Unified observability events (Phase 5) — structured, queryable; does not replace workflow_events.

Append-only. Small metadata only; no raw notes or large payloads.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from services.workflow.workflow_db import get_workflow_db

_log = logging.getLogger(__name__)

EVENT_CATEGORIES = frozenset(
    {
        "navigation",
        "input",
        "processing",
        "decision",
        "failure",
        "completion",
    }
)

EVENT_STATUSES = frozenset({"success", "failure", "attempt", "info"})

EVENT_SOURCES = frozenset(
    {"execution_runtime", "workflow", "strategy", "system", "frontend"}
)

_MAX_METADATA_KEYS = 12


def _json_for_db(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return json.dumps(v, separators=(",", ":"))
    return json.dumps(v, separators=(",", ":"))


def _coerce_meta_row(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            o = json.loads(raw)
            return dict(o) if isinstance(o, dict) else {}
        except Exception:
            return {}
    return {}


def sanitize_observability_metadata(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not meta or not isinstance(meta, dict):
        return {}
    out: Dict[str, Any] = {}
    for i, (k, v) in enumerate(meta.items()):
        if i >= _MAX_METADATA_KEYS:
            break
        key = str(k)[:64]
        if isinstance(v, (str, int, float, bool)) or v is None:
            if isinstance(v, str) and len(v) > 256:
                v = v[:256]
            out[key] = v
        elif isinstance(v, list) and len(v) <= 24:
            if all(isinstance(x, str) for x in v):
                out[key] = [str(x)[:64] for x in v[:24]]
            elif all(isinstance(x, int) for x in v):
                out[key] = [int(x) for x in v[:24]]
    return out


def map_workflow_event_type(event_type: str) -> Tuple[str, str, str]:
    """
    Map legacy workflow_events.event_type → (event_name, event_category, status).
    """
    et = (event_type or "unknown").strip()[:80] or "unknown"
    low = et.lower()
    ename = (f"workflow_event:{et}")[:120]
    if low.startswith("transition."):
        return (ename, "navigation", "info")
    if "fail" in low or "error" in low:
        return (ename, "failure", "failure")
    if "complete" in low or "completed" in low or low.endswith(".done"):
        return (ename, "completion", "success")
    if low.startswith("demo.") or "letter" in low or "upload" in low or "parse" in low:
        return (ename, "processing", "success")
    return (ename, "decision", "info")


def fetch_user_id_for_workflow_tx(cur, workflow_id: str) -> Optional[int]:
    cur.execute(
        "SELECT user_id FROM workflow_sessions WHERE workflow_id = %s",
        (str(workflow_id).strip(),),
    )
    row = cur.fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        uid = row.get("user_id")
    else:
        uid = row[0]
    try:
        return int(uid) if uid is not None else None
    except (TypeError, ValueError):
        return None


def insert_observability_event_tx(
    cur,
    *,
    user_id: int,
    workflow_id: str,
    step_id: Optional[str],
    event_name: str,
    event_category: str,
    status: str,
    metadata: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    duration_ms: Optional[int] = None,
    source: str = "system",
) -> None:
    if event_category not in EVENT_CATEGORIES:
        event_category = "decision"
    if status not in EVENT_STATUSES:
        status = "info"
    src = source if source in EVENT_SOURCES else "system"
    eid = str(uuid.uuid4())
    ename = (event_name or "unknown").strip()[:120] or "unknown"
    sid = (step_id or "").strip()[:64] or None
    meta = sanitize_observability_metadata(metadata)
    err = (error_code or "").strip()[:64] or None
    dur = int(duration_ms) if duration_ms is not None else None
    if dur is not None and (dur < 0 or dur > 86_400_000):
        dur = None
    cur.execute(
        """
        INSERT INTO observability_events (
            event_id, user_id, workflow_id, step_id, event_name, event_category,
            status, metadata, error_code, duration_ms, source
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
        """,
        (
            eid,
            int(user_id),
            str(workflow_id).strip(),
            sid,
            ename,
            event_category,
            status,
            _json_for_db(meta),
            err,
            dur,
            src[:64],
        ),
    )


def try_emit_observability_for_workflow_event_tx(
    cur,
    *,
    workflow_id: str,
    event_type: str,
    step_id: Optional[str],
    actor: str,
    source: str,
) -> None:
    """Mirror workflow_events row into observability_events (same transaction)."""
    try:
        uid = fetch_user_id_for_workflow_tx(cur, workflow_id)
        if uid is None:
            return
        ename, cat, st = map_workflow_event_type(event_type)
        meta = {
            "workflow_event_type": (event_type or "")[:120],
            "actor": (actor or "")[:64],
            "workflow_engine_source": (source or "")[:64],
        }
        insert_observability_event_tx(
            cur,
            user_id=uid,
            workflow_id=workflow_id,
            step_id=step_id,
            event_name=ename,
            event_category=cat,
            status=st,
            metadata=meta,
            source="workflow",
        )
    except Exception:
        _log.debug(
            "observability mirror skipped for workflow_event wf=%s type=%s",
            workflow_id,
            event_type,
            exc_info=True,
        )


def emit_observability_event(
    *,
    user_id: int,
    workflow_id: str,
    step_id: Optional[str],
    event_name: str,
    event_category: str,
    status: str,
    metadata: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    duration_ms: Optional[int] = None,
    source: str = "system",
) -> None:
    """Standalone insert + commit (never raises to callers)."""
    try:
        with get_workflow_db() as (conn, cur):
            insert_observability_event_tx(
                cur,
                user_id=user_id,
                workflow_id=workflow_id,
                step_id=step_id,
                event_name=event_name,
                event_category=event_category,
                status=status,
                metadata=metadata,
                error_code=error_code,
                duration_ms=duration_ms,
                source=source,
            )
            conn.commit()
    except Exception:
        _log.warning(
            "observability event insert failed wf=%s name=%s",
            workflow_id,
            event_name,
            exc_info=True,
        )


def list_observability_events(
    *,
    workflow_id: Optional[str] = None,
    user_id: Optional[int] = None,
    step_id: Optional[str] = None,
    event_category: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    cap = max(1, min(2000, int(limit)))
    parts = ["1=1"]
    params: List[Any] = []
    if workflow_id is not None and str(workflow_id).strip():
        parts.append("workflow_id = %s")
        params.append(str(workflow_id).strip())
    if user_id is not None:
        parts.append("user_id = %s")
        params.append(int(user_id))
    if step_id is not None and str(step_id).strip():
        parts.append("step_id = %s")
        params.append(str(step_id).strip()[:64])
    if event_category is not None and str(event_category).strip():
        parts.append("event_category = %s")
        params.append(str(event_category).strip()[:32])
    params.append(cap)
    where = " AND ".join(parts)
    sql = f"""
        SELECT event_id, user_id, workflow_id, step_id, event_name, event_category,
               status, metadata, error_code, duration_ms, source, timestamp
        FROM observability_events
        WHERE {where}
        ORDER BY timestamp DESC, event_id DESC
        LIMIT %s
    """
    out: List[Dict[str, Any]] = []
    try:
        with get_workflow_db(dict_cursor=True) as (conn, cur):
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
    except Exception:
        _log.warning("list_observability_events failed", exc_info=True)
        return []

    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        ts = d.get("timestamp")
        if hasattr(ts, "isoformat"):
            ts_s = ts.isoformat()
        else:
            ts_s = str(ts or "")
        out.append(
            {
                "eventId": str(d.get("event_id", "")),
                "userId": int(d.get("user_id", 0) or 0),
                "workflowId": str(d.get("workflow_id", "")),
                "stepId": d.get("step_id"),
                "eventName": d.get("event_name"),
                "eventCategory": d.get("event_category"),
                "status": d.get("status"),
                "timestamp": ts_s,
                "metadata": _coerce_meta_row(d.get("metadata")),
                "errorCode": d.get("error_code"),
                "durationMs": d.get("duration_ms"),
                "source": d.get("source"),
            }
        )
    return out
