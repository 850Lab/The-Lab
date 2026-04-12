"""
Canonical Case Intelligence Layer — unit tests (no DB for core composer).
"""

from __future__ import annotations

from claims import Claim, ClaimState, ClaimType
from review_claims import (
    Audit,
    ClaimConfidenceSummary,
    ConsumerResponse,
    CreditImpact,
    CrossBureauStatus,
    EvidenceSummary,
    ImpactAssessment,
    ReviewClaim,
    ReviewType,
    Severity,
)

from services.case_intelligence.compose import build_canonical_case_intelligence
from services.case_intelligence.contradictions import detect_contradictions
from services.case_intelligence.grouping import build_normalized_account_groups
from services.case_intelligence.models import CaseIntelligenceInputs


def _rc(
    rid: str,
    rtype: ReviewType,
    *,
    high_conf: bool = True,
    bureau: str = "Experian",
) -> ReviewClaim:
    conf = ClaimConfidenceSummary(high=1 if high_conf else 0, medium=0 if high_conf else 1, low=0)
    return ReviewClaim(
        review_claim_id=rid,
        review_type=rtype,
        summary="Test item",
        question="Is this accurate?",
        entities={"bureau": bureau, "account_name": "TestCreditor"},
        supporting_claim_ids=["s1"],
        evidence_summary=EvidenceSummary(
            system_observations=[],
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=conf,
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(CreditImpact.NEGATIVE, Severity.MODERATE),
        audit=Audit(),
    )


def _bal(cid: str, bureau: str, creditor: str, balance: str, last4: str = "1111") -> Claim:
    return Claim(
        claim_id=cid,
        claim_type=ClaimType.BALANCE_REPORTED,
        entity=creditor,
        source=bureau,
        confidence=0.9,
        state=ClaimState.EXTRACTED,
        fields={"creditor": creditor, "balance": balance, "last4": last4},
    )


def _stat(cid: str, bureau: str, creditor: str, status: str, last4: str = "2222") -> Claim:
    return Claim(
        claim_id=cid,
        claim_type=ClaimType.STATUS_REPORTED,
        entity=creditor,
        source=bureau,
        confidence=0.85,
        state=ClaimState.EXTRACTED,
        fields={"creditor": creditor, "status": status, "last4": last4},
    )


def test_review_claim_from_dict_roundtrip():
    rc = _rc("rc_a", ReviewType.NEGATIVE_IMPACT)
    d = rc.to_dict()
    back = ReviewClaim.from_dict(d)
    assert back.review_claim_id == rc.review_claim_id
    assert back.review_type == rc.review_type
    assert back.evidence_summary.claim_confidence_summary.high == 1


def test_grouping_multi_bureau_same_fingerprint():
    raw = [
        _bal("b1", "experian", "ACME BANK", "500", "9999"),
        _bal("b2", "equifax", "ACME BANK", "510", "9999"),
    ]
    groups = build_normalized_account_groups(raw)
    assert len(groups) == 1
    assert len(groups[0].bureaus_present) == 2
    assert groups[0].linkage_confidence == "medium"


def test_grouping_canonical_key_high_confidence():
    raw = [
        Claim(
            claim_id="c1",
            claim_type=ClaimType.BALANCE_REPORTED,
            entity="X",
            source="experian",
            confidence=0.9,
            state=ClaimState.EXTRACTED,
            fields={"canonical_account_key": "ck-1", "balance": "100"},
        ),
    ]
    groups = build_normalized_account_groups(raw)
    assert len(groups) == 1
    assert groups[0].linkage_confidence == "high"


def test_contradiction_balance_mismatch_cross_bureau():
    raw = [
        _bal("b1", "experian", "Same Bank", "1000", "1234"),
        _bal("b2", "equifax", "Same Bank", "5000", "1234"),
    ]
    cons = detect_contradictions(raw, [])
    types = {c.signal_type for c in cons}
    assert "cross_bureau_balance_mismatch" in types


def test_contradiction_status_inconsistency():
    raw = [
        _stat("s1", "experian", "Door Bank", "Open / pays as agreed", "7777"),
        _stat("s2", "transunion", "Door Bank", "Charged off", "7777"),
    ]
    cons = detect_contradictions(raw, [])
    assert any(c.signal_type == "cross_bureau_status_inconsistency" for c in cons)


def test_documentation_rich_partial_thin():
    from services.case_intelligence.compose import _build_documentation_summary

    rich = _build_documentation_summary(
        {"hasGovernmentId": True, "hasAddressProof": True, "hasSignature": True}
    )
    assert rich.sufficiency == "rich"
    assert rich.evidence_richness == "high"

    partial = _build_documentation_summary(
        {"hasGovernmentId": True, "hasAddressProof": False, "hasSignature": False}
    )
    assert partial.sufficiency == "partial"

    thin = _build_documentation_summary(
        {"hasGovernmentId": False, "hasAddressProof": False, "hasSignature": False}
    )
    assert thin.sufficiency == "thin"
    assert "government_id" in thin.missing_doc_flags


def test_objective_unknown_vs_present():
    from services.case_intelligence.compose import _goal_state
    from services.case_intelligence.models import DocumentationStateSummary

    doc = DocumentationStateSummary(
        has_government_id=True,
        has_address_proof=True,
        has_signature=True,
        sufficiency="rich",
        missing_doc_flags=[],
        evidence_richness="high",
    )
    unknown = _goal_state({}, "review_claims", doc, eligible_dispute_count=2)
    assert unknown.stated_objective is None
    assert unknown.objective_source == "unknown"

    present = _goal_state(
        {"caseObjective": "fastest_cleanup"},
        "select_disputes",
        doc,
        eligible_dispute_count=1,
    )
    assert present.stated_objective == "fastest_cleanup"
    assert present.objective_source == "workflow_metadata"


def test_stable_generation_from_inputs():
    review = [
        _rc("r1", ReviewType.NEGATIVE_IMPACT),
        _rc("r2", ReviewType.DUPLICATE_ACCOUNT, high_conf=True),
    ]
    raw = [
        _bal("x1", "experian", "ACME", "200", "3333"),
        _bal("x2", "equifax", "ACME", "200", "3333"),
    ]
    inputs = CaseIntelligenceInputs(
        workflow_id="wf_test",
        user_id=42,
        report_scope=[
            {
                "reportId": 1,
                "bureau": "experian",
                "counts": {"negativeItems": 2, "accounts": 3},
            }
        ],
        raw_claims=raw,
        review_claims=review,
        workflow_metadata={
            "dispute_selection": {
                "dispute_round_number": 1,
                "cumulative_disputed_review_claim_ids": ["r9"],
                "claim_outcomes": {"r9": "no_response"},
            }
        },
        selected_review_claim_ids=["r1"],
        proof_flags={
            "hasGovernmentId": True,
            "hasAddressProof": False,
            "hasSignature": True,
        },
        letter_records=[
            {"report_id": 1, "bureau": "experian", "id": 10},
        ],
        authoritative_step_id="review_claims",
    )
    out = build_canonical_case_intelligence(inputs)
    d = out.to_dict()
    assert d["schemaVersion"] == "case_intelligence.v1"
    assert d["caseSummary"]["totalReviewClaims"] == 2
    assert d["caseSummary"]["candidateDisputeItemsEligibleNow"] >= 1
    assert len(d["accountGroups"]) >= 1
    assert len(d["strategySignals"]) >= 1
    assert d["documentation"]["sufficiency"] == "partial"
    assert d["actionHistory"]["unresolvedDisputedIds"] == ["r9"]
    assert d["identity"]["workflowId"] == "wf_test"

    out2 = build_canonical_case_intelligence(inputs)
    assert out.to_dict() == out2.to_dict()
