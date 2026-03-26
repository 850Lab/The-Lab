"""
Stalled-workflow detection, wait attribution, failed-step re-entry hints, reminder flags.

No outbound notifications here — only derived state for later schedulers and UI.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.workflow import registry as reg


FAILED_RETRYABLE_STEPS = frozenset(
    {
        "upload",
        "parse_analyze",
        "payment",
        "letter_generation",
        "proof_attachment",
        "mail",
        "track",
    }
)


def _parse_ts(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            # ISO from DB or API
            if val.endswith("Z"):
                val = val[:-1] + "+00:00"
            return datetime.fromisoformat(val)
        except Exception:
            return None
    return None


def _step_row(steps_map: Dict[str, Dict[str, Any]], step_id: str) -> Optional[Dict[str, Any]]:
    return steps_map.get(step_id)


def compute_waiting_attribution(
    head_step_id: Optional[str],
    head_status: Optional[str],
    steps_map: Dict[str, Dict[str, Any]],
) -> str:
    """
    waiting_on_user: linear head is available/failed (user can act).
    waiting_on_system: head in_progress (backend/async expected).
    waiting_on_external: track completed, no classification yet (bureau clock).
    none: completed or unknown.
    """
    if not head_step_id:
        track = _step_row(steps_map, "track")
        if track and track.get("status") == "completed":
            return "waiting_on_external"
        return "none"

    if head_status in ("available", "failed"):
        return "waiting_on_user"
    if head_status == "in_progress":
        return "waiting_on_system"
    return "none"


def compute_stalled(
    *,
    session: Dict[str, Any],
    steps_map: Dict[str, Dict[str, Any]],
    latest_response_received_at: Optional[datetime],
    now: Optional[datetime] = None,
    track_grace_days: int = 45,
    in_progress_stall_days: int = 7,
) -> Tuple[bool, List[str]]:
    """
    Heuristic stall signals (conservative; multiple flags can apply).
    """
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []

    head_id = None
    for sid in reg.LINEAR_STEP_ORDER:
        row = steps_map.get(sid)
        if not row:
            continue
        if row["status"] != "completed":
            head_id = sid
            break

    if head_id:
        row = steps_map[head_id]
        st = row.get("status")
        started = _parse_ts(row.get("started_at"))
        if st == "in_progress" and started and (now - started).days >= in_progress_stall_days:
            reasons.append("head_step_in_progress_too_long")

    track = _step_row(steps_map, "track")
    if track and track.get("status") == "completed":
        completed = _parse_ts(track.get("completed_at"))
        if completed and not latest_response_received_at:
            if (now - completed).days >= track_grace_days:
                reasons.append("no_bureau_response_after_track_window")

    updated = _parse_ts(session.get("updated_at"))
    if updated and session.get("overall_status") == "active" and head_id:
        if (now - updated).days >= max(track_grace_days, 60):
            reasons.append("session_idle_extended")

    return bool(reasons), reasons


def compute_reminder_eligibility(
    *,
    waiting_on: str,
    stalled: bool,
    failed_step_id: Optional[str],
    head_status: Optional[str],
    head_step_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Flags for a future notification worker (no sends here).
    """
    hid = head_step_id or ""
    return {
        "nudge_upload": waiting_on == "waiting_on_user"
        and head_status == "available"
        and hid == "upload",
        "nudge_retry_failed": failed_step_id is not None and failed_step_id in FAILED_RETRYABLE_STEPS,
        "nudge_bureau_clock": stalled and waiting_on == "waiting_on_external",
        "nudge_resume_payment": waiting_on == "waiting_on_user"
        and head_status == "available"
        and hid == "payment",
        "nudge_response_upload": waiting_on == "waiting_on_external",
        "eligible": bool(
            stalled
            or (waiting_on == "waiting_on_user" and head_status in ("available", "failed"))
            or waiting_on == "waiting_on_external"
        ),
    }


def failed_step_reentry_eligible(
    steps_map: Dict[str, Dict[str, Any]],
    session_overall: str,
) -> Tuple[Optional[str], bool]:
    if session_overall != "failed":
        return None, False
    for sid in reg.LINEAR_STEP_ORDER:
        row = steps_map.get(sid)
        if row and row.get("status") == "failed":
            return sid, sid in FAILED_RETRYABLE_STEPS
    return None, False
