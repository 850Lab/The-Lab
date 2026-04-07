"""Unit tests for report upload object storage config (no live S3)."""

from __future__ import annotations

import pytest

pytest.importorskip("boto3")

from services.report_upload_object_storage import (
    ReportUploadStorageError,
    object_storage_configured,
    report_upload_bucket,
)


def test_object_storage_configured_requires_bucket(monkeypatch):
    monkeypatch.delenv("REPORT_UPLOAD_S3_BUCKET", raising=False)
    assert object_storage_configured() is False
    monkeypatch.setenv("REPORT_UPLOAD_S3_BUCKET", "test-bucket")
    assert object_storage_configured() is True


def test_report_upload_bucket_raises_when_missing(monkeypatch):
    monkeypatch.delenv("REPORT_UPLOAD_S3_BUCKET", raising=False)
    with pytest.raises(ReportUploadStorageError, match="REPORT_UPLOAD_S3_BUCKET"):
        report_upload_bucket()
