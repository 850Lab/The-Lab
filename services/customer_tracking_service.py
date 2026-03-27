"""
Customer tracking step: post-send Lob rows + workflow / home-summary hints (Streamlit parity for status).

Does not call Lob live APIs; uses durable ``lob_sends`` + workflow step rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import database as db
import lob_client
from services.customer_dispute_strategy import parse_workflow_metadata_value
from services.customer_mail_service import (
    latest_lob_row_for_target,
    resolve_mail_targets,
    selected_bureau_keys_from_session,
)
from services.workflow.engine import compute_authoritative_step
from services.workflow.home_summary_service import build_home_summary
from services.workflow.mail_gating import get_mail_gate_state
from services.workflow.repository import fetch_steps


def _norm_bureau(b: str) -> str:
    return (b or "").strip().lower()[:32]


def _iso(dt: Any) -> str:
    if dt is None:
        return ""
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def _parse_dt(dt: Any) -> Optional[datetime]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def build_tracking_context_payload(
    user_id: int,
    workflow_id: str,
    *,
    session_row: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    steps = fetch_steps(workflow_id)
    smap = {s["step_id"]: s for s in steps}
    head, phase = compute_authoritative_step(smap)
    mail_row = smap.get("mail") or {}
    track_row = smap.get("track") or {}

    meta = parse_workflow_metadata_value((session_row or {}).get("metadata"))
    expected, confirmed, failed_ct = get_mail_gate_state(meta)
    mail_meta = meta.get("mail") if isinstance(meta.get("mail"), dict) else {}
    last_fail = ""
    if isinstance(mail_meta, dict):
        last_fail = str(mail_meta.get("last_failure_message_safe") or "")[:400]

    targets = resolve_mail_targets(user_id, selected_bureau_keys_from_session(session_row))

    bureau_rows: List[Dict[str, Any]] = []
    earliest_mailed: Optional[datetime] = None

    for t in targets:
        b = _norm_bureau(str(t.get("bureau") or ""))
        rid = t.get("reportId")
        disp = str(t.get("bureauDisplay") or b.title())
        lob_r = latest_lob_row_for_target(user_id, b, rid)

        row_status = "not_mailed"
        tn = ""
        trk_url = ""
        exp_del = ""
        mailed_at = ""
        err_msg = ""
        lob_db_status = ""
        is_test_send = False
        lob_id_str = ""

        if lob_r:
            lob_db_status = str(lob_r.get("status") or "").lower()
            mailed_at = _iso(lob_r.get("created_at"))
            exp_del = str(lob_r.get("expected_delivery") or "")
            err_msg = str(lob_r.get("error_message") or "")[:300]
            lob_id_str = str(lob_r.get("lob_id") or "")
            is_test_send = bool(lob_r.get("is_test"))
            if lob_db_status == "mailed":
                row_status = "mailed"
                tn = str(lob_r.get("tracking_number") or "")
                trk_url = lob_client.get_tracking_url(tn) if tn else ""
                dt = _parse_dt(lob_r.get("created_at"))
                if dt and (earliest_mailed is None or dt < earliest_mailed):
                    earliest_mailed = dt
            elif lob_db_status == "error":
                row_status = "error"
            else:
                row_status = "other"

        if row_status == "not_mailed":
            display_status = "Not submitted"
        elif row_status == "error":
            display_status = "Send failed"
        elif row_status == "other":
            display_status = "Processing"
        elif row_status == "mailed" and is_test_send:
            display_status = "Test — no USPS mail"
        elif row_status == "mailed" and trk_url:
            display_status = "Submitted — tracking active"
        elif row_status == "mailed":
            display_status = "Submitted — tracking pending"
        else:
            display_status = "Unknown"

        bureau_rows.append(
            {
                "bureau": b,
                "bureauDisplay": disp,
                "reportId": rid,
                "rowStatus": row_status,
                "displayStatus": display_status,
                "trackingNumber": tn,
                "trackingUrl": trk_url,
                "expectedDelivery": exp_del,
                "mailedAt": mailed_at,
                "lobDbStatus": lob_db_status,
                "errorMessage": err_msg if row_status == "error" else "",
                "isTestSend": is_test_send,
                "lobId": lob_id_str,
            }
        )

    days_since = 0
    if earliest_mailed:
        now = datetime.now(timezone.utc)
        delta = now - earliest_mailed
        days_since = max(0, min(30, delta.days))

    hs = build_home_summary(workflow_id)
    home_compact: Optional[Dict[str, Any]] = None
    if isinstance(hs, dict) and hs.get("ok"):
        home_compact = {
            "nextBestAction": hs.get("nextBestAction"),
            "waitingOn": hs.get("waitingOn"),
            "failedStep": hs.get("failedStep"),
            "safeRouteHint": hs.get("safeRouteHint"),
            "responseStatus": hs.get("responseStatus"),
            "currentStepId": hs.get("currentStepId"),
            "overallStatus": hs.get("overallStatus"),
            "linearPhase": hs.get("linearPhase"),
            "stalled": hs.get("stalled"),
            "escalationAvailable": hs.get("escalationAvailable"),
        }

    mailed_ct = sum(1 for x in bureau_rows if x.get("rowStatus") == "mailed")
    pending_mail_ct = sum(1 for x in bureau_rows if x.get("rowStatus") == "not_mailed")
    mailed_live_ct = sum(
        1
        for x in bureau_rows
        if x.get("rowStatus") == "mailed" and not x.get("isTestSend")
    )
    mailed_test_ct = sum(
        1
        for x in bureau_rows
        if x.get("rowStatus") == "mailed" and x.get("isTestSend")
    )
    any_tracking = any(bool(str(x.get("trackingUrl") or "").strip()) for x in bureau_rows)

    if not bureau_rows:
        ts_title = "No mail targets"
        ts_message = "Dispute letters and sends are not on file for this workflow yet."
    elif mailed_ct == 0:
        ts_title = "Nothing submitted yet"
        ts_message = (
            "No certified send is recorded for your selected bureaus. "
            "Complete the send step first — generating letters is not the same as mailing."
        )
    elif mailed_test_ct > 0 and mailed_live_ct > 0:
        ts_title = "Mix of test and live mail"
        ts_message = (
            "Some bureaus used Lob test mode (no USPS mail); others used live mail. "
            "Use each row below to see which is which."
        )
    elif mailed_test_ct > 0 and mailed_live_ct == 0:
        ts_title = "Test sends only"
        ts_message = (
            "Recorded sends used Lob test mode. No physical USPS letters were produced. "
            "Anything labeled tracking is for test artifacts, not live delivery."
        )
    elif mailed_live_ct > 0 and any_tracking:
        ts_title = "Tracking available"
        ts_message = (
            "USPS tracking shows handoff and transit when a number is on file. "
            "That is not proof of delivery to the bureau’s decision desk."
        )
    elif mailed_live_ct > 0:
        ts_title = "Submitted — tracking pending"
        ts_message = (
            "Live mail was accepted by the processor. "
            "A USPS tracking number may appear after the piece is fully processed."
        )
    else:
        ts_title = "Status"
        ts_message = "Review each bureau row for the latest recorded status."

    tracking_status = {
        "title": ts_title,
        "message": ts_message,
        "hasLiveSubmissions": mailed_live_ct > 0,
        "hasTestSubmissionsOnly": mailed_ct > 0 and mailed_live_ct == 0,
        "hasTrackingLink": any_tracking,
    }

    return {
        "authoritativeHeadStepId": head,
        "linearPhase": phase,
        "mailStepStatus": mail_row.get("status"),
        "trackStepStatus": track_row.get("status"),
        "onTrackStep": head == "track" and phase == "active",
        "trackStepCompleted": track_row.get("status") == "completed",
        "mailGateExpected": expected,
        "mailGateConfirmedBureaus": confirmed,
        "mailGateFailedSendCount": failed_ct,
        "mailGateLastFailureMessageSafe": last_fail,
        "bureauRows": bureau_rows,
        "mailedBureauCount": mailed_ct,
        "notMailedBureauCount": pending_mail_ct,
        "hasTargets": len(bureau_rows) > 0,
        "timeline": {
            "earliestMailedAt": earliest_mailed.isoformat() if earliest_mailed else "",
            "daysSinceFirstMail": days_since,
            "timelineTotalDays": 30,
        },
        "homeSummary": home_compact,
        "trackingStatus": tracking_status,
    }
