"""O.R.I.O.N. V1.4 — deterministic delivery prioritization (no event history)."""

from __future__ import annotations

import ast
import uuid

import pytest

pytest.importorskip("sqlite3")


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_delivery_prioritization.sqlite"
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


def _seed_session(cur, conn, wf: str, *, user_id: int = 1, current_step: str, overall: str, metadata="{}"):
    cur.execute(
        """
        INSERT INTO workflow_sessions (
            workflow_id, user_id, workflow_type, current_step, overall_status, metadata, updated_at
        )
        VALUES (%s, %s, 'dispute_linear_v1', %s, %s, %s, %s)
        """,
        (wf, user_id, current_step, overall, metadata, "2026-01-15T12:00:00+00:00"),
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


def test_warning_guidance_dominates():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api

    g = {
        "type": "warning",
        "displayEligible": True,
        "ruleKey": "orion.repeated_upload_failure",
    }
    ba = {"actionKey": "retry_upload", "targetStepId": "upload", "availability": "ready"}
    expl = {"explanationType": "warning"}
    cands = [{"actionKey": "retry_upload"}, {"actionKey": "resume_upload"}]
    ctx = {"overallStatus": "active", "phase": "active"}
    dp = compute_delivery_prioritization_user_api(
        guidance=g,
        best_action=ba,
        action_candidates=cands,
        best_action_explanation=expl,
        readiness_context=ctx,
    )
    assert dp["primaryFocus"]["kind"] == "guidance"
    assert dp["primaryFocus"]["reasonCode"] == "warning_guidance_dominates"
    kinds = {x["kind"] for x in dp["secondarySupport"]}
    assert "best_action" in kinds
    assert "explanation" in kinds
    sup = {x["kind"]: x["reasonCode"] for x in dp["suppressedSignals"]}
    assert sup.get("candidate_list") == "candidate_list_suppressed_to_reduce_noise"


def test_best_action_primary_without_guidance():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api

    ba = {
        "actionKey": "complete_payment",
        "targetStepId": "payment",
        "availability": "ready",
    }
    expl = {"explanationType": "requirement"}
    dp = compute_delivery_prioritization_user_api(
        guidance=None,
        best_action=ba,
        action_candidates=[ba],
        best_action_explanation=expl,
        readiness_context={"overallStatus": "active", "phase": "active"},
    )
    assert dp["primaryFocus"]["kind"] == "best_action"
    assert dp["primaryFocus"]["reasonCode"] == "best_action_primary_no_guidance"
    assert any(
        s["kind"] == "explanation" and s["reasonCode"] == "explanation_secondary_for_confidence"
        for s in dp["secondarySupport"]
    )


def test_instruction_aligned_best_action_primary():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api

    g = {
        "type": "instruction",
        "displayEligible": True,
        "recommendedAction": {"targetStepId": "payment"},
    }
    ba = {"actionKey": "complete_payment", "targetStepId": "payment", "availability": "ready"}
    expl = {"explanationType": "requirement"}
    dp = compute_delivery_prioritization_user_api(
        guidance=g,
        best_action=ba,
        action_candidates=[ba],
        best_action_explanation=expl,
        readiness_context={"overallStatus": "active", "phase": "active"},
    )
    assert dp["primaryFocus"]["kind"] == "best_action"
    assert dp["primaryFocus"]["reasonCode"] == "instruction_supports_best_action"
    assert any(s["kind"] == "guidance" for s in dp["secondarySupport"])


def test_waiting_posture_explanation_primary():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api

    ba = {"actionKey": "wait_for_processing", "availability": "ready"}
    expl = {"explanationType": "waiting"}
    dp = compute_delivery_prioritization_user_api(
        guidance=None,
        best_action=ba,
        action_candidates=[ba],
        best_action_explanation=expl,
        readiness_context={"overallStatus": "active", "phase": "active"},
    )
    assert dp["primaryFocus"]["kind"] == "explanation"
    assert dp["primaryFocus"]["reasonCode"] == "waiting_state_explanation_primary"
    assert any(s["kind"] == "best_action" for s in dp["secondarySupport"])
    sup_k = {x["kind"] for x in dp["suppressedSignals"]}
    assert "candidate_list" in sup_k


def test_candidate_list_suppressed_when_single_dominant_path():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api

    ba = {"actionKey": "upload_proof_documents", "targetStepId": "proof_attachment"}
    expl = {"explanationType": "requirement"}
    dp = compute_delivery_prioritization_user_api(
        guidance=None,
        best_action=ba,
        action_candidates=[ba],
        best_action_explanation=expl,
        readiness_context={"overallStatus": "active", "phase": "active"},
    )
    sup = {x["kind"]: x["reasonCode"] for x in dp["suppressedSignals"]}
    assert sup.get("candidate_list") == "candidate_list_suppressed_to_reduce_noise"


def test_completed_workflow_status_primary(isolated_workflow_sqlite):
    from services.guidance.guidance_engine import customer_orion_bundle_for_api
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    with get_workflow_db() as (conn, cur):
        _seed_session(cur, conn, wf, current_step="track", overall="completed")
        _seed_steps(cur, conn, wf, stmap)

    bundle = customer_orion_bundle_for_api(wf, 1, None)
    dp = bundle["deliveryPrioritization"]
    assert dp["primaryFocus"]["kind"] == "status"
    assert dp["primaryFocus"]["reasonCode"] == "completed_state_no_primary_action"
    assert dp["prioritizationVersion"] == "orion_delivery_prioritization_v1"


def test_prioritization_stable_reason_codes():
    from services.guidance.delivery_prioritization import compute_delivery_prioritization_user_api

    dp = compute_delivery_prioritization_user_api(
        guidance=None,
        best_action={"actionKey": "review_claims", "actionType": "review"},
        action_candidates=[{"actionKey": "review_claims"}],
        best_action_explanation={"explanationType": "review"},
        readiness_context={"overallStatus": "active", "phase": "active"},
    )
    assert dp["primaryFocus"]["reasonCode"] == "review_action_primary"
    assert all("reasonCode" in s for s in dp["secondarySupport"])
    assert all("reasonCode" in s for s in dp["suppressedSignals"])


def test_bundle_includes_delivery_prioritization(isolated_workflow_sqlite):
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
    assert "deliveryPrioritization" in bundle
    assert bundle["deliveryPrioritization"]["prioritizationVersion"]


def test_audit_includes_prioritization_version(isolated_workflow_sqlite):
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
    dpa = audit["deliveryPrioritizationAudit"]
    assert dpa["prioritizationVersion"] == "orion_delivery_prioritization_v1"
    assert dpa["primaryReasonCode"] == dpa["deliveryPrioritization"]["primaryFocus"]["reasonCode"]
    assert isinstance(dpa["secondaryKinds"], list)
    assert isinstance(dpa["suppressedKinds"], list)


def test_prioritization_module_no_event_history_dependency():
    import services.guidance.delivery_prioritization as dp

    src = open(dp.__file__, "r", encoding="utf-8").read()
    tree = ast.parse(src)
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
    assert not any("workflow_event_service" in (m or "") for m in modules)
    assert "list_workflow_events" not in src


def test_review_multi_candidate_secondary_list(isolated_workflow_sqlite):
    from services.guidance.guidance_engine import customer_orion_bundle_for_api
    from services.workflow.workflow_db import get_workflow_db

    wf = str(uuid.uuid4())
    stmap = {s: "completed" for s in _linear_dispute()}
    # ``available`` avoids explanationType ``waiting``, so review + multi-candidate path applies.
    stmap["track"] = "available"
    with get_workflow_db() as (conn, cur):
        _seed_session(
            cur,
            conn,
            wf,
            current_step="track",
            overall="active",
            metadata='{"escalationEligible": true}',
        )
        _seed_steps(cur, conn, wf, stmap)

    bundle = customer_orion_bundle_for_api(wf, 1, None)
    assert len(bundle.get("actionCandidates") or []) >= 2
    dp = bundle["deliveryPrioritization"]
    assert dp["primaryFocus"]["kind"] == "best_action"
    kinds = [s["kind"] for s in dp["secondarySupport"]]
    assert "candidate_list" in kinds
