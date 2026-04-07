"""
Create and load ``report_upload_sessions`` rows for direct-to-storage uploads.

Session ``status`` values: ``pending_upload`` → ``finalizing`` (during finalize) → ``finalized``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from database import get_db
from psycopg2.extras import Json

from services.report_upload_object_storage import (
    ReportUploadStorageError,
    delete_object,
    generate_presigned_put_url,
    get_object_bytes,
    head_object,
    object_storage_configured,
    report_upload_bucket,
)
from services.report_upload_staging import MAX_SINGLE_REPORT_UPLOAD_MB
from services.workflow.workflow_job_service import (
    JOB_TYPE_REPORT_UPLOAD_PARSE,
    create_job,
)

_log = logging.getLogger(__name__)


def _session_ttl_seconds() -> int:
    raw = (os.environ.get("REPORT_UPLOAD_SESSION_TTL_SECONDS") or "3600").strip()
    try:
        s = int(raw)
    except ValueError:
        s = 3600
    return max(300, min(s, 86400))


def _presign_ttl_seconds() -> int:
    """Presigned URL lifetime (typically <= session TTL)."""
    raw = (os.environ.get("REPORT_UPLOAD_PRESIGN_EXPIRES_SECONDS") or "").strip()
    if raw:
        try:
            return max(60, min(int(raw), 604800))
        except ValueError:
            pass
    return min(_session_ttl_seconds(), 3600)


def create_report_upload_session(
    *,
    user_id: int,
    workflow_id: str,
    kind: str,
    organization_id: Optional[int] = None,
    organization_program_enrollment_id: Optional[int] = None,
    content_type: str = "application/pdf",
) -> Dict[str, Any]:
    """
    Insert a pending session row and return presigned PUT + metadata.

    Raises ``ReportUploadStorageError`` if object storage is not configured.
    """
    if not object_storage_configured():
        raise ReportUploadStorageError(
            "Direct-to-storage upload is not configured (set REPORT_UPLOAD_S3_BUCKET and credentials)."
        )
    bucket = report_upload_bucket()
    upload_id = uuid.uuid4()
    wf = str(workflow_id).strip()
    key = f"report-uploads/{wf}/{upload_id}/upload.pdf"
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_session_ttl_seconds())
    presign_ttl = _presign_ttl_seconds()

    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO report_upload_sessions (
                id, user_id, workflow_id, kind,
                organization_id, organization_program_enrollment_id,
                bucket, object_key, status, expires_at, metadata
            )
            VALUES (
                %s::uuid, %s, %s::uuid, %s,
                %s, %s,
                %s, %s, %s, %s, %s::jsonb
            )
            """,
            (
                str(upload_id),
                int(user_id),
                wf,
                kind,
                organization_id,
                organization_program_enrollment_id,
                bucket,
                key,
                "pending_upload",
                expires_at,
                "{}",
            ),
        )
        conn.commit()

    upload_url = generate_presigned_put_url(
        bucket=bucket,
        object_key=key,
        content_type=content_type,
        expires_in=presign_ttl,
    )

    return {
        "uploadId": str(upload_id),
        "uploadUrl": upload_url,
        "method": "PUT",
        "headers": {
            "Content-Type": content_type,
        },
        "bucket": bucket,
        "objectKey": key,
        "expiresAt": expires_at.isoformat(),
        "presignedExpiresIn": presign_ttl,
        "workflowId": wf,
        "kind": kind,
    }


def get_report_upload_session_for_user(
    *,
    upload_id: str,
    user_id: int,
) -> Optional[Dict[str, Any]]:
    """Load session if owned by user and not expired (status may still be pending_upload)."""
    uid = str(upload_id).strip()
    if not uid:
        return None
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, user_id, workflow_id, kind, organization_id,
                   organization_program_enrollment_id, bucket, object_key,
                   status, expires_at, created_at, finalized_at, metadata
            FROM report_upload_sessions
            WHERE id = %s::uuid AND user_id = %s
            """,
            (uid, int(user_id)),
        )
        row = cur.fetchone()
    if not row:
        return None
    return dict(row)


class ReportUploadFinalizeError(Exception):
    """Finalize preconditions failed; map to HTTP in routes."""

    def __init__(self, code: str, message_safe: str, *, http_status: int = 400) -> None:
        self.code = code
        self.message_safe = message_safe
        self.http_status = http_status
        super().__init__(message_safe)


def _normalize_uuid_str(value: Any) -> str:
    return str(value).strip().lower()


def _metadata_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    md = row.get("metadata")
    if md is None:
        return {}
    if isinstance(md, dict):
        return dict(md)
    if isinstance(md, str):
        try:
            return json.loads(md) if md else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _reset_session_to_pending(upload_id: str) -> None:
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                UPDATE report_upload_sessions
                SET status = 'pending_upload'
                WHERE id = %s::uuid AND status = 'finalizing'
                """,
                (str(upload_id).strip(),),
            )
            conn.commit()
    except Exception:
        _log.exception("report_upload_sessions reset to pending failed upload_id=%s", upload_id)


