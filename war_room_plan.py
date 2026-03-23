"""
war_room_plan.py | 850 Lab Parser Machine
72-Hour Credit Strike Protocol (War Room) — dynamic action plan generator.
Deterministic, explainable, mission-aware. Uses strike_metrics + violations.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


@dataclass
class PlanAction:
    id: str
    phase: str
    title: str
    why: str
    success_criteria: str
    primary_button_label: str
    primary_route: str
    secondary_button_label: Optional[str] = None
    secondary_route: Optional[str] = None
    script: Optional[str] = None
    requires: Optional[str] = None


@dataclass
class WarRoomPlan:
    risk_level: str
    primary_lever: str
    phases: Dict[str, List[Dict[str, Any]]]
    top3_actions: List[Dict[str, Any]]
    notes: List[str]
    mission_goal: str = ""
    mission_timeline: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _compute_risk_level(sm: Dict[str, Any]) -> str:
    neg = sm.get('negative_accounts_count', 0)
    coll = sm.get('collections_count', 0)
    critical = sm.get('critical_utilization_flag', False)
    high_util = sm.get('high_utilization_flag', False)
    inq_heavy = sm.get('inquiry_heavy_flag', False)

    if neg >= 2 or critical or coll >= 2:
        return "HIGH"
    if neg >= 1 or high_util or inq_heavy:
        return "MODERATE"
    return "CONTROLLED"


def _action_dict(action: PlanAction) -> Dict[str, Any]:
    return asdict(action)


MISSION_PRIORITIES = {
    'Auto Purchase': ['utilization', 'inquiry', 'certified_mail'],
    'Apartment': ['collections', 'chargeoffs', 'stability'],
    'Credit Card': ['utilization', 'inquiry', 'revolving'],
    'Bank Account': ['chex', 'banking', 'disputes'],
    'General Rebuild': ['deletion', 'utilization', 'stability'],
}


def build_war_room_plan(
    strike_metrics: Dict[str, Any],
    violations: Optional[List] = None,
    tradelines: Optional[List] = None,
    mission_goal: str = "General Rebuild",
    mission_timeline: str = "ASAP (7 days)",
    has_letters: bool = False,
    has_mailed: bool = False,
    days_elapsed: int = 0,
) -> WarRoomPlan:
    sm = strike_metrics or {}
    violations = violations or []
    tradelines = tradelines or []

    risk_level = _compute_risk_level(sm)
    primary_lever = sm.get('primary_lever', 'OPTIMIZATION')

    phases: Dict[str, List[Dict[str, Any]]] = {
        "0-6": [],
        "6-24": [],
        "24-48": [],
        "48-72": [],
    }
    notes: List[str] = []

    # ━━━ PHASE 0–6: LOCK THE FIELD ━━━
    _skip_freeze = (
        mission_goal in ('Auto Purchase', 'Credit Card', 'Apartment')
        and mission_timeline in ('ASAP (7 days)', '30 days')
    )
    if not _skip_freeze:
        phases["0-6"].append(_action_dict(PlanAction(
            id="freeze_bureaus",
            phase="0-6",
            title="Freeze all 3 bureaus",
            why="Prevents new accounts from opening while you dispute. Locks the field.",
            success_criteria="Freeze confirmation from Equifax, Experian, and TransUnion",
            primary_button_label="How to freeze",
            primary_route="strategy",
            script=(
                "Go to each bureau's website:\n"
                "• Equifax: equifax.com/personal/credit-report-services/credit-freeze\n"
                "• Experian: experian.com/freeze\n"
                "• TransUnion: transunion.com/credit-freeze\n\n"
                "Create an account or log in, then request a security freeze. "
                "Save your PIN/confirmation number."
            ),
        )))
    else:
        phases["0-6"].append(_action_dict(PlanAction(
            id="freeze_skip_note",
            phase="0-6",
            title="DO NOT freeze bureaus yet",
            why=f"You plan to apply for credit ({mission_goal}) soon. A freeze would block lenders from pulling your report.",
            success_criteria="Understood — skip freeze until after approval",
            primary_button_label=None,
            primary_route=None,
            script=(
                f"Since your goal is '{mission_goal}' within {mission_timeline}, "
                "do NOT freeze your credit bureaus right now. Freezing would prevent "
                "lenders from accessing your report, which blocks approvals.\n\n"
                "After you've been approved, come back and freeze to protect your credit."
            ),
        )))

    if mission_goal in ('Bank Account', 'General Rebuild'):
        phases["0-6"].append(_action_dict(PlanAction(
            id="freeze_chex",
            phase="0-6",
            title="Freeze ChexSystems",
            why="Protects banking profile. Required for new bank account applications.",
            success_criteria="ChexSystems freeze confirmation received",
            primary_button_label="ChexSystems info",
            primary_route="strategy",
            script=(
                "Contact ChexSystems:\n"
                "• Online: chexsystems.com/security-freeze\n"
                "• Phone: 1-800-428-9623\n\n"
                "Request a security freeze on your consumer file."
            ),
        )))

    phases["0-6"].append(_action_dict(PlanAction(
        id="save_baseline",
        phase="0-6",
        title="Save baseline report snapshot",
        why="Establishes your starting point. Proves what changed after disputes.",
        success_criteria="PDF copies of all uploaded reports saved locally",
        primary_button_label="View Documents",
        primary_route="documents",
    )))

    phases["0-6"].append(_action_dict(PlanAction(
        id="confirm_proof",
        phase="0-6",
        title="Confirm proof documents ready",
        why="Certified mail requires ID and proof of address. Get these ready now.",
        success_criteria="Government ID + proof of address (utility bill or bank statement) ready",
        primary_button_label="View Documents",
        primary_route="documents",
    )))

    # ━━━ PHASE 6–24: DEPLOY PRIMARY STRIKE ━━━
    if has_letters and not has_mailed:
        phases["6-24"].append(_action_dict(PlanAction(
            id="send_certified",
            phase="6-24",
            title="Send Certified Mail now",
            why="Certified mail creates a legal timestamp. The 30-day clock starts when the bureau receives it.",
            success_criteria="Certified mail tracking number logged for each bureau",
            primary_button_label="Send Mail",
            primary_route="send_mail",
        )))
    elif not has_letters:
        phases["6-24"].append(_action_dict(PlanAction(
            id="generate_letters",
            phase="6-24",
            title="Generate dispute letters",
            why="Your letters are the primary weapon. Generate them from your analyzed report.",
            success_criteria="Dispute letters generated for all applicable bureaus",
            primary_button_label="Generate Letters",
            primary_route="documents",
        )))

    if has_letters:
        phases["6-24"].append(_action_dict(PlanAction(
            id="log_tracking",
            phase="6-24",
            title="Log tracking numbers",
            why="Tracking numbers prove delivery date. Needed for escalation if bureaus don't respond.",
            success_criteria="All tracking numbers entered in the tracker",
            primary_button_label="Open Tracker",
            primary_route="tracker",
        )))

    phases["6-24"].append(_action_dict(PlanAction(
        id="start_clock",
        phase="6-24",
        title="Start the 30-day clock",
        why="Bureaus have 30 days to respond from receipt. Mark the start date now.",
        success_criteria="Mail date set in tracker, countdown active",
        primary_button_label="Set Date",
        primary_route="tracker",
    )))

    # ━━━ PHASE 24–48: SCORE OPTIMIZATION ASSAULT ━━━
    util_pct = sm.get('overall_utilization_pct')
    max_card_util = sm.get('max_single_card_utilization_pct')
    neg_count = sm.get('negative_accounts_count', 0)
    coll_count = sm.get('collections_count', 0)
    inq_heavy = sm.get('inquiry_heavy_flag', False)

    if util_pct is not None and util_pct >= 70:
        phases["24-48"].append(_action_dict(PlanAction(
            id="util_critical",
            phase="24-48",
            title="Utilization Assault (critical)",
            why=f"Your utilization is {util_pct:.0f}% — severely hurting your score. Pay down revolving balances to under 29%.",
            success_criteria="Total revolving utilization below 30%",
            primary_button_label="View Accounts",
            primary_route="documents",
            script=(
                "Paydown strategy (highest-impact first):\n"
                "1. Pay down the card with the highest utilization first\n"
                "2. Target getting EACH card below 29% individually\n"
                "3. If you can only make one payment, hit the highest-balance revolving card\n"
                "4. Request a balance report date from your issuer — pay BEFORE that date\n"
                "5. Do NOT close cards after paying down (kills available credit)"
            ),
        )))
    elif util_pct is not None and util_pct >= 50:
        phases["24-48"].append(_action_dict(PlanAction(
            id="util_high",
            phase="24-48",
            title="Drop utilization below 29%",
            why=f"Your utilization is {util_pct:.0f}%. Getting under 29% is a fast score boost.",
            success_criteria="Total revolving utilization below 29%",
            primary_button_label="View Accounts",
            primary_route="documents",
            script=(
                "Quick wins:\n"
                "1. Pay down highest-utilization card first\n"
                "2. Pay BEFORE statement closing date (call issuer for date)\n"
                "3. Do NOT close any cards\n"
                "4. Consider requesting a credit limit increase (no hard pull if possible)"
            ),
        )))
    elif max_card_util is not None and max_card_util >= 80:
        phases["24-48"].append(_action_dict(PlanAction(
            id="util_single_card",
            phase="24-48",
            title="Pay down maxed card",
            why=f"One card is at {max_card_util:.0f}% utilization. Even one maxed card drags your score.",
            success_criteria="No single card above 29% utilization",
            primary_button_label="View Accounts",
            primary_route="documents",
        )))

    if inq_heavy:
        _inq_note = ""
        if mission_goal == 'Auto Purchase':
            _inq_note = " Rate-shop window: multiple auto inquiries within 14 days count as one."
        phases["24-48"].append(_action_dict(PlanAction(
            id="inquiry_freeze",
            phase="24-48",
            title="Application freeze + rate-shop plan",
            why=f"You have 6+ recent inquiries. Stop all new applications.{_inq_note}",
            success_criteria="No new credit applications submitted",
            primary_button_label="View Strategy",
            primary_route="strategy",
            script=(
                "Inquiry management:\n"
                "1. Stop all new credit applications immediately\n"
                "2. If shopping for auto/mortgage: bundle all applications within a 14-day window\n"
                "   (FICO treats them as one inquiry)\n"
                "3. Inquiries fall off after 2 years, but stop impacting score after ~12 months\n"
                "4. Do NOT dispute legitimate inquiries you authorized"
            ),
        )))

    if neg_count >= 1:
        _goodwill_script = (
            "Goodwill call script (for PAID or settled accounts only):\n\n"
            "\"Hi, I'm calling about account [ACCOUNT]. I previously had a late payment / "
            "this account went to collections, but it has since been paid in full. "
            "I'm working on improving my credit and was hoping you might consider "
            "a goodwill adjustment to remove the negative mark from my credit report. "
            "I understand this is at your discretion and I appreciate any help you can provide.\"\n\n"
            "Tips:\n"
            "• Be polite and patient\n"
            "• Only call about accounts that are PAID or SETTLED\n"
            "• Ask to speak with a supervisor if the first rep can't help\n"
            "• Follow up in writing if they agree (get the rep's name and reference number)"
        )
        phases["24-48"].append(_action_dict(PlanAction(
            id="goodwill_calls",
            phase="24-48",
            title="Goodwill call list (paid accounts only)",
            why="Paid collections and old lates can sometimes be removed with a polite phone call.",
            success_criteria="Called each paid negative account and requested goodwill removal",
            primary_button_label="View Accounts",
            primary_route="documents",
            script=_goodwill_script,
        )))

    if not phases["24-48"]:
        phases["24-48"].append(_action_dict(PlanAction(
            id="maintain_discipline",
            phase="24-48",
            title="Maintain credit discipline",
            why="Your profile looks stable. Keep utilization low and avoid new applications.",
            success_criteria="No new applications, all payments on time",
            primary_button_label="View Tracker",
            primary_route="tracker",
        )))

    # ━━━ PHASE 48–72: ESCALATION WEAPONS (PREP ONLY) ━━━
    phases["48-72"].append(_action_dict(PlanAction(
        id="prep_escalation",
        phase="48-72",
        title="Prepare escalation packet",
        why="If bureaus don't respond or don't fix items, you need an escalation ready to go.",
        success_criteria="MOV request template + CFPB complaint draft + executive contact list saved",
        primary_button_label="View Strategy",
        primary_route="strategy",
        script=(
            "Escalation packet checklist:\n"
            "1. Method of Verification (MOV) demand letter — request the exact method used to verify disputed items\n"
            "2. CFPB complaint draft — factual, concise, reference your dispute dates and tracking numbers\n"
            "3. State AG complaint template — same facts, different recipient\n"
            "4. Executive escalation contacts for each bureau\n\n"
            "IMPORTANT: Do NOT file complaints until Day 31+ (after the investigation window expires). "
            "Filing early weakens your position."
        ),
    )))

    if days_elapsed >= 28 and days_elapsed < 31:
        phases["48-72"].append(_action_dict(PlanAction(
            id="escalation_standby",
            phase="48-72",
            title="Escalation standby — Day {0}".format(days_elapsed),
            why="Investigation window closes soon. Get your escalation materials final-reviewed.",
            success_criteria="All escalation documents reviewed and ready to submit",
            primary_button_label="View Strategy",
            primary_route="strategy",
        )))
        notes.append(f"Day {days_elapsed}: Investigation window closing soon. Prepare escalation materials.")

    if days_elapsed >= 31:
        phases["48-72"].append(_action_dict(PlanAction(
            id="escalation_authorized",
            phase="48-72",
            title="Escalation authorized — Day {0}".format(days_elapsed),
            why="The 30-day investigation window has expired. You may now escalate unresolved items.",
            success_criteria="CFPB complaint filed for unresolved items, MOV demand sent",
            primary_button_label="Escalation Tools",
            primary_route="escalation",
        )))
        notes.append(f"Day {days_elapsed}: 30-day window expired. Escalation is now appropriate for unresolved items.")

    # ━━━ TOP 3 ACTIONS ━━━
    all_actions = []
    for phase_key in ("0-6", "6-24", "24-48", "48-72"):
        all_actions.extend(phases[phase_key])

    priority_ids = _get_priority_ids(sm, mission_goal, has_letters, has_mailed, mission_timeline)
    top3 = []
    for pid in priority_ids:
        for a in all_actions:
            if a['id'] == pid and a not in top3:
                top3.append(a)
                if len(top3) >= 3:
                    break
        if len(top3) >= 3:
            break

    if len(top3) < 3:
        for a in all_actions:
            if a not in top3:
                top3.append(a)
                if len(top3) >= 3:
                    break

    # ━━━ NOTES ━━━
    if mission_goal == 'Auto Purchase' and mission_timeline == 'ASAP (7 days)':
        notes.append("Auto purchase ASAP: Focus on utilization drop + certified mail timestamp first.")
    if sm.get('thin_file_flag'):
        notes.append("Thin file detected (< 5 accounts). Building credit history is a long-term goal.")

    return WarRoomPlan(
        risk_level=risk_level,
        primary_lever=primary_lever,
        phases=phases,
        top3_actions=top3,
        notes=notes,
        mission_goal=mission_goal,
        mission_timeline=mission_timeline,
    )


def _get_priority_ids(
    sm: Dict[str, Any],
    mission_goal: str,
    has_letters: bool,
    has_mailed: bool,
    mission_timeline: str = "ASAP (7 days)",
) -> List[str]:
    priorities = []

    if has_letters and not has_mailed:
        priorities.append("send_certified")
    elif not has_letters:
        priorities.append("generate_letters")

    lever = sm.get('primary_lever', 'OPTIMIZATION')
    if lever == 'UTILIZATION':
        priorities.extend(["util_critical", "util_high", "util_single_card"])
    elif lever == 'DELETION':
        priorities.extend(["goodwill_calls"])
    elif lever == 'STABILITY':
        priorities.extend(["inquiry_freeze"])

    _skip_freeze_p = (
        mission_goal in ('Auto Purchase', 'Credit Card', 'Apartment')
        and mission_timeline in ('ASAP (7 days)', '30 days')
    )
    if not _skip_freeze_p:
        priorities.append("freeze_bureaus")

    if mission_goal == 'Bank Account':
        priorities.insert(1, "freeze_chex")
    if mission_goal == 'Auto Purchase':
        priorities.insert(1, "inquiry_freeze")

    return priorities


PHASE_LABELS = {
    "0-6": "0–6 Hours: Lock the Field",
    "6-24": "6–24 Hours: Deploy Primary Strike",
    "24-48": "24–48 Hours: Score Optimization",
    "48-72": "48–72 Hours: Escalation Prep",
}
