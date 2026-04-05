"""
Customer escalation layer: deterministic triggers from mail timeline + responses + outcomes,
paired with concrete leverage actions (furnisher, CFPB, scripts, follow-up letters).

Educational / operational guidance only — not legal advice.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from services.customer_dispute_strategy import (
    claim_outcomes_from_meta,
    parse_workflow_metadata_value,
)
from services.customer_tracking_service import build_tracking_context_payload
from services.workflow import response_repository as rr
from services.workflow.escalation_ux_payload import build_program_escalation_ux_payload
from services.workflow.repository import fetch_session

NO_RESPONSE_THRESHOLD_DAYS = 30

CFPB_COMPLAINT_URL = "https://www.consumerfinance.gov/complaint/"
FTC_COMPLAINT_URL = "https://reportfraud.ftc.gov/"


def _parse_iso_dt(s: str) -> Optional[datetime]:
    if not (s or "").strip():
        return None
    try:
        t = s.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(t)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _responses_on_or_after_mail(
    rows: List[Dict[str, Any]], earliest_mailed: Optional[datetime]
) -> int:
    if earliest_mailed is None:
        return 0
    n = 0
    for r in rows:
        ra = r.get("received_at")
        dt = ra if isinstance(ra, datetime) else _parse_iso_dt(str(ra or ""))
        if dt is None:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt >= earliest_mailed:
            n += 1
    return n


def _action_furnisher() -> Dict[str, Any]:
    return {
        "id": "furnisher_dispute",
        "title": "Furnisher (data furnisher) dispute",
        "tagline": "Go to the company that reported the item, not only the bureau.",
        "whyNow": "Bureaus often ‘verify’ from furnisher data. A direct furnisher dispute creates a separate investigation trail.",
        "steps": [
            "List each account name and partial account number as shown on your report.",
            "State what is inaccurate and what you want changed or deleted.",
            "Send certified mail with return receipt, or use the furnisher’s registered dispute channel if you prefer.",
            "Keep copies of everything; note dates for follow-up.",
        ],
        "callScript": (
            "Hi, I’m calling about an account you report to the credit bureaus. "
            "I already disputed with the bureau and the item was verified. "
            "I’m requesting you open a direct investigation under your obligations as a furnisher, "
            "and I’d like a written outcome sent to me. Can you give me a reference number today?"
        ),
        "links": [
            {"label": "CFPB — how to dispute", "url": "https://www.consumerfinance.gov/ask-cfpb/how-do-i-dispute-an-error-on-my-credit-report-en-314/"},
        ],
    }


def _action_follow_up_letter() -> Dict[str, Any]:
    return {
        "id": "follow_up_letter",
        "title": "Certified follow-up letter",
        "tagline": "Timed, written pressure when answers are late or incomplete.",
        "whyNow": "A clear paper trail after day 30 (or after a weak reply) shows you are serious and organized.",
        "steps": [
            "Reference your prior certified letter and the date it was sent.",
            "State that the investigation window has passed or the response was incomplete.",
            "Request deletion or correction and a description of how the item was verified if they insist it stays.",
            "Mail certified, return receipt; keep the green card or electronic equivalent.",
        ],
        "callScript": "",
        "links": [],
    }


def _action_cfpb() -> Dict[str, Any]:
    return {
        "id": "cfpb_complaint",
        "title": "CFPB complaint (formal path)",
        "tagline": "Regulatory channel when standard disputes stall or break down.",
        "whyNow": "Useful after you have documentation: what you disputed, what you sent, and what they answered (or didn’t).",
        "steps": [
            "Gather dates of letters, tracking numbers, and any bureau or furnisher replies.",
            "File at consumerfinance.gov with a concise timeline (facts, not emotion).",
            "Attach or summarize key documents if the form allows.",
            "Continue any in-progress disputes; complaints are parallel leverage, not a substitute for your records.",
        ],
        "callScript": "",
        "links": [
            {"label": "Start a CFPB complaint", "url": CFPB_COMPLAINT_URL},
            {"label": "FTC fraud report (if identity theft)", "url": FTC_COMPLAINT_URL},
        ],
    }


def _action_call_scripts() -> Dict[str, Any]:
    return {
        "id": "call_scripts",
        "title": "Phone leverage",
        "tagline": "Scripts that keep you calm, specific, and on-record.",
        "whyNow": "A short call can surface a reference number or supervisor queue while your certified mail is in flight.",
        "steps": [
            "Write down the representative’s name, time, and reference number.",
            "Do not argue; repeat your request and ask what they will mail or email you.",
            "If they refuse a dispute, ask for it in writing and hang up — then use mail.",
        ],
        "callScript": (
            "I’m following up on a credit reporting dispute. I need a written confirmation of what you’re investigating, "
            "the deadline you’re using, and how you’ll notify me of results. If you can’t help, please escalate to a supervisor "
            "and give me a reference number for this call."
        ),
        "links": [],
    }


_ACTION_BUILDERS = {
    "furnisher_dispute": _action_furnisher,
    "follow_up_letter": _action_follow_up_letter,
    "cfpb_complaint": _action_cfpb,
    "call_scripts": _action_call_scripts,
}


def _merge_actions(ids: List[str]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for i, aid in enumerate(ids):
        if aid in seen or aid not in _ACTION_BUILDERS:
            continue
        seen.add(aid)
        block = dict(_ACTION_BUILDERS[aid]())
        block["priority"] = i + 1
        out.append(block)
    return out


def build_escalation_layer_payload(
    user_id: int,
    workflow_id: str,
    *,
    session_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Returns UI-safe JSON: triggers, ordered leverage actions, and small context facts.
    """
    sess = session_row if session_row is not None else fetch_session(workflow_id)
    meta = parse_workflow_metadata_value(sess.get("metadata") if sess else {})
    outcomes = claim_outcomes_from_meta(meta)

    tracking = build_tracking_context_payload(user_id, workflow_id, session_row=sess)
    tl = tracking.get("timeline") if isinstance(tracking.get("timeline"), dict) else {}
    earliest_iso = str(tl.get("earliestMailedAt") or "")
    days_raw = int(tl.get("daysSinceFirstMailRaw") or 0)
    has_live = bool(tracking.get("trackingStatus", {}).get("hasLiveSubmissions"))

    earliest_mailed = _parse_iso_dt(earliest_iso)

    rows = rr.list_responses_detailed_for_workflow(workflow_id, limit=60)
    responses_after_mail = _responses_on_or_after_mail(rows, earliest_mailed)

    classifications = [
        str(r.get("response_classification") or "").strip()
        for r in rows
        if (r.get("classification_status") or "") == "classified"
    ]

    triggers: List[Dict[str, Any]] = []
    trigger_ids: Set[str] = set()
    action_order: List[str] = []

    def add_trigger(tid: str, label: str, severity: str, detail: str) -> None:
        if tid in trigger_ids:
            return
        trigger_ids.add(tid)
        triggers.append(
            {
                "id": tid,
                "label": label,
                "severity": severity,
                "detailSafe": detail[:500],
            }
        )

    # 1) No bureau/furnisher response logged after mail + 30d
    if (
        has_live
        and earliest_mailed is not None
        and days_raw >= NO_RESPONSE_THRESHOLD_DAYS
        and responses_after_mail == 0
    ):
        add_trigger(
            "no_response_30d",
            "No response logged after 30+ days",
            "high",
            f"It has been about {days_raw} days since your earliest live certified send, and no bureau or furnisher "
            "response is recorded in this program yet. You can add a summary under Responses, then use the actions below.",
        )
        action_order.extend(
            ["follow_up_letter", "call_scripts", "cfpb_complaint", "furnisher_dispute"]
        )

    # 2) Incorrect / unfavorable verification
    if "verification_only" in classifications:
        add_trigger(
            "incorrect_verification",
            "Bureau says they verified the item",
            "high",
            "At least one saved response looks like a verification-only outcome. That often calls for method-of-verification "
            "pressure and furnisher-side review.",
        )
    for oc in outcomes.values():
        if oc == "verified":
            add_trigger(
                "incorrect_verification",
                "You marked an item as bureau-verified",
                "high",
                "Per-item outcomes include a ‘verified’ bucket — treat those as candidates for furnisher disputes and MOV follow-up.",
            )
            break

    # 3) Incomplete updates
    if "partial_resolution" in classifications:
        add_trigger(
            "incomplete_update",
            "Incomplete or partial fix",
            "normal",
            "A response looks like only part of the issue was fixed. You can dispute remaining inaccuracies again with clearer proof.",
        )
    for oc in outcomes.values():
        if oc == "updated":
            add_trigger(
                "incomplete_update",
                "You marked an item as partially updated",
                "normal",
                "Items tagged ‘updated’ often still need another bureau or furnisher pass on what’s left wrong.",
            )
            break

    if "incorrect_verification" in trigger_ids or "incomplete_update" in trigger_ids:
        action_order.extend(
            ["furnisher_dispute", "follow_up_letter", "call_scripts", "cfpb_complaint"]
        )

    latest = rows[0] if rows else None
    latest_cls = str(latest.get("response_classification") or "") if latest else ""
    latest_esc = latest.get("escalation_recommendation") if isinstance(latest, dict) else {}
    if not isinstance(latest_esc, dict):
        latest_esc = {}

    # If nothing fired but user has any non-favorable classified response, still offer baseline leverage
    if not triggers and has_live and rows:
        bad = any(
            c
            for c in classifications
            if c
            in (
                "verification_only",
                "stall_or_non_answer",
                "adverse_or_rejected",
                "partial_resolution",
            )
        )
        if bad:
            add_trigger(
                "response_requires_leverage",
                "Saved response suggests follow-up leverage",
                "normal",
                "Your last responses are not in the ‘fully resolved’ bucket — use the actions below if you still disagree with what’s reporting.",
            )
            action_order.extend(
                ["follow_up_letter", "furnisher_dispute", "call_scripts", "cfpb_complaint"]
            )

    if not action_order:
        action_order = ["follow_up_letter", "call_scripts", "furnisher_dispute", "cfpb_complaint"]

    actions = _merge_actions(action_order)

    headline = (
        "You have more options, not fewer"
        if triggers
        else "Escalation toolkit (when you need more leverage)"
    )
    subcopy = (
        "These steps are real-world pressure tools people use after bureau mail — furnisher disputes, written follow-ups, "
        "structured calls, and formal complaints. Pick what fits your facts; this app does not file on your behalf."
        if triggers
        else "Use this when standard disputes need another gear. Nothing here replaces your judgment or a licensed professional."
    )

    program_escalation = build_program_escalation_ux_payload(user_id, meta)

    return {
        "leverageHeadline": headline,
        "subcopy": subcopy,
        "triggers": triggers,
        "actions": actions,
        "programEscalation": program_escalation,
        "latestResponse": (
            {
                "classification": latest_cls or None,
                "escalationPrimaryPath": str(latest_esc.get("primary_path") or "") or None,
                "escalationReasoningSafe": str(latest_esc.get("reasoning_safe") or "")[:400] or None,
            }
            if latest
            else None
        ),
        "context": {
            "daysSinceFirstMailRaw": days_raw,
            "hasLiveMail": has_live,
            "responsesRecordedAfterFirstMail": responses_after_mail,
            "earliestMailedAt": earliest_iso or None,
            "trackStepCompleted": bool(tracking.get("trackStepCompleted")),
        },
    }
