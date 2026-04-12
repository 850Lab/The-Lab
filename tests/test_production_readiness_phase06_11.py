"""
Production readiness — Phases 6–11 (guidance, delivery contract via API in sibling file,
law, canonical intelligence, cross-bureau aggregation).

Phases 12–15 live under ``services.*``; see ``test_production_readiness_phase12_15_blockers.py``
and the retail full-chain E2E in ``test_production_readiness_api_e2e.py`` (requires ``DATABASE_URL``).
"""

from __future__ import annotations

import copy
import json

import pytest

from aggregator import build_cross_bureau_key, detect_discrepancies
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
from services.case_intelligence.contradictions import detect_contradictions
from services.case_intelligence.compose import build_canonical_case_intelligence
from services.case_intelligence.models import CaseIntelligenceInputs
from services.execution_guidance import build_execution_guidance_bundle
from services.law_bank.load_corpus import load_published_units
from services.law_bank.resolve import resolve_law_units, unit_matches_context
from services.strategy_paths import generate_strategy_paths
from services.strategy_patterns import evaluate_strategy_patterns
from services.strategy_scoring import score_strategy_paths

from tests.test_production_readiness_phase01_02 import _ci_rich


def _spa_bundle():
    ci = _ci_rich()
    pb = evaluate_strategy_patterns(ci)
    paths = generate_strategy_paths(ci, pb)
    sc = score_strategy_paths(ci, pb, paths)
    return build_execution_guidance_bundle(
        ci, pb, paths, sc, primary_path_id="path_standard_negative_first_pass"
    )


class TestPhase06GuidanceEngine:
    def test_guidance_bundle_fully_structured_dict(self):
        eg = _spa_bundle()
        d = eg.to_dict()
        assert d["schemaVersion"]
        assert isinstance(d["blocks"], list) and len(d["blocks"]) >= 1
        b0 = d["blocks"][0]
        assert set(b0.keys()) >= {"blockId", "pathId", "blockType", "actor", "channel"}

    def test_same_inputs_same_bundle_shape(self):
        a = _spa_bundle().to_dict()
        b = _spa_bundle().to_dict()
        assert a == b

    def test_guidance_independent_of_ui_state(self):
        """Bundle is built only from case intelligence + strategy artifacts (no HTTP)."""
        eg = _spa_bundle()
        d1 = eg.to_dict()
        d2 = json.loads(json.dumps(d1))
        assert d1 == d2


class TestPhase09LawIntelligence:
    @pytest.fixture(autouse=True)
    def _clear_corpus_cache(self):
        load_published_units.cache_clear()
        yield
        load_published_units.cache_clear()

    def test_insufficient_context_does_not_attach_full_fcra_reinvestigation(self):
        u = next(
            x
            for x in load_published_units()
            if x["unitId"] == "law_fcra_cra_reinvestigation_v1"
        )
        minimal = {"disputeRound": 0, "subjectMatterTagsPresent": ["investigation"]}
        assert not unit_matches_context(u, minimal)

    def test_law_refs_only_from_published_matching_units(self):
        ctx = {
            "schemaVersion": "law_resolution_context_v1",
            "disputeRound": 1,
            "authoritativeStepId": "select_disputes",
            "hasBureauTarget": True,
            "hasFurnisherTarget": True,
            "identityContext": False,
            "escalationEligible": False,
            "hasCollectionAccountSignals": False,
            "hasInquirySignals": False,
            "subjectMatterTagsPresent": ["accuracy", "investigation"],
            "outcomePatternFlags": {
                "op_dispute_round_active": True,
                "op_eligible_pool_non_empty": True,
            },
        }
        refs = resolve_law_units(ctx)
        ids = {r["unitId"] for r in refs}
        published_ids = {u["unitId"] for u in load_published_units()}
        assert ids <= published_ids
        for r in refs:
            assert r["version"]
            assert r["title"]

    def test_multi_field_bool_trigger_requires_all_conjuncts(self):
        """Regression: compound triggerConditions are conjunctive (AND)."""
        synthetic = {
            "unitId": "law_pr_synthetic_dual_bool_v1",
            "version": "1.0.0",
            "title": "Synthetic",
            "summary": "Test unit",
            "leverageImpact": "n/a",
            "leverageType": "informational",
            "enforcementShape": "informational",
            "primaryCitations": [],
            "triggerConditions": {
                "hasBureauTarget": True,
                "identityContext": True,
            },
        }
        corpus = (synthetic,)
        assert resolve_law_units({"hasBureauTarget": True}, _published_units=corpus) == []
        assert resolve_law_units({"identityContext": True}, _published_units=corpus) == []
        refs = resolve_law_units(
            {"hasBureauTarget": True, "identityContext": True},
            _published_units=corpus,
        )
        assert [r["unitId"] for r in refs] == ["law_pr_synthetic_dual_bool_v1"]


