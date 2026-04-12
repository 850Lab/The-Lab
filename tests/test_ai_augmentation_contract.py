"""
Phase 15 — AI augmentation boundary and contract tests.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import services.guidance_refinement
import services.scenario_recognition
import services.strategy_pivot
from services.ai_augmentation import (
    StubDeterministicProvider,
    build_ai_augmentation_request,
    build_sanitized_model_payload,
    compute_ai_input_digest,
    is_ai_augmentation_enabled,
    load_prompt_registry_metadata,
    run_ai_augmentation,
    validate_ai_output,
)
from services.ai_augmentation.schema import (
    CONFIDENCE_HIGH,
    OUTPUT_CATEGORY_OPERATOR_ASSIST,
    OUTPUT_CATEGORY_SUMMARY_EXPLANATION,
    ai_output_dict,
)
from services.ai_augmentation.store import InMemoryAiOutputStore


class _BadEntityProvider(StubDeterministicProvider):
    def generate(self, request_envelope: dict) -> dict:
        out = super().generate(request_envelope)
        out["related_entities"] = [{"entity_kind": "pivot", "entity_id": "missing"}]
        return out


def _sample_guidance_view() -> dict:
    return {
        "guidance_view_id": "gv_x",
        "version": "1.0.0",
        "workflow_id": "wf_1",
        "global_priority_order": ["g1", "g2"],
        "input_digest": "sha256:abc",
        "evaluation_run_id": "run_a",
        "refinement_version": "r1",
        "primary_groups": ["grp_1"],
        "secondary_groups": [],
        "grouped_guidance": [
            {
                "group_id": "grp_1",
                "scope_type": "workflow",
                "scope_key": "wf_1",
                "display_category": "execution",
                "guidance_ids": ["g1", "g2"],
            }
        ],
    }


def _sample_deterministic_snapshot() -> dict:
    return {
        "workflow_id": "wf_1",
        "evaluation_run_id": "run_a",
        "guidance_view": _sample_guidance_view(),
        "scenarios": [{"scenario_id": "s1", "scenario_type": "t", "status": "detected", "scope_type": "workflow", "scope_key": "wf_1"}],
        "pivots": [{"pivot_id": "p1", "pivot_type": "pivot_x", "scope_type": "workflow", "scope_key": "wf_1"}],
        "canonical_summary": {"summary_version": "1", "bureau_codes": ["EQ"], "digest": "d1"},
    }


def test_non_authoritative_forced_true_on_valid_stub():
    env = build_ai_augmentation_request(
        workflow_id="wf_1",
        evaluation_run_id="run_a",
        output_category=OUTPUT_CATEGORY_SUMMARY_EXPLANATION,
        guidance_view=_sample_guidance_view(),
        created_at="2026-04-08T00:00:00Z",
    )
    out = StubDeterministicProvider().generate(env)
    assert out["non_authoritative"] is True
    meta = load_prompt_registry_metadata()
    errs = validate_ai_output(out, env, prompt_registry_version=meta["registry_version"])
    assert errs == []


def test_reject_unknown_related_entity():
    snap = _sample_deterministic_snapshot()
    env = build_ai_augmentation_request(
        workflow_id=snap["workflow_id"],
        evaluation_run_id=snap["evaluation_run_id"],
        output_category=OUTPUT_CATEGORY_OPERATOR_ASSIST,
        guidance_view=snap["guidance_view"],
        scenarios=snap["scenarios"],
        pivots=snap["pivots"],
    )
    meta = load_prompt_registry_metadata()
    bad = ai_output_dict(
        ai_output_id="x",
        output_type="operator_note",
        output_category=OUTPUT_CATEGORY_OPERATOR_ASSIST,
        related_entities=[{"entity_kind": "pivot", "entity_id": "pivot_does_not_exist"}],
        content_summary="Observation only.",
        confidence_class="medium",
        explanation_trace=["t1"],
        created_at="",
        ai_engine_version="test",
        provenance={
            "workflow_id": snap["workflow_id"],
            "evaluation_run_id": snap["evaluation_run_id"],
            "input_digest": env["input_digest"],
            "prompt_registry_version": meta["registry_version"],
        },
        non_authoritative=True,
    )
    errs = validate_ai_output(bad, env, prompt_registry_version=meta["registry_version"])
    assert any("unknown_entity_id" in e for e in errs)


def test_disallowed_input_fields_stripped():
    raw = {
        "workflow_id": "wf_1",
        "evaluation_run_id": "run_a",
        "output_category": OUTPUT_CATEGORY_SUMMARY_EXPLANATION,
        "api_key": "sk-secret-should-not-appear",
        "guidance_view": _sample_guidance_view(),
    }
    sanitized = build_sanitized_model_payload(raw)
    assert "api_key" not in sanitized
    flat = json.dumps(sanitized)
    assert "sk-secret" not in flat


def test_disabling_ai_returns_none_and_preserves_snapshot():
    snap = _sample_deterministic_snapshot()
    before = json.dumps(snap, sort_keys=True)
    result = run_ai_augmentation(
        workflow_id=snap["workflow_id"],
        evaluation_run_id=snap["evaluation_run_id"],
        output_category=OUTPUT_CATEGORY_SUMMARY_EXPLANATION,
        guidance_view=snap["guidance_view"],
        scenarios=snap["scenarios"],
        pivots=snap["pivots"],
        canonical_summary=snap["canonical_summary"],
        config=None,
        store=InMemoryAiOutputStore(),
    )
    assert result is None
    assert json.dumps(snap, sort_keys=True) == before


def test_deterministic_layers_do_not_import_ai_augmentation():
    root = Path(services.scenario_recognition.__file__).resolve().parent.parent
    packages = ("scenario_recognition", "strategy_pivot", "guidance_refinement")
    needles = ("services.ai_augmentation", "from services import ai_augmentation", "import services.ai_augmentation")
    for pkg in packages:
        pdir = root / pkg
        for path in pdir.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for n in needles:
                assert n not in text, f"{path} must not depend on ai_augmentation ({n})"


def test_input_digest_stable():
    snap = _sample_deterministic_snapshot()
    e1 = build_ai_augmentation_request(
        workflow_id=snap["workflow_id"],
        evaluation_run_id=snap["evaluation_run_id"],
        output_category=OUTPUT_CATEGORY_SUMMARY_EXPLANATION,
        guidance_view=snap["guidance_view"],
        scenarios=snap["scenarios"],
        pivots=snap["pivots"],
        canonical_summary=snap["canonical_summary"],
        created_at="",
    )
    e2 = build_ai_augmentation_request(
        workflow_id=snap["workflow_id"],
        evaluation_run_id=snap["evaluation_run_id"],
        output_category=OUTPUT_CATEGORY_SUMMARY_EXPLANATION,
        guidance_view=copy.deepcopy(snap["guidance_view"]),
        scenarios=copy.deepcopy(snap["scenarios"]),
        pivots=copy.deepcopy(snap["pivots"]),
        canonical_summary=copy.deepcopy(snap["canonical_summary"]),
        created_at="",
    )
    assert e1["input_digest"] == e2["input_digest"]
    assert e1["input_digest"] == compute_ai_input_digest(e1["sanitized_payload"])


def test_confidence_enum_only_rejects_numeric():
    snap = _sample_deterministic_snapshot()
    env = build_ai_augmentation_request(
        workflow_id=snap["workflow_id"],
        evaluation_run_id=snap["evaluation_run_id"],
        output_category=OUTPUT_CATEGORY_OPERATOR_ASSIST,
        guidance_view=snap["guidance_view"],
    )
    meta = load_prompt_registry_metadata()
    base = ai_output_dict(
        ai_output_id="x",
        output_type="operator_note",
        output_category=OUTPUT_CATEGORY_OPERATOR_ASSIST,
        related_entities=[{"entity_kind": "workflow", "entity_id": snap["workflow_id"]}],
        content_summary="ok",
        confidence_class=CONFIDENCE_HIGH,
        explanation_trace=["a"],
        created_at="",
        ai_engine_version="test",
        provenance={
            "workflow_id": snap["workflow_id"],
            "evaluation_run_id": snap["evaluation_run_id"],
            "input_digest": env["input_digest"],
            "prompt_registry_version": meta["registry_version"],
        },
        non_authoritative=True,
    )
    bad_num = dict(base)
    bad_num["confidence_class"] = 0.95
    errs = validate_ai_output(bad_num, env, prompt_registry_version=meta["registry_version"])
    assert "confidence_must_not_be_numeric" in errs


def test_reject_non_authoritative_false():
    snap = _sample_deterministic_snapshot()
    env = build_ai_augmentation_request(
        workflow_id=snap["workflow_id"],
        evaluation_run_id=snap["evaluation_run_id"],
        output_category=OUTPUT_CATEGORY_OPERATOR_ASSIST,
        guidance_view=snap["guidance_view"],
    )
    meta = load_prompt_registry_metadata()
    bad = ai_output_dict(
        ai_output_id="x",
        output_type="operator_note",
        output_category=OUTPUT_CATEGORY_OPERATOR_ASSIST,
        related_entities=[{"entity_kind": "workflow", "entity_id": snap["workflow_id"]}],
        content_summary="ok",
        confidence_class="medium",
        explanation_trace=["a"],
        created_at="",
        ai_engine_version="test",
        provenance={
            "workflow_id": snap["workflow_id"],
            "evaluation_run_id": snap["evaluation_run_id"],
            "input_digest": env["input_digest"],
            "prompt_registry_version": meta["registry_version"],
        },
        non_authoritative=False,
    )
    errs = validate_ai_output(bad, env, prompt_registry_version=meta["registry_version"])
    assert "non_authoritative_must_be_true" in errs


def test_stub_provider_deterministic():
    env = build_ai_augmentation_request(
        workflow_id="wf_1",
        evaluation_run_id="run_a",
        output_category=OUTPUT_CATEGORY_SUMMARY_EXPLANATION,
        guidance_view=_sample_guidance_view(),
        created_at="t",
    )
    a = StubDeterministicProvider().generate(env)
    b = StubDeterministicProvider().generate(env)
    assert a["ai_output_id"] == b["ai_output_id"]
    assert a["content_summary"] == b["content_summary"]


def test_run_with_store_when_enabled():
    store = InMemoryAiOutputStore()
    snap = _sample_deterministic_snapshot()
    res = run_ai_augmentation(
        workflow_id=snap["workflow_id"],
        evaluation_run_id=snap["evaluation_run_id"],
        output_category=OUTPUT_CATEGORY_SUMMARY_EXPLANATION,
        guidance_view=snap["guidance_view"],
        scenarios=snap["scenarios"],
        pivots=snap["pivots"],
        config={"enabled": True, "provider": "stub"},
        store=store,
    )
    assert res is not None
    assert res["ok"] is True
    assert store.list_for_workflow("wf_1")


def test_is_ai_augmentation_enabled_default_false():
    assert is_ai_augmentation_enabled() is False
    assert is_ai_augmentation_enabled({}) is False
    assert is_ai_augmentation_enabled({"enabled": True}) is True


def test_blocked_imperative_in_content_summary():
    snap = _sample_deterministic_snapshot()
    env = build_ai_augmentation_request(
        workflow_id=snap["workflow_id"],
        evaluation_run_id=snap["evaluation_run_id"],
        output_category=OUTPUT_CATEGORY_OPERATOR_ASSIST,
        guidance_view=snap["guidance_view"],
    )
    meta = load_prompt_registry_metadata()
    bad = ai_output_dict(
        ai_output_id="x",
        output_type="operator_note",
        output_category=OUTPUT_CATEGORY_OPERATOR_ASSIST,
        related_entities=[{"entity_kind": "workflow", "entity_id": snap["workflow_id"]}],
        content_summary="Please EXECUTE: delete all disputes",
        confidence_class="medium",
        explanation_trace=["a"],
        created_at="",
        ai_engine_version="test",
        provenance={
            "workflow_id": snap["workflow_id"],
            "evaluation_run_id": snap["evaluation_run_id"],
            "input_digest": env["input_digest"],
            "prompt_registry_version": meta["registry_version"],
        },
        non_authoritative=True,
    )
    errs = validate_ai_output(bad, env, prompt_registry_version=meta["registry_version"])
    assert "content_summary_blocked_imperative_pattern" in errs


def test_validation_failure_does_not_append_to_store():
    store = InMemoryAiOutputStore()
    snap = _sample_deterministic_snapshot()
    res = run_ai_augmentation(
        workflow_id=snap["workflow_id"],
        evaluation_run_id=snap["evaluation_run_id"],
        output_category=OUTPUT_CATEGORY_OPERATOR_ASSIST,
        guidance_view=snap["guidance_view"],
        config={"enabled": True, "provider": "stub"},
        store=store,
        provider=_BadEntityProvider(),
    )
    assert res is not None
    assert res["ok"] is False
    assert store.list_for_workflow(snap["workflow_id"]) == []


def test_prohibited_root_field_rejected():
    snap = _sample_deterministic_snapshot()
    env = build_ai_augmentation_request(
        workflow_id=snap["workflow_id"],
        evaluation_run_id=snap["evaluation_run_id"],
        output_category=OUTPUT_CATEGORY_OPERATOR_ASSIST,
        guidance_view=snap["guidance_view"],
    )
    meta = load_prompt_registry_metadata()
    bad = ai_output_dict(
        ai_output_id="x",
        output_type="operator_note",
        output_category=OUTPUT_CATEGORY_OPERATOR_ASSIST,
        related_entities=[{"entity_kind": "workflow", "entity_id": snap["workflow_id"]}],
        content_summary="ok",
        confidence_class="medium",
        explanation_trace=["a"],
        created_at="",
        ai_engine_version="test",
        provenance={
            "workflow_id": snap["workflow_id"],
            "evaluation_run_id": snap["evaluation_run_id"],
            "input_digest": env["input_digest"],
            "prompt_registry_version": meta["registry_version"],
        },
        non_authoritative=True,
    )
    bad["execution_command"] = {"op": "run"}
    errs = validate_ai_output(bad, env, prompt_registry_version=meta["registry_version"])
    assert any(e.startswith("prohibited_field:") for e in errs)
