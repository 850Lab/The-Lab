"""
O.R.I.O.N. V1.1 — thin delivery interpretation for already-triggered rule results.

Does not re-run business rules; only maps rule_key → channel, cooldown, recommendedAction,
and display eligibility vs recent display history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.guidance.guidance_response_model import GuidanceResponse
from services.guidance.guidance_rules import RuleEval
from services.guidance.guidance_storage import seconds_since_last_display_eligible

# Rule-specific cooldowns (seconds) before another *display-eligible* surfacing.
RULE_COOLDOWN_SECONDS: Dict[str, int] = {
    "orion.repeated_upload_failure": 180,
    "orion.payment_complete_next": 300,
    "orion.inactivity_120s": 180,
    "orion.step_opened_no_action": 180,
    "orion.low_value_selection_placeholder": 240,
    "orion.step_completion_reinforcement": 120,
}

DEFAULT_COOLDOWN = 180


def _next_linear_step(session: Dict[str, Any], completed_step_id: str) -> Optional[str]:
    """Deterministic next step id after a completed step, if any."""
    try:
        from services.workflow.registry import linear_order_for

        wt = str(session.get("workflow_type") or "")
        order = linear_order_for(wt)
        if completed_step_id not in order:
            return None
        idx = order.index(completed_step_id)
        if idx + 1 >= len(order):
            return None
        return str(order[idx + 1])
    except Exception:
        return None


def _recommended_action(
    *,
    action_key: str,
    label: str,
    target_step_id: Optional[str],
    action_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "actionKey": action_key,
        "label": label,
        "targetStepId": target_step_id,
        "actionType": action_type,
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


def build_recommended_action_for_rule(rule_key: str, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    session = ctx.get("session") or {}
    head = str(session.get("current_step") or "").strip() or None

    if rule_key == "orion.repeated_upload_failure":
        return _recommended_action(
            action_key="retry_upload_with_help",
            label="Try upload again",
            target_step_id="upload",
            action_type="retry",
        )
    if rule_key == "orion.payment_complete_next":
        return _recommended_action(
            action_key="go_to_letter_generation",
            label="Review generated letters",
            target_step_id="letter_generation",
            action_type="navigate",
        )
    if rule_key == "orion.inactivity_120s":
        return _recommended_action(
            action_key="resume_current_step",
            label="Continue where you left off",
            target_step_id=head,
            action_type="navigate" if head else "review",
        )
    if rule_key == "orion.low_value_selection_placeholder":
        return _recommended_action(
            action_key="review_selection",
            label="Review dispute selection",
            target_step_id="select_disputes",
            action_type="review",
        )
    if rule_key == "orion.step_opened_no_action":
        return _recommended_action(
            action_key="focus_current_step",
            label="Finish this step",
            target_step_id=head,
            action_type="review",
        )
    if rule_key == "orion.step_completion_reinforcement":
        latest = ctx.get("latest_event")
        sid = None
        if isinstance(latest, dict):
            sid = str(latest.get("stepId") or "").strip() or None
        nxt = _next_linear_step(session, sid) if sid else None
        if not nxt:
            return None
        return _recommended_action(
            action_key="open_next_step",
            label="Go to next step",
            target_step_id=nxt,
            action_type="navigate",
        )
    return None


def default_delivery_channel(rule_key: str) -> str:
    if rule_key == "orion.repeated_upload_failure":
        return "banner"
    if rule_key == "orion.payment_complete_next":
        return "inline"
    if rule_key == "orion.inactivity_120s":
        return "passive"
    if rule_key == "orion.step_opened_no_action":
        return "inline"
    if rule_key == "orion.low_value_selection_placeholder":
        return "inline"
    if rule_key == "orion.step_completion_reinforcement":
        return "passive"
    if rule_key.startswith("orion.internal."):
        return "internal_only"
    return "inline"


def apply_delivery(
    rule_eval: RuleEval,
    *,
    workflow_id: str,
    ctx: Dict[str, Any],
    guidance_id: str,
    step_id: str,
    timestamp: datetime,
) -> Tuple[GuidanceResponse, bool]:
    """
    Build GuidanceResponse with delivery fields.

    Returns (response, display_suppressed_by_cooldown).
    """
    rule_key = str(rule_eval.get("rule_key") or rule_eval.get("trigger_source") or "").strip()
    if not rule_key:
        rule_key = "orion.unknown"

    gtype = str(rule_eval.get("type") or "nudge")
    if gtype not in ("nudge", "warning", "instruction", "optimization"):
        gtype = "nudge"

    cooldown = int(RULE_COOLDOWN_SECONDS.get(rule_key, DEFAULT_COOLDOWN))
    channel = default_delivery_channel(rule_key)

    rec = build_recommended_action_for_rule(rule_key, ctx)

    display_eligible = True
    suppressed = False
    if channel != "internal_only":
        since = seconds_since_last_display_eligible(workflow_id, rule_key)
        if since is not None and since < cooldown:
            display_eligible = False
            suppressed = True

    if channel == "internal_only":
        display_eligible = False

    resp = GuidanceResponse(
        guidance_id=guidance_id,
        rule_key=rule_key,
        type=gtype,  # type: ignore[arg-type]
        message=str(rule_eval.get("message") or "").strip() or "Guidance available.",
        step_id=(step_id or "")[:64],
        priority=int(rule_eval.get("priority") or 0),
        trigger_source=str(rule_eval.get("trigger_source") or rule_key),
        timestamp=timestamp,
        display_eligible=display_eligible,
        delivery_channel=channel,  # type: ignore[arg-type]
        cooldown_seconds=cooldown,
        recommended_action=rec,
        suggested_actions=list(rule_eval.get("suggested_actions") or []),
    )
    return resp, suppressed