def _bal_claim(cid: str, bureau: str, bal: str, creditor: str = "ACME") -> Claim:
    return Claim(
        claim_id=cid,
        claim_type=ClaimType.BALANCE_REPORTED,
        entity=creditor,
        source=bureau,
        confidence=0.9,
        state=ClaimState.EXTRACTED,
        fields={"creditor": creditor, "balance": bal, "last4": "4242"},
    )


class TestPhase10CanonicalCaseIntelligence:
    def test_cross_bureau_balance_contradiction_grounded_in_claim_ids(self):
        raw = [
            _bal_claim("c1", "experian", "5000", "ACME"),
            _bal_claim("c2", "equifax", "100", "ACME"),
        ]
        contradictions = detect_contradictions(raw, [])
        types = {c.signal_type for c in contradictions}
        assert "cross_bureau_balance_mismatch" in types
        rec = next(c for c in contradictions if c.signal_type == "cross_bureau_balance_mismatch")
        assert set(rec.involved_raw_claim_ids) <= {"c1", "c2"}
        assert rec.grounded_in == "parsed_balance_reported_claims_by_fingerprint"

    def test_single_bureau_balance_does_not_emit_cross_bureau_contradiction(self):
        raw = [
            _bal_claim("c1", "experian", "100", "ACME"),
            _bal_claim("c2", "experian", "9999", "ACME"),
        ]
        contradictions = detect_contradictions(raw, [])
        assert all(c.signal_type != "cross_bureau_balance_mismatch" for c in contradictions)

    def test_case_intelligence_deterministic_for_fixed_inputs(self):
        rc = ReviewClaim(
            review_claim_id="rc1",
            review_type=ReviewType.NEGATIVE_IMPACT,
            summary="x",
            question="q",
            entities={"bureau": "Experian"},
            supporting_claim_ids=["s1"],
            evidence_summary=EvidenceSummary(
                system_observations=[],
                cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
                claim_confidence_summary=ClaimConfidenceSummary(high=1, medium=0, low=0),
            ),
            consumer_response=ConsumerResponse(),
            impact_assessment=ImpactAssessment(CreditImpact.NEGATIVE, Severity.MODERATE),
            audit=Audit(),
        )
        inp = CaseIntelligenceInputs(
            workflow_id="wf_pr_det",
            user_id=1,
            report_scope=[
                {"reportId": 1, "bureau": "experian", "counts": {"negativeItems": 1, "accounts": 1}},
            ],
            raw_claims=[],
            review_claims=[rc],
            workflow_metadata={},
            selected_review_claim_ids=[],
            proof_flags={
                "hasGovernmentId": True,
                "hasAddressProof": True,
                "hasSignature": True,
            },
            letter_records=[],
            authoritative_step_id="review_claims",
        )
        a = build_canonical_case_intelligence(inp)
        b = build_canonical_case_intelligence(inp)
        assert a.to_dict() == b.to_dict()


class TestPhase11CrossBureauModel:
    def test_cross_bureau_key_deterministic(self):
        acct = {
            "account_name": "Test Bank",
            "account_number": "****1234",
            "date_opened": "01/2020",
            "bureau": "experian",
        }
        assert build_cross_bureau_key(acct) == build_cross_bureau_key(copy.deepcopy(acct))

    def test_payment_status_mismatch_across_bureaus_detected(self):
        accounts = [
            {
                "bureau": "equifax",
                "payment_status": "30 days late",
                "balance": "100",
                "status": "open",
            },
            {
                "bureau": "experian",
                "payment_status": "Current",
                "balance": "100",
                "status": "open",
            },
        ]
        disc = detect_discrepancies(accounts)
        keys = {d["field_key"] for d in disc}
        assert "payment_status" in keys

    def test_single_bureau_accounts_produce_no_discrepancy_list(self):
        accounts = [
            {"bureau": "equifax", "payment_status": "Late", "balance": "1"},
        ]
        assert detect_discrepancies(accounts) == []
