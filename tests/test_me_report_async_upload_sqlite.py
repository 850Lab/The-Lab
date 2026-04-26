"""
Regression: ``POST /api/me/report`` must enqueue ``report_upload_parse`` (never inline
``process_uploaded_reports``). Worker completes the job; org follow-up runs on the worker path.

Uses isolated workflow SQLite + targeted mocks for main-DB-only org enrollment rows.
"""

from __future__ import annotations

import io
import os
from typing import Any, Dict, List

import pytest

pytest.importorskip("sqlite3")


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_me_report_async.sqlite"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(dbfile))
    monkeypatch.setenv("WORKFLOW_JOB_WORKER_ENABLED", "0")
    monkeypatch.setenv("REPORT_INTAKE_ARTIFACT_DIR", str(tmp_path / "intake_artifacts"))
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("REPLIT_DEPLOYMENT", raising=False)

    import services.workflow.workflow_sqlite as wsq

    wsq._conn = None
    wsq.ensure_schema()
    yield dbfile
    wsq._conn = None


def _one_page_pdf_bytes() -> bytes:
    from io import BytesIO

    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "me_report_async_test")
    c.showPage()
    c.save()
    return buf.getvalue()


def _bootstrap_org_program_workflow_id(uid: int, oid: int, eid: int) -> str:
    from services.workflow.engine import WorkflowEngine
    from services.workflow.registry import ORG_PROGRAM_WORKFLOW_TYPE, linear_order_for
    from services.workflow.repository import create_workflow_with_steps

    meta: Dict[str, Any] = {
        "programContext": "org",
        "organizationProgramEnrollmentId": eid,
        "organizationId": oid,
    }
    first = linear_order_for(ORG_PROGRAM_WORKFLOW_TYPE)[0]
    wid = create_workflow_with_steps(
        user_id=uid,
        workflow_type=ORG_PROGRAM_WORKFLOW_TYPE,
        metadata=meta,
        first_step_id=first,
    )
    eng = WorkflowEngine()
    eng.service_complete_step(
        wid,
        "orgprog_enrollment",
        {"source": "test_bootstrap"},
        audit_source="test",
        audit_user_id=uid,
    )
    return wid


