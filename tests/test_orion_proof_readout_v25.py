"""ORION V2.5 — internal Proof script signal readout (aggregation only)."""

from __future__ import annotations

import json
import uuid

import pytest

pytest.importorskip("sqlite3")


def test_summarize_orion_proof_readout_from_rows_ordering():
    from services.observability.orion_proof_readout import summarize_orion_proof_script_signals_from_rows
    from services.observability.orion_signal_events import (
        ORION_PROOF_SCRIPT_RENDERED,
        ORION_PROOF_SCRIPT_VISIBLE,
        ORION_PROOF_STEP_COMPLETED,
    )

    wf_ok = "wf-readout-ok"
    wf_late_visible = "wf-readout-late-vis"
    base = "2026-04-01T12:00:00+00:00"

    rows = [
        {
            "workflow_id": wf_ok,
            "user_id": 7,
            "event_name": ORION_PROOF_SCRIPT_RENDERED,
            "timestamp": base,
            "metadata": {
                "scriptAugmentationStatus": "available",
                "proofScriptRefinementStatus": "accepted",
                "contractCompleteness": "full",
            },
        },
        {
            "workflow_id": wf_ok,
            "user_id": 7,
            "event_name": ORION_PROOF_SCRIPT_VISIBLE,
            "timestamp": "2026-04-01T12:00:05+00:00",
            "metadata": {},
        },
        {
            "workflow_id": wf_ok,
            "user_id": 7,
            "event_name": ORION_PROOF_STEP_COMPLETED,
            "timestamp": "2026-04-01T12:00:10+00:00",
            "metadata": {},
        },
        {
            "workflow_id": wf_late_visible,
            "user_id": 8,
            "event_name": ORION_PROOF_SCRIPT_RENDERED,
            "timestamp": "2026-04-01T13:00:00+00:00",
            "metadata": {
                "scriptAugmentationStatus": "null",
                "proofScriptRefinementStatus": "suppressed_x",
                "contractCompleteness": "partial",
            },
        },
        {
            "workflow_id": wf_late_visible,
            "user_id": 8,
            "event_name": ORION_PROOF_STEP_COMPLETED,
            "timestamp": "2026-04-01T13:00:05+00:00",
            "metadata": {},
        },
        {
            "workflow_id": wf_late_visible,
            "user_id": 8,
            "event_name": ORION_PROOF_SCRIPT_VISIBLE,
            "timestamp": "2026-04-01T13:00:10+00:00",
            "metadata": {},
        },
    ]

    out = summarize_orion_proof_script_signals_from_rows(rows)
    t = out["totals"]
    assert t["sessionsRendered"] == 2
    assert t["sessionsVisible"] == 2
    assert t["sessionsCompleted"] == 2
    assert t["completedAfterVisible"] == 1
    assert t["distinctUsersRendered"] == 2
    assert t["distinctUsersCompletedAfterVisible"] == 1

    sa = out["byScriptAugmentationStatus"]
    assert sa["available"]["sessionsRendered"] == 1
    assert sa["available"]["completedAfterVisible"] == 1
    assert sa["null"]["completedAfterVisible"] == 0

    pr = out["byProofScriptRefinementStatus"]
    assert pr["accepted"]["completedAfterVisible"] == 1
    assert pr["suppressed_x"]["sessionsVisible"] == 1
    assert pr["suppressed_x"]["completedAfterVisible"] == 0


def test_summarize_orion_proof_readout_no_duplicate_meta_spam():
    from services.observability.orion_proof_readout import summarize_orion_proof_script_signals_from_rows
    from services.observability.orion_signal_events import ORION_PROOF_SCRIPT_RENDERED

    wf = "wf-dup"
    rows = [
        {
            "workflow_id": wf,
            "user_id": 1,
            "event_name": ORION_PROOF_SCRIPT_RENDERED,
            "timestamp": "2026-04-02T10:00:00+00:00",
            "metadata": {"contractCompleteness": "full"},
        },
        {
            "workflow_id": wf,
            "user_id": 1,
            "event_name": ORION_PROOF_SCRIPT_RENDERED,
            "timestamp": "2026-04-02T10:00:01+00:00",
            "metadata": {"contractCompleteness": "legacy"},
        },
    ]
    out = summarize_orion_proof_script_signals_from_rows(rows)
    assert out["totals"]["sessionsRendered"] == 1
    assert out["byContractCompleteness"]["full"]["sessionsRendered"] == 1
    assert "legacy" not in out["byContractCompleteness"] or out["byContractCompleteness"]["legacy"]["sessionsRendered"] == 0


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_orion_readout.sqlite"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(dbfile))

    import services.workflow.workflow_sqlite as wsq

    wsq._conn = None
    wsq.ensure_schema()
    yield dbfile
    wsq._conn = None


def test_summarize_orion_proof_readout_end_to_end_sqlite(isolated_workflow_sqlite):
    from services.observability.orion_proof_readout import summarize_orion_proof_script_signals
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
        meta = json.dumps(
            {
                "scriptAugmentationStatus": "available",
                "proofScriptRefinementStatus": "accepted",
                "contractCompleteness": "full",
            },
            separators=(",", ":"),
        )
        for ts, ename, cat in [
            ("2026-01-15T12:01:00+00:00", "orion_proof_script_rendered", "input"),
            ("2026-01-15T12:02:00+00:00", "orion_proof_script_visible", "navigation"),
            ("2026-01-15T12:03:00+00:00", "orion_proof_step_completed", "completion"),
        ]:
            cur.execute(
                """
                INSERT INTO observability_events (
                    event_id, user_id, workflow_id, step_id, event_name, event_category,
                    status, timestamp, metadata, source
                )
                VALUES (%s, 1, %s, 'proof_attachment', %s, %s, 'info', %s, %s, 'frontend')
                """,
                (str(uuid.uuid4()), wf, ename, cat, ts, meta),
            )
        conn.commit()

    out = summarize_orion_proof_script_signals(event_row_limit=10_000)
    assert out["totals"]["sessionsRendered"] == 1
    assert out["totals"]["sessionsVisible"] == 1
    assert out["totals"]["sessionsCompleted"] == 1
    assert out["totals"]["completedAfterVisible"] == 1
    assert out["sample"]["eventRowsUsed"] == 3
    assert out["sample"]["likelyTruncated"] is False
