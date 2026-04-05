"""
Plain-text drafts for escalation UX (MOV, furnisher, CFPB). Educational templates only.

Not a substitute for licensed advice; user edits before sending.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def _lines_for_claims(claim_lines: List[str]) -> str:
    if not claim_lines:
        return "— [Add account names / partial numbers from your credit report]\n"
    return "".join(f"• {ln}\n" for ln in claim_lines[:40])


def build_method_of_verification_draft(claim_lines: List[str], consumer_name: str = "") -> str:
    who = (consumer_name or "[Your full legal name]").strip()
    items = _lines_for_claims(claim_lines)
    return (
        f"{who}\n"
        "[Your address]\n"
        "[Date]\n\n"
        "Re: Method of verification request — FCRA dispute\n\n"
        "Dear Sir or Madam,\n\n"
        "I am writing regarding my dispute of the following item(s) on my consumer report. "
        "Please provide the method of verification used, including the identity of any "
        "furnisher contacted, the nature of that contact, and any documentation relied upon.\n\n"
        f"Disputed item(s):\n{items}\n"
        "Please respond in writing within the timeframes applicable under the Fair Credit "
        "Reporting Act.\n\n"
        "Sincerely,\n"
        f"{who}\n"
    )


def build_furnisher_dispute_draft(claim_lines: List[str], consumer_name: str = "") -> str:
    who = (consumer_name or "[Your full legal name]").strip()
    items = _lines_for_claims(claim_lines)
    return (
        f"{who}\n"
        "[Your address]\n"
        "[Date]\n\n"
        "Re: Direct dispute of information furnished to consumer reporting agencies\n\n"
        "To whom it may concern,\n\n"
        "I am disputing the accuracy of the following information you furnished (or verified) "
        "to consumer reporting agencies. Please investigate and correct or delete inaccurate "
        "information as required.\n\n"
        f"Account / tradeline summary:\n{items}\n"
        "I request a written outcome of your investigation.\n\n"
        "Sincerely,\n"
        f"{who}\n"
    )


def build_cfpb_complaint_outline(claim_lines: List[str]) -> str:
    items = _lines_for_claims(claim_lines)
    return (
        "CFPB complaint — draft facts (paste into consumerfinance.gov complaint form)\n\n"
        "1) What happened (short timeline):\n"
        "   • Dates you mailed bureau disputes (certified / tracking).\n"
        "   • What the bureau or furnisher responded (or that there was no substantive response).\n\n"
        "2) Item(s) still at issue:\n"
        f"{items}"
        "3) What you want:\n"
        "   • Investigation / correction / deletion as appropriate.\n"
        "   • Written description of verification method if they claim accuracy.\n\n"
        "4) Attachments to gather:\n"
        "   • Copies of dispute letters, green cards or tracking, bureau replies.\n"
    )


def draft_for_escalation_action(
    action_type: str,
    claim_lines: List[str],
    *,
    consumer_name: str = "",
) -> str:
    t = (action_type or "").strip().lower()
    if t == "method_of_verification":
        return build_method_of_verification_draft(claim_lines, consumer_name=consumer_name)
    if t == "furnisher_dispute":
        return build_furnisher_dispute_draft(claim_lines, consumer_name=consumer_name)
    if t == "cfpb_complaint":
        return build_cfpb_complaint_outline(claim_lines)
    return ""


def merge_escalation_ux_state(
    existing: Dict[str, Any],
    action_id: str,
    *,
    reviewed: bool,
    proceeded: bool,
) -> Dict[str, Any]:
    st = dict(existing) if isinstance(existing, dict) else {}
    actions = st.get("actionStates")
    if not isinstance(actions, dict):
        actions = {}
    else:
        actions = dict(actions)
    cur = actions.get(action_id)
    if not isinstance(cur, dict):
        cur = {}
    else:
        cur = dict(cur)
    now = datetime.now(timezone.utc).isoformat()
    if reviewed:
        cur["reviewed"] = True
        cur["reviewedAt"] = now
    if proceeded:
        cur["proceeded"] = True
        cur["proceededAt"] = now
    actions[action_id] = cur
    st["actionStates"] = actions
    return st
