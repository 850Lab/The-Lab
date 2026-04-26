"""
Workflow-facing intake / parse visibility (authoritative job row + runtime worker hints).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.workflow.workflow_job_service import (
    JOB_TYPE_REPORT_UPLOAD_PARSE,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    get_job,
)


def workflow_parse_worker_enabled() -> bool:
    raw = (os.environ.get("WORKFLOW_JOB_WORKER_ENABLED") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _parse_ts(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        dt = val
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    if isinstance(val, str):
        try:
            if val.endswith("Z"):
                val = val[:-1] + "+00:00"
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


def build_report_parse_intake_status(
    workflow_id: str,
    job_id: str,
    *,
    job_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Map ``report_upload_parse`` job row → explicit phase + safe client hints.

    Phases align with orchestration (not PDF merge internals).
    """
    jid = (job_id or "").strip()
    wf = (workflow_id or "").strip()
    worker_on = workflow_parse_worker_enabled()
    base: Dict[str, Any] = {
        "parseJobId": jid,
        "backgroundWorkerEnabled": worker_on,
    }

    row = job_row if job_row is not None else (get_job(jid) if jid else None)
    if not row or str(row.get("workflow_id") or "") != wf:
        return {
            **base,
            "phase": "parse_unknown",
            "parseJobStatus": None,
            "userSafeSummary": "Upload status could not be loaded. Try refreshing.",
            "nextAction": "retry_check",
        }

    jt = str(row.get("job_type") or "")
    if jt != JOB_TYPE_REPORT_UPLOAD_PARSE:
        return {
            **base,
            "phase": "parse_unknown",
            "parseJobStatus": str(row.get("status") or ""),
            "userSafeSummary": "This job is not a report parse task.",
            "nextAction": "retry_check",
        }

    st = str(row.get("status") or "")
    res = row.get("result") if isinstance(row.get("result"), dict) else {}
    err_code = None
    if isinstance(res, dict):
        err_code = res.get("errorCode")
    err_text = str(row.get("error") or "").strip() or None

    created = _parse_ts(row.get("created_at"))
    pending_age_sec: Optional[float] = None
    if created and st == STATUS_PENDING:
        pending_age_sec = max(0.0, (datetime.now(timezone.utc) - created).total_seconds())

    phase = "parse_pending"
    summary = "Your file is saved; parsing is queued."
    next_action = "wait"

    if st == STATUS_RUNNING:
        phase = "parse_running"
        summary = "Your credit report is being processed."
    elif st == STATUS_COMPLETED:
        phase = "parse_completed"
        ok = bool(res.get("ok")) if isinstance(res, dict) else False
        if ok:
            summary = "Parsing finished successfully."
            next_action = "continue"
        else:
            phase = "parse_failed"
            summary = "Parsing finished but no usable report was produced."
            next_action = "retry_upload"
    elif st == STATUS_FAILED:
        phase = "parse_failed"
        summary = err_text or "Parsing failed."
        next_action = "retry_upload"
    elif st == STATUS_PENDING:
        if not worker_on:
            phase = "parse_worker_unavailable"
            summary = (
                "Your file was accepted, but background processing is disabled on this server. "
                "An operator must enable the workflow job worker or run processing manually."
            )
            next_action = "blocked"
        elif pending_age_sec is not None and pending_age_sec > 120:
            summary = (
                "Your file is saved; parsing is still queued. "
                "If this lasts several minutes, the background worker may be stuck or overloaded."
            )
            next_action = "wait"

    out: Dict[str, Any] = {
        **base,
        "phase": phase,
        "parseJobStatus": st,
        "userSafeSummary": summary[:500],
        "nextAction": next_action,
    }
    if err_code:
        out["parseErrorCode"] = str(err_code)[:128]
    if pending_age_sec is not None:
        out["pendingSecondsApprox"] = int(pending_age_sec)
    return out
