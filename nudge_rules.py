"""
nudge_rules.py | 850 Lab
Lightweight rule-based nudge engine for admin-visible insights.
Evaluates user state and produces actionable nudges.
"""

from dataclasses import dataclass, asdict
from typing import List, Optional
from datetime import datetime, timedelta


@dataclass
class Nudge:
    id: str
    trigger_name: str
    severity: str  # info / warn / critical
    message: str
    recommended_action_route: Optional[str]
    cooldown_days: int = 1

    def as_dict(self):
        return asdict(self)


def evaluate_rules(user_state: dict) -> List[Nudge]:
    nudges = []

    has_letters = user_state.get('has_letters', False)
    has_mailed = user_state.get('has_mailed', False)
    letters_generated_at = user_state.get('letters_generated_at')
    mailed_at = user_state.get('mailed_at')
    days_elapsed = user_state.get('days_elapsed', 0)
    has_clock_started = user_state.get('has_clock_started', False)
    utilization_pct = user_state.get('utilization_pct', 0)
    critical_utilization = user_state.get('critical_utilization', False)
    high_utilization = user_state.get('high_utilization', False)
    has_balance_update = user_state.get('has_balance_update', False)
    escalation_opened = user_state.get('escalation_opened', False)
    now = datetime.utcnow()

    if has_letters and not has_mailed:
        hours_since = 0
        if letters_generated_at:
            if isinstance(letters_generated_at, str):
                try:
                    letters_generated_at = datetime.fromisoformat(letters_generated_at.replace('Z', '+00:00'))
                except Exception:
                    letters_generated_at = None
            if letters_generated_at:
                hours_since = (now - letters_generated_at.replace(tzinfo=None)).total_seconds() / 3600
        if hours_since >= 48:
            nudges.append(Nudge(
                id='letters_not_mailed_48h',
                trigger_name='Letters generated but not mailed (48h+)',
                severity='warn',
                message='Letters were generated over 48 hours ago but haven\'t been mailed yet. Disputes don\'t start until bureaus receive the letters.',
                recommended_action_route='send_mail',
                cooldown_days=3,
            ))

    if has_mailed and not has_clock_started:
        nudges.append(Nudge(
            id='clock_not_started',
            trigger_name='Mailed but clock not started',
            severity='warn',
            message='Letters have been mailed but the 30-day investigation clock hasn\'t been started. Start tracking to know when to escalate.',
            recommended_action_route='tracker',
            cooldown_days=2,
        ))

    if (critical_utilization or high_utilization) and not has_balance_update:
        hours_since_report = 0
        report_at = user_state.get('report_uploaded_at')
        if report_at:
            if isinstance(report_at, str):
                try:
                    report_at = datetime.fromisoformat(report_at.replace('Z', '+00:00'))
                except Exception:
                    report_at = None
            if report_at:
                hours_since_report = (now - report_at.replace(tzinfo=None)).total_seconds() / 3600
        if hours_since_report >= 72 or (not report_at and critical_utilization):
            label = 'Critical' if critical_utilization else 'High'
            nudges.append(Nudge(
                id='utilization_no_update_72h',
                trigger_name=f'{label} utilization with no balance update (72h+)',
                severity='critical' if critical_utilization else 'warn',
                message=f'{label} credit utilization detected ({utilization_pct:.0f}%) with no balance paydown logged in 72+ hours. Paying down balances is the fastest way to improve scores.',
                recommended_action_route='strategy',
                cooldown_days=3,
            ))

    if has_mailed and days_elapsed >= 25 and days_elapsed < 31:
        nudges.append(Nudge(
            id='approaching_day_28',
            trigger_name='Approaching Day 28 of investigation',
            severity='info',
            message=f'Day {days_elapsed} of the 30-day investigation period. Bureaus must respond by Day 30. Prepare escalation materials now in case they miss the deadline.',
            recommended_action_route='escalation',
            cooldown_days=1,
        ))

    if has_mailed and days_elapsed >= 31 and not escalation_opened:
        nudges.append(Nudge(
            id='day31_escalation_ready',
            trigger_name='Day 31+ escalation authorized',
            severity='critical',
            message=f'Day {days_elapsed}: The 30-day investigation period has expired. Bureaus that haven\'t responded are now in violation of FCRA §611. Escalation is authorized.',
            recommended_action_route='escalation',
            cooldown_days=7,
        ))

    return nudges


NUDGE_SEVERITY_COLORS = {
    'info': '#42A5F5',
    'warn': '#FFA726',
    'critical': '#EF5350',
}

NUDGE_SEVERITY_LABELS = {
    'info': 'Info',
    'warn': 'Warning',
    'critical': 'Critical',
}
