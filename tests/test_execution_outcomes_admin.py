"""
Execution outcome admin query: repository list + flattened outcomes (SQLite).
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("sqlite3")


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_exec_outcomes.sqlite"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(dbfile))

    import services.workflow.workflow_sqlite as wsq

    wsq._conn = None
    wsq.ensure_schema()
    yield dbfile
    wsq._conn = None


def _minimal_progress_state(
    *,
    run_id: str,
    workflow_id: str,
    outcome_rows: list,
) -> dict:
    return {
        "runId": run_id,
        "workflowId": workflow_id,
        "guidanceSchemaVersion": "execution_guidance.v1",
        "playbookId": "pb",
        "playbookVersion": "1.0.0",
        "primaryPathId": None,
        "completedBlockIds": [],
        "completedOutcomes": {},
        "activatedBlockIds": [],
        "externalFlags": {},
        "outcomeHistory": outcome_rows,
        "executionNotes": [],
    }


def test_list_execution_runs_for_admin_filters(isolated_workflow_sqlite):
    from services.workflow.workflow_db import get_workflow_db
    from services.execution_runtime.repository import list_execution_runs_for_admin

    wf = "wf-admin-list-1"
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_sessions (workflow_id, user_id, workflow_type, overall_status, metadata)
            VALUES (%s, 1, 'dispute_linear_v1', 'active', '{}')
            """,
            (wf,),
        )
        conn.commit()

    bundle = {"schemaVersion": "x"}
    for i, bid in enumerate(["b1", "b2"]):
        rid = f"run-{i}"
        ps = _minimal_progress_state(
            run_id=rid,
            workflow_id=wf,
            outcome_rows=[
                {
                    "blockId": bid,
                    "outcomeKey": "complete",
                    "source": "user_reported",
                    "notes": f"note-{i}",
                    "matchedSignalTargetIds": [],
                    "guidanceSchemaVersion": "execution_guidance.v1",
                    "playbookId": "pb",
                    "playbookVersion": "1.0.0",
                    "recordedAt": f"2026-01-0{i+1}T12:00:00Z",
                    "externalFlagsSnapshot": {},
                }
            ],
        )
        with get_workflow_db(dict_cursor=True) as (conn, cur):
            cur.execute(
                """
                INSERT INTO workflow_execution_runs (
                    run_id, workflow_id, user_id,
                    guidance_bundle_json, progress_state_json, runtime_schema_version
                )
                VALUES (%s, %s, %s, %s, %s, 'execution_runtime.v1')
                """,
                (rid, wf, 1, json.dumps(bundle), json.dumps(ps)),
            )
            conn.commit()

    rows = list_execution_runs_for_admin(workflow_id=wf, limit=10)
    assert len(rows) == 2
    assert {r["run_id"] for r in rows} == {"run-0", "run-1"}

    one = list_execution_runs_for_admin(run_id="run-0", limit=10)
    assert len(one) == 1
    assert one[0]["run_id"] == "run-0"


def test_list_execution_outcomes_filters(isolated_workflow_sqlite):
    from services.workflow.workflow_db import get_workflow_db
    from services.execution_runtime.outcomes_query import list_execution_outcomes

    wf = "wf-outcomes-flat"
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_sessions (workflow_id, user_id, workflow_type, overall_status, metadata)
            VALUES (%s, 1, 'dispute_linear_v1', 'active', '{}')
            """,
            (wf,),
        )
        conn.commit()

    ps = _minimal_progress_state(
        run_id="run-x",
        workflow_id=wf,
        outcome_rows=[
            {
                "blockId": "block-a",
                "outcomeKey": "complete",
                "source": "user_reported",
                "notes": "",
                "matchedSignalTargetIds": [],
                "guidanceSchemaVersion": "execution_guidance.v1",
                "playbookId": "pb",
                "playbookVersion": "1.0.0",
                "recordedAt": "2026-01-05T10:00:00Z",
                "externalFlagsSnapshot": {},
            },
            {
                "blockId": "block-b",
                "outcomeKey": "complete",
                "source": "user_reported",
                "notes": "other outcome text",
                "matchedSignalTargetIds": [],
                "guidanceSchemaVersion": "execution_guidance.v1",
                "playbookId": "pb",
                "playbookVersion": "1.0.0",
                "recordedAt": "2026-01-05T11:00:00Z",
                "externalFlagsSnapshot": {"notSure": True},
            },
            {
                "blockId": "block-b",
                "outcomeKey": "complete",
                "source": "transcript_derived",
                "notes": "from call",
                "matchedSignalTargetIds": [],
                "guidanceSchemaVersion": "execution_guidance.v1",
                "playbookId": "pb",
                "playbookVersion": "1.0.0",
                "recordedAt": "2026-01-05T12:00:00Z",
                "externalFlagsSnapshot": {},
            },
        ],
    )
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_execution_runs (
                run_id, workflow_id, user_id,
                guidance_bundle_json, progress_state_json, runtime_schema_version
            )
            VALUES (%s, %s, %s, %s, %s, 'execution_runtime.v1')
            """,
            ("run-x", wf, 1, json.dumps({}), json.dumps(ps)),
        )
        conn.commit()

    all_rows = list_execution_outcomes(workflow_id=wf, limit=10)
    assert len(all_rows) == 3

    only_b = list_execution_outcomes(workflow_id=wf, block_id="block-b", limit=10)
    assert len(only_b) == 2
    only_b_user = list_execution_outcomes(
        workflow_id=wf, block_id="block-b", source="user_reported", limit=10
    )
    assert len(only_b_user) == 1
    assert only_b_user[0]["notes"] == "other outcome text"
    assert only_b_user[0]["externalFlagsSnapshot"] == {"notSure": True}

    only_complete = list_execution_outcomes(workflow_id=wf, outcome_key="complete", limit=10)
    assert len(only_complete) == 3

    with_notes = list_execution_outcomes(workflow_id=wf, has_notes=True, limit=10)
    assert len(with_notes) == 2
    with_notes_user = list_execution_outcomes(
        workflow_id=wf, has_notes=True, source="user_reported", limit=10
    )
    assert len(with_notes_user) == 1
    assert with_notes_user[0]["notes"] == "other outcome text"

    no_notes = list_execution_outcomes(workflow_id=wf, has_notes=False, limit=10)
    assert len(no_notes) == 1
    assert no_notes[0]["blockId"] == "block-a"

    user_only = list_execution_outcomes(workflow_id=wf, source="user_reported", limit=10)
    assert len(user_only) == 2
    transcript_only = list_execution_outcomes(workflow_id=wf, source="transcript_derived", limit=10)
    assert len(transcript_only) == 1
    assert transcript_only[0]["notes"] == "from call"
