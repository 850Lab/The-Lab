"""O.R.I.O.N. V1.3 — deterministic action explanation (no AI, no event history)."""

from __future__ import annotations

import ast
import uuid

import pytest

pytest.importorskip("sqlite3")


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_action_explanation.sqlite"
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


def test_explain_resume_upload_progress(isolated_workflow_sqlite):
    from services.guidance.action_explanation import explain_best_action_user_api
    from services.guidance.action_readiness import build_action_readiness_context
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
    ctx = build_action_readiness_context(session, steps, guidance_api=None)
    best = {
        "actionKey": "resume_upload",
        "label": "Continue your upload",
        "description": "x",
        "targetStepId": "upload",
        "actionType": "upload",
        "reasonCodes": ["head_step_in_progress"],
        "availability": "ready",
    }
    ex = explain_best_action_user_api(best, ctx)
    assert ex["explanationType"] == "progress"
    assert "credit report" in ex["summary"].lower()
    assert ex["blockingContext"] is None


def test_explain_retry_upload_warning_with_blocking(isolated_workflow_sqlite):
    from services.guidance.action_explanation import explain_best_action_user_api
    from services.guidance.action_readiness import build_action_readiness_context
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
    ctx = build_action_readiness_context(session, steps, guidance_api=None)
    best = {
        "actionKey": "retry_upload",
        "label": "Try upload again",
        "description": "x",
        "targetStepId": "upload",
        "actionType": "retry",
        "reasonCodes": ["upload_failed_recently", "upload_high_attempt_count"],
        "availability": "ready",
    }
    ex = explain_best_action_user_api(best, ctx)
    assert ex["explanationType"] == "warning"
    assert ex["blockingContext"]
    assert "upload" in ex["blockingContext"].lower()


def test_explain_wait_for_processing(isolated_workflow_sqlite):
    from services.guidance.action_explanation import explain_best_action_user_api
    from services.guidance.action_readiness import build_action_readiness_context
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
    ctx = build_action_readiness_context(session, steps, guidance_api=None)
    best = {
        "actionKey": "wait_for_processing",
        "label": "Wait",
        "description": "x",
        "targetStepId": None,
        "actionType": "wait",
        "reasonCodes": ["awaiting_background_processing"],
        "availability": "ready",
    }
    ex = explain_best_action_user_api(best, ctx)
    assert ex["explanationType"] == "waiting"
    assert "processing" in ex["summary"].lower()


def test_explain_complete_payment_requirement(isolated_workflow_sqlite):
    from services.guidance.action_explanation import explain_best_action_user_api
    from services.guidance.action_readiness import build_action_readiness_context
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
    ctx = build_action_readiness_context(session, steps, guidance_api=None)
    best = {
        "actionKey": "complete_payment",
        "label": "Complete payment",
        "description": "x",
        "targetStepId": "payment",
        "actionType": "navigate",
        "reasonCodes": ["payment_required"],
        "availability": "ready",
    }
    ex = explain_best_action_user_api(best, ctx)
    assert ex["explanationType"] == "requirement"
    assert "payment" in ex["summary"].lower()
    assert "letter" in ex["whatItUnlocks"].lower()


def test_explain_upload_proof_mailing_dependency(isolated_workflow_sqlite):
    from services.guidance.action_explanation import explain_best_action_user_api
    from services.guidance.action_readiness import build_action_readiness_context
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
    ctx = build_action_readiness_context(session, steps, guidance_api=None)
    best = {
        "actionKey": "upload_proof_documents",
        "label": "Upload proof",
        "description": "x",
        "targetStepId": "proof_attachment",
        "actionType": "upload",
        "reasonCodes": ["proof_required_before_mail"],
        "availability": "ready",
    }
    ex = explain_best_action_user_api(best, ctx)
    assert ex["explanationType"] == "requirement"
    assert "mail" in ex["whatItUnlocks"].lower()


