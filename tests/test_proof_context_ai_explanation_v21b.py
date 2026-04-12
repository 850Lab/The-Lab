"""ORION V2.1B — proof context customer AI exposure (optional, non-authoritative)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")


def _fixed_workflow_payload():
    return {
        "workflow": {"workflowId": "wf-proof-ai", "currentStep": "proof_attachment"},
        "progression": {},
        "canonicalProgression": {},
        "workflowSync": {},
        "guidance": None,
        "bestAction": {"actionKey": "attach_proof_documents", "label": "Add proof"},
        "actionCandidates": [],
        "bestActionExplanation": {
            "summary": "Complete verification",
            "whyNow": "Mail partner needs ID and address on file.",
            "explanationType": "requirement",
        },
        "deliveryPrioritization": {"prioritizationVersion": "orion_delivery_prioritization_v1"},
        "uxSurfaceContract": None,
    }


def _fixed_proof():
    return {
        "hasGovernmentId": False,
        "hasAddressProof": False,
        "hasSignature": False,
        "governmentId": None,
        "addressProof": None,
        "workflowHeadStepId": "proof_attachment",
        "workflowPhase": "active",
        "proofStepStatus": None,
        "proofStepCompleted": False,
        "onProofAttachmentStep": True,
        "allRequirementsMet": False,
    }


class TestProofContextAiExplanationRoute:
    def test_default_response_has_no_ai_keys(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user

        wf = "00000000-0000-4000-8000-0000000000aa"
        monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)
        monkeypatch.setattr(
            "api.workflow_app._workflow_payload_with_progression",
            lambda _wid: _fixed_workflow_payload(),
        )
        monkeypatch.setattr(
            "api.workflow_app.build_proof_context_payload",
            lambda _uid, _wid: _fixed_proof(),
        )

        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 1,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 1,
            "role": "consumer",
            "email": "u@example.com",
        }
        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r = client.get(
                    f"/api/workflows/{wf}/proof/context",
                    headers={"Authorization": "Bearer t"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 200, r.text
        data = r.json()
        assert "aiExplanation" not in data
        assert "aiAugmentationStatus" not in data
        assert "aiScript" not in data
        assert "scriptAugmentationStatus" not in data
        assert data["bestAction"]["actionKey"] == "attach_proof_documents"

    def test_include_flag_adds_nullable_ai_and_trace_fields(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user

        wf = "00000000-0000-4000-8000-0000000000bb"
        monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)
        monkeypatch.setattr(
            "api.workflow_app._workflow_payload_with_progression",
            lambda _wid: _fixed_workflow_payload(),
        )
        monkeypatch.setattr(
            "api.workflow_app.build_proof_context_payload",
            lambda _uid, _wid: _fixed_proof(),
        )

        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 1,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 1,
            "role": "consumer",
            "email": "u@example.com",
        }
        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r = client.get(
                    f"/api/workflows/{wf}/proof/context?includeAiExplanation=true",
                    headers={"Authorization": "Bearer t"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["bestAction"]["actionKey"] == "attach_proof_documents"
        assert "aiExplanation" in data
        assert data["aiExplanation"] is not None
        assert data["aiExplanation"]["groundedIn"]["bestActionKey"] == "attach_proof_documents"
        assert data["aiAugmentationStatus"] == "available"
        assert data["intelligentExplanationFamily"]

    def test_merge_exception_yields_failed_status_not_500(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user

        wf = "00000000-0000-4000-8000-0000000000cc"
        monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)
        monkeypatch.setattr(
            "api.workflow_app._workflow_payload_with_progression",
            lambda _wid: _fixed_workflow_payload(),
        )
        monkeypatch.setattr(
            "api.workflow_app.build_proof_context_payload",
            lambda _uid, _wid: _fixed_proof(),
        )

        def boom(**_kwargs):
            raise RuntimeError("simulated augmentation failure")

        monkeypatch.setattr(
            "services.ai_augmentation.intelligent_explanation.merge_customer_workflow_payload_with_proof_ai_explanation",
            boom,
        )

        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 1,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 1,
            "role": "consumer",
            "email": "u@example.com",
        }
        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r = client.get(
                    f"/api/workflows/{wf}/proof/context?includeAiExplanation=true",
                    headers={"Authorization": "Bearer t"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["aiExplanation"] is None
        assert data["aiAugmentationStatus"] == "failed"

    def test_include_explanation_only_does_not_add_script_fields(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user

        wf = "00000000-0000-4000-8000-0000000000dd"
        monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)
        monkeypatch.setattr(
            "api.workflow_app._workflow_payload_with_progression",
            lambda _wid: _fixed_workflow_payload(),
        )
        monkeypatch.setattr(
            "api.workflow_app.build_proof_context_payload",
            lambda _uid, _wid: _fixed_proof(),
        )

        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 1,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 1,
            "role": "consumer",
            "email": "u@example.com",
        }
        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r = client.get(
                    f"/api/workflows/{wf}/proof/context?includeAiExplanation=true",
                    headers={"Authorization": "Bearer t"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 200, r.text
        data = r.json()
        assert "aiScript" not in data
        assert "scriptAugmentationStatus" not in data


class TestProofContextAiScriptRoute:
    def test_include_script_adds_nullable_fields(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user

        wf = "00000000-0000-4000-8000-0000000000ee"
        monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)
        monkeypatch.setattr(
            "api.workflow_app._workflow_payload_with_progression",
            lambda _wid: _fixed_workflow_payload(),
        )
        monkeypatch.setattr(
            "api.workflow_app.build_proof_context_payload",
            lambda _uid, _wid: _fixed_proof(),
        )

        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 1,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 1,
            "role": "consumer",
            "email": "u@example.com",
        }
        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r = client.get(
                    f"/api/workflows/{wf}/proof/context?includeAiScript=true",
                    headers={"Authorization": "Bearer t"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["bestAction"]["actionKey"] == "attach_proof_documents"
        assert "aiScript" in data
        assert data["aiScript"] is not None
        assert data["aiScript"]["scriptIntent"] == "proof_submission_support"
        assert data["aiScript"]["groundedIn"]["bestActionKey"] == "attach_proof_documents"
        assert data["scriptAugmentationStatus"] == "available"
        assert data["intelligentScriptFamily"] == "orion_intelligent_script_v1"
        assert data.get("proofScriptRefinementStatus") == "accepted"

    def test_script_suppressed_when_grounding_conflicts(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user
        from services.ai_augmentation import intelligent_scripts as iscr

        wf = "00000000-0000-4000-8000-0000000000ff"
        monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)
        monkeypatch.setattr(
            "api.workflow_app._workflow_payload_with_progression",
            lambda _wid: _fixed_workflow_payload(),
        )
        monkeypatch.setattr(
            "api.workflow_app.build_proof_context_payload",
            lambda _uid, _wid: _fixed_proof(),
        )

        bad_script = {
            "scriptIntent": "proof_submission_support",
            "title": "T",
            "intro": None,
            "lines": [{"speaker": "user", "text": "x"}],
            "talkingPoints": ["a"],
            "tone": "clear",
            "groundedIn": {
                "bestActionKey": "wrong_key",
                "explanationType": None,
                "guidanceType": None,
            },
        }

        def fake_gen(**_kwargs):
            return {
                "intelligentScriptFamily": iscr.INTELLIGENT_SCRIPT_FAMILY,
                "aiScript": bad_script,
                "scriptAugmentationStatus": "available",
            }

        monkeypatch.setattr(iscr, "generate_intelligent_script", fake_gen)

        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 1,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 1,
            "role": "consumer",
            "email": "u@example.com",
        }
        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r = client.get(
                    f"/api/workflows/{wf}/proof/context?includeAiScript=true",
                    headers={"Authorization": "Bearer t"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["aiScript"] is None
        assert data["scriptAugmentationStatus"] == "suppressed_ungrounded"
        assert data.get("proofScriptRefinementStatus") == "suppressed_ungrounded"

    def test_script_merge_exception_yields_failed_not_500(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user

        wf = "00000000-0000-4000-8000-000000000011"
        monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)
        monkeypatch.setattr(
            "api.workflow_app._workflow_payload_with_progression",
            lambda _wid: _fixed_workflow_payload(),
        )
        monkeypatch.setattr(
            "api.workflow_app.build_proof_context_payload",
            lambda _uid, _wid: _fixed_proof(),
        )

        def boom(**_kwargs):
            raise RuntimeError("simulated script merge failure")

        monkeypatch.setattr(
            "services.ai_augmentation.intelligent_scripts.merge_customer_workflow_payload_with_proof_ai_script",
            boom,
        )

        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 1,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 1,
            "role": "consumer",
            "email": "u@example.com",
        }
        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r = client.get(
                    f"/api/workflows/{wf}/proof/context?includeAiScript=true",
                    headers={"Authorization": "Bearer t"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["aiScript"] is None
        assert data["scriptAugmentationStatus"] == "failed"
        assert data.get("proofScriptRefinementStatus") == "not_applicable"

    def test_script_suppressed_redundant_sets_refinement_status(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.workflow_app import app
        from api.workflow_deps import get_owned_workflow, get_session_user

        wf = "00000000-0000-4000-8000-000000000022"
        monkeypatch.setattr("api.workflow_app.enforce_customer_action", lambda *a, **k: None)
        monkeypatch.setattr(
            "api.workflow_app._workflow_payload_with_progression",
            lambda _wid: _fixed_workflow_payload(),
        )
        monkeypatch.setattr(
            "api.workflow_app.build_proof_context_payload",
            lambda _uid, _wid: _fixed_proof(),
        )
        monkeypatch.setattr(
            "services.ai_augmentation.intelligent_scripts.assess_proof_script_distinctiveness",
            lambda *a, **k: "suppressed_redundant",
        )

        app.dependency_overrides[get_owned_workflow] = lambda: {
            "user_id": 1,
            "workflow_id": wf,
        }
        app.dependency_overrides[get_session_user] = lambda: {
            "user_id": 1,
            "role": "consumer",
            "email": "u@example.com",
        }
        try:
            with TestClient(app, raise_server_exceptions=True) as client:
                r = client.get(
                    f"/api/workflows/{wf}/proof/context?includeAiScript=true",
                    headers={"Authorization": "Bearer t"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["aiScript"] is None
        assert data["scriptAugmentationStatus"] == "suppressed_redundant"
        assert data.get("proofScriptRefinementStatus") == "suppressed_redundant"


class TestCustomerAiExplanationValidation:
    def test_suppresses_conflicting_best_action_key(self):
        from services.ai_augmentation.intelligent_explanation import (
            validate_customer_ai_explanation_against_orion,
        )

        orion = {"bestAction": {"actionKey": "a_ok"}}
        ai = {
            "headline": "H",
            "body": "B",
            "tone": "clear",
            "groundedIn": {"bestActionKey": "other", "explanationType": None, "guidanceType": None},
        }
        assert validate_customer_ai_explanation_against_orion(ai, orion) is None

    def test_suppresses_waiting_vs_urgent_mismatch(self):
        from services.ai_augmentation.intelligent_explanation import (
            validate_customer_ai_explanation_against_orion,
        )

        orion = {
            "bestAction": {"actionKey": "x"},
            "bestActionExplanation": {"explanationType": "waiting"},
        }
        ai = {
            "headline": "H",
            "body": "B",
            "tone": "urgent",
            "groundedIn": {"bestActionKey": "x", "explanationType": None, "guidanceType": None},
        }
        assert validate_customer_ai_explanation_against_orion(ai, orion) is None

    def test_merge_marks_suppressed_when_raw_conflicts(self, monkeypatch):
        from services.ai_augmentation import intelligent_explanation as ie

        orion = {"bestAction": {"actionKey": "correct_key", "label": "L"}}
        bad = {
            "headline": "H",
            "body": "B",
            "tone": "clear",
            "groundedIn": {
                "bestActionKey": "wrong_key",
                "explanationType": None,
                "guidanceType": None,
            },
        }

        def fake_gen(**_kwargs):
            return {
                "intelligentExplanationFamily": ie.INTELLIGENT_EXPLANATION_FAMILY,
                "aiExplanation": bad,
                "augmentationStatus": "available",
            }

        monkeypatch.setattr(ie, "generate_intelligent_explanation", fake_gen)
        out = ie.merge_customer_workflow_payload_with_proof_ai_explanation(
            payload={**orion, "proof": {}},
            workflow_id="w",
            include_ai_explanation=True,
        )
        assert out["aiExplanation"] is None
        assert out["aiAugmentationStatus"] == "suppressed_ungrounded"

    def test_merge_off_returns_empty(self):
        from services.ai_augmentation.intelligent_explanation import (
            merge_customer_workflow_payload_with_proof_ai_explanation,
        )

        assert (
            merge_customer_workflow_payload_with_proof_ai_explanation(
                payload={"bestAction": {}},
                workflow_id="w",
                include_ai_explanation=False,
            )
            == {}
        )
