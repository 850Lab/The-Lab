"""
Deterministic O.R.I.O.N. rules. Each returns a uniform evaluation dict.

Rules are explicit, testable, and traceable — no LLM.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict


class RuleEval(TypedDict):
    triggered: bool
    priority: int
    type: str
    message: str
    suggested_actions: List[str]
    trigger_source: str
    rule_key: str


def _empty_rule(rule_key: str) -> RuleEval:
    return {
        "triggered": False,
        "priority": 0,
        "type": "nudge",
        "message": "",
        "suggested_actions": [],
        "trigger_source": rule_key,
        "rule_key": rule_key,
    }


def _parse_ts(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s)
        except Exception:
            return None
    return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def rule_inactivity_over_120s(ctx: Dict[str, Any]) -> RuleEval:
    """No meaningful activity for >120s (session clock + event log)."""
    out = _empty_rule("orion.inactivity_120s")
    session = ctx.get("session") or {}
    events: List[Dict[str, Any]] = list(ctx.get("recent_events") or [])

    last_ts: Optional[datetime] = _parse_ts(session.get("updated_at"))
    for ev in events:
        t = _parse_ts(ev.get("createdAt"))
        if t and (last_ts is None or t > last_ts):
            last_ts = t

    if last_ts is None:
        return out
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)
    idle = (_now_utc() - last_ts).total_seconds()
    if idle <= 120:
        return out

    cur_step = str(session.get("current_step") or "").strip() or "current"
    out["triggered"] = True
    out["priority"] = 75
    out["type"] = "nudge"
    out["message"] = (
        "It's been a couple of minutes — still with us? "
        f"When you're ready, continue with **{cur_step}** or refresh your progress."
    )
    out["suggested_actions"] = [
        "Resume the current step",
        "Refresh workflow state",
    ]
    return out


def rule_repeated_upload_failure(ctx: Dict[str, Any]) -> RuleEval:
    """Upload step: repeated failures (attempts or explicit fail events)."""
    out = _empty_rule("orion.repeated_upload_failure")
    steps_by_id: Dict[str, Dict[str, Any]] = ctx.get("steps_by_id") or {}
    up = steps_by_id.get("upload") or {}
    attempts = int(up.get("attempt_count") or 0)
    fail_events = 0
    for ev in ctx.get("recent_events") or []:
        if str(ev.get("stepId") or "") != "upload":
            continue
        et = str(ev.get("eventType") or "")
        ns = ev.get("newState") if isinstance(ev.get("newState"), dict) else {}
        if et == "step.status" and str(ns.get("status") or "") == "failed":
            fail_events += 1
    if attempts < 3 and fail_events < 3:
        return out

    out["triggered"] = True
    out["priority"] = 95
    out["type"] = "warning"
    out["message"] = (
        "Upload has failed several times. Try a smaller PDF, a different browser, "
        "or check your connection — then try again."
    )
    out["suggested_actions"] = [
        "Retry upload with a different file",
        "Check file size and format (PDF)",
        "Contact support if this keeps happening",
    ]
    return out


def rule_step_opened_no_action(ctx: Dict[str, Any]) -> RuleEval:
    """Step in progress but user idle on it for >90s (started_at vs now)."""
    out = _empty_rule("orion.step_opened_no_action")
    session = ctx.get("session") or {}
    steps_by_id: Dict[str, Dict[str, Any]] = ctx.get("steps_by_id") or {}
    head = str(session.get("current_step") or "").strip()
    if not head:
        return out
    row = steps_by_id.get(head) or {}
    if str(row.get("status") or "") != "in_progress":
        return out
    started = _parse_ts(row.get("started_at"))
    if started is None:
        return out
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if (_now_utc() - started).total_seconds() < 90:
        return out

    out["triggered"] = True
    out["priority"] = 70
    out["type"] = "nudge"
    out["message"] = (
        f"You've been on **{head}** for a bit. If something's unclear, finish the required fields "
        "or step back and review the previous screen."
    )
    out["suggested_actions"] = [
        f"Complete {head}",
        "Review the previous step summary",
    ]
    return out


def rule_low_value_selection_placeholder(ctx: Dict[str, Any]) -> RuleEval:
    """Placeholder: user on dispute selection with effectively empty selection."""
    out = _empty_rule("orion.low_value_selection_placeholder")
    session = ctx.get("session") or {}
    if str(session.get("current_step") or "") != "select_disputes":
        return out
    meta = session.get("metadata") if isinstance(session.get("metadata"), dict) else {}
    ds = meta.get("dispute_selection") if isinstance(meta.get("dispute_selection"), dict) else {}
    ids = ds.get("selectedItemIds") or ds.get("selected_item_ids") or []
    if isinstance(ids, list) and len(ids) > 0:
        return out
    confirmed = bool(ds.get("selectionConfirmed") or ds.get("selection_confirmed"))
    if confirmed:
        return out

    out["triggered"] = True
    out["priority"] = 45
    out["type"] = "optimization"
    out["message"] = (
        "Pick the items that matter most before moving on — stronger selections usually "
        "produce clearer letters."
    )
    out["suggested_actions"] = [
        "Select at least one dispute item",
        "Remove low-impact lines you don't want to challenge",
    ]
    return out


def rule_step_completion_reinforcement(ctx: Dict[str, Any]) -> RuleEval:
    """Positive reinforcement after a step completes (from latest event hint)."""
    out = _empty_rule("orion.step_completion_reinforcement")
    latest = ctx.get("latest_event")
    if not isinstance(latest, dict):
        return out
    et = str(latest.get("eventType") or "")
    if et != "step.status":
        return out
    ns = latest.get("newState") if isinstance(latest.get("newState"), dict) else {}
    if str(ns.get("status") or "") != "completed":
        return out
    sid = str(latest.get("stepId") or "").strip() or "this step"

    out["triggered"] = True
    out["priority"] = 35
    out["type"] = "instruction"
    out["message"] = f"**{sid}** is complete — nice work. Move forward when you're ready."
    out["suggested_actions"] = ["Open the next available step", "Review progression"]
    return out


def rule_payment_complete_next(ctx: Dict[str, Any]) -> RuleEval:
    """After payment completes, orient user toward letter generation."""
    out = _empty_rule("orion.payment_complete_next")
    steps_by_id: Dict[str, Dict[str, Any]] = ctx.get("steps_by_id") or {}
    pay = steps_by_id.get("payment") or {}
    if str(pay.get("status") or "") != "completed":
        return out
    lg = steps_by_id.get("letter_generation") or {}
    if str(lg.get("status") or "") == "completed":
        return out

    out["triggered"] = True
    out["priority"] = 85
    out["type"] = "instruction"
    out["message"] = (
        "Payment is recorded. Continue with **letter generation** when you're ready — "
        "that's where your dispute letters are produced."
    )
    out["suggested_actions"] = [
        "Start letter generation",
        "Review payment receipt in your email",
    ]
    return out


ALL_RULES = (
    rule_repeated_upload_failure,
    rule_payment_complete_next,
    rule_inactivity_over_120s,
    rule_step_opened_no_action,
    rule_low_value_selection_placeholder,
    rule_step_completion_reinforcement,
)
