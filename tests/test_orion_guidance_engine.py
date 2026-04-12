"""O.R.I.O.N. guidance engine (Phase 9 + V1.1 delivery contract)."""

from __future__ import annotations

import uuid

import pytest

pytest.importorskip("sqlite3")


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_orion.sqlite"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(dbfile))

    import services.workflow.workflow_sqlite as wsq

    wsq._conn = None
    wsq.ensure_schema()
    yield dbfile
    wsq._conn = None


def _seed_minimal_workflow(cur, conn, wf: str, *, user_id: int = 1) -> None:
    cur.execute(
        """
        INSERT INTO workflow_sessions (
            workflow_id, user_id, workflow_type, current_step, overall_status, metadata, updated_at
        )
        VALUES (%s, %s, 'dispute_linear_v1', 'upload', 'active', '{}', %s)
        """,
        (wf, user_id, "2026-01-15T12:00:00+00:00"),
    )
    for sid, st, ac in [
        ("upload", "in_progress", 0),
        ("parse_analyze", "not_started", 0),
        ("payment", "not_started", 0),
        ("letter_generation", "not_started", 0),
    ]:
        cur.execute(
            """
            INSERT INTO workflow_steps (
                workflow_step_id, workflow_id, step_id, status, attempt_count
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), wf, sid, st, ac),
        )
    conn.commit()


def test_orion_inactivity_triggers(isolated_workflow_sqlite):
    from services.guidance.guidance_engine import evaluate_guidance
    from services.workflow.workflow_db import get_workflow_db

    wf = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    with get_workflow_db() as (conn, cur):
        _seed_minimal_workflow(cur, conn, wf)
        cur.execute(
            "UPDATE workflow_sessions SET updated_at = %s WHERE workflow_id = %s",
            ("2020-01-01T00:00:00+00:00", wf),
        )
        conn.commit()

    g = evaluate_guidance(1, wf, None, persist=False)
    assert g is not None
    assert g.rule_key == "orion.inactivity_120s"
    assert g.delivery_channel == "passive"
    assert g.display_eligible is True
    assert g.recommended_action is not None
    assert g.recommended_action.get("actionType") in ("navigate", "review")


def test_orion_repeated_upload_failure(isolated_workflow_sqlite):
    from services.guidance.guidance_engine import evaluate_guidance
    from services.workflow.workflow_db import get_workflow_db

    wf = "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee"
    with get_workflow_db() as (conn, cur):
        _seed_minimal_workflow(cur, conn, wf)
        cur.execute(
            "UPDATE workflow_steps SET attempt_count = 5, status = 'failed' WHERE workflow_id = %s AND step_id = 'upload'",
            (wf,),
        )
        conn.commit()

    g = evaluate_guidance(1, wf, None, persist=False)
    assert g is not None
    assert g.rule_key == "orion.repeated_upload_failure"
    assert g.delivery_channel == "banner"
    ra = g.recommended_action
    assert ra is not None
    assert ra.get("actionKey") == "retry_upload_with_help"
    assert ra.get("targetStepId") == "upload"
    assert ra.get("actionType") == "retry"


def test_orion_payment_complete_recommended_action(isolated_workflow_sqlite):
    from services.guidance.guidance_engine import evaluate_guidance
    from services.workflow.workflow_db import get_workflow_db

    wf = "cccccccc-bbbb-cccc-dddd-eeeeeeeeeeee"
    with get_workflow_db() as (conn, cur):
        _seed_minimal_workflow(cur, conn, wf)
        cur.execute(
            "UPDATE workflow_steps SET status = 'completed' WHERE workflow_id = %s AND step_id = 'payment'",
            (wf,),
        )
        cur.execute(
            "UPDATE workflow_steps SET status = 'available' WHERE workflow_id = %s AND step_id = 'letter_generation'",
            (wf,),
        )
        cur.execute(
            "UPDATE workflow_sessions SET current_step = 'letter_generation' WHERE workflow_id = %s",
            (wf,),
        )
        conn.commit()

    g = evaluate_guidance(1, wf, None, persist=False)
    assert g is not None
    assert g.rule_key == "orion.payment_complete_next"
    assert g.delivery_channel == "inline"
    ra = g.recommended_action
    assert ra is not None
    assert ra.get("actionKey") == "go_to_letter_generation"
    assert ra.get("targetStepId") == "letter_generation"
    assert ra.get("actionType") == "navigate"
    assert isinstance(ra.get("metadata"), dict)


def test_orion_persists_v11_shape(isolated_workflow_sqlite):
    import json

    from services.guidance.guidance_engine import evaluate_guidance
    from services.guidance.guidance_storage import fetch_latest_guidance_row
    from services.workflow.workflow_db import get_workflow_db

    wf = "dddddddd-bbbb-cccc-dddd-eeeeeeeeeeee"
    with get_workflow_db() as (conn, cur):
        _seed_minimal_workflow(cur, conn, wf)
        cur.execute(
            "UPDATE workflow_steps SET attempt_count = 5, status = 'failed' WHERE workflow_id = %s AND step_id = 'upload'",
            (wf,),
        )
        conn.commit()

    evaluate_guidance(1, wf, None, persist=True)
    row = fetch_latest_guidance_row(wf)
    assert row is not None
    assert row.get("rule_key") == "orion.repeated_upload_failure"
    assert row.get("delivery_channel") == "banner"
    assert int(row.get("cooldown_seconds") or 0) == 180
    raw = row.get("recommended_action")
    if isinstance(raw, str):
        rec = json.loads(raw)
    else:
        rec = raw
    assert isinstance(rec, dict)
    assert rec.get("actionKey") == "retry_upload_with_help"


def test_orion_cooldown_second_eval_not_user_deliverable(isolated_workflow_sqlite):
    from services.guidance.guidance_engine import evaluate_guidance, guidance_for_api
    from services.workflow.workflow_db import get_workflow_db

    wf = "ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee"
    with get_workflow_db() as (conn, cur):
        _seed_minimal_workflow(cur, conn, wf)
        cur.execute(
            "UPDATE workflow_sessions SET updated_at = %s WHERE workflow_id = %s",
            ("2020-01-01T00:00:00+00:00", wf),
        )
        conn.commit()

    g1 = evaluate_guidance(1, wf, None, persist=True)
    assert g1 is not None
    assert g1.display_eligible is True

    g2 = evaluate_guidance(1, wf, None, persist=True)
    assert g2 is not None
    assert g2.display_eligible is False
    assert guidance_for_api(wf, 1) is None


def test_orion_internal_only_not_exposed_on_api(isolated_workflow_sqlite):
    from datetime import datetime, timezone

    from services.guidance.guidance_delivery import apply_delivery
    from services.guidance.guidance_rules import RuleEval

    ev: RuleEval = {
        "triggered": True,
        "priority": 99,
        "type": "nudge",
        "message": "internal note",
        "suggested_actions": [],
        "trigger_source": "orion.internal.test_rule",
        "rule_key": "orion.internal.test_rule",
    }
    resp, _ = apply_delivery(
        ev,
        workflow_id="wf-x",
        ctx={"session": {}, "steps_by_id": {}, "recent_events": [], "latest_event": None},
        guidance_id="gid",
        step_id="upload",
        timestamp=datetime.now(timezone.utc),
    )
    assert resp.delivery_channel == "internal_only"
    assert resp.to_user_api_dict() is None


def test_orion_bounded_event_lookback_calls_list_with_cap(
    isolated_workflow_sqlite, monkeypatch
):
    from services.guidance.guidance_engine import evaluate_guidance
    from services.workflow.workflow_db import get_workflow_db

    captured: dict = {}

    def fake_list(wid, limit=500, oldest_first=True):
        captured["limit"] = limit
        captured["oldest_first"] = oldest_first
        return []

    monkeypatch.setattr(
        "services.guidance.guidance_engine.list_workflow_events", fake_list
    )

    wf = "99999999-bbbb-cccc-dddd-eeeeeeeeeeee"
    with get_workflow_db() as (conn, cur):
        _seed_minimal_workflow(cur, conn, wf)
        cur.execute(
            "UPDATE workflow_steps SET attempt_count = 5, status = 'failed' WHERE workflow_id = %s AND step_id = 'upload'",
            (wf,),
        )
        conn.commit()

    evaluate_guidance(1, wf, None, persist=False)
    assert captured.get("limit") == 25
    assert captured.get("oldest_first") is False


def test_orion_audit_list_for_workflow(isolated_workflow_sqlite):
    from services.guidance.guidance_engine import evaluate_guidance
    from services.guidance.guidance_storage import list_guidance_events_for_workflow
    from services.workflow.workflow_db import get_workflow_db

    wf = "aaaa1111-bbbb-cccc-dddd-eeeeeeeeeeee"
    with get_workflow_db() as (conn, cur):
        _seed_minimal_workflow(cur, conn, wf)
        cur.execute(
            "UPDATE workflow_steps SET attempt_count = 5, status = 'failed' WHERE workflow_id = %s AND step_id = 'upload'",
            (wf,),
        )
        conn.commit()

    evaluate_guidance(1, wf, None, persist=True)
    items = list_guidance_events_for_workflow(wf, limit=10)
    assert len(items) == 1
    assert items[0].get("ruleKey") == "orion.repeated_upload_failure"
    assert items[0].get("displayEligible") is True
    assert items[0].get("recommendedAction", {}).get("actionKey") == "retry_upload_with_help"


def test_orion_completed_workflow_returns_no_guidance(isolated_workflow_sqlite):
    from services.guidance.guidance_engine import evaluate_guidance
    from services.workflow.workflow_db import get_workflow_db

    wf = "eeeeeeee-bbbb-cccc-dddd-eeeeeeeeeeee"
    with get_workflow_db() as (conn, cur):
        _seed_minimal_workflow(cur, conn, wf)
        cur.execute(
            "UPDATE workflow_sessions SET overall_status = 'completed', current_step = NULL WHERE workflow_id = %s",
            (wf,),
        )
        conn.commit()

    assert evaluate_guidance(1, wf, None, persist=False) is None
