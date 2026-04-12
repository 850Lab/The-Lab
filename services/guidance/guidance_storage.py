"""
Persist O.R.I.O.N. emissions to ``guidance_events`` (append-only audit).

V1.1: rule_key, delivery metadata, display_eligible, recommended_action JSON.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.guidance.guidance_response_model import GuidanceResponse
from services.workflow.workflow_db import get_workflow_db
from services.workflow.workflow_db_config import should_use_workflow_sqlite

_log = logging.getLogger(__name__)


def fetch_latest_guidance_row(workflow_id: str) -> Optional[dict]:
    """Most recent row for workflow (debug / tests)."""
    wf = (workflow_id or "").strip()
    if not wf:
        return None
    try:
        with get_workflow_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                """
                SELECT id, user_id, workflow_id, step_id, guidance_type, priority,
                       message, trigger_source, suggested_actions, created_at,
                       rule_key, display_eligible, delivery_channel, cooldown_seconds,
                       recommended_action
                FROM guidance_events
                WHERE workflow_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (wf,),
            )
            row = cur.fetchone()
    except Exception:
        return None
    if not row:
        return None
    return dict(row) if not isinstance(row, dict) else row


def _json(val: Any) -> str:
    return json.dumps(val) if not isinstance(val, str) else val


def seconds_since_last_display_eligible(workflow_id: str, rule_key: str) -> Optional[float]:
    """
    Seconds since last display-eligible row for this workflow + rule_key.
    None if no prior display-eligible emission.
    """
    wf = (workflow_id or "").strip()
    rk = (rule_key or "").strip()
    if not wf or not rk:
        return None
    de_pred = "display_eligible = 1" if should_use_workflow_sqlite() else "display_eligible IS TRUE"
    try:
        with get_workflow_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                f"""
                SELECT created_at FROM guidance_events
                WHERE workflow_id = %s AND rule_key = %s AND {de_pred}
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (wf, rk),
            )
            row = cur.fetchone()
    except Exception:
        _log.debug("seconds_since_last_display_eligible failed", exc_info=True)
        return None
    if not row:
        return None
    d = dict(row) if not isinstance(row, dict) else row
    created = d.get("created_at")
    ts = _parse_dt(created)
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())


def _parse_dt(created: Any) -> Optional[datetime]:
    if created is None:
        return None
    if isinstance(created, datetime):
        return created if created.tzinfo else created.replace(tzinfo=timezone.utc)
    if isinstance(created, str):
        try:
            s = created.replace("Z", "+00:00") if created.endswith("Z") else created
            return datetime.fromisoformat(s)
        except Exception:
            return None
    return None


def _row_to_audit_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    raw_rec = row.get("recommended_action")
    if isinstance(raw_rec, str):
        try:
            rec = json.loads(raw_rec)
        except Exception:
            rec = None
    else:
        rec = raw_rec
    raw_sug = row.get("suggested_actions")
    if isinstance(raw_sug, str):
        try:
            sug = json.loads(raw_sug)
        except Exception:
            sug = []
    elif isinstance(raw_sug, list):
        sug = raw_sug
    else:
        sug = []
    ts = _parse_dt(row.get("created_at"))
    ts_s = ts.isoformat() if ts else str(row.get("created_at") or "")
    de = row.get("display_eligible")
    display_eligible = bool(de) if de is not None else False
    return {
        "guidanceId": str(row.get("id", "")),
        "ruleKey": row.get("rule_key") or row.get("trigger_source"),
        "type": row.get("guidance_type"),
        "message": row.get("message"),
        "stepId": row.get("step_id"),
        "priority": int(row.get("priority") or 0),
        "triggerSource": row.get("trigger_source"),
        "timestamp": ts_s,
        "displayEligible": display_eligible,
        "deliveryChannel": row.get("delivery_channel") or "inline",
        "cooldownSeconds": int(row.get("cooldown_seconds") or 0),
        "recommendedAction": rec if isinstance(rec, dict) else None,
        "suggestedActions": [str(x) for x in sug] if isinstance(sug, list) else [],
    }


def list_guidance_events_for_workflow(
    workflow_id: str,
    *,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Operator/admin: recent ORION rows for a workflow."""
    wf = (workflow_id or "").strip()
    if not wf:
        return []
    cap = max(1, min(200, limit))
    try:
        with get_workflow_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                """
                SELECT id, user_id, workflow_id, step_id, guidance_type, priority, message,
                       trigger_source, rule_key, suggested_actions, created_at,
                       display_eligible, delivery_channel, cooldown_seconds, recommended_action
                FROM guidance_events
                WHERE workflow_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (wf, cap),
            )
            rows = cur.fetchall()
    except Exception:
        _log.warning("list_guidance_events_for_workflow failed wf=%s", wf, exc_info=True)
        return []
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        item = _row_to_audit_dict(d)
        item["userId"] = d.get("user_id")
        item["workflowId"] = str(d.get("workflow_id", ""))
        out.append(item)
    return out


def list_guidance_events_for_user(
    user_id: int,
    *,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Operator/admin: recent ORION rows for a user across workflows."""
    cap = max(1, min(200, limit))
    if user_id < 1:
        return []
    try:
        with get_workflow_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                """
                SELECT id, user_id, workflow_id, step_id, guidance_type, priority, message,
                       trigger_source, rule_key, suggested_actions, created_at,
                       display_eligible, delivery_channel, cooldown_seconds, recommended_action
                FROM guidance_events
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (user_id, cap),
            )
            rows = cur.fetchall()
    except Exception:
        _log.warning("list_guidance_events_for_user failed uid=%s", user_id, exc_info=True)
        return []
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        item = _row_to_audit_dict(d)
        item["userId"] = d.get("user_id")
        item["workflowId"] = str(d.get("workflow_id", ""))
        out.append(item)
    return out


def persist_guidance_event(
    *,
    user_id: int,
    workflow_id: str,
    response: GuidanceResponse,
) -> Optional[str]:
    """Insert one guidance row (audit). Always logs when caller invokes (V1.1)."""
    wf = (workflow_id or "").strip()
    if not wf or user_id < 1:
        return None

    gid = str(response.guidance_id or uuid.uuid4())
    de_val: Any = (1 if response.display_eligible else 0) if should_use_workflow_sqlite() else bool(
        response.display_eligible
    )
    rec_json = _json(response.recommended_action) if response.recommended_action else "{}"

    try:
        with get_workflow_db() as (conn, cur):
            cur.execute(
                """
                INSERT INTO guidance_events (
                    id, user_id, workflow_id, step_id, guidance_type, priority,
                    message, trigger_source, suggested_actions,
                    rule_key, display_eligible, delivery_channel, cooldown_seconds,
                    recommended_action
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                        %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    gid,
                    user_id,
                    wf,
                    (response.step_id or "")[:64] or None,
                    (response.type or "nudge")[:32],
                    int(response.priority),
                    response.message[:8000],
                    (response.trigger_source or "")[:120],
                    _json(response.suggested_actions),
                    (response.rule_key or "")[:120],
                    de_val,
                    (response.delivery_channel or "inline")[:24],
                    int(response.cooldown_seconds),
                    rec_json,
                ),
            )
            conn.commit()
    except Exception:
        _log.warning(
            "guidance_events insert failed wf=%s user=%s", wf, user_id, exc_info=True
        )
        return None
    return gid
