"""Finalize routes for direct-to-storage upload (mocked finalize service)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")


def test_retail_finalize_ok(monkeypatch):
    from fastapi.testclient import TestClient

    from api.workflow_app import app
    from api.workflow_deps import get_owned_workflow

    monkeypatch.setattr(
        "api.workflow_app.finalize_direct_storage_report_upload",
        lambda **kwargs: ("job-uuid-1", False),
    )
    monkeypatch.setattr(
        "api.workflow_app.enforce_customer_action",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "api.workflow_app._workflow_payload_with_progression",
        lambda wf: {"workflow": {"id": wf}, "progression": {}, "canonicalProgression": {}},
    )

    app.dependency_overrides[get_owned_workflow] = lambda: {
        "user_id": 1,
        "workflow_id": "00000000-0000-4000-8000-000000000002",
    }
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            r = client.post(
                "/api/workflows/00000000-0000-4000-8000-000000000002/report-upload/finalize",
                headers={"Authorization": "Bearer x"},
                json={
                    "uploadId": "00000000-0000-4000-8000-000000000099",
                    "byteSize": 100,
                    "sha256Hex": "a" * 64,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    b = r.json()
    assert b["ok"] is True
    assert b["jobId"] == "job-uuid-1"
    assert b.get("idempotent") is False


def test_retail_finalize_idempotent(monkeypatch):
    from fastapi.testclient import TestClient

    from api.workflow_app import app
    from api.workflow_deps import get_owned_workflow

    monkeypatch.setattr(
        "api.workflow_app.finalize_direct_storage_report_upload",
        lambda **kwargs: ("job-uuid-1", True),
    )
    monkeypatch.setattr(
        "api.workflow_app.enforce_customer_action",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "api.workflow_app._workflow_payload_with_progression",
        lambda wf: {"workflow": {"id": wf}},
    )

    app.dependency_overrides[get_owned_workflow] = lambda: {
        "user_id": 1,
        "workflow_id": "00000000-0000-4000-8000-000000000002",
    }
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            r = client.post(
                "/api/workflows/00000000-0000-4000-8000-000000000002/report-upload/finalize",
                headers={"Authorization": "Bearer x"},
                json={
                    "uploadId": "00000000-0000-4000-8000-000000000099",
                    "byteSize": 100,
                    "sha256Hex": "b" * 64,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json().get("idempotent") is True


def test_retail_finalize_storage_unavailable(monkeypatch):
    from fastapi.testclient import TestClient

    from api.workflow_app import app
    from api.workflow_deps import get_owned_workflow
    from services.report_upload_object_storage import ReportUploadStorageError

    def boom(**kwargs):
        raise ReportUploadStorageError("no bucket")

    monkeypatch.setattr(
        "api.workflow_app.finalize_direct_storage_report_upload",
        boom,
    )
    monkeypatch.setattr(
        "api.workflow_app.enforce_customer_action",
        lambda *a, **k: None,
    )

    app.dependency_overrides[get_owned_workflow] = lambda: {
        "user_id": 1,
        "workflow_id": "00000000-0000-4000-8000-000000000002",
    }
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            r = client.post(
                "/api/workflows/00000000-0000-4000-8000-000000000002/report-upload/finalize",
                headers={"Authorization": "Bearer x"},
                json={
                    "uploadId": "00000000-0000-4000-8000-000000000099",
                    "byteSize": 100,
                    "sha256Hex": "c" * 64,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 503


def test_retail_finalize_business_error(monkeypatch):
    from fastapi.testclient import TestClient

    from api.workflow_app import app
    from api.workflow_deps import get_owned_workflow
    from services.report_upload_session_service import ReportUploadFinalizeError

    def boom(**kwargs):
        raise ReportUploadFinalizeError("UPLOAD_NOT_FOUND", "gone", http_status=404)

    monkeypatch.setattr(
        "api.workflow_app.finalize_direct_storage_report_upload",
        boom,
    )
    monkeypatch.setattr(
        "api.workflow_app.enforce_customer_action",
        lambda *a, **k: None,
    )

    app.dependency_overrides[get_owned_workflow] = lambda: {
        "user_id": 1,
        "workflow_id": "00000000-0000-4000-8000-000000000002",
    }
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            r = client.post(
                "/api/workflows/00000000-0000-4000-8000-000000000002/report-upload/finalize",
                headers={"Authorization": "Bearer x"},
                json={
                    "uploadId": "00000000-0000-4000-8000-000000000099",
                    "byteSize": 100,
                    "sha256Hex": "d" * 64,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "UPLOAD_NOT_FOUND"


def test_org_finalize_ok(monkeypatch):
    from fastapi.testclient import TestClient

    from api.workflow_app import app
    from api.workflow_deps import get_session_user

    monkeypatch.setattr(
        "api.workflow_app.finalize_direct_storage_report_upload",
        lambda **kwargs: ("job-org-1", False),
    )
    monkeypatch.setattr(
        "api.workflow_app.get_program_workflow_id_for_enrollment",
        lambda eid: "00000000-0000-4000-8000-0000000000aa",
    )
    monkeypatch.setattr(
        "api.workflow_app._me_org_engine_bundle",
        lambda ctx, uid: None,
    )

    app.dependency_overrides[get_session_user] = lambda: {
        "user_id": 1,
        "role": "consumer",
        "email": "t@example.com",
    }
    monkeypatch.setattr(
        "api.workflow_app._require_enrolled_org_participant",
        lambda user: {
            "organization_id": 10,
            "organization_program_enrollment_id": 20,
            "membership": {"role": "org_user"},
            "enrollment": {"id": 20},
        },
    )
    monkeypatch.setattr(
        "api.workflow_app._require_org_program_payment_access",
        lambda ctx: None,
    )
    monkeypatch.setattr(
        "api.workflow_app._require_org_program_not_paused",
        lambda user, ctx: None,
    )

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            r = client.post(
                "/api/me/report-upload/finalize",
                headers={"Authorization": "Bearer x"},
                json={
                    "uploadId": "00000000-0000-4000-8000-000000000099",
                    "byteSize": 200,
                    "sha256Hex": "e" * 64,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    b = r.json()
    assert b["ok"] is True
    assert b["jobId"] == "job-org-1"
    assert b["programWorkflowId"] == "00000000-0000-4000-8000-0000000000aa"
