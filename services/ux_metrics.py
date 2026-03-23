"""Pure UX flow score aggregation from event lists (Streamlit-free)."""

from __future__ import annotations

from typing import Any, Dict, List


def compute_uxfs_report(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    COUNTED_EVENTS = {"TAP", "UPLOAD", "CHECK", "APPROVE", "GENERATE"}
    screens = ["UPLOAD", "REVIEW", "BUILD", "GENERATE"]

    screen_events = {s: [] for s in screens}
    for ev in events:
        s = ev["screen"]
        if s not in screen_events:
            screen_events[s] = []
        screen_events[s].append(ev)

    screen_dt_seconds = {s: 0.0 for s in screen_events}
    for i in range(len(events) - 1):
        delta = events[i + 1]["ts"] - events[i]["ts"]
        s = events[i]["screen"]
        screen_dt_seconds[s] += delta

    def dt_bucket(seconds):
        if seconds < 1:
            return 1
        elif seconds <= 3:
            return 2
        elif seconds <= 7:
            return 3
        else:
            return 4

    report_rows = []
    total_uxfs = 0.0

    for s in screen_events:
        counted = [e for e in screen_events[s] if e["event"] in COUNTED_EVENTS]
        fc = len(counted)
        dt_sec = screen_dt_seconds.get(s, 0.0)
        dt_b = dt_bucket(dt_sec)
        if counted:
            cc_avg = round(sum(e["cc"] for e in counted) / len(counted), 2)
        else:
            cc_avg = 4
            fc = 0
        uxfs = (fc * dt_b) / max(cc_avg, 1)
        total_uxfs += uxfs
        report_rows.append(
            {
                "screen": s,
                "FC": fc,
                "DT_seconds": round(dt_sec, 3),
                "DT_bucket": dt_b,
                "CC_avg": cc_avg,
                "UXFS": round(uxfs, 4),
            }
        )

    return {
        "rows": report_rows,
        "total_uxfs": round(total_uxfs, 4),
        "raw_event_count": len(events),
    }
