"""HTTP routes for POST .../report-upload/session (no live S3)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")


def test_report_upload_session_routes_return_shape(monkeypatch):
    from fastapi.testclient import TestClient

    from api.workflow_app import app
    from api.workflow_deps import get_owned_workflow, get_session_user

    fake_payload = {
        "uploadId": "00000000-0000-4000-8000-000000000001",
        "uploadUrl": "https://example.com/presigned",
        "method": "PUT",
        "headers": {"Content-Type": "application/pdf"},
        "bucket": "b",
        "objectKey": "report-uploads/wf/u/upload.pdf",
        "expiresAt": "2026-01-01T00:00:00+00:00",
        "presignedExpiresIn": 3600,
        "workflowId": "00000000-0000-4000-8000-000000000002",
        "kind": "retail",
    }

    monkeypatch.setattr(
        "api.workflow_app.create_report_upload_session",
        lambda **kwargs: fake_payload,
    )

    app.dependency_overrides[get_owned_workflow] = lambda: {
        "user_id": 1,
        "workflow_id": "00000000-0000-4000-8000-000000000002",
    }
    app.dependency_overrides[get_session_user] = lambda: {
        "user_id": 1,
        "role": "consumer",
        "email": "t@example.com",
    }

    monkeypatch.setattr(
        "api.workflow_app.enforce_customer_action",
        lambda *a, **k: None,
    )

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            r = client.post(
                "/api/workflows/00000000-0000-4000-8000-000000000002/report-upload/session",
                headers={"Authorization": "Bearer x"},
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["uploadId"] == fake_payload["uploadId"]
    assert body["uploadUrl"] == fake_payload["uploadUrl"]
    assert body["objectKey"] == fake_payload["objectKey"]
    assert "constraints" in body
    assert body["constraints"]["contentType"] == "application/pdf"
