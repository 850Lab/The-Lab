"""Phase 13 — strategy pivot deterministic behavior."""

from __future__ import annotations

import copy

from services.strategy_pivot import (
    build_pivot_evaluation_context,
    build_strategy_pivots,
    compute_pivot_input_digest,
)
from services.strategy_pivot.rule_model import load_compatibility_matrix, load_pivot_rules_json


def _scenario(
    *,
    sid: str,
    stype: str,
    scope_type: str,
    scope_key: str,
    status: str = "detected",
    priority: int = 20,
    bureaus_compared: list | None = None,
    related_account_fingerprint: str | None = None,
    evidence: dict | None = None,
) -> dict:
    return {
        "scenario_id": sid,
        "version": "1.0.0",
        "scenario_type": stype,
        "status": status,
        "priority": priority,
        "scope_type": scope_type,
        "scope_key": scope_key,
        "triggering_fields": [],
        "evidence": evidence or {},
        "reason_code": "R",
        "detected_at": "2026-04-08T12:00:00Z",
        "detector_version": "sr@test",
        "rule_id": "r",
        "rule_version": "1.0.0",
        "evaluation_run_id": "erun_x",
        "input_digest": "sha256:x",
        **({"bureaus_compared": bureaus_compared} if bureaus_compared is not None else {}),
        **(
            {"related_account_fingerprint": related_account_fingerprint}
            if related_account_fingerprint
            else {}
        ),
    }


def _ctx(scenarios: list, **kwargs):
    return build_pivot_evaluation_context(
        evaluation_run_id=kwargs.get("evaluation_run_id", "erun_pv_1"),
        as_of=kwargs.get("as_of", "2026-04-08T12:00:00Z"),
        scenarios=scenarios,
        pivot_engine_version=kwargs.get("pivot_engine_version", "pivot_test@1.0.0"),
    )


def test_same_scenarios_same_pivots_order_and_digest():
    s = [
        _scenario(
            sid="s1",
            stype="cross_bureau_late_payment_misalignment",
            scope_type="account_fingerprint",
            scope_key="afp_a",
            bureaus_compared=["equifax", "experian"],
        )
    ]
    ctx = _ctx(s)
    a = build_strategy_pivots(ctx)
    b = build_strategy_pivots(copy.deepcopy(ctx))
    assert a == b
    d1 = compute_pivot_input_digest(s, {}, "erun_pv_1")
    d2 = compute_pivot_input_digest(s, {}, "erun_pv_1")
    assert d1 == d2


def test_cross_bureau_late_payment_directives():
    s = [
        _scenario(
            sid="s_late",
            stype="cross_bureau_late_payment_misalignment",
            scope_type="account_fingerprint",
            scope_key="afp_z",
            bureaus_compared=["equifax", "transunion"],
        )
    ]
    out = build_strategy_pivots(_ctx(s))
    assert len(out) == 1
    p = out[0]
    assert p["pivot_type"] == "pivot_cross_bureau_late_payment"
    assert p["scope_type"] == "account_fingerprint"
    assert p["scope_key"] == "afp_z"
    cats = [d["category"] for d in p["strategy_directives"]]
    assert cats == [
        "target_focus",
        "dispute_framing_type",
        "grouping_strategy",
        "sequencing_hint",
    ]
    tf = next(x for x in p["strategy_directives"] if x["category"] == "target_focus")
    assert tf["value"]["mode"] == "all_mismatch_bureaus"
    assert tf["params"]["bureau_codes"] == ["equifax", "transunion"]
    df = next(x for x in p["strategy_directives"] if x["category"] == "dispute_framing_type")
    assert df["value"]["type"] == "consistency_challenge"


def test_payment_arrangement_delinquency_pivot():
    s = [
        _scenario(
            sid="s_pad",
            stype="payment_arrangement_with_persistent_delinquency",
            scope_type="account_fingerprint",
            scope_key="afp_p",
        )
    ]
    out = build_strategy_pivots(_ctx(s))
    p = next(x for x in out if x["pivot_type"] == "pivot_payment_arrangement_delinquency")
    assert p["reason_code"] == "PIVOT_ARR_DELINQ_V1"
    types = {d["value"].get("type") for d in p["strategy_directives"] if d["category"] == "dispute_framing_type"}
    assert "remedy_state_contradiction" in types


def test_adverse_action_workflow_pivot():
    s = [
        _scenario(
            sid="s_adv",
            stype="adverse_action_context_incomplete_or_contradictory",
            scope_type="workflow",
            scope_key="wf_main",
        )
    ]
    out = build_strategy_pivots(_ctx(s))
    p = next(x for x in out if x["pivot_type"] == "pivot_adverse_action_context")
    assert p["scope_type"] == "workflow"
    prefs = {
        d["value"]["preference"]
        for d in p["strategy_directives"]
        if d["category"] == "escalation_path_preference"
    }
    assert "fact_completion_first" in prefs


def test_exclusive_pair_suppresses_lower_precedence_pivot():
    s = [
        _scenario(
            sid="s_adv",
            stype="adverse_action_context_incomplete_or_contradictory",
            scope_type="workflow",
            scope_key="wf_x",
            priority=5,
        ),
        _scenario(
            sid="s_cfpb",
            stype="cfpb_complaint_with_unresolved_account_facts",
            scope_type="workflow",
            scope_key="wf_x",
            priority=5,
            evidence={"unresolved_account_fingerprints": ["afp_u1", "afp_u2"]},
        ),
    ]
    out = build_strategy_pivots(_ctx(s))
    winners = [p for p in out if not p.get("suppressed_by")]
    suppressed = [p for p in out if p.get("suppressed_by")]
    assert len(suppressed) == 1
    assert suppressed[0]["strategy_directives"] == []
    w = next(p for p in winners if p["pivot_type"] == "pivot_cfpb_unresolved_facts")
    assert suppressed[0]["suppressed_by"] == [w["pivot_id"]]
    assert int(w["priority"]) < int(
        next(p for p in out if p["pivot_type"] == "pivot_adverse_action_context")["priority"]
    )


def test_directives_structured_no_prose_keys():
    s = [
        _scenario(
            sid="s1",
            stype="cross_bureau_account_status_misalignment",
            scope_type="account_fingerprint",
            scope_key="afp_s",
            bureaus_compared=["equifax"],
        )
    ]
    out = build_strategy_pivots(_ctx(s))
    for p in out:
        for d in p.get("strategy_directives") or []:
            assert "instructions" not in d
            assert "text" not in d
            assert "message" not in d
            for k, v in (d.get("value") or {}).items():
                assert isinstance(k, str)
                assert isinstance(v, (str, int, float, bool)) or v is None
            for k, v in (d.get("params") or {}).items():
                assert isinstance(k, str)
                assert isinstance(v, list)
                for item in v:
                    assert isinstance(item, (str, int))


def test_pivot_ids_stable():
    s = [
        _scenario(
            sid="sid_stable",
            stype="cro_engagement_fee_timing_gap_or_conflict",
            scope_type="workflow",
            scope_key="wf_y",
        )
    ]
    ctx = _ctx(s, evaluation_run_id="fixed_erun")
    a = [p["pivot_id"] for p in build_strategy_pivots(ctx)]
    b = [p["pivot_id"] for p in build_strategy_pivots(copy.deepcopy(ctx))]
    assert a == b


def test_rules_load_six_active():
    rules = load_pivot_rules_json()
    assert len([r for r in rules if r.status == "active"]) == 6


def test_compatibility_matrix_loads():
    m = load_compatibility_matrix()
    assert "exclusive_pivot_pairs" in m
