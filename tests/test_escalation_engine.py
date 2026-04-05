"""Escalation engine triggers (no DB)."""

from services.workflow.escalation_engine import (
    TRIGGER_INSUFFICIENT_UPDATE,
    TRIGGER_NO_RESPONSE,
    TRIGGER_REPEATED_VERIFIED,
    build_escalation_actions_from_triggers,
    collect_escalation_triggers,
    verified_snapshot_count_for_claim,
)


def test_verified_snapshot_count():
    prior = [
        {
            "kind": "response_intake",
            "claimOutcomeSnapshot": {"c1": "verified", "c2": "updated"},
        },
        {
            "kind": "response_intake",
            "claimOutcomeSnapshot": {"c1": "verified"},
        },
    ]
    assert verified_snapshot_count_for_claim(prior, "c1") == 2


def test_no_response_triggers_actions():
    ds = {
        "dispute_round_number": 1,
        "cumulative_disputed_review_claim_ids": ["a"],
        "claim_outcomes": {"a": "no_response"},
        "prior_outcomes": [],
    }
    tr = collect_escalation_triggers(ds)
    assert "a" in tr[TRIGGER_NO_RESPONSE]
    acts = build_escalation_actions_from_triggers(tr)
    types = {a["type"] for a in acts}
    assert "method_of_verification" in types
    assert "cfpb_complaint" in types
    assert "furnisher_dispute" in types
    assert "call_script" in types


def test_repeated_verified_triggers():
    ds = {
        "cumulative_disputed_review_claim_ids": ["x"],
        "claim_outcomes": {"x": "verified"},
        "prior_outcomes": [
            {"kind": "response_intake", "claimOutcomeSnapshot": {"x": "verified"}},
            {"kind": "response_intake", "claimOutcomeSnapshot": {"x": "verified"}},
        ],
    }
    tr = collect_escalation_triggers(ds)
    assert "x" in tr[TRIGGER_REPEATED_VERIFIED]


def test_insufficient_update_round_two():
    ds = {
        "dispute_round_number": 2,
        "cumulative_disputed_review_claim_ids": ["z"],
        "claim_outcomes": {"z": "updated"},
        "prior_outcomes": [],
    }
    tr = collect_escalation_triggers(ds)
    assert "z" in tr[TRIGGER_INSUFFICIENT_UPDATE]
