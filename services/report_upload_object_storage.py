"""
S3-compatible object storage for direct browser uploads (presigned PUT) and worker reads.

Configure via env (see ``.env.example``):
- ``REPORT_UPLOAD_S3_BUCKET`` (required for object path)
- ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` (or provider-specific keys)
- ``AWS_REGION`` or ``REPORT_UPLOAD_S3_REGION``
- ``REPORT_UPLOAD_S3_ENDPOINT`` — optional; set for Cloudflare R2, MinIO, etc.

Uses boto3 (S3 API). Not used until finalize/worker phases wire object keys into jobs.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError


class ReportUploadStorageError(Exception):
    """Misconfiguration or S3 API failure."""


def object_storage_configured() -> bool:
    return bool((os.environ.get("REPORT_UPLOAD_S3_BUCKET") or "").strip())


def report_upload_bucket() -> str:
    b = (os.environ.get("REPORT_UPLOAD_S3_BUCKET") or "").strip()
    if not b:
        raise ReportUploadStorageError(
            "REPORT_UPLOAD_S3_BUCKET is not set; direct-to-storage upload is disabled."
        )
    return b


def _region() -> str:
    return (
        (os.environ.get("REPORT_UPLOAD_S3_REGION") or "").strip()
        or (os.environ.get("AWS_REGION") or "").strip()
        or "us-east-1"
    )


def _endpoint_url() -> Optional[str]:
    u = (os.environ.get("REPORT_UPLOAD_S3_ENDPOINT") or "").strip()
    return u or None


def get_s3_client() -> BaseClient:
    """Shared client for presigned URLs, head, get, delete."""
    kwargs: Dict[str, Any] = {"region_name": _region()}
    ep = _endpoint_url()
    if ep:
        kwargs["endpoint_url"] = ep
    return boto3.client("s3", **kwargs)


def generate_presigned_put_url(
    *,
    bucket: str,
    object_key: str,
    content_type: str = "application/pdf",
    expires_in: int = 3600,
) -> str:
    """
    Presigned PUT URL for browser → object storage (no API hop for bytes).
    """
    if expires_in < 60 or expires_in > 604800:
        raise ReportUploadStorageError("expires_in must be between 60 and 604800 seconds.")
    client = get_s3_client()
    try:
        return client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )
    except ClientError as e:
        raise ReportUploadStorageError(f"Could not generate presigned URL: {e}") from e


def head_object(*, bucket: str, object_key: str) -> Dict[str, Any]:
    """Return S3 HeadObject-style metadata (ContentLength, ETag, etc.)."""
    client = get_s3_client()
    try:
        return client.head_object(Bucket=bucket, Key=object_key)
    except ClientError as e:
        code = (e.response.get("Error") or {}).get("Code") or ""
        if code in ("404", "NoSuchKey", "NotFound"):
            raise ReportUploadStorageError("Object not found in storage.") from e
        raise ReportUploadStorageError(f"head_object failed: {e}") from e


def get_object_bytes(*, bucket: str, object_key: str) -> bytes:
    client = get_s3_client()
    try:
        resp = client.get_object(Bucket=bucket, Key=object_key)
        return resp["Body"].read()
    except ClientError as e:
        raise ReportUploadStorageError(f"get_object failed: {e}") from e


def delete_object(*, bucket: str, object_key: str) -> None:
    client = get_s3_client()
    try:
        client.delete_object(Bucket=bucket, Key=object_key)
    except ClientError as e:
        raise ReportUploadStorageError(f"delete_object failed: {e}") from e