def test_explain_check_tracking_by_track_step_status(isolated_workflow_sqlite):
    from services.guidance.action_explanation import explain_best_action_user_api
    from services.guidance.action_readiness import build_action_readiness_context
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
    ctx = build_action_readiness_context(session, steps, guidance_api=None)
    best = {
        "actionKey": "check_tracking_status",
        "label": "Tracking",
        "description": "x",
        "targetStepId": "track",
        "actionType": "review",
        "reasonCodes": ["mail_sent_tracking_active"],
        "availability": "ready",
    }
    ex_wait = explain_best_action_user_api(best, ctx)
    assert ex_wait["explanationType"] == "waiting"

    stmap["track"] = "available"
    with get_workflow_db() as (conn, cur):
        cur.execute(
            "UPDATE workflow_steps SET status = %s WHERE workflow_id = %s AND step_id = %s",
            ("available", wf, "track"),
        )
        conn.commit()
    steps2 = fetch_steps(wf, session=session)
    ctx2 = build_action_readiness_context(session, steps2, guidance_api=None)
    ex_prog = explain_best_action_user_api(best, ctx2)
    assert ex_prog["explanationType"] == "progress"


def test_explain_null_when_no_best_action():
    from services.guidance.action_explanation import explain_best_action_user_api

    assert explain_best_action_user_api(None, {}) is None
    assert explain_best_action_user_api({}, {}) is None


def test_bundle_explanation_null_when_workflow_completed(isolated_workflow_sqlite):
    from services.guidance.guidance_engine import customer_orion_bundle_for_api
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="track", overall="completed")
        _seed_steps(cur, conn, wf, stmap)

    bundle = customer_orion_bundle_for_api(wf, 1, None)
    assert bundle.get("bestAction") is None
    assert bundle.get("bestActionExplanation") is None
    assert bundle.get("deliveryPrioritization", {}).get("primaryFocus", {}).get("reasonCode") == (
        "completed_state_no_primary_action"
    )


def test_customer_bundle_includes_explanation(isolated_workflow_sqlite):
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

    bundle = customer_orion_bundle_for_api(wf, 1, None)
    assert bundle["bestAction"] is not None
    expl = bundle.get("bestActionExplanation")
    assert expl is not None
    assert set(expl.keys()) == {
        "summary",
        "whyNow",
        "whatItUnlocks",
        "blockingContext",
        "explanationType",
    }
    assert expl["explanationType"] == "requirement"
    dp = bundle.get("deliveryPrioritization")
    assert dp and dp.get("prioritizationVersion") == "orion_delivery_prioritization_v1"
    assert bundle.get("uxSurfaceContract", {}).get("surfaceContractVersion") == (
        "orion_ux_surface_contract_v1"
    )


def test_audit_includes_explanation_version(isolated_workflow_sqlite):
    from services.guidance.action_readiness import audit_action_readiness_for_workflow
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    for s in ("payment", "letter_generation", "proof_attachment", "mail", "track"):
        stmap[s] = "not_started"
    stmap["payment"] = "available"
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="payment", overall="active")
        _seed_steps(cur, conn, wf, stmap)

    audit = audit_action_readiness_for_workflow(wf, guidance_api=None)
    assert audit["deliveryPrioritizationAudit"]["prioritizationVersion"] == "orion_delivery_prioritization_v1"
    assert audit["uxSurfaceContractAudit"]["surfaceContractVersion"] == "orion_ux_surface_contract_v1"
    assert audit["actionExplanationVersion"] == "orion_action_explanation_v1"
    assert audit["orionLayerVersions"]["actionReadinessVersion"] == "orion_action_readiness_v1"
    assert audit["orionLayerVersions"]["actionExplanationVersion"] == "orion_action_explanation_v1"
    assert audit["orionLayerVersions"]["deliveryPrioritizationVersion"] == "orion_delivery_prioritization_v1"
    assert audit["orionLayerVersions"]["uxSurfaceContractVersion"] == "orion_ux_surface_contract_v1"
    bex = audit["bestActionExplanation"]
    assert bex["actionExplanationVersion"] == "orion_action_explanation_v1"
    assert "reasonCodes" in bex
    assert bex["sourceActionKey"] == "complete_payment"


def test_explanation_module_has_no_event_history_dependency():
    import services.guidance.action_explanation as ae

    src = open(ae.__file__, "r", encoding="utf-8").read()
    tree = ast.parse(src)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
    assert not any("workflow_event_service" in (n or "") for n in names)
    assert "list_workflow_events" not in src
