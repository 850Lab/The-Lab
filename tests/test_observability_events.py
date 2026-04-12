"""Observability events: storage + workflow_event mirror (SQLite)."""

from __future__ import annotations

import pytest

pytest.importorskip("sqlite3")


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_obs.sqlite"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(dbfile))

    import services.workflow.workflow_sqlite as wsq

    wsq._conn = None
    wsq.ensure_schema()
    yield dbfile
    wsq._conn = None


def test_workflow_event_mirrored_to_observability(isolated_workflow_sqlite):
    from services.workflow.observability_events import list_observability_events
    from services.workflow.workflow_db import get_workflow_db
    from services.workflow.workflow_event_service import record_event

    wf = "wf-obs-mirror-1"
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_sessions (workflow_id, user_id, workflow_type, overall_status, metadata)
            VALUES (%s, 1, 'dispute_linear_v1', 'active', '{}')
            """,
            (wf,),
        )
        conn.commit()

    record_event(wf, "transition.step_done", step_id="upload", actor="user", source="engine")

    items = list_observability_events(workflow_id=wf, limit=10)
    assert len(items) == 1
    assert items[0]["eventCategory"] == "navigation"
    assert items[0]["status"] == "info"
    assert str(items[0]["eventName"]).startswith("workflow_event:")
    assert items[0]["userId"] == 1
    assert items[0]["workflowId"] == wf
    assert items[0]["stepId"] == "upload"
    assert items[0]["source"] == "workflow"


def test_list_observability_by_user_id(isolated_workflow_sqlite):
    from services.workflow.observability_events import emit_observability_event, list_observability_events
    from services.workflow.workflow_db import get_workflow_db

    wf = "wf-obs-user-1"
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_sessions (workflow_id, user_id, workflow_type, overall_status, metadata)
            VALUES (%s, 1, 'dispute_linear_v1', 'active', '{}')
            """,
            (wf,),
        )
        conn.commit()

    emit_observability_event(
        user_id=1,
        workflow_id=wf,
        step_id="select_disputes",
        event_name="strategy_generated",
        event_category="processing",
        status="success",
        metadata={"eligibleCount": 3},
        source="strategy",
    )

    by_user = list_observability_events(user_id=1, limit=10)
    assert len(by_user) == 1
    assert by_user[0]["eventName"] == "strategy_generated"
    assert by_user[0]["metadata"].get("eligibleCount") == 3


def test_map_workflow_event_type():
    from services.workflow.observability_events import map_workflow_event_type

    name, cat, st = map_workflow_event_type("transition.foo")
    assert cat == "navigation" and st == "info"
    name2, cat2, st2 = map_workflow_event_type("job_failed")
    assert cat2 == "failure" and st2 == "failure"