def finalize_direct_storage_report_upload(
    *,
    upload_id: str,
    user_id: int,
    workflow_id: str,
    kind: str,
    byte_size: int,
    sha256_hex: str,
    organization_id: Optional[int] = None,
    organization_program_enrollment_id: Optional[int] = None,
) -> Tuple[str, bool]:
    """
    Verify object in S3, stage to temp, enqueue ``report_upload_parse``, mark session finalized.

    Returns ``(job_id, idempotent)``. Idempotent when session was already finalized with a job.
    """
    if not object_storage_configured():
        raise ReportUploadStorageError(
            "Direct-to-storage upload is not configured (set REPORT_UPLOAD_S3_BUCKET and credentials)."
        )

    uid = str(upload_id).strip()
    if not uid:
        raise ReportUploadFinalizeError("INVALID_UPLOAD_ID", "uploadId is required.")

    try:
        bs = int(byte_size)
    except (TypeError, ValueError):
        raise ReportUploadFinalizeError("INVALID_BYTE_SIZE", "byteSize must be a positive integer.")
    if bs <= 0:
        raise ReportUploadFinalizeError("INVALID_BYTE_SIZE", "byteSize must be a positive integer.")

    max_single = MAX_SINGLE_REPORT_UPLOAD_MB * 1024 * 1024
    if bs > max_single:
        raise ReportUploadFinalizeError(
            "FILE_TOO_LARGE",
            f"Maximum upload size is {MAX_SINGLE_REPORT_UPLOAD_MB} MB.",
            http_status=413,
        )

    hx = (sha256_hex or "").strip().lower()
    if len(hx) != 64 or not re.fullmatch(r"[0-9a-f]{64}", hx):
        raise ReportUploadFinalizeError("INVALID_SHA256", "sha256Hex must be 64 hex characters.")

    wf = str(workflow_id).strip()
    want_kind = kind.strip()

    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, user_id, workflow_id, kind, organization_id,
                   organization_program_enrollment_id, bucket, object_key,
                   status, expires_at, created_at, finalized_at, metadata
            FROM report_upload_sessions
            WHERE id = %s::uuid AND user_id = %s
            """,
            (uid, int(user_id)),
        )
        row = cur.fetchone()
    if not row:
        raise ReportUploadFinalizeError("UPLOAD_NOT_FOUND", "Upload session not found.", http_status=404)

    md = _metadata_dict(row)
    st = (row.get("status") or "").strip()
    if st == "finalized" and md.get("jobId"):
        return str(md["jobId"]), True

    if st != "pending_upload":
        raise ReportUploadFinalizeError(
            "UPLOAD_NOT_FINALIZABLE",
            "This upload session cannot be finalized.",
            http_status=409,
        )

    exp = row.get("expires_at")
    if exp is not None:
        if getattr(exp, "tzinfo", None) is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            raise ReportUploadFinalizeError(
                "UPLOAD_SESSION_EXPIRED",
                "Upload session expired. Create a new session.",
                http_status=410,
            )

    if _normalize_uuid_str(row.get("workflow_id")) != _normalize_uuid_str(wf):
        raise ReportUploadFinalizeError(
            "WORKFLOW_MISMATCH",
            "Upload does not belong to this workflow.",
            http_status=403,
        )

    if (row.get("kind") or "").strip() != want_kind:
        raise ReportUploadFinalizeError("KIND_MISMATCH", "Upload session kind mismatch.", http_status=403)

    if want_kind == "org_program":
        if organization_id is None or organization_program_enrollment_id is None:
            raise ReportUploadFinalizeError(
                "ORG_CONTEXT_REQUIRED",
                "Organization context is required for this upload.",
            )
        if int(row.get("organization_id") or 0) != int(organization_id):
            raise ReportUploadFinalizeError(
                "ORG_MISMATCH",
                "Upload does not belong to this organization context.",
                http_status=403,
            )
        if int(row.get("organization_program_enrollment_id") or 0) != int(organization_program_enrollment_id):
            raise ReportUploadFinalizeError(
                "ENROLLMENT_MISMATCH",
                "Upload does not belong to this enrollment.",
                http_status=403,
            )

    bucket = (row.get("bucket") or "").strip()
    object_key = (row.get("object_key") or "").strip()
    if not bucket or not object_key:
        raise ReportUploadFinalizeError("SESSION_INCOMPLETE", "Upload session is missing storage metadata.")

    claimed = False
    with get_db() as (conn, cur):
        cur.execute(
            """
            UPDATE report_upload_sessions
            SET status = 'finalizing'
            WHERE id = %s::uuid AND user_id = %s AND status = 'pending_upload'
            """,
            (uid, int(user_id)),
        )
        claimed = cur.rowcount == 1
        conn.commit()

    if not claimed:
        with get_db(dict_cursor=True) as (conn2, cur2):
            cur2.execute(
                """
                SELECT metadata, status FROM report_upload_sessions
                WHERE id = %s::uuid AND user_id = %s
                """,
                (uid, int(user_id)),
            )
            row2 = cur2.fetchone()
        if row2 and (row2.get("status") or "").strip() == "finalized":
            md2 = _metadata_dict(dict(row2))
            if md2.get("jobId"):
                return str(md2["jobId"]), True
        raise ReportUploadFinalizeError(
            "UPLOAD_NOT_FINALIZABLE",
            "This upload session cannot be finalized.",
            http_status=409,
        )

    temp_path: Optional[str] = None
    try:
        ho = head_object(bucket=bucket, object_key=object_key)
        cl = int(ho.get("ContentLength") or 0)
        if cl != bs:
            raise ReportUploadFinalizeError(
                "SIZE_MISMATCH",
                f"Object size in storage ({cl} bytes) does not match byteSize ({bs}).",
            )

        raw = get_object_bytes(bucket=bucket, object_key=object_key)
        if len(raw) != bs:
            raise ReportUploadFinalizeError(
                "SIZE_MISMATCH",
                "Downloaded object size does not match declared byteSize.",
            )
        got = hashlib.sha256(raw).hexdigest()
        if got != hx:
            raise ReportUploadFinalizeError(
                "CHECKSUM_MISMATCH",
                "Object checksum does not match sha256Hex.",
            )

        fd, temp_path = tempfile.mkstemp(suffix=".pdf", prefix="wf_report_finalize_")
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(raw)
        except Exception:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
            raise

        part_name = "upload.pdf"
        if want_kind == "org_program":
            jid = create_job(
                wf,
                JOB_TYPE_REPORT_UPLOAD_PARSE,
                {
                    "userId": int(user_id),
                    "staging": "parts_v1",
                    "tempPartPaths": [temp_path],
                    "partFilenames": [part_name],
                    "partByteSizes": [bs],
                    "partSha256Hex": [hx],
                    "orgProgramFollowup": True,
                    "organizationId": int(organization_id),
                    "organizationProgramEnrollmentId": int(organization_program_enrollment_id),
                },
                dedupe_pending=False,
            )
        else:
            jid = create_job(
                wf,
                JOB_TYPE_REPORT_UPLOAD_PARSE,
                {
                    "userId": int(user_id),
                    "staging": "parts_v1",
                    "tempPartPaths": [temp_path],
                    "partFilenames": [part_name],
                    "partByteSizes": [bs],
                    "partSha256Hex": [hx],
                },
                dedupe_pending=False,
            )
        temp_path = None

        try:
            delete_object(bucket=bucket, object_key=object_key)
        except ReportUploadStorageError as e:
            _log.warning("S3 delete after finalize failed upload_id=%s: %s", uid, e)

        with get_db() as (conn, cur):
            cur.execute(
                """
                UPDATE report_upload_sessions
                SET status = 'finalized',
                    finalized_at = CURRENT_TIMESTAMP,
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                WHERE id = %s::uuid AND user_id = %s
                """,
                (Json({"jobId": str(jid), "finalizeJobId": str(jid)}), uid, int(user_id)),
            )
            conn.commit()

        return jid, False
    except ReportUploadFinalizeError:
        _reset_session_to_pending(uid)
        raise
    except ReportUploadStorageError as e:
        _reset_session_to_pending(uid)
        raise ReportUploadFinalizeError(
            "STORAGE_ERROR",
            (str(e) or "Could not read from object storage.")[:280],
            http_status=502,
        ) from e
    except Exception:
        _reset_session_to_pending(uid)
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        raise
