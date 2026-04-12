"""ORION V2.1 — intelligent explanation augmentation (non-authoritative)."""

from __future__ import annotations

import copy

import pytest

pytest.importorskip("sqlite3")

from services.ai_augmentation.intelligent_explanation import (
    INTELLIGENT_EXPLANATION_FAMILY,
    build_intelligent_explanation_input,
    build_intelligent_explanation_prompt_messages,
    contract_completeness_from_orion_bundle,
    generate_intelligent_explanation,
)


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_intelligent_explanation.sqlite"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(dbfile))

    import services.workflow.workflow_sqlite as wsq

    wsq._conn = None
    wsq.ensure_schema()
    yield dbfile
    wsq._conn = None


def test_build_input_grounding_no_event_history():
    bundle = {
        "bestAction": {"actionKey": "complete_payment", "label": "Pay"},
        "bestActionExplanation": {"summary": "Finish pay", "explanationType": "requirement"},
        "guidance": None,
        "deliveryPrioritization": {"prioritizationVersion": "orion_delivery_prioritization_v1"},
        "uxSurfaceContract": None,
    }
    inp = build_intelligent_explanation_input(
        bundle,
        workflow_id="wf-1",
        contract_completeness="partial",
    )
    assert inp["workflowId"] == "wf-1"
    assert inp["bestAction"]["actionKey"] == "complete_payment"
    assert "events" not in inp
    assert "workflow_events" not in inp
    assert inp["intelligentExplanationFamily"] == INTELLIGENT_EXPLANATION_FAMILY


def test_contract_completeness_from_bundle():
    full_b = {
        "deliveryPrioritization": {"primaryFocus": {"kind": "best_action"}},
        "uxSurfaceContract": {"primarySurface": {"surfaceType": "hero_panel"}},
    }
    assert contract_completeness_from_orion_bundle(full_b) == "full"
    partial_b = {"bestAction": {"actionKey": "x"}}
    assert contract_completeness_from_orion_bundle(partial_b) == "partial"
    assert contract_completeness_from_orion_bundle({}) == "legacy"


def test_generate_skipped_by_default():
    bundle = {"bestAction": {"actionKey": "a", "label": "L"}}
    out = generate_intelligent_explanation(orion_bundle=bundle, workflow_id="w")
    assert out["augmentationStatus"] == "skipped"
    assert out["aiExplanation"] is None
    assert out["intelligentExplanationFamily"] == INTELLIGENT_EXPLANATION_FAMILY


def test_generate_stub_available():
    bundle = {
        "bestAction": {"actionKey": "complete_payment", "label": "Finish payment"},
        "bestActionExplanation": {
            "summary": "Activate round",
            "whyNow": "Letters unlock next",
            "explanationType": "requirement",
        },
    }
    out = generate_intelligent_explanation(
        orion_bundle=bundle,
        workflow_id="w",
        invoke_ai=True,
        backend=None,
    )
    assert out["augmentationStatus"] == "available"
    assert out["aiExplanation"] is not None
    assert out["aiExplanation"]["groundedIn"]["bestActionKey"] == "complete_payment"
    assert out["aiExplanation"]["tone"] == "clear"


def test_generate_backend_none_returns_unavailable():
    class NoAnswer:
        def complete_json(self, *, system: str, user: str):
            return None

    bundle = {"bestAction": {"actionKey": "x", "label": "Y"}}
    out = generate_intelligent_explanation(
        orion_bundle=bundle,
        workflow_id="w",
        invoke_ai=True,
        backend=NoAnswer(),
    )
    assert out["augmentationStatus"] == "unavailable"
    assert out["aiExplanation"] is None


def test_generate_backend_invalid_shape_failed():
    class BadShape:
        def complete_json(self, *, system: str, user: str):
            return {"headline": 1, "body": "b", "tone": "calm", "groundedIn": {}}

    bundle = {"bestAction": {"actionKey": "x"}}
    out = generate_intelligent_explanation(
        orion_bundle=bundle,
        workflow_id="w",
        invoke_ai=True,
        backend=BadShape(),
    )
    assert out["augmentationStatus"] == "failed"
    assert out["aiExplanation"] is None


def test_generate_backend_valid_shape():
    class Good:
        def complete_json(self, *, system: str, user: str):
            return {
                "headline": "H",
                "body": "B",
                "nextStepLabel": "Go",
                "tone": "calm",
                "groundedIn": {
                    "bestActionKey": "k",
                    "explanationType": None,
                    "guidanceType": None,
                },
            }

    bundle = {"bestAction": {"actionKey": "x"}}
    out = generate_intelligent_explanation(
        orion_bundle=bundle,
        workflow_id="w",
        invoke_ai=True,
        backend=Good(),
    )
    assert out["augmentationStatus"] == "available"
    assert out["aiExplanation"]["headline"] == "H"


def test_orion_bundle_not_mutated():
    bundle = {
        "bestAction": {"actionKey": "k1", "label": "L"},
        "bestActionExplanation": {"summary": "S"},
    }
    snap = copy.deepcopy(bundle)
    generate_intelligent_explanation(orion_bundle=bundle, workflow_id="w", invoke_ai=True)
    assert bundle == snap


def test_prompt_messages_contain_grounding():
    inp = build_intelligent_explanation_input(
        {"bestAction": {"actionKey": "pay"}},
        workflow_id="w",
        contract_completeness="partial",
    )
    sys_m, usr = build_intelligent_explanation_prompt_messages(inp)
    assert "authoritative" in sys_m.lower()
    assert "Ground truth ORION" in usr and "pay" in usr


@pytest.mark.usefixtures("isolated_workflow_sqlite")
def test_internal_audit_smoke(isolated_workflow_sqlite):
    from services.ai_augmentation.intelligent_explanation import internal_intelligent_explanation_audit
    from services.workflow.workflow_db import get_workflow_db
    import uuid

    wf = str(uuid.uuid4())
    with get_workflow_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_sessions (
                workflow_id, user_id, workflow_type, current_step, overall_status, metadata, updated_at
            )
            VALUES (%s, %s, 'dispute_linear_v1', 'payment', 'active', %s, %s)
            """,
            (wf, 1, "{}", "2026-01-15T12:00:00+00:00"),
        )
        conn.commit()

    audit = internal_intelligent_explanation_audit(wf, invoke_ai=True, persist_guidance=False)
    assert audit["workflowId"] == wf
    assert audit["augmentation"]["intelligentExplanationFamily"] == INTELLIGENT_EXPLANATION_FAMILY
    assert audit["augmentation"]["augmentationStatus"] in ("available", "skipped", "unavailable", "failed")
