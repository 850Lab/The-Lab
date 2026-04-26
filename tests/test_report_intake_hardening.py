"""Focused tests for durable report intake staging and intake status contract."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone

from services.report_intake_artifacts import promote_temp_files_to_durable
from services.workflow.report_intake_status import build_report_parse_intake_status


def test_promote_temp_files_to_durable_moves_under_artifact_root(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_INTAKE_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    fd, p = tempfile.mkstemp(suffix=".pdf", prefix="t_promote_")
    try:
        os.write(fd, b"%PDF-1.4 minimal")
        os.close(fd)
        wf = str(uuid.uuid4())
        jid = str(uuid.uuid4())
        out = promote_temp_files_to_durable(wf, jid, [p])
        assert len(out) == 1
        assert os.path.isfile(out[0])
        assert not os.path.isfile(p)
        assert "part_000.pdf" in out[0]
    finally:
        try:
            os.unlink(p)
        except OSError:
            pass


def test_intake_status_maps_pending_and_worker_disabled(monkeypatch):
    monkeypatch.setenv("WORKFLOW_JOB_WORKER_ENABLED", "0")
    wf = str(uuid.uuid4())
    jid = str(uuid.uuid4())
    row = {
        "id": jid,
        "workflow_id": wf,
        "job_type": "report_upload_parse",
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "result": {},
        "error": None,
    }
    st = build_report_parse_intake_status(wf, jid, job_row=row)
    assert st["phase"] == "parse_worker_unavailable"
    assert st["backgroundWorkerEnabled"] is False
    assert st["nextAction"] == "blocked"


def test_intake_status_running_when_worker_on(monkeypatch):
    monkeypatch.setenv("WORKFLOW_JOB_WORKER_ENABLED", "1")
    wf = str(uuid.uuid4())
    jid = str(uuid.uuid4())
    row = {
        "id": jid,
        "workflow_id": wf,
        "job_type": "report_upload_parse",
        "status": "running",
        "created_at": datetime.now(timezone.utc),
        "result": {},
        "error": None,
    }
    st = build_report_parse_intake_status(wf, jid, job_row=row)
    assert st["phase"] == "parse_running"
    assert st["backgroundWorkerEnabled"] is True
