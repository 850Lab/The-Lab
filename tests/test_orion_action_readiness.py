"""O.R.I.O.N. V1.2 — deterministic action readiness (no workflow writes)."""

from __future__ import annotations

import ast
import uuid

import pytest

pytest.importorskip("sqlite3")


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_action_readiness.sqlite"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(dbfile))

    import services.workflow.workflow_sqlite as wsq

    wsq._conn = None
    wsq.ensure_schema()
    yield dbfile
    wsq._conn = None


def _linear_dispute():
    from services.workflow import registry as reg

    return reg.linear_order_for("dispute_linear_v1")


def _seed_session(cur, conn, wf: str, *, user_id: int = 1, current_step: str, overall: str):
    cur.execute(
        """
        INSERT INTO workflow_sessions (
            workflow_id, user_id, workflow_type, current_step, overall_status, metadata, updated_at
        )
        VALUES (%s, %s, 'dispute_linear_v1', %s, %s, %s, %s)
        """,
        (wf, user_id, current_step, overall, "{}", "2026-01-15T12:00:00+00:00"),
    )
    conn.commit()


def _seed_steps(cur, conn, wf: str, status_by_id: dict[str, str]):
    for sid in _linear_dispute():
        st = status_by_id.get(sid, "not_started")
        cur.execute(
            """
            INSERT INTO workflow_steps (
                workflow_step_id, workflow_id, step_id, status, attempt_count
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), wf, sid, st, 0),
        )
    conn.commit()


def test_readiness_upload_in_progress_resume(isolated_workflow_sqlite):
    from services.guidance.action_readiness import compute_action_readiness_for_api
    from services.workflow.repository import fetch_session, fetch_steps
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    stmap["upload"] = "in_progress"
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="upload", overall="active")
        _seed_steps(cur, conn, wf, stmap)

    session = fetch_session(wf)
    steps = fetch_steps(wf, session=session)
    out = compute_action_readiness_for_api(session, steps, None)
    assert out["bestAction"]["actionKey"] == "resume_upload"
    assert "head_step_in_progress" in out["bestAction"]["reasonCodes"]


def test_readiness_upload_failed_retry(isolated_workflow_sqlite):
    from services.guidance.action_readiness import compute_action_readiness_for_api
    from services.workflow.repository import fetch_session, fetch_steps
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    stmap["upload"] = "failed"
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="upload", overall="active")
        _seed_steps(cur, conn, wf, stmap)

    session = fetch_session(wf)
    steps = fetch_steps(wf, session=session)
    out = compute_action_readiness_for_api(session, steps, None)
    assert out["bestAction"]["actionKey"] == "retry_upload"
    assert "upload_failed_recently" in out["bestAction"]["reasonCodes"]


def test_readiness_parse_wait(isolated_workflow_sqlite):
    from services.guidance.action_readiness import compute_action_readiness_for_api
    from services.workflow.repository import fetch_session, fetch_steps
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    stmap["upload"] = "completed"
    stmap["parse_analyze"] = "in_progress"
    for s in ("review_claims", "select_disputes", "payment", "letter_generation", "proof_attachment", "mail", "track"):
        stmap[s] = "not_started"
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="parse_analyze", overall="active")
        _seed_steps(cur, conn, wf, stmap)

    session = fetch_session(wf)
    steps = fetch_steps(wf, session=session)
    out = compute_action_readiness_for_api(session, steps, None)
    assert out["bestAction"]["actionKey"] == "wait_for_processing"
    assert "awaiting_background_processing" in out["bestAction"]["reasonCodes"]


def test_readiness_select_disputes(isolated_workflow_sqlite):
    from services.guidance.action_readiness import compute_action_readiness_for_api
    from services.workflow.repository import fetch_session, fetch_steps
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    for s in ("select_disputes", "payment", "letter_generation", "proof_attachment", "mail", "track"):
        stmap[s] = "not_started"
    stmap["select_disputes"] = "in_progress"
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="select_disputes", overall="active")
        _seed_steps(cur, conn, wf, stmap)

    session = fetch_session(wf)
    steps = fetch_steps(wf, session=session)
    out = compute_action_readiness_for_api(session, steps, None)
    assert out["bestAction"]["actionKey"] == "review_dispute_selection"
    assert "selection_incomplete" in out["bestAction"]["reasonCodes"]


def test_readiness_payment_gate(isolated_workflow_sqlite):
    from services.guidance.action_readiness import compute_action_readiness_for_api
    from services.workflow.repository import fetch_session, fetch_steps
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    for s in ("payment", "letter_generation", "proof_attachment", "mail", "track"):
        stmap[s] = "not_started"
    stmap["payment"] = "available"
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="payment", overall="active")
        _seed_steps(cur, conn, wf, stmap)

    session = fetch_session(wf)
    steps = fetch_steps(wf, session=session)
    out = compute_action_readiness_for_api(session, steps, None)
    assert out["bestAction"]["actionKey"] == "complete_payment"
    assert "payment_required" in out["bestAction"]["reasonCodes"]


def test_readiness_post_payment_letters(isolated_workflow_sqlite):
    from services.guidance.action_readiness import compute_action_readiness_for_api
    from services.workflow.repository import fetch_session, fetch_steps
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    for s in ("letter_generation", "proof_attachment", "mail", "track"):
        stmap[s] = "not_started"
    stmap["letter_generation"] = "in_progress"
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="letter_generation", overall="active")
        _seed_steps(cur, conn, wf, stmap)

    session = fetch_session(wf)
    steps = fetch_steps(wf, session=session)
    out = compute_action_readiness_for_api(session, steps, None)
    assert out["bestAction"]["actionKey"] == "review_generated_letters"


def test_readiness_proof_required(isolated_workflow_sqlite):
    from services.guidance.action_readiness import compute_action_readiness_for_api
    from services.workflow.repository import fetch_session, fetch_steps
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    for s in ("proof_attachment", "mail", "track"):
        stmap[s] = "not_started"
    stmap["proof_attachment"] = "available"
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="proof_attachment", overall="active")
        _seed_steps(cur, conn, wf, stmap)

    session = fetch_session(wf)
    steps = fetch_steps(wf, session=session)
    out = compute_action_readiness_for_api(session, steps, None)
    assert out["bestAction"]["actionKey"] == "upload_proof_documents"
    assert "proof_required_before_mail" in out["bestAction"]["reasonCodes"]


def test_readiness_tracking_active(isolated_workflow_sqlite):
    from services.guidance.action_readiness import compute_action_readiness_for_api
    from services.workflow.repository import fetch_session, fetch_steps
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    stmap["track"] = "in_progress"
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="track", overall="active")
        _seed_steps(cur, conn, wf, stmap)

    session = fetch_session(wf)
    steps = fetch_steps(wf, session=session)
    out = compute_action_readiness_for_api(session, steps, None)
    assert out["bestAction"]["actionKey"] == "check_tracking_status"
    assert "mail_sent_tracking_active" in out["bestAction"]["reasonCodes"]


def test_readiness_completed_workflow_null_best(isolated_workflow_sqlite):
    from services.guidance.action_readiness import compute_action_readiness_for_api
    from services.workflow.repository import fetch_session, fetch_steps
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="track", overall="completed")
        _seed_steps(cur, conn, wf, stmap)

    session = fetch_session(wf)
    steps = fetch_steps(wf, session=session)
    out = compute_action_readiness_for_api(session, steps, None)
    assert out["bestAction"] is None
    assert out["actionCandidates"] == []


def test_readiness_bounded_no_event_history_import():
    import services.guidance.action_readiness as ar

    src = open(ar.__file__, "r", encoding="utf-8").read()
    tree = ast.parse(src)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
    assert not any("workflow_event_service" in n for n in names if n)
    assert not any("guidance_storage" in n for n in names if n)


def test_readiness_candidates_capped_at_three(isolated_workflow_sqlite):
    from services.guidance.action_readiness import compute_action_readiness_for_api
    from services.workflow.repository import fetch_session, fetch_steps
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    stmap["track"] = "in_progress"
    with get_workflow_db() as (conn, cur):
        _seed_session(
            cur,
            conn,
            wf,
            current_step="track",
            overall="active",
        )
        cur.execute(
            "UPDATE workflow_sessions SET metadata = %s WHERE workflow_id = %s",
            ('{"escalationEligible": true}', wf),
        )
        _seed_steps(cur, conn, wf, stmap)

    session = fetch_session(wf)
    steps = fetch_steps(wf, session=session)
    out = compute_action_readiness_for_api(session, steps, None)
    assert len(out["actionCandidates"]) <= 3


def test_customer_bundle_best_without_guidance_rule(isolated_workflow_sqlite):
    from services.guidance.guidance_engine import customer_orion_bundle_for_api
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    for s in ("payment", "letter_generation", "proof_attachment", "mail", "track"):
        stmap[s] = "not_started"
    stmap["payment"] = "in_progress"
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="payment", overall="active")
        _seed_steps(cur, conn, wf, stmap)
        cur.execute(
            "UPDATE workflow_sessions SET updated_at = %s WHERE workflow_id = %s",
            ("2026-04-11T12:00:00+00:00", wf),
        )
        conn.commit()

    # Fresh session/steps: no stale ORION rules required for readiness
    bundle = customer_orion_bundle_for_api(wf, 1, None)
    assert bundle.get("bestAction") is not None
    assert bundle["bestAction"]["actionKey"] == "complete_payment"
    # Guidance may or may not fire; readiness still present
    assert "actionCandidates" in bundle
