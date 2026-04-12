"""
Customer-facing sync bundle: job activity + parse readiness for one workflow.

Attached to resume / workflow payloads so the SPA can use a single refresh surface.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.workflow.workflow_job_service import (
    JOB_TYPE_REPORT_UPLOAD_PARSE,
    STATUS_PENDING,
    STATUS_RUNNING,
    list_jobs,
    public_job_view,
)

_STEP_UPLOAD = "upload"
_STEP_PARSE = "parse_analyze"


def _step_status(step_status: Optional[List[Dict[str, Any]]], step_id: str) -> Optional[str]:
    if not step_status:
        return None
    for row in step_status:
        if str(row.get("stepId") or row.get("step_id") or "") == step_id:
            return str(row.get("status") or "")
    return None


def build_workflow_sync_payload(
    workflow_id: str,
    step_status: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Non-authoritative observability: active parse jobs, last terminal parse job, parse readiness.
    Step truth remains in ``stepStatus`` / engine.
    """
    wf = (workflow_id or "").strip()
    if not wf:
        return {
            "activeReportParseJobs": [],
            "lastReportParseJob": None,
            "parseReadiness": {
                "uploadStepStatus": None,
                "parseStepStatus": None,
                "asyncPhase": "idle",
            },
        }

    jobs = list_jobs(wf, limit=40)
    parse_jobs = [j for j in jobs if str(j.get("job_type") or "") == JOB_TYPE_REPORT_UPLOAD_PARSE]

    raw_active = [
        j
        for j in parse_jobs
        if str(j.get("status") or "") in (STATUS_PENDING, STATUS_RUNNING)
    ]
    active = [public_job_view(j) for j in raw_active]

    last_terminal: Optional[Dict[str, Any]] = None
    for j in parse_jobs:
        st = str(j.get("status") or "")
        if st in ("completed", "failed"):
            last_terminal = public_job_view(j)
            break

    upload_st = _step_status(step_status, _STEP_UPLOAD)
    parse_st = _step_status(step_status, _STEP_PARSE)

    if raw_active:
        phase = (
            "pending"
            if any(str(x.get("status") or "") == STATUS_PENDING for x in raw_active)
            else "running"
        )
    elif parse_st == "completed":
        phase = "steady"
    else:
        phase = "idle"

    return {
        "activeReportParseJobs": active,
        "lastReportParseJob": last_terminal,
        "parseReadiness": {
            "uploadStepStatus": upload_st,
            "parseStepStatus": parse_st,
            "asyncPhase": phase,
        },
    }
