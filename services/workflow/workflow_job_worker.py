"""
In-process background worker: polls ``workflow_jobs``, claims, executes known job types.

No Celery/Redis — single daemon thread inside the FastAPI process.

Control layer: each job type must map in ``job_type_to_customer_action`` so execution is
preflight-gated like the matching HTTP route. Add a mapping before introducing new
``job_type`` values, or jobs will fail at dispatch after preflight returns unsupported.
"""

from __future__ import annotations

import hashlib
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


def _unlink_temp_paths(paths: List[str]) -> None:
    for p in paths:
        try:
            os.unlink(p)
        except OSError:
            pass


def _execute_report_upload_parse(job: Dict[str, Any]) -> None:
    from services.me_org_report_service import apply_org_report_upload_side_effects
    from services.report_pipeline import process_uploaded_reports
    from services.report_upload_staging import (
        ReportUploadStagingError,
        merge_and_normalize_report_parts,
    )

    jid = str(job["id"])
    wf = str(job["workflow_id"])
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    try:
        uid = int(payload["userId"])
    except (KeyError, TypeError, ValueError):
        fail_job(jid, "Invalid job payload: userId required")
        return

    org_followup = bool(payload.get("orgProgramFollowup"))

    sess = fetch_session(wf)
    if not sess:
        fail_job(jid, "Workflow session not found")
        return
    if int(sess["user_id"]) != uid:
        fail_job(jid, "Job userId does not match workflow owner")
        return

    opts: Dict[str, Any] = {
        "user_id": uid,
        "mutation_channel": "workflow_http",
    }
    oid = 0
    eid = 0
    if org_followup:
        try:
            oid = int(payload["organizationId"])
            eid = int(payload["organizationProgramEnrollmentId"])
        except (KeyError, TypeError, ValueError):
            fail_job(jid, "Invalid org program upload payload")
            return
        opts["organization_id"] = oid
        opts["organization_program_enrollment_id"] = eid
    else:
        opts["workflow_id"] = wf

    part_paths = payload.get("tempPartPaths")
    part_names = payload.get("partFilenames")
    raw: bytes
    fname: str

    if (
        isinstance(part_paths, list)
        and isinstance(part_names, list)
        and len(part_paths) == len(part_names)
        and len(part_paths) > 0
    ):
        paths_to_clean = [str(p).strip() for p in part_paths]
        names_only = [str(n).strip() or "part.pdf" for n in part_names]
        if len(paths_to_clean) != len(names_only):
            fail_job(jid, "Invalid report upload staging payload")
            return
        sizes = payload.get("partByteSizes")
        hexes = payload.get("partSha256Hex")
        if (
            not isinstance(sizes, list)
            or not isinstance(hexes, list)
            or len(sizes) != len(paths_to_clean)
            or len(hexes) != len(paths_to_clean)
        ):
            fail_job(jid, "Report upload job missing integrity metadata")
            return
        parts_loaded: List[tuple[str, bytes]] = []
        try:
            for pth, n, exp_sz, exp_hx in zip(
                paths_to_clean, names_only, sizes, hexes
            ):
                if not pth or not os.path.isfile(pth):
                    _unlink_temp_paths(paths_to_clean)
                    fail_job(jid, "Report parse job missing temp file")
                    return
                try:
                    want = int(exp_sz)
                except (TypeError, ValueError):
                    _unlink_temp_paths(paths_to_clean)
                    fail_job(jid, "Invalid staged part size in job payload")
                    return
                st = os.path.getsize(pth)
                if st != want:
                    _unlink_temp_paths(paths_to_clean)
                    fail_job(
                        jid,
                        f"Staged file size mismatch (expected {want} bytes, found {st}).",
                    )
                    return
                with open(pth, "rb") as f:
                    raw_part = f.read()
                if len(raw_part) != want:
                    _unlink_temp_paths(paths_to_clean)
                    fail_job(jid, "Staged file read length mismatch.")
                    return
                got = hashlib.sha256(raw_part).hexdigest()
                want_h = str(exp_hx).strip().lower()
                if got != want_h:
                    _unlink_temp_paths(paths_to_clean)
                    fail_job(
                        jid,
                        "Staged file failed integrity check (checksum mismatch).",
                    )
                    return
                parts_loaded.append((n, raw_part))
        finally:
            _unlink_temp_paths(paths_to_clean)

        try:
            fname, raw = merge_and_normalize_report_parts(parts_loaded)
        except ReportUploadStagingError as e:
            fail_job(jid, e.message_safe)
            return
    else:
        path = (payload.get("tempPdfPath") or "").strip()
        fname = (payload.get("filename") or "report.pdf").strip() or "report.pdf"
        if not path or not os.path.isfile(path):
            fail_job(jid, "Report parse job missing temp file")
            return
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as e:
            fail_job(jid, f"Could not read uploaded PDF: {e}")
            return
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    try:
        result = process_uploaded_reports([(fname, raw)], opts)
    except Exception:
        _log.exception("report_upload_parse job failed workflow_id=%s job_id=%s", wf, jid)
        fail_job(jid, "Report processing failed. Try again or use a different PDF.")
        return

    skips = result.get("file_skips") or []
    processed = int(result.get("reports_processed") or 0)
    ok = processed > 0 and len(skips) == 0

    if org_followup and ok:
        apply_org_report_upload_side_effects(
            uid,
            oid,
            eid,
            result,
            audit_source="api:me_report",
        )

    report_ids: List[int] = []
    for _k, rep in (result.get("uploaded_reports") or {}).items():
        rid = rep.get("report_id")
        if rid is not None:
            report_ids.append(int(rid))

    complete_job(
        jid,
        {
            "ok": ok,
            "reportsProcessed": processed,
            "fileSkips": skips,
            "reportIds": report_ids,
        },
    )


# Single registry: DB `job_type` must match these keys (see workflow_job_service constants).
_JOB_HANDLERS: Dict[str, Callable[[Dict[str, Any]], None]] = {
    JOB_TYPE_LETTER_GENERATION: _execute_letter_generation,
    JOB_TYPE_REPORT_UPLOAD_PARSE: _execute_report_upload_parse,
}


def _dispatch(job: Dict[str, Any]) -> None:
    jid = str(job["id"])
    pre_err = _job_flow_preflight(job)
    if pre_err:
        fail_job(jid, pre_err)
        return

    jt = str(job.get("job_type") or "").strip()
    handler = _JOB_HANDLERS.get(jt)
    if handler:
        handler(job)
        return

    fail_job(jid, f"Unsupported job_type: {jt}")


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
        return
    _stop_flag.clear()
    _worker_thread = threading.Thread(
        target=_worker_loop,
        name="workflow-job-worker",
        daemon=True,
    )
    _worker_thread.start()


def stop_job_worker() -> None:
    _stop_flag.set()
