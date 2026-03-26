"""
Multi-bureau mail completion: only finish workflow `mail` (and `track`) when all
expected bureau sends have succeeded.

Expected count is stored on workflow_sessions.metadata.mail.expected_unique_bureau_sends
(default 1). Confirmed bureaus live in metadata.mail.confirmed_bureaus (lowercase keys).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple

from services.workflow.repository import fetch_session, update_session_fields


def _norm_bureau(b: str) -> str:
    return (b or "").strip().lower()[:32]


def get_mail_gate_state(metadata: Any) -> Tuple[int, List[str], int]:
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    mail = metadata.get("mail") or {}
    if not isinstance(mail, dict):
        mail = {}
    expected = int(mail.get("expected_unique_bureau_sends") or 1)
    expected = max(1, min(expected, 12))
    raw = mail.get("confirmed_bureaus") or []
    confirmed: List[str] = []
    if isinstance(raw, list):
        confirmed = [str(x).lower()[:32] for x in raw if x]
    try:
        failed_send_count = int(mail.get("failed_send_count") or 0)
    except (TypeError, ValueError):
        failed_send_count = 0
    failed_send_count = max(0, min(failed_send_count, 99))
    return expected, confirmed, failed_send_count


def should_complete_mail_after_send(
    workflow_id: str,
    bureau: str,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Record this bureau as mailed; return (True, patch) if mail+track should complete now.
    """
    session = fetch_session(workflow_id)
    if not session:
        return False, {}
    meta = session.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    expected, confirmed_list, failed_send_count = get_mail_gate_state(meta)
    confirmed: Set[str] = set(confirmed_list)
    b = _norm_bureau(bureau)
    if b:
        confirmed.add(b)
    confirmed_list_out = sorted(confirmed)
    successful_send_count = len(confirmed)
    done = successful_send_count >= expected
    patch = {
        "mail": {
            "expected_unique_bureau_sends": expected,
            "confirmed_bureaus": confirmed_list_out,
            "successful_send_count": successful_send_count,
            "failed_send_count": failed_send_count,
            "completed_all_sends": done,
        }
    }
    return done, patch


def record_mail_attempt_failed(
    workflow_id: str,
    *,
    error_code: str = "",
    message_safe: str = "",
) -> None:
    """Increment failed_send_count and store last failure hints (truthful partial state)."""
    session = fetch_session(workflow_id)
    if not session:
        return
    meta = session.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    if not isinstance(meta, dict):
        meta = {}
    mail = dict(meta.get("mail") or {}) if isinstance(meta.get("mail"), dict) else {}
    try:
        fc = int(mail.get("failed_send_count") or 0) + 1
    except (TypeError, ValueError):
        fc = 1
    mail["failed_send_count"] = min(fc, 99)
    if error_code:
        mail["last_failure_error_code"] = str(error_code)[:64]
    if message_safe:
        mail["last_failure_message_safe"] = str(message_safe)[:400]
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db() as (conn, cur):
        update_session_fields(conn, cur, workflow_id, metadata_patch={"mail": mail})
        conn.commit()


def apply_mail_progress_metadata(workflow_id: str, metadata_patch: Dict[str, Any]) -> None:
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db() as (conn, cur):
        update_session_fields(conn, cur, workflow_id, metadata_patch=metadata_patch)
        conn.commit()
