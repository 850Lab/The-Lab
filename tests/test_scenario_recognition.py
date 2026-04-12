"""Phase 12 — scenario recognition deterministic behavior."""

from __future__ import annotations

import copy

import pytest

from services.scenario_recognition.context_adapter import build_evaluation_context
from services.scenario_recognition.evaluator import compute_input_digest, detect_scenarios
from services.scenario_recognition.rule_model import active_rules, load_rules_json
from services.scenario_recognition.schema import STATUS_BLOCKED_INSUFFICIENT_EVIDENCE, STATUS_DETECTED


def _slice(fp: str, bureaus: dict) -> dict:
    return {"account_fingerprint": fp, "bureaus": bureaus}


def _ctx(**kwargs):
    base = build_evaluation_context(
        evaluation_run_id=kwargs.pop("evaluation_run_id", "erun_test_1"),
        workflow_id=kwargs.pop("workflow_id", "wf_test"),
        detected_at=kwargs.pop("detected_at", "2026-04-08T12:00:00Z"),
        detector_version=kwargs.pop("detector_version", "scenario_test@1.0.0"),
        canonical_snapshot=kwargs.pop("canonical_snapshot", {}),
        cross_bureau_slices=kwargs.pop("cross_bureau_slices", []),
    )
    base.update(kwargs)
    return base


def test_cross_bureau_late_payment_only_with_two_bureaus_and_mismatch():
    ctx = _ctx(
        cross_bureau_slices=[
            _slice(
                "afp_1",
                {
                    "equifax": {
                        "values": {"late_payment_indicator": "late_30"},
                        "dimension_eligibility": {"late_payment_indicator": True},
                    },
                    "experian": {
                        "values": {"late_payment_indicator": "current"},
                        "dimension_eligibility": {"late_payment_indicator": True},
                    },
                },
            )
        ]
    )
    out = detect_scenarios(ctx)
    types = [x["scenario_type"] for x in out if x["status"] == STATUS_DETECTED]
    assert "cross_bureau_late_payment_misalignment" in types
    hit = next(x for x in out if x["scenario_type"] == "cross_bureau_late_payment_misalignment")
    assert hit["reason_code"] == "CB_LATE_PAY_MISMATCH_V1"
    assert hit["scope_key"] == "afp_1"
    assert set(hit.get("bureaus_compared") or []) == {"equifax", "experian"}


def test_incomplete_bureau_data_blocked_not_false_mismatch():
    """One bureau with late_payment value, other bureau row missing dimension → blocked (not mismatch)."""
    ctx = _ctx(
        cross_bureau_slices=[
            _slice(
                "afp_2",
                {
                    "equifax": {
                        "values": {"late_payment_indicator": "late_30"},
                        "dimension_eligibility": {"late_payment_indicator": True},
                    },
                    "experian": {
                        "values": {},
                        "dimension_eligibility": {"late_payment_indicator": True},
                    },
                },
            )
        ]
    )
    out = detect_scenarios(ctx)
    blocked = [
        x
        for x in out
        if x["scenario_type"] == "cross_bureau_late_payment_misalignment"
        and x["status"] == STATUS_BLOCKED_INSUFFICIENT_EVIDENCE
    ]
    assert len(blocked) == 1
    assert blocked[0]["blocking_reasons"] == ["INSUFFICIENT_BUREAU_COVERAGE"]
    assert "INSUFFICIENT_BUREAU_COVERAGE" in (blocked[0]["evidence"].get("blocking_detail") or "")


def test_status_mismatch_omits_when_insufficient_bureaus_no_false_positive():
    """Status rule uses omit policy: <2 bureaus with values → no scenario."""
    ctx = _ctx(
        cross_bureau_slices=[
            _slice(
                "afp_3",
                {
                    "equifax": {
                        "values": {"account_status_normalized": "open"},
                        "dimension_eligibility": {"account_status_normalized": True},
                    },
                },
            )
        ]
    )
    out = detect_scenarios(ctx)
    assert not any(
        x["scenario_type"] == "cross_bureau_account_status_misalignment" for x in out
    )


def test_payment_arrangement_and_delinquency_detected():
    ctx = _ctx(
        canonical_snapshot={
            "cf_payment_arrangement_active": {"value": True, "legally_eligible": True},
            "cf_delinquency_reported": {"value": True, "legally_eligible": True},
        }
    )
    out = detect_scenarios(ctx)
    hit = next(
        x
        for x in out
        if x["scenario_type"] == "payment_arrangement_with_persistent_delinquency"
    )
    assert hit["status"] == STATUS_DETECTED
    assert hit["reason_code"] == "NB_ARR_DELINQ_CONFLICT_V1"
    ids = {t["field_id"] for t in hit["triggering_fields"]}
    assert "cf_payment_arrangement_active" in ids
    assert "cf_delinquency_reported" in ids


