"""
Enqueue ``report_upload_parse`` with durable on-disk inputs (not request temp paths).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from services.report_intake_artifacts import promote_temp_files_to_durable, rmtree_intake_job
from services.workflow.workflow_job_service import JOB_TYPE_REPORT_UPLOAD_PARSE, create_job

_log = logging.getLogger(__name__)


def enqueue_durable_report_upload_parse_job(
    workflow_id: str,
    user_id: int,
    temp_part_paths: List[str],
    part_filenames: List[str],
    part_byte_sizes: List[int],
    part_sha256_hex: List[str],
    *,
    org_program_followup: bool = False,
    organization_id: Optional[int] = None,
    organization_program_enrollment_id: Optional[int] = None,
    dedupe_pending: bool = False,
) -> str:
    """
    Move staged temp parts into durable intake storage, insert ``workflow_jobs`` row.

    On failure after promotion, the intake directory for this job id is removed.
    """
    wf = (workflow_id or "").strip()
    if not wf:
        raise ValueError("workflow_id required")
    jid = str(uuid.uuid4())

    durable_paths = promote_temp_files_to_durable(wf, jid, temp_part_paths)

    payload: Dict[str, Any] = {
        "userId": int(user_id),
        "staging": "durable_parts_v1",
        "intakePartPaths": durable_paths,
        "partFilenames": list(part_filenames),
        "partByteSizes": list(part_byte_sizes),
        "partSha256Hex": list(part_sha256_hex),
    }
    if org_program_followup:
        payload["orgProgramFollowup"] = True
        payload["organizationId"] = int(organization_id or 0)
        payload["organizationProgramEnrollmentId"] = int(organization_program_enrollment_id or 0)

    try:
        created = create_job(
            wf,
            JOB_TYPE_REPORT_UPLOAD_PARSE,
            payload,
            dedupe_pending=dedupe_pending,
            job_id=jid,
        )
    except Exception:
        rmtree_intake_job(wf, jid)
        raise

    _log.info(
        "intake.parse_job_created workflow_id=%s job_id=%s user_id=%s staging=durable_parts_v1",
        wf,
        created,
        int(user_id),
    )
    return created
