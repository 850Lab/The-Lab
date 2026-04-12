"""ORION V2.2 — intelligent script augmentation (non-authoritative)."""

from __future__ import annotations

import copy

import pytest

pytest.importorskip("sqlite3")

from services.ai_augmentation.intelligent_scripts import (
    ALLOWED_SCRIPT_INTENTS,
    INTELLIGENT_SCRIPT_FAMILY,
    PROOF_CUSTOMER_SCRIPT_INTENT,
    assess_proof_script_distinctiveness,
    build_intelligent_script_input,
    build_intelligent_script_prompt_messages,
    generate_intelligent_script,
    internal_intelligent_script_audit,
    merge_customer_workflow_payload_with_proof_ai_script,
    stub_complete_script_from_orion_input,
    validate_customer_ai_script_against_orion,
)


@pytest.fixture()
def isolated_workflow_sqlite(monkeypatch, tmp_path):
    dbfile = tmp_path / "wf_intelligent_scripts.sqlite"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(dbfile))

    import services.workflow.workflow_sqlite as wsq

    wsq._conn = None
    wsq.ensure_schema()
    yield dbfile
    wsq._conn = None


def _sample_bundle():
    return {
        "bestAction": {"actionKey": "attach_proof_documents", "label": "Add proof documents"},
        "bestActionExplanation": {
            "summary": "Complete verification",
            "whyNow": "Mail partner needs documents.",
            "explanationType": "requirement",
        },
        "guidance": None,
        "deliveryPrioritization": {"prioritizationVersion": "orion_delivery_prioritization_v1"},
        "uxSurfaceContract": None,
    }


def test_build_input_compact_no_event_history():
    b = _sample_bundle()
    inp = build_intelligent_script_input(
        b,
        workflow_id="wf-1",
        script_intent="proof_submission_support",
        contract_completeness="partial",
    )
    assert inp["workflowId"] == "wf-1"
    assert inp["scriptIntent"] == "proof_submission_support"
    assert inp["intelligentScriptFamily"] == INTELLIGENT_SCRIPT_FAMILY
    assert "events" not in inp
    assert "workflow_events" not in inp


def test_generate_skipped_by_default():
    out = generate_intelligent_script(
        orion_bundle=_sample_bundle(),
        workflow_id="w",
        script_intent="proof_submission_support",
    )
    assert out["scriptAugmentationStatus"] == "skipped"
    assert out["aiScript"] is None
    assert out["intelligentScriptFamily"] == INTELLIGENT_SCRIPT_FAMILY


def test_generate_stub_available_proof_intent():
    out = generate_intelligent_script(
        orion_bundle=_sample_bundle(),
        workflow_id="w",
        script_intent="proof_submission_support",
        invoke_ai=True,
        backend=None,
    )
    assert out["scriptAugmentationStatus"] == "available"
    assert out["aiScript"] is not None
    assert out["aiScript"]["scriptIntent"] == "proof_submission_support"
    assert out["aiScript"]["groundedIn"]["bestActionKey"] == "attach_proof_documents"
    assert out["aiScript"]["title"] == "What you're doing right now"
    assert 1 <= len(out["aiScript"]["lines"]) <= 4
    assert 1 <= len(out["aiScript"]["talkingPoints"]) <= 4
    flat = " ".join(
        [out["aiScript"]["title"], str(out["aiScript"].get("intro") or "")]
        + [ln["text"] for ln in out["aiScript"]["lines"]]
        + out["aiScript"]["talkingPoints"]
    ).lower()
    assert "upload" in flat or "sign" in flat


def test_generate_backend_unavailable():
    class NoAnswer:
        def complete_json(self, *, system: str, user: str):
            return None

    out = generate_intelligent_script(
        orion_bundle=_sample_bundle(),
        workflow_id="w",
        script_intent="bureau_contact_talking_points",
        invoke_ai=True,
        backend=NoAnswer(),
    )
    assert out["scriptAugmentationStatus"] == "unavailable"
    assert out["aiScript"] is None


