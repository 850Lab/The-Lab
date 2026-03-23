"""
72-Hour Tactical Credit Command Plan
Deterministic, rule-based action plan generated from parsed credit report data.
"""
from typing import List, Dict, Any, Optional
from review_claims import ReviewType


def build_credit_command_plan(
    items_by_type: Dict[Any, List[Any]],
    selected_count: int,
    bureaus: set,
    parsed_reports: Optional[Dict] = None,
) -> Dict[str, Any]:
    neg_count = len(items_by_type.get(ReviewType.NEGATIVE_IMPACT, []))
    wrong_count = len(items_by_type.get(ReviewType.ACCURACY_VERIFICATION, []))
    dup_count = len(items_by_type.get(ReviewType.DUPLICATE_ACCOUNT, []))
    unverif_count = len(items_by_type.get(ReviewType.UNVERIFIABLE_INFORMATION, []))

    quick_wins = dup_count + unverif_count
    score_damaging = neg_count

    has_high_util = False
    if parsed_reports:
        for _k, rr in parsed_reports.items():
            pd = rr.get('parsed_data', {})
            for acct in pd.get('accounts', []):
                try:
                    bal = float(str(acct.get('balance', 0) or 0).replace(',', '').replace('$', '').strip() or 0)
                    limit_ = float(str(acct.get('credit_limit', 0) or 0).replace(',', '').replace('$', '').strip() or 0)
                except (ValueError, TypeError):
                    bal, limit_ = 0, 0
                if limit_ > 0 and bal > 0:
                    if (bal / limit_) > 0.30:
                        has_high_util = True
                        break

    day1 = []
    day2 = []
    day3 = []

    day1.append({
        "title": "Do NOT apply for new credit",
        "why": "Every new inquiry can drop your score 5-10 points. Freeze activity for 45 days.",
        "do_next": "Set a calendar reminder: no applications until the investigation window closes.",
        "warning": "Even 'soft pull' pre-qualifications can sometimes trigger hard inquiries.",
    })

    if neg_count > 0:
        day1.append({
            "title": f"Review your {neg_count} negative mark{'s' if neg_count != 1 else ''}",
            "why": "Negative marks are the #1 score suppressor. Some can be removed with the right approach.",
            "do_next": "Your dispute letters already target these. Review them before mailing.",
            "script": (
                "If you call the creditor's executive office:\n"
                "\"I'm reviewing my credit file and found a negative mark from your company. "
                "I'd like to discuss a goodwill adjustment given my overall payment history. "
                "Can you connect me with someone who handles goodwill requests?\""
            ),
        })

    if wrong_count > 0:
        day1.append({
            "title": f"Flag {wrong_count} data inconsistenc{'ies' if wrong_count != 1 else 'y'}",
            "why": "Incorrect details (dates, balances, statuses) can trigger verification penalties.",
            "do_next": "Your letters cite FCRA Section 611 for each inaccuracy. Mail them promptly.",
        })

    if has_high_util:
        day1.append({
            "title": "Pay down high-utilization cards",
            "why": "Utilization over 30% drags your score. Under 10% is ideal.",
            "do_next": "Make a payment to bring your highest-balance card under 30% of its limit.",
        })

    if dup_count > 0:
        day2.append({
            "title": f"Confirm {dup_count} duplicate{'s are' if dup_count != 1 else ' is'} addressed",
            "why": "Double-reported accounts inflict double damage on your score.",
            "do_next": "Your dispute letters flag these. Verify each duplicate is included.",
        })

    bureau_list = ", ".join(sorted(b.title() for b in bureaus))
    day2.append({
        "title": f"Mail dispute letters to {bureau_list}",
        "why": "Certified mail creates a legal paper trail and starts the 30-day investigation clock.",
        "do_next": "Print, sign, and send via certified mail with return receipt requested.",
        "warning": "Do not send by email or regular mail — you need proof of delivery.",
    })

    if unverif_count > 0:
        day2.append({
            "title": "Gather supporting documentation",
            "why": "Having proof ready strengthens your position if the bureau pushes back.",
            "do_next": f"Pull any receipts, statements, or records that support your {unverif_count} unverifiable item{'s' if unverif_count != 1 else ''}.",
        })

    day3.append({
        "title": "Set up your 30-day tracking system",
        "why": "Bureaus must investigate within 30 days. Missing the window means free escalation leverage.",
        "do_next": "Use the Bureau Investigation Tracker below to monitor countdown and status.",
    })

    day3.append({
        "title": "Freeze non-essential credit activity",
        "why": "New accounts or inquiries during investigation can complicate your dispute.",
        "do_next": "Consider placing a temporary credit freeze via each bureau's website.",
    })

    if neg_count > 0:
        day3.append({
            "title": "Plan your escalation strategy",
            "why": "If bureaus don't respond in 30 days, you can escalate to the CFPB or state AG.",
            "do_next": "Review the escalation options that will unlock in your tracker after Day 30.",
        })

    day1 = day1[:4]
    day2 = day2[:3]
    day3 = day3[:3]

    return {
        "total_issues": selected_count,
        "high_impact": score_damaging + wrong_count,
        "score_damaging": score_damaging,
        "quick_wins": quick_wins,
        "days": [
            {"label": "Day 1 (Today)", "actions": day1},
            {"label": "Day 2", "actions": day2},
            {"label": "Day 3", "actions": day3},
        ],
    }


