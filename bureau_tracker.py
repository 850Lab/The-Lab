"""
Bureau Investigation Tracker
Countdown timers, dispute status, and escalation triggers.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import database as db


INVESTIGATION_WINDOW = 30

STATUS_LABELS = {
    "not_started": "Not Started",
    "ready_to_send": "Ready to Send",
    "sent": "Under Investigation",
    "response_received": "Response Received",
    "escalation_recommended": "Escalation Recommended",
}

STATUS_COLORS = {
    "not_started": ("#666666", "rgba(100,100,100,0.08)"),
    "ready_to_send": ("#1565C0", "rgba(66,165,245,0.08)"),
    "sent": ("#E65100", "rgba(255,167,38,0.08)"),
    "response_received": ("#2E7D32", "rgba(102,187,106,0.08)"),
    "escalation_recommended": ("#D32F2F", "rgba(239,83,80,0.08)"),
}

BUREAU_ICONS = {
    "experian": "&#x1F7E6;",
    "transunion": "&#x1F7E9;",
    "equifax": "&#x1F7E8;",
}


def compute_expected_outcome(category_counts: Dict[str, int]) -> str:
    neg = category_counts.get("negative", 0)
    wrong = category_counts.get("wrong", 0)
    dup = category_counts.get("duplicate", 0)
    unverif = category_counts.get("unverifiable", 0)
    total = neg + wrong + dup + unverif

    if total == 0:
        return "Low"
    if dup >= 2 or unverif >= 2:
        return "High"
    if neg >= 3 or wrong >= 4:
        return "High"
    if total >= 5:
        return "Medium"
    if neg >= 1 or wrong >= 2:
        return "Medium"
    return "Low"


def build_bureau_disputes(
    selected_items: list,
    bureaus: set,
    tracker_rows: list,
    lob_sends: Optional[List[Dict]] = None,
    has_generated_letters: bool = True,
    review_type_cls=None,
) -> List[Dict[str, Any]]:
    from review_claims import ReviewType
    RT = review_type_cls or ReviewType

    lob_by_bureau = {}
    if lob_sends:
        for send in lob_sends:
            if send.get('status') != 'mailed':
                continue
            b = (send.get('bureau') or '').lower()
            if b:
                dt = send.get('created_at')
                if dt and (b not in lob_by_bureau or dt < lob_by_bureau[b]):
                    lob_by_bureau[b] = dt

    global_mailed_at = None
    if tracker_rows:
        for t in tracker_rows:
            if t.get('mailed_at'):
                dt = t['mailed_at']
                if isinstance(dt, str):
                    try:
                        dt = datetime.fromisoformat(dt)
                    except Exception:
                        continue
                if global_mailed_at is None or dt > global_mailed_at:
                    global_mailed_at = dt

    bureau_items = {}
    for rc in selected_items:
        b = (rc.entities.get('bureau') or 'unknown').lower()
        if b not in bureau_items:
            bureau_items[b] = {"negative": 0, "wrong": 0, "duplicate": 0, "unverifiable": 0, "total": 0}
        bureau_items[b]["total"] += 1
        if rc.review_type == RT.NEGATIVE_IMPACT:
            bureau_items[b]["negative"] += 1
        elif rc.review_type == RT.ACCURACY_VERIFICATION:
            bureau_items[b]["wrong"] += 1
        elif rc.review_type == RT.DUPLICATE_ACCOUNT:
            bureau_items[b]["duplicate"] += 1
        elif rc.review_type == RT.UNVERIFIABLE_INFORMATION:
            bureau_items[b]["unverifiable"] += 1

    disputes = []
    for bureau in sorted(bureaus):
        b_lower = bureau.lower()
        counts = bureau_items.get(b_lower, {"negative": 0, "wrong": 0, "duplicate": 0, "unverifiable": 0, "total": 0})

        mailed_at = lob_by_bureau.get(b_lower) or global_mailed_at
        if mailed_at and isinstance(mailed_at, str):
            try:
                mailed_at = datetime.fromisoformat(mailed_at)
            except Exception:
                mailed_at = None

        if mailed_at:
            days_elapsed = (datetime.now() - mailed_at).days
            days_remaining = max(0, INVESTIGATION_WINDOW - days_elapsed)
            if days_elapsed >= INVESTIGATION_WINDOW + 1:
                status = "escalation_recommended"
            else:
                status = "sent"
        elif has_generated_letters and counts["total"] > 0:
            days_elapsed = 0
            days_remaining = INVESTIGATION_WINDOW
            status = "ready_to_send"
        else:
            days_elapsed = 0
            days_remaining = INVESTIGATION_WINDOW
            status = "not_started"

        expected_outcome = compute_expected_outcome(counts)

        disputes.append({
            "bureau": bureau.title(),
            "bureau_lower": b_lower,
            "icon": BUREAU_ICONS.get(b_lower, "&#x1F4CB;"),
            "date_sent": mailed_at.strftime("%b %d, %Y") if mailed_at else None,
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
            "accounts_count": counts["total"],
            "status": status,
            "expected_outcome": expected_outcome,
            "category_counts": counts,
        })

    return disputes


def render_bureau_tracker_html(disputes: List[Dict[str, Any]], colors: Dict[str, str]) -> str:
    TEXT_0 = colors["TEXT_0"]
    TEXT_1 = colors["TEXT_1"]
    GOLD = colors["GOLD"]

    cards_html = ""
    for d in disputes:
        status_label = STATUS_LABELS.get(d["status"], "Unknown")
        status_color, status_bg = STATUS_COLORS.get(d["status"], ("#666", "rgba(100,100,100,0.08)"))

        date_display = d["date_sent"] if d["date_sent"] else "Not sent yet"

        pct = min(100, int((d["days_elapsed"] / INVESTIGATION_WINDOW) * 100)) if d["status"] in ("sent", "escalation_recommended") else 0
        bar_color = "#EF5350" if d["status"] == "escalation_recommended" else GOLD

        outcome_color = {"High": "#2E7D32", "Medium": "#E65100", "Low": "#666666"}.get(d["expected_outcome"], TEXT_1)

        countdown_html = ""
        if d["status"] in ("sent", "escalation_recommended"):
            bar_active = " bt-bar-fill-active" if d["status"] == "sent" else ""
            countdown_html = (
                f'<div class="bt-countdown">'
                f'<div class="bt-countdown-labels">'
                f'<span>Day {d["days_elapsed"]}</span>'
                f'<span>{d["days_remaining"]} day{"s" if d["days_remaining"] != 1 else ""} left</span>'
                f'</div>'
                f'<div class="bt-bar"><div class="bt-bar-fill{bar_active}" style="width:{pct}%;background:{bar_color};"></div></div>'
                f'</div>'
            )

        escalation_html = ""
        if d["status"] == "escalation_recommended":
            escalation_html = (
                f'<div class="bt-escalation">'
                f'<div class="bt-escalation-title">&#x26A0;&#xFE0F; Investigation window elapsed &mdash; escalation recommended</div>'
                f'<div class="bt-escalation-actions">'
                f'<span class="bt-esc-btn">Method of Verification Letter</span>'
                f'<span class="bt-esc-btn">CFPB Complaint Draft</span>'
                f'<span class="bt-esc-btn">Executive Escalation Letter</span>'
                f'</div>'
                f'</div>'
            )

        cards_html += (
            f'<div class="bt-card">'
            f'<div class="bt-card-top">'
            f'<div class="bt-bureau-icon">{d["icon"]}</div>'
            f'<div class="bt-bureau-info">'
            f'<div class="bt-bureau-name">{d["bureau"]}</div>'
            f'<div class="bt-bureau-date">{date_display}</div>'
            f'</div>'
            f'<div class="bt-status-pill" style="color:{status_color};background:{status_bg};">{status_label}</div>'
            f'</div>'
            f'{countdown_html}'
            f'<div class="bt-meta">'
            f'<span class="bt-meta-item">{d["accounts_count"]} account{"s" if d["accounts_count"] != 1 else ""}</span>'
            f'<span class="bt-meta-item">Outcome: <strong style="color:{outcome_color};">{d["expected_outcome"]}</strong></span>'
            f'</div>'
            f'{escalation_html}'
            f'</div>'
        )

    return (
        f'<div class="bt-wrap">'
        f'<div class="bt-header">'
        f'<div class="bt-badge">FREE</div>'
        f'<div class="bt-title">Bureau Investigation Tracker</div>'
        f'<div class="bt-subtitle">Real-time countdown for each bureau\'s 30-day investigation window.</div>'
        f'</div>'
        f'{cards_html}'
        f'</div>'
    )