def test_generate_backend_invalid_shape_failed():
    class BadShape:
        def complete_json(self, *, system: str, user: str):
            return {"scriptIntent": "bureau_contact_talking_points", "title": 1}

    out = generate_intelligent_script(
        orion_bundle=_sample_bundle(),
        workflow_id="w",
        script_intent="bureau_contact_talking_points",
        invoke_ai=True,
        backend=BadShape(),
    )
    assert out["scriptAugmentationStatus"] == "failed"
    assert out["aiScript"] is None


def test_generate_backend_valid_shape():
    class Good:
        def complete_json(self, *, system: str, user: str):
            return {
                "scriptIntent": "bureau_contact_talking_points",
                "title": "T",
                "intro": None,
                "lines": [{"speaker": "user", "text": "Hello"}],
                "talkingPoints": ["One", "Two"],
                "tone": "calm",
                "groundedIn": {
                    "bestActionKey": "attach_proof_documents",
                    "explanationType": None,
                    "guidanceType": None,
                },
            }

    out = generate_intelligent_script(
        orion_bundle=_sample_bundle(),
        workflow_id="w",
        script_intent="bureau_contact_talking_points",
        invoke_ai=True,
        backend=Good(),
    )
    assert out["scriptAugmentationStatus"] == "available"
    assert out["aiScript"]["title"] == "T"


def test_validate_suppresses_script_intent_mismatch():
    orion = {"bestAction": {"actionKey": "x"}}
    script = {
        "scriptIntent": "proof_submission_support",
        "title": "T",
        "intro": None,
        "lines": [{"speaker": "user", "text": "x"}],
        "talkingPoints": ["p"],
        "tone": "clear",
        "groundedIn": {"bestActionKey": "x", "explanationType": None, "guidanceType": None},
    }
    assert (
        validate_customer_ai_script_against_orion(
            script,
            orion,
            script_intent="creditor_call_script",
        )
        is None
    )


def test_validate_suppresses_conflicting_action_key():
    orion = {"bestAction": {"actionKey": "a_ok"}}
    script = {
        "scriptIntent": "proof_submission_support",
        "title": "T",
        "intro": None,
        "lines": [{"speaker": "user", "text": "x"}],
        "talkingPoints": ["p"],
        "tone": "clear",
        "groundedIn": {"bestActionKey": "other", "explanationType": None, "guidanceType": None},
    }
    assert (
        validate_customer_ai_script_against_orion(
            script,
            orion,
            script_intent="proof_submission_support",
        )
        is None
    )


def test_validate_suppresses_creditor_script_when_waiting():
    orion = {
        "bestAction": {"actionKey": "wait", "label": "Wait"},
        "bestActionExplanation": {"explanationType": "waiting"},
    }
    script = {
        "scriptIntent": "creditor_call_script",
        "title": "Call",
        "intro": None,
        "lines": [{"speaker": "user", "text": "Hi"}],
        "talkingPoints": ["a"],
        "tone": "calm",
        "groundedIn": {"bestActionKey": "wait", "explanationType": "waiting", "guidanceType": None},
    }
    assert (
        validate_customer_ai_script_against_orion(
            script,
            orion,
            script_intent="creditor_call_script",
        )
        is None
    )


def test_orion_bundle_not_mutated():
    b = _sample_bundle()
    snap = copy.deepcopy(b)
    generate_intelligent_script(
        orion_bundle=b,
        workflow_id="w",
        script_intent="creditor_call_script",
        invoke_ai=True,
        backend=None,
    )
    assert b == snap


def test_invalid_script_intent_failed():
    out = generate_intelligent_script(
        orion_bundle=_sample_bundle(),
        workflow_id="w",
        script_intent="not_a_real_intent",
        invoke_ai=True,
        backend=None,
    )
    assert out["scriptAugmentationStatus"] == "failed"
    assert out["aiScript"] is None


def test_allowed_intents_frozen():
    assert set(ALLOWED_SCRIPT_INTENTS) == {
        "proof_submission_support",
        "creditor_call_script",
        "bureau_contact_talking_points",
    }


def test_proof_customer_intent_constant():
    assert PROOF_CUSTOMER_SCRIPT_INTENT == "proof_submission_support"


def test_merge_proof_script_off_returns_empty():
    out = merge_customer_workflow_payload_with_proof_ai_script(
        payload={"bestAction": {"actionKey": "x"}},
        workflow_id="w",
        include_ai_script=False,
    )
    assert out == {}