def test_adverse_action_notice_without_application():
    ctx = _ctx(
        canonical_snapshot={
            "cf_adverse_action_notice_received": {"value": True, "legally_eligible": True},
            "cf_credit_application_submitted_recent": {"value": False, "legally_eligible": True},
        }
    )
    out = detect_scenarios(ctx)
    codes = {x["reason_code"] for x in out if x["status"] == STATUS_DETECTED}
    assert "NB_ADV_ACTION_NOTICE_WITHOUT_APP_V1" in codes


def test_adverse_action_application_without_notice():
    ctx = _ctx(
        canonical_snapshot={
            "cf_credit_application_submitted_recent": {"value": True, "legally_eligible": True},
            "cf_adverse_action_notice_received": {"value": False, "legally_eligible": True},
        }
    )
    out = detect_scenarios(ctx)
    codes = {x["reason_code"] for x in out if x["status"] == STATUS_DETECTED}
    assert "NB_ADV_ACTION_APP_WITHOUT_NOTICE_V1" in codes


def test_cro_engagement_fee_gap():
    ctx = _ctx(
        canonical_snapshot={
            "cf_credit_repair_organization_engaged": {"value": "yes", "legally_eligible": True},
            "cf_cro_fee_or_payment_before_outcome": {"value": False, "legally_eligible": True},
        }
    )
    out = detect_scenarios(ctx)
    hit = next(
        x for x in out if x["scenario_type"] == "cro_engagement_fee_timing_gap_or_conflict"
    )
    assert hit["reason_code"] == "NB_CRO_FEE_SIGNAL_GAP_V1"


def test_cfpb_complaint_unresolved_facts():
    ctx = _ctx(
        canonical_snapshot={
            "cf_regulatory_complaint_filed_cfpb": {"value": True, "legally_eligible": True},
            "cf_account_facts_fully_resolved": {"value": False, "legally_eligible": True},
        }
    )
    out = detect_scenarios(ctx)
    hit = next(
        x for x in out if x["scenario_type"] == "cfpb_complaint_with_unresolved_account_facts"
    )
    assert hit["reason_code"] == "NB_CFPB_ACCOUNT_FACTS_UNRESOLVED_V1"


def test_identical_inputs_identical_ordered_output_and_digest():
    ctx = _ctx(
        canonical_snapshot={
            "cf_regulatory_complaint_filed_cfpb": {"value": True, "legally_eligible": True},
            "cf_account_facts_fully_resolved": {"value": False, "legally_eligible": True},
        }
    )
    a = detect_scenarios(copy.deepcopy(ctx))
    b = detect_scenarios(copy.deepcopy(ctx))
    assert a == b
    assert compute_input_digest(ctx) == compute_input_digest(ctx)


def test_scenario_objects_have_required_fields():
    ctx = _ctx(
        cross_bureau_slices=[
            _slice(
                "afp_fields",
                {
                    "equifax": {"values": {"late_payment_indicator": "a"}},
                    "experian": {"values": {"late_payment_indicator": "b"}},
                },
            )
        ]
    )
    out = detect_scenarios(ctx)
    assert len(out) >= 1
    for s in out:
        for k in (
            "scenario_id",
            "version",
            "scenario_type",
            "status",
            "priority",
            "scope_type",
            "scope_key",
            "triggering_fields",
            "evidence",
            "reason_code",
            "detected_at",
            "detector_version",
            "rule_id",
            "rule_version",
            "evaluation_run_id",
            "input_digest",
        ):
            assert k in s


def test_dimension_eligibility_excludes_bureau_from_comparison():
    ctx = _ctx(
        cross_bureau_slices=[
            _slice(
                "afp_inelig",
                {
                    "equifax": {
                        "values": {"late_payment_indicator": "late_30"},
                        "dimension_eligibility": {"late_payment_indicator": False},
                    },
                    "experian": {
                        "values": {"late_payment_indicator": "current"},
                        "dimension_eligibility": {"late_payment_indicator": True},
                    },
                },
            )
        ]
    )
    out = detect_scenarios(ctx)
    assert not any(
        x["status"] == STATUS_DETECTED
        and x["scenario_type"] == "cross_bureau_late_payment_misalignment"
        for x in out
    )
    blocked = [x for x in out if x["status"] == STATUS_BLOCKED_INSUFFICIENT_EVIDENCE]
    assert len(blocked) == 1


def test_rules_load_and_active_subset():
    rules = load_rules_json()
    assert len(rules) >= 7
    assert all(r.status == "active" for r in active_rules(rules))


def test_balance_mismatch_detected_via_any_of_branch():
    ctx = _ctx(
        cross_bureau_slices=[
            _slice(
                "afp_bal",
                {
                    "equifax": {
                        "values": {"balance_normalized": 100, "past_due_normalized": 0},
                    },
                    "experian": {
                        "values": {"balance_normalized": 500, "past_due_normalized": 0},
                    },
                },
            )
        ]
    )
    out = detect_scenarios(ctx)
    assert any(
        x["scenario_type"] == "cross_bureau_balance_past_due_mismatch"
        and x["status"] == STATUS_DETECTED
        for x in out
    )
