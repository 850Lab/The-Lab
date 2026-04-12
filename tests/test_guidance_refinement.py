"""
Phase 14 — guidance refinement deterministic behavior.
"""

from __future__ import annotations

import copy

import pytest

from services.guidance_refinement import build_guidance_view, compute_refinement_input_digest
from services.guidance_refinement.builder import load_refinement_rules
from services.guidance_refinement.context_adapter import build_refinement_context


def _base_ctx(**kwargs):
    defaults = {
        "workflow_id": "wf_test",
        "evaluation_run_id": "run_001",
        "created_at": "2026-04-08T00:00:00Z",
        "guidance_items": [
            {
                "guidance_id": "g_a",
                "guidance_kind": "cross_bureau_tradeline",
                "original_priority": 40,
                "scope_type": "workflow",
                "scope_key": "wf_test",
                "source_triggers": [{"trigger_id": "t1"}],
            },
            {
                "guidance_id": "g_b",
                "guidance_kind": "low_stakes_hygiene",
                "original_priority": 30,
                "scope_type": "workflow",
                "scope_key": "wf_test",
                "source_triggers": [{"trigger_id": "t2"}],
            },
            {
                "guidance_id": "g_c",
                "guidance_kind": "workflow_gate",
                "original_priority": 20,
                "scope_type": "bureau",
                "scope_key": "bureau:EXP",
                "source_triggers": [{"trigger_id": "t3"}],
            },
        ],
        "pivots": [],
        "scenarios": [],
    }
    defaults.update(kwargs)
    return build_refinement_context(**defaults)


def test_same_inputs_identical_global_priority_order_and_digest():
    ctx = _base_ctx()
    r1 = build_guidance_view(ctx)
    r2 = build_guidance_view(ctx)
    assert r1["global_priority_order"] == r2["global_priority_order"]
    assert r1["input_digest"] == r2["input_digest"]
    rules = load_refinement_rules()
    assert compute_refinement_input_digest(ctx, rules["rules_version"]) == r1["input_digest"]


def test_regroup_preserves_item_identities():
    ctx = _base_ctx()
    view = build_guidance_view(ctx)
    ids_in = {str(x["guidance_id"]) for x in ctx["guidance_items"]}
    ids_grouped = set()
    for g in view["grouped_guidance"]:
        ids_grouped.update(g["guidance_ids"])
    assert ids_grouped == ids_in
    for g in view["grouped_guidance"]:
        for it in g["items"]:
            assert it["guidance_id"] in ids_in


def test_pivot_elevate_and_deemphasize_deterministic():
    ctx = _base_ctx(
        pivots=[
            {
                "pivot_id": "p1",
                "pivot_type": "pivot_cross_bureau_late_payment",
                "scope_type": "workflow",
                "scope_key": "wf_test",
            },
            {
                "pivot_id": "p2",
                "pivot_type": "pivot_cfpb_unresolved_facts",
                "scope_type": "workflow",
                "scope_key": "wf_test",
            },
        ],
    )
    view = build_guidance_view(ctx)
    by_id = {str(x["guidance_id"]): x for x in _all_refined_items(view)}
    assert by_id["g_a"]["priority"] < 40
    assert "prio_pivot:pl_cb_late_elevate" in (by_id["g_a"].get("refinement_reason_codes") or [])
    assert by_id["g_b"]["priority"] > 30
    assert "prio_pivot:pl_cfpb_deemphasize" in (by_id["g_b"].get("refinement_reason_codes") or [])
    assert by_id["g_b"]["emphasis_level"] == "secondary"


def test_workflow_only_step_defers_non_workflow_scope():
    ctx = _base_ctx(
        step_context={"step_scope_mode": "workflow_only"},
    )
    view = build_guidance_view(ctx)
    by_id = {str(x["guidance_id"]): x for x in _all_refined_items(view)}
    assert by_id["g_c"]["visibility"] == "deferred"
    assert "DEFER_NON_WORKFLOW_IN_WORKFLOW_STEP" in (by_id["g_c"].get("refinement_reason_codes") or [])


def test_bureau_focus_mismatch_hidden_auditable_in_excluded():
    ctx = _base_ctx(
        step_context={
            "step_scope_mode": "bureau_detail",
            "focused_scope_key": "bureau:EQ",
        },
    )
    view = build_guidance_view(ctx)
    excluded = view.get("excluded_items") or []
    hidden = [x for x in excluded if x["guidance_id"] == "g_c"]
    assert len(hidden) == 1
    assert hidden[0]["visibility"] == "hidden"
    assert "BUREAU_FOCUS_MISMATCH" in hidden[0]["refinement_reason_codes"]
    assert hidden[0]["guidance_id"] == "g_c"
    assert "priority_tier" in hidden[0]


def test_pivot_suppress_moves_to_excluded_auditable():
    ctx = _base_ctx(
        pivots=[
            {
                "pivot_id": "p2",
                "pivot_type": "pivot_cfpb_unresolved_facts",
                "scope_type": "workflow",
                "scope_key": "wf_test",
            },
        ],
    )
    view = build_guidance_view(ctx)
    ex = {x["guidance_id"]: x for x in (view.get("excluded_items") or [])}
    assert "g_b" in ex
    assert ex["g_b"]["visibility"] == "suppressed"
    assert "SUPPRESS_HYGIENE_UNDER_CFPB_PIVOT" in ex["g_b"]["refinement_reason_codes"]
    assert not any("g_b" in (g.get("guidance_ids") or []) for g in view["grouped_guidance"])


def test_group_ids_and_order_stable():
    ctx = _base_ctx()
    g1 = build_guidance_view(ctx)["grouped_guidance"]
    g2 = build_guidance_view(copy.deepcopy(ctx))["grouped_guidance"]
    assert [x["group_id"] for x in g1] == [x["group_id"] for x in g2]
    for a, b in zip(g1, g2):
        assert a["guidance_ids"] == b["guidance_ids"]


def test_refinement_fields_are_structural_not_prose():
    ctx = _base_ctx()
    view = build_guidance_view(ctx)
    for it in _all_refined_items(view):
        for key in (
            "priority_tier",
            "display_category",
            "emphasis_level",
            "visibility",
            "scope_type",
        ):
            val = str(it.get(key) or "")
            assert "\n" not in val
            assert len(val) < 80
        for code in it.get("refinement_reason_codes") or []:
            assert isinstance(code, str)
            assert len(code) < 160


def _all_refined_items(view):
    out = []
    for g in view["grouped_guidance"]:
        out.extend(g["items"])
    for x in view.get("excluded_items") or []:
        out.append(x)
    return out


def test_scenario_severity_adjusts_priority():
    ctx = _base_ctx(
        guidance_items=[
            {
                "guidance_id": "g_s",
                "guidance_kind": "cross_bureau_tradeline",
                "original_priority": 50,
                "scope_type": "workflow",
                "scope_key": "wf_test",
                "source_triggers": [],
            },
        ],
        scenarios=[
            {
                "scenario_id": "s1",
                "scenario_type": "payment_arrangement_with_persistent_delinquency",
                "status": "detected",
                "scope_type": "workflow",
                "scope_key": "wf_test",
            },
        ],
    )
    view = build_guidance_view(ctx)
    it = view["grouped_guidance"][0]["items"][0]
    assert it["priority"] < 50
    assert any(x.startswith("prio_scenario:") for x in (it.get("refinement_reason_codes") or []))