def test_me_report_enqueues_parse_job_no_inline_parse(isolated_workflow_sqlite, monkeypatch):
    """
    1) POST returns async envelope (processing + jobId + programWorkflowId).
    2) ``process_uploaded_reports`` is not invoked during the request handler (regression guard).
    3) Worker runs the same job to ``completed`` with ``reportIds`` in result.
    4) Org follow-up path executes (engine steps advanced on org_program_v1 workflow).
    """
    parse_calls: List[Dict[str, Any]] = []

    def fake_process_uploaded_reports(
        pdf_files: Any,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        parse_calls.append(dict(options))
        return {
            "reports_processed": 1,
            "file_skips": [],
            "uploaded_reports": {"u1": {"report_id": 9001}},
        }

    monkeypatch.setattr(
        "services.report_pipeline.process_uploaded_reports",
        fake_process_uploaded_reports,
    )
    # Worker imports a bound reference — patch where the job executes.
    monkeypatch.setattr(
        "services.workflow.jobs.report_upload_parse.process_uploaded_reports",
        fake_process_uploaded_reports,
    )
    monkeypatch.setattr(
        "services.me_org_report_service.build_findings_payload",
        lambda user_id, report_id=None: {"processingStatus": "complete"},
    )
    monkeypatch.setattr(
        "services.program_progress_service.sync_org_progress_row_from_org_workflow",
        lambda *args, **kwargs: None,
    )

    wid = _bootstrap_org_program_workflow_id(1, 1, 42)
    monkeypatch.setattr(
        "api.workflow_app.ensure_org_program_workflow",
        lambda uid, oid, eid: wid,
    )
    monkeypatch.setattr(
        "services.org_program_workflow_service.ensure_org_program_workflow",
        lambda uid, oid, eid: wid,
    )
    monkeypatch.setattr(
        "api.workflow_app.get_enrolled_org_participant_context",
        lambda uid: {
            "organization_id": 1,
            "organization_program_enrollment_id": 42,
            "membership": {"role": "org_user"},
            "enrollment": {"id": 42},
        },
    )
    monkeypatch.setattr(
        "api.workflow_app.get_organization",
        lambda oid: {"id": oid, "payment_access": "full"},
    )
    monkeypatch.setattr(
        "api.workflow_app.participant_forward_paused",
        lambda uid, eid: False,
    )

    from fastapi.testclient import TestClient

    from api.workflow_app import app
    from api.workflow_deps import get_session_user
    from services.workflow.repository import fetch_steps
    from services.workflow.workflow_job_service import (
        JOB_TYPE_REPORT_UPLOAD_PARSE,
        claim_job,
        get_job,
        public_job_view,
    )
    from services.workflow.workflow_job_worker import _dispatch

    app.dependency_overrides[get_session_user] = lambda: {
        "user_id": 1,
        "role": "consumer",
        "email": "me-report-test@example.com",
    }

    pdf = _one_page_pdf_bytes()
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            res = client.post(
                "/api/me/report",
                files={"file": ("report.pdf", io.BytesIO(pdf), "application/pdf")},
                data={"privacy_consent": "true"},
                headers={"Authorization": "Bearer test-session-token"},
            )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("ok") is True
    assert body.get("processing") is True
    assert body.get("jobId")
    assert body.get("intakeStatus", {}).get("phase") == "parse_worker_unavailable"
    assert body.get("programWorkflowId") == wid
    assert body.get("processingStatus") == "queued"
    assert parse_calls == [], (
        "process_uploaded_reports must not run inline in POST /api/me/report "
        f"(got {len(parse_calls)} call(s) before worker)"
    )

    jid = str(body["jobId"])
    row = get_job(jid)
    assert row is not None
    assert str(row.get("job_type")) == JOB_TYPE_REPORT_UPLOAD_PARSE
    assert str(row.get("status")) == "pending"
    pl = row.get("payload") or {}
    assert pl.get("staging") == "durable_parts_v1"
    paths = pl.get("intakePartPaths") or []
    assert isinstance(paths, list) and len(paths) == 1
    assert os.path.isfile(paths[0])

    job = claim_job()
    assert job is not None
    assert str(job["id"]) == jid
    _dispatch(job)

    row_done = get_job(jid)
    assert row_done is not None
    assert str(row_done.get("status")) == "completed"
    view = public_job_view(row_done)
    assert view.get("status") == "completed"
    result = view.get("result") or {}
    assert result.get("ok") is True
    assert result.get("reportIds") == [9001]

    app.dependency_overrides[get_session_user] = lambda: {
        "user_id": 1,
        "role": "consumer",
        "email": "me-report-test@example.com",
    }
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            http_job = client.get(
                f"/api/workflows/{wid}/jobs/{jid}",
                headers={"Authorization": "Bearer test-session-token"},
            )
    finally:
        app.dependency_overrides.clear()
    assert http_job.status_code == 200
    http_body = http_job.json()
    assert http_body.get("ok") is True
    assert (http_body.get("intakeStatus") or {}).get("phase") == "parse_completed"
    hj = http_body.get("job") or {}
    assert hj.get("status") == "completed"
    assert (hj.get("result") or {}).get("reportIds") == [9001]

    steps = fetch_steps(wid)
    by_id = {str(s.get("step_id")): s.get("status") for s in steps}
    assert by_id.get("orgprog_upload") == "completed"
    assert by_id.get("orgprog_findings_ready") == "completed"

    assert len(parse_calls) == 1
    opts = parse_calls[0]
    assert opts.get("user_id") == 1
    assert opts.get("organization_id") == 1
    assert opts.get("organization_program_enrollment_id") == 42
    assert "workflow_id" not in opts
