"""O.R.I.O.N. V1.5 — UX surface contract (deterministic, no event history)."""

from __future__ import annotations

import ast
import uuid

import pytest

pytest.importorskip("sqlite3")


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_ux_surface.sqlite"
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


def _seed_session(cur, conn, wf: str, *, current_step: str, overall: str, metadata="{}"):
    cur.execute(
        """
        INSERT INTO workflow_sessions (
            workflow_id, user_id, workflow_type, current_step, overall_status, metadata, updated_at
        )
        VALUES (%s, %s, 'dispute_linear_v1', %s, %s, %s, %s)
        """,
        (wf, 1, current_step, overall, metadata, "2026-01-15T12:00:00+00:00"),
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


def test_warning_maps_to_warning_banner():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api
    from services.guidance.ux_surface_contract import compute_ux_surface_contract_user_api

    g = {"type": "warning", "displayEligible": True}
    ba = {"actionKey": "retry_upload", "targetStepId": "upload", "availability": "ready"}
    expl = {"explanationType": "warning"}
    dp = compute_delivery_prioritization_user_api(
        guidance=g,
        best_action=ba,
        action_candidates=[ba, {"actionKey": "resume_upload"}],
        best_action_explanation=expl,
        readiness_context={"overallStatus": "active", "phase": "active"},
    )
    ux = compute_ux_surface_contract_user_api(
        guidance=g,
        best_action=ba,
        best_action_explanation=expl,
        delivery_prioritization=dp,
        readiness_context={"overallStatus": "active"},
    )
    assert ux["primarySurface"]["surfaceType"] == "warning_banner"
    assert ux["primarySurface"]["reasonCode"] == "warning_guidance_maps_to_banner"
    assert ux["primarySurface"]["actionPresentation"] == "secondary_cta"


def test_best_action_forward_progress_hero_panel():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api
    from services.guidance.ux_surface_contract import compute_ux_surface_contract_user_api

    ba = {"actionKey": "review_generated_letters", "targetStepId": "letter_generation"}
    expl = {"explanationType": "progress"}
    dp = compute_delivery_prioritization_user_api(
        guidance=None,
        best_action=ba,
        action_candidates=[ba],
        best_action_explanation=expl,
        readiness_context={"overallStatus": "active", "phase": "active"},
    )
    ux = compute_ux_surface_contract_user_api(
        guidance=None,
        best_action=ba,
        best_action_explanation=expl,
        delivery_prioritization=dp,
        readiness_context={"overallStatus": "active"},
    )
    assert ux["primarySurface"]["surfaceType"] == "hero_panel"
    assert ux["primarySurface"]["reasonCode"] == "best_action_progress_maps_to_hero_panel"


def test_waiting_maps_to_passive_status():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api
    from services.guidance.ux_surface_contract import compute_ux_surface_contract_user_api

    ba = {"actionKey": "wait_for_processing"}
    expl = {"explanationType": "waiting"}
    dp = compute_delivery_prioritization_user_api(
        guidance=None,
        best_action=ba,
        action_candidates=[ba],
        best_action_explanation=expl,
        readiness_context={"overallStatus": "active", "phase": "active"},
    )
    ux = compute_ux_surface_contract_user_api(
        guidance=None,
        best_action=ba,
        best_action_explanation=expl,
        delivery_prioritization=dp,
        readiness_context={"overallStatus": "active"},
    )
    assert ux["primarySurface"]["surfaceType"] == "passive_status"
    assert ux["primarySurface"]["reasonCode"] == "waiting_posture_maps_to_passive_status"
    assert ux["primarySurface"]["renderIntent"] == "waiting"


def test_requirement_payment_maps():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api
    from services.guidance.ux_surface_contract import compute_ux_surface_contract_user_api

    ba = {"actionKey": "complete_payment", "targetStepId": "payment", "availability": "ready"}
    expl = {"explanationType": "requirement"}
    dp = compute_delivery_prioritization_user_api(
        guidance=None,
        best_action=ba,
        action_candidates=[ba],
        best_action_explanation=expl,
        readiness_context={"overallStatus": "active", "phase": "active"},
    )
    ux = compute_ux_surface_contract_user_api(
        guidance=None,
        best_action=ba,
        best_action_explanation=expl,
        delivery_prioritization=dp,
        readiness_context={"overallStatus": "active"},
    )
    assert ux["primarySurface"]["surfaceType"] == "hero_panel"
    assert ux["primarySurface"]["renderIntent"] == "requirement"
    assert ux["primarySurface"]["actionPresentation"] == "primary_cta"
    assert ux["primarySurface"]["reasonCode"] == "requirement_action_maps_to_primary_surface"


def test_proof_requirement_hero_or_strong():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api
    from services.guidance.ux_surface_contract import compute_ux_surface_contract_user_api

    ba = {"actionKey": "upload_proof_documents", "targetStepId": "proof_attachment"}
    expl = {"explanationType": "requirement"}
    dp = compute_delivery_prioritization_user_api(
        guidance=None,
        best_action=ba,
        action_candidates=[ba],
        best_action_explanation=expl,
        readiness_context={"overallStatus": "active", "phase": "active"},
    )
    ux = compute_ux_surface_contract_user_api(
        guidance=None,
        best_action=ba,
        best_action_explanation=expl,
        delivery_prioritization=dp,
        readiness_context={"overallStatus": "active"},
    )
    assert ux["primarySurface"]["surfaceType"] == "hero_panel"
    assert ux["primarySurface"]["attentionLevel"] == "strong"


def test_review_action_inline_card():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api
    from services.guidance.ux_surface_contract import compute_ux_surface_contract_user_api

    ba = {"actionKey": "review_claims", "actionType": "review"}
    expl = {"explanationType": "review"}
    dp = compute_delivery_prioritization_user_api(
        guidance=None,
        best_action=ba,
        action_candidates=[ba],
        best_action_explanation=expl,
        readiness_context={"overallStatus": "active", "phase": "active"},
    )
    ux = compute_ux_surface_contract_user_api(
        guidance=None,
        best_action=ba,
        best_action_explanation=expl,
        delivery_prioritization=dp,
        readiness_context={"overallStatus": "active"},
    )
    assert ux["primarySurface"]["surfaceType"] == "inline_card"
    assert ux["primarySurface"]["reasonCode"] == "review_action_maps_to_inline_card"


def test_completed_completion_status(isolated_workflow_sqlite):
    from services.guidance.guidance_engine import customer_orion_bundle_for_api
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="track", overall="completed")
        _seed_steps(cur, conn, wf, stmap)

    bundle = customer_orion_bundle_for_api(wf, 1, None)
    ux = bundle["uxSurfaceContract"]
    assert ux["primarySurface"]["surfaceType"] == "completion_status"
    assert ux["primarySurface"]["reasonCode"] == "completed_posture_maps_to_completion_status"
    assert ux["supportingSurfaces"] == []