def test_merge_proof_script_includes_validated_stub():
    payload = {
        "bestAction": {"actionKey": "attach_proof_documents", "label": "Add proof"},
        "bestActionExplanation": {
            "summary": "S",
            "explanationType": "requirement",
        },
        "guidance": None,
        "deliveryPrioritization": {"prioritizationVersion": "orion_delivery_prioritization_v1"},
        "uxSurfaceContract": None,
    }
    out = merge_customer_workflow_payload_with_proof_ai_script(
        payload=payload,
        workflow_id="wf",
        include_ai_script=True,
    )
    assert out["scriptAugmentationStatus"] == "available"
    assert out["aiScript"] is not None
    assert out["aiScript"]["scriptIntent"] == "proof_submission_support"
    assert out["intelligentScriptFamily"] == INTELLIGENT_SCRIPT_FAMILY
    assert out["proofScriptRefinementStatus"] == "accepted"


def test_merge_proof_script_suppressed_when_distinctiveness_fails(monkeypatch):
    monkeypatch.setattr(
        "services.ai_augmentation.intelligent_scripts.assess_proof_script_distinctiveness",
        lambda *a, **k: "suppressed_redundant",
    )
    payload = {
        "bestAction": {"actionKey": "attach_proof_documents", "label": "Add proof"},
        "bestActionExplanation": {
            "summary": "S",
            "explanationType": "requirement",
        },
        "guidance": None,
        "deliveryPrioritization": {"prioritizationVersion": "orion_delivery_prioritization_v1"},
        "uxSurfaceContract": None,
    }
    out = merge_customer_workflow_payload_with_proof_ai_script(
        payload=payload,
        workflow_id="wf",
        include_ai_script=True,
    )
    assert out["aiScript"] is None
    assert out["scriptAugmentationStatus"] == "suppressed_redundant"
    assert out["proofScriptRefinementStatus"] == "suppressed_redundant"


def test_proof_submission_prompt_is_execution_focused():
    inp = build_intelligent_script_input(
        _sample_bundle(),
        workflow_id="w",
        script_intent="proof_submission_support",
        contract_completeness="partial",
    )
    sys_m, _ = build_intelligent_script_prompt_messages(inp)
    low = sys_m.lower()
    assert "execution" in low
    assert "forbidden" in low
    assert "phone" in low or "call" in low


def test_assess_proof_script_too_long_extra_lines():
    orion = {"bestAction": {"actionKey": "x"}, "bestActionExplanation": {}}
    script = {
        "scriptIntent": "proof_submission_support",
        "title": "T",
        "intro": None,
        "lines": [{"speaker": "user", "text": f"L{i}"} for i in range(5)],
        "talkingPoints": [],
        "tone": "clear",
        "groundedIn": {"bestActionKey": None, "explanationType": None, "guidanceType": None},
    }
    assert assess_proof_script_distinctiveness(script, orion) == "suppressed_too_long"


def test_assess_proof_script_not_action_shaped():
    orion = {"bestAction": {"actionKey": "x"}, "bestActionExplanation": {}}
    script = {
        "scriptIntent": "proof_submission_support",
        "title": "Reflection",
        "intro": None,
        "lines": [
            {
                "speaker": "user",
                "text": "The abstract fairness of credit reporting narratives remains philosophically complex.",
            }
        ],
        "talkingPoints": ["Historical context informs systemic interpretation broadly."],
        "tone": "calm",
        "groundedIn": {"bestActionKey": None, "explanationType": None, "guidanceType": None},
    }
    assert assess_proof_script_distinctiveness(script, orion) == "suppressed_not_action_shaped"


def test_assess_proof_script_redundant_overlap_with_explanation():
    orion = {
        "bestAction": {"actionKey": "x"},
        "bestActionExplanation": {
            "summary": "complete verification identity address mailing package dispute filing",
            "whyNow": "partner documentation preparation confirmation requirements process",
        },
    }
    script = {
        "scriptIntent": "proof_submission_support",
        "title": "Note",
        "intro": "complete verification identity address mailing package dispute filing partner",
        "lines": [
            {
                "speaker": "user",
                "text": "upload save documents now verification address mailing package dispute filing",
            }
        ],
        "talkingPoints": [
            "documentation preparation confirmation requirements process partner verification"
        ],
        "tone": "clear",
        "groundedIn": {"bestActionKey": None, "explanationType": None, "guidanceType": None},
    }
    assert assess_proof_script_distinctiveness(script, orion) == "suppressed_redundant"


