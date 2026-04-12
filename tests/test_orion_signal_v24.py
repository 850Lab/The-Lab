"""ORION V2.4 — lightweight Proof script / step observability signals."""

from __future__ import annotations

import uuid

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlite3")


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_orion_signal.sqlite"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(dbfile))

    import services.workflow.workflow_sqlite as wsq

    wsq._conn = None
    wsq.ensure_schema()
    yield dbfile
    wsq._conn = None


def test_try_record_orion_signal_inserts_row(isolated_workflow_sqlite):
    from services.observability.orion_signal_events import (
        ORION_PROOF_SCRIPT_RENDERED,
        try_record_orion_signal,
    )
    from services.workflow.observability_events import list_observability_events
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_sessions (
                workflow_id, user_id, workflow_type, current_step, overall_status, metadata, updated_at
            )
            VALUES (%s, 1, 'dispute_linear_v1', 'proof_attachment', 'active', %s, %s)
            """,
            (wf, "{}", "2026-01-15T12:00:00+00:00"),
        )
        conn.commit()

    try_record_orion_signal(
        user_id=1,
        workflow_id=wf,
        event_name=ORION_PROOF_SCRIPT_RENDERED,
        metadata={"scriptAugmentationStatus": "available", "contractCompleteness": "partial"},
        client_timestamp="2026-01-15T12:00:00Z",
    )

    items = list_observability_events(workflow_id=wf, limit=10)
    assert len(items) == 1
    assert items[0]["eventName"] == ORION_PROOF_SCRIPT_RENDERED
    assert items[0]["stepId"] == "proof_attachment"
    assert items[0]["source"] == "frontend"
    meta = items[0]["metadata"]
    assert meta.get("scriptAugmentationStatus") == "available"
    assert meta.get("clientTimestamp") == "2026-01-15T12:00:00Z"


def test_try_record_unknown_event_no_op(isolated_workflow_sqlite):
    from services.observability.orion_signal_events import try_record_orion_signal
    from services.workflow.observability_events import list_observability_events
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_sessions (
                workflow_id, user_id, workflow_type, overall_status, metadata, updated_at
            )
            VALUES (%s, 1, 'dispute_linear_v1', 'active', %s, %s)
            """,
            (wf, "{}", "2026-01-15T12:00:00+00:00"),
        )
        conn.commit()

    try_record_orion_signal(user_id=1, workflow_id=wf, event_name="not_a_real_orion_event")
    assert list_observability_events(workflow_id=wf, limit=10) == []


def test_post_orion_signal_route_returns_200_and_inserts(isolated_workflow_sqlite, monkeypatch):
    from fastapi.testclient import TestClient

    from api.workflow_app import app
    from api.workflow_deps import get_owned_workflow, get_session_user
    from services.observability.orion_signal_events import ORION_PROOF_SCRIPT_VISIBLE
    from services.workflow.observability_events import list_observability_events
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_sessions (
                workflow_id, user_id, workflow_type, overall_status, metadata, updated_at
            )
            VALUES (%s, 1, 'dispute_linear_v1', 'active', %s, %s)
            """,
            (wf, "{}", "2026-01-15T12:00:00+00:00"),
        )
        conn.commit()

    monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)
    app.dependency_overrides[get_owned_workflow] = lambda: {
        "user_id": 1,
        "workflow_id": wf,
    }
    app.dependency_overrides[get_session_user] = lambda: {
        "user_id": 1,
        "role": "consumer",
        "email": "t@example.com",
    }
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            r = client.post(
                f"/api/workflows/{wf}/observability/orion-signal",
                headers={"Authorization": "Bearer t"},
                json={
                    "event": ORION_PROOF_SCRIPT_VISIBLE,
                    "timestamp": "2026-01-15T12:01:00Z",
                    "metadata": {"proofScriptRefinementStatus": "accepted"},
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
    items = list_observability_events(workflow_id=wf, limit=5)
    assert len(items) == 1
    assert items[0]["eventName"] == ORION_PROOF_SCRIPT_VISIBLE


def test_post_orion_signal_sparse_metadata_still_200(isolated_workflow_sqlite, monkeypatch):
    from fastapi.testclient import TestClient

    from api.workflow_app import app
    from api.workflow_deps import get_owned_workflow, get_session_user
    from services.observability.orion_signal_events import ORION_PROOF_STEP_COMPLETED
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_sessions (
                workflow_id, user_id, workflow_type, overall_status, metadata, updated_at
            )
            VALUES (%s, 1, 'dispute_linear_v1', 'active', %s, %s)
            """,
            (wf, "{}", "2026-01-15T12:00:00+00:00"),
        )
        conn.commit()

    monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)
    app.dependency_overrides[get_owned_workflow] = lambda: {
        "user_id": 1,
        "workflow_id": wf,
    }
    app.dependency_overrides[get_session_user] = lambda: {
        "user_id": 1,
        "role": "consumer",
        "email": "t@example.com",
    }
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            r = client.post(
                f"/api/workflows/{wf}/observability/orion-signal",
                headers={"Authorization": "Bearer t"},
                json={"event": ORION_PROOF_STEP_COMPLETED},
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json().get("ok") is True