def test_supporting_surfaces_max_two():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api
    from services.guidance.ux_surface_contract import compute_ux_surface_contract_user_api

    g = {"type": "warning", "displayEligible": True}
    ba = {"actionKey": "retry_upload", "targetStepId": "upload"}
    expl = {"explanationType": "warning"}
    dp = compute_delivery_prioritization_user_api(
        guidance=g,
        best_action=ba,
        action_candidates=[ba, {"actionKey": "x"}],
        best_action_explanation=expl,
        readiness_context={"overallStatus": "active", "phase": "active"},
    )
    # Force three secondaries in dp (if prioritization only returns 2, inject synthetic)
    dp["secondarySupport"] = [
        {"kind": "best_action", "emphasis": "medium", "reasonCode": "a"},
        {"kind": "explanation", "emphasis": "medium", "reasonCode": "b"},
        {"kind": "candidate_list", "emphasis": "low", "reasonCode": "c"},
    ]
    ux = compute_ux_surface_contract_user_api(
        guidance=g,
        best_action=ba,
        best_action_explanation=expl,
        delivery_prioritization=dp,
        readiness_context={"overallStatus": "active"},
    )
    assert len(ux["supportingSurfaces"]) <= 2


def test_bundle_includes_ux_surface_contract(isolated_workflow_sqlite):
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
    assert "uxSurfaceContract" in bundle
    assert bundle["uxSurfaceContract"]["surfaceContractVersion"] == "orion_ux_surface_contract_v1"


def test_audit_includes_surface_contract(isolated_workflow_sqlite):
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
    uxa = audit["uxSurfaceContractAudit"]
    assert uxa["surfaceContractVersion"] == "orion_ux_surface_contract_v1"
    assert uxa["primarySurfaceReasonCode"] == uxa["uxSurfaceContract"]["primarySurface"]["reasonCode"]
    assert isinstance(uxa["supportingSurfaceTypes"], list)


def test_ux_module_no_event_history_dependency():
    import services.guidance.ux_surface_contract as uxc

    src = open(uxc.__file__, "r", encoding="utf-8").read()
    tree = ast.parse(src)
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    assert not any("workflow_event_service" in (m or "") for m in modules)
    assert "list_workflow_events" not in src