def test_assess_accepts_refined_stub_like_script():
    bundle = _sample_bundle()
    inp = build_intelligent_script_input(
        bundle,
        workflow_id="w",
        script_intent="proof_submission_support",
        contract_completeness="partial",
    )
    stub = stub_complete_script_from_orion_input(inp, orion_bundle=bundle)
    assert assess_proof_script_distinctiveness(stub, bundle, ai_explanation=None) == "accepted"


def test_creditor_script_skipped_when_waiting_posture():
    waiting_bundle = {
        **_sample_bundle(),
        "bestActionExplanation": {
            "summary": "Hold",
            "explanationType": "waiting",
        },
    }
    out = generate_intelligent_script(
        orion_bundle=waiting_bundle,
        workflow_id="w",
        script_intent="creditor_call_script",
        invoke_ai=True,
        backend=None,
    )
    assert out["scriptAugmentationStatus"] == "skipped"
    assert out["aiScript"] is None


def test_proof_script_still_available_when_waiting():
    waiting_bundle = {
        **_sample_bundle(),
        "bestActionExplanation": {
            "summary": "Hold",
            "explanationType": "waiting",
        },
    }
    out = generate_intelligent_script(
        orion_bundle=waiting_bundle,
        workflow_id="w",
        script_intent="proof_submission_support",
        invoke_ai=True,
        backend=None,
    )
    assert out["scriptAugmentationStatus"] == "available"
    assert out["aiScript"] is not None


def test_prompt_messages_reference_intent():
    inp = build_intelligent_script_input(
        _sample_bundle(),
        workflow_id="w",
        script_intent="creditor_call_script",
        contract_completeness="partial",
    )
    sys_m, usr = build_intelligent_script_prompt_messages(inp)
    assert "creditor_call_script" in sys_m
    assert INTELLIGENT_SCRIPT_FAMILY in usr


@pytest.mark.usefixtures("isolated_workflow_sqlite")
def test_internal_audit_structure(isolated_workflow_sqlite):
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

    audit = internal_intelligent_script_audit(
        wf,
        "proof_submission_support",
        invoke_ai=True,
        persist_guidance=False,
    )
    assert audit["workflowId"] == wf
    assert audit["scriptIntent"] == "proof_submission_support"
    assert audit["input"]["intelligentScriptFamily"] == INTELLIGENT_SCRIPT_FAMILY
    assert "augmentation" in audit
    assert audit["augmentation"]["intelligentScriptFamily"] == INTELLIGENT_SCRIPT_FAMILY
    assert "orionEcho" in audit
    assert "proofCustomerPreview" not in audit


@pytest.mark.usefixtures("isolated_workflow_sqlite")
def test_internal_audit_apply_refinement_adds_proof_customer_preview(isolated_workflow_sqlite):
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

    audit = internal_intelligent_script_audit(
        wf,
        "proof_submission_support",
        invoke_ai=True,
        persist_guidance=False,
        apply_refinement=True,
    )
    assert "proofCustomerPreview" in audit
    prev = audit["proofCustomerPreview"]
    assert "aiScript" in prev
    assert "scriptAugmentationStatus" in prev
    assert "proofScriptRefinementStatus" in prev
    assert prev["proofScriptRefinementStatus"] == "accepted"
    assert prev["aiScript"] is not None
    assert audit["augmentation"]["aiScript"] is not None


@pytest.mark.usefixtures("isolated_workflow_sqlite")
def test_internal_audit_apply_refinement_ignored_for_non_proof_intent(isolated_workflow_sqlite):
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

    audit = internal_intelligent_script_audit(
        wf,
        "creditor_call_script",
        invoke_ai=True,
        persist_guidance=False,
        apply_refinement=True,
    )
    assert "proofCustomerPreview" not in audit
