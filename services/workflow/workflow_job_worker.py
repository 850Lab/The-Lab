"""
In-process background worker: polls ``workflow_jobs``, claims, executes known job types.

No Celery/Redis — single daemon thread inside the FastAPI process.

Control layer: each job type must map in ``job_type_to_customer_action`` so execution is
preflight-gated like the matching HTTP route. Add a mapping before introducing new
``job_type`` values, or jobs will fail at dispatch after preflight returns unsupported.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from services.workflow.workflow_job_service import (
    JOB_TYPE_LETTER_GENERATION,
    JOB_TYPE_REPORT_UPLOAD_PARSE,
    complete_job,
    fail_job,
)
from services.workflow.workflow_flow_gates import (
    FlowEnforcementError,
    enforce_customer_action,
    job_type_to_customer_action,
)
from services.workflow.repository import fetch_session

_log = logging.getLogger(__name__)

_worker_thread: Optional[threading.Thread] = None
_stop_flag = threading.Event()


def _job_flow_preflight(job: Dict[str, Any]) -> Optional[str]:
    """
    Before executing a job, apply the same customer flow gate as the enqueueing HTTP route.
    Returns a human-safe error string to fail the job with, or None if OK / no mapping.
    """
    jt = str(job.get("job_type") or "").strip()
    action_key = job_type_to_customer_action(jt)
    if not action_key:
        return None
    wf = str(job.get("workflow_id") or "")
    try:
        enforce_customer_action(wf, action_key)
    except FlowEnforcementError as e:
        return e.message_safe
    return None


def _execute_letter_generation(job: Dict[str, Any]) -> None:
    from services.customer_letter_service import run_letter_generation

    jid = str(job["id"])
    wf = str(job["workflow_id"])
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    try:
        uid = int(payload["userId"])
    except (KeyError, TypeError, ValueError):
        fail_job(jid, "Invalid job payload: userId required")
        return

    is_admin = bool(payload.get("isAdmin", False))

    sess = fetch_session(wf)
    if not sess:
        fail_job(jid, "Workflow session not found")
        return
    if int(sess["user_id"]) != uid:
        fail_job(jid, "Job userId does not match workflow owner")
        return

    result, err = run_letter_generation(
        uid,
        wf,
        session_row=sess,
        is_admin=is_admin,
    )
    if err:
        fail_job(jid, err)
        return

    letters = result.get("letters") or {}
    bureaus = [str(b).lower() for b in letters.keys() if b]
    complete_job(
        jid,
        {
            "bureaus": bureaus,
            "billing": result.get("billing"),
            "hasReadiness": bool(result.get("readiness")),
        },
    )


def _execute_report_upload_parse(job: Dict[str, Any]) -> None:
    from services.workflow.jobs.report_upload_parse import execute_report_upload_parse_job

    execute_report_upload_parse_job(job)


# Single registry: DB `job_type` must match these keys (see workflow_job_service constants).
_JOB_HANDLERS: Dict[str, Callable[[Dict[str, Any]], None]] = {
    JOB_TYPE_LETTER_GENERATION: _execute_letter_generation,
    JOB_TYPE_REPORT_UPLOAD_PARSE: _execute_report_upload_parse,
}


def _dispatch(job: Dict[str, Any]) -> None:
    jid = str(job["id"])
    pre_err = _job_flow_preflight(job)
    if pre_err:
        fail_job(jid, pre_err, error_code="FLOW_GATE")
        return

    jt = str(job.get("job_type") or "").strip()
    handler = _JOB_HANDLERS.get(jt)
    if handler:
        handler(job)
        return

    fail_job(jid, f"Unsupported job_type: {jt}", error_code="UNSUPPORTED_JOB_TYPE")


def _worker_loop() -> None:
    from services.workflow.workflow_job_service import claim_job

    raw = (os.environ.get("WORKFLOW_JOB_POLL_SEC") or "2").strip()
    try:
        poll = max(0.5, min(60.0, float(raw)))
    except ValueError:
        poll = 2.0

    _log.info("workflow job worker started (poll=%ss)", poll)
    while not _stop_flag.is_set():
        try:
            job = claim_job()
            if job:
                _dispatch(job)
            else:
                time.sleep(poll)
        except Exception:
            _log.exception("workflow job worker iteration failed")
            time.sleep(poll)
    _log.info("workflow job worker stopped")


def start_job_worker() -> None:
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        _log.info("workflow job worker already running; start skipped")
        return
    _stop_flag.clear()
    _worker_thread = threading.Thread(
        target=_worker_loop,
        name="workflow-job-worker",
        daemon=True,
    )
    _worker_thread.start()
    _log.info("workflow job worker thread spawned (in-process background parse/letter jobs)")


def stop_job_worker() -> None:
    _stop_flag.set()
