"""
Report upload → parse job body (invoked by ``workflow_job_worker``).

Isolated so the same logic can move to an external worker process later
without changing the workflow engine or HTTP routes.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Dict, List

from services.report_pipeline import process_uploaded_reports
from services.report_upload_staging import (
    ReportUploadStagingError,
    merge_and_normalize_report_parts,
)
from services.workflow.claims_snapshot import persist_intake_claims_snapshot
from services.workflow.repository import fetch_session
from services.workflow.workflow_job_service import complete_job, fail_job

_log = logging.getLogger(__name__)


def _unlink_temp_paths(paths: List[str]) -> None:
    for p in paths:
        try:
            os.unlink(p)
        except OSError:
            pass


def execute_report_upload_parse_job(job: Dict[str, Any]) -> None:
    """Run ``report_upload_parse`` job — merge parts, parse, persist snapshot metadata, complete job row."""
    from services.me_org_report_service import apply_org_report_upload_side_effects

    jid = str(job["id"])
    wf = str(job["workflow_id"])
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    try:
        uid = int(payload["userId"])
    except (KeyError, TypeError, ValueError):
        fail_job(jid, "Invalid job payload: userId required", error_code="INVALID_JOB_PAYLOAD")
        return

    org_followup = bool(payload.get("orgProgramFollowup"))

    sess = fetch_session(wf)
    if not sess:
        fail_job(jid, "Workflow session not found", error_code="WORKFLOW_NOT_FOUND")
        return
    if int(sess["user_id"]) != uid:
        fail_job(jid, "Job userId does not match workflow owner", error_code="WORKFLOW_OWNER_MISMATCH")
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
            fail_job(jid, "Invalid org program upload payload", error_code="INVALID_ORG_PAYLOAD")
            return
        opts["organization_id"] = oid
        opts["organization_program_enrollment_id"] = eid
    else:
        opts["workflow_id"] = wf

    part_paths = payload.get("intakePartPaths")
    if not isinstance(part_paths, list) or len(part_paths) == 0:
        part_paths = payload.get("tempPartPaths")
    part_names = payload.get("partFilenames")
    raw: bytes
    fname: str

    _log.info("intake.parse_started workflow_id=%s job_id=%s", wf, jid)

    if (
        isinstance(part_paths, list)
        and isinstance(part_names, list)
        and len(part_paths) == len(part_names)
        and len(part_paths) > 0
    ):
        paths_to_clean = [str(p).strip() for p in part_paths]
        names_only = [str(n).strip() or "part.pdf" for n in part_names]
        if len(paths_to_clean) != len(names_only):
            fail_job(jid, "Invalid report upload staging payload", error_code="INVALID_STAGING_PAYLOAD")
            return
        sizes = payload.get("partByteSizes")
        hexes = payload.get("partSha256Hex")
        if (
            not isinstance(sizes, list)
            or not isinstance(hexes, list)
            or len(sizes) != len(paths_to_clean)
            or len(hexes) != len(paths_to_clean)
        ):
            fail_job(jid, "Report upload job missing integrity metadata", error_code="MISSING_STAGING_INTEGRITY")
            return
        parts_loaded: List[tuple[str, bytes]] = []
        try:
            for pth, n, exp_sz, exp_hx in zip(
                paths_to_clean, names_only, sizes, hexes
            ):
                if not pth or not os.path.isfile(pth):
                    _unlink_temp_paths(paths_to_clean)
                    fail_job(
                        jid,
                        "Report parse job missing staged file (intake artifact).",
                        error_code="PARSE_FAILED_INTAKE_ARTIFACT_MISSING",
                    )
                    return
                try:
                    want = int(exp_sz)
                except (TypeError, ValueError):
                    _unlink_temp_paths(paths_to_clean)
                    fail_job(jid, "Invalid staged part size in job payload", error_code="INVALID_PART_SIZE")
                    return
                st = os.path.getsize(pth)
                if st != want:
                    _unlink_temp_paths(paths_to_clean)
                    fail_job(
                        jid,
                        f"Staged file size mismatch (expected {want} bytes, found {st}).",
                        error_code="STAGING_SIZE_MISMATCH",
                    )
                    return
                with open(pth, "rb") as f:
                    raw_part = f.read()
                if len(raw_part) != want:
                    _unlink_temp_paths(paths_to_clean)
                    fail_job(jid, "Staged file read length mismatch.", error_code="STAGING_READ_MISMATCH")
                    return
                got = hashlib.sha256(raw_part).hexdigest()
                want_h = str(exp_hx).strip().lower()
                if got != want_h:
                    _unlink_temp_paths(paths_to_clean)
                    fail_job(
                        jid,
                        "Staged file failed integrity check (checksum mismatch).",
                        error_code="STAGING_CHECKSUM_MISMATCH",
                    )
                    return
                parts_loaded.append((n, raw_part))
        finally:
            _unlink_temp_paths(paths_to_clean)

        try:
            fname, raw = merge_and_normalize_report_parts(parts_loaded)
        except ReportUploadStagingError as e:
            fail_job(jid, e.message_safe, error_code="PDF_MERGE_FAILED")
            return
    else:
        path = (payload.get("tempPdfPath") or "").strip()
        fname = (payload.get("filename") or "report.pdf").strip() or "report.pdf"
        if not path or not os.path.isfile(path):
            fail_job(
                jid,
                "Report parse job missing staged file.",
                error_code="PARSE_FAILED_INTAKE_ARTIFACT_MISSING",
            )
            return
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as e:
            fail_job(jid, f"Could not read uploaded PDF: {e}", error_code="TEMP_READ_FAILED")
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
        fail_job(
            jid,
            "Report processing failed. Try again or use a different PDF.",
            error_code="PIPELINE_EXCEPTION",
        )
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

    review_claims = result.get("review_claims") or []
    if ok and not org_followup and wf and review_claims and report_ids:
        persist_intake_claims_snapshot(
            wf,
            report_ids=report_ids,
            compressed_claims=review_claims,
        )

    out_result: Dict[str, Any] = {
        "ok": ok,
        "reportsProcessed": processed,
        "fileSkips": skips,
        "reportIds": report_ids,
    }
    if not ok:
        out_result["errorCode"] = "PARSE_SKIPPED_OR_EMPTY"

    _log.info(
        "intake.parse_job_completing workflow_id=%s job_id=%s pipeline_ok=%s reports=%s",
        wf,
        jid,
        ok,
        processed,
    )
    complete_job(jid, out_result)