def render_command_plan_html(plan: Dict[str, Any], colors: Dict[str, str]) -> str:
    TEXT_0 = colors["TEXT_0"]
    TEXT_1 = colors["TEXT_1"]
    GOLD = colors["GOLD"]
    BG_1 = colors["BG_1"]
    BORDER = colors["BORDER"]

    chips_html = (
        f'<span class="ccp-chip ccp-chip-high">{plan["high_impact"]} High Impact</span>'
        f'<span class="ccp-chip ccp-chip-score">{plan["score_damaging"]} Score-Damaging</span>'
        f'<span class="ccp-chip ccp-chip-qw">{plan["quick_wins"]} Quick Win{"s" if plan["quick_wins"] != 1 else ""}</span>'
    )

    days_html = ""
    for i, day in enumerate(plan["days"]):
        actions_html = ""
        for action in day["actions"]:
            script_block = ""
            if action.get("script"):
                script_lines = action["script"].replace("\n", "<br>")
                script_block = (
                    f'<details class="ccp-script-detail">'
                    f'<summary class="ccp-script-toggle">&#x1F4DE; Call / Message Script</summary>'
                    f'<div class="ccp-script-content">{script_lines}</div>'
                    f'</details>'
                )

            warning_block = ""
            if action.get("warning"):
                warning_block = (
                    f'<div class="ccp-warning">'
                    f'&#x26A0;&#xFE0F; {action["warning"]}'
                    f'</div>'
                )

            actions_html += (
                f'<div class="ccp-action">'
                f'<div class="ccp-action-title">{action["title"]}</div>'
                f'<div class="ccp-action-why">{action["why"]}</div>'
                f'<div class="ccp-action-do">&#x2192; {action["do_next"]}</div>'
                f'{script_block}'
                f'{warning_block}'
                f'</div>'
            )

        day_class = "ccp-day-active" if i == 0 else ""
        day_num = i + 1
        days_html += (
            f'<div class="ccp-day {day_class}">'
            f'<div class="ccp-day-label"><span class="ccp-day-num">{day_num}</span>{day["label"]}</div>'
            f'{actions_html}'
            f'</div>'
        )

    return (
        f'<div class="ccp-wrap">'
        f'<div class="ccp-header">'
        f'<div class="ccp-badge">FREE</div>'
        f'<div class="ccp-title">Your 72-Hour Credit Command Plan</div>'
        f'<div class="ccp-subtitle">Your personalized action sequence for maximum credit score impact.</div>'
        f'<div class="ccp-chips">{chips_html}</div>'
        f'</div>'
        f'{days_html}'
        f'</div>'
    )
