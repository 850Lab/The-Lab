"""
Strategy Pattern Library — load, match, exclusions, stable output (no DB).
"""

from __future__ import annotations

import json

from services.case_intelligence.models import (
    ActionHistorySummary,
    CanonicalCaseIntelligenceV1,
    ContradictionRecord,
    DocumentationStateSummary,
    GoalConstraintState,
    StrategySignalRecord,
)
from services.strategy_patterns import (
    evaluate_strategy_patterns,
    load_pattern_library_v1,
)
from services.strategy_patterns.matcher import _gate_match_confidence
from services.strategy_patterns.facts import build_case_fact_snapshot


def _by_id(bundle):
    return {e.pattern_id: e for e in bundle.evaluations}


def _ci(
    *,
    case_summary: dict | None = None,
    contradictions: list | None = None,
    strategy_signals: list | None = None,
    documentation: DocumentationStateSummary | None = None,
    action_history: ActionHistorySummary | None = None,
    identity: dict | None = None,
    goal_constraints: GoalConstraintState | None = None,
) -> CanonicalCaseIntelligenceV1:
    base_summary = {
        "contradictionCount": 0,
        "multiBureauNormalizedGroups": 0,
        "candidateDisputeItemsEligibleNow": 0,
        "totalReviewClaims": 0,
        "caseTypeSummary": "",
    }
    if case_summary:
        base_summary.update(case_summary)
    return CanonicalCaseIntelligenceV1(
        schema_version="canonical_case_intelligence.v1",
        identity=identity if identity is not None else {"bureauCoverage": []},
        case_summary=base_summary,
        account_groups=[],
        strategy_signals=strategy_signals or [],
        contradictions=contradictions or [],
        documentation=documentation
        or DocumentationStateSummary(
            has_government_id=False,
            has_address_proof=False,
            has_signature=False,
            sufficiency="unknown",
            missing_doc_flags=[],
            evidence_richness="low",
        ),
        action_history=action_history
        or ActionHistorySummary(
            cumulative_disputed_review_claim_ids=[],
            claim_outcomes={},
            dispute_round_number=0,
            letter_count_for_scope=0,
            letter_bureaus_distinct=[],
            unresolved_disputed_ids=[],
        ),
        goal_constraints=goal_constraints
        or GoalConstraintState(
            stated_objective=None,
            objective_source="unknown",
            timing_sensitivity="unknown",
            readiness_blockers=[],
            next_dependencies=[],
        ),
        confidence_notes=[],
        explainability=[],
    )


def test_load_pattern_library_v1_count_and_ids():
    lib = load_pattern_library_v1()
    assert len(lib) == 8
    ids = sorted(p.pattern_id for p in lib)
    assert ids == sorted(set(ids))
    assert "pat_inconsistency_led_challenge" in ids
    assert all(p.version for p in lib)


def test_evaluate_stable_json_roundtrip():
    ci = _ci(
        case_summary={"candidateDisputeItemsEligibleNow": 1, "contradictionCount": 0},
        documentation=DocumentationStateSummary(
            has_government_id=True,
            has_address_proof=True,
            has_signature=True,
            sufficiency="rich",
            missing_doc_flags=[],
            evidence_richness="high",
        ),
    )
    b1 = evaluate_strategy_patterns(ci).to_dict()
    b2 = evaluate_strategy_patterns(ci).to_dict()
    assert b1 == b2
    json.dumps(b1)
    assert b1["matchedPatternIds"] == sorted(b1["matchedPatternIds"])
    assert b1["unmatchedPatternIds"] == sorted(b1["unmatchedPatternIds"])


def test_exclusion_no_candidate_suppresses_inconsistency_pattern():
    ci = _ci(
        contradictions=[
            ContradictionRecord(
                signal_type="cross_bureau_balance_mismatch",
                description="x",
                grounded_in="test",
            )
        ],
        case_summary={
            "contradictionCount": 1,
            "candidateDisputeItemsEligibleNow": 0,
            "totalReviewClaims": 1,
        },
    )
    bundle = evaluate_strategy_patterns(ci)
    inc = _by_id(bundle)["pat_inconsistency_led_challenge"]
    assert not inc.matched
    assert inc.exclusion_hits
    assert "no_candidate" in inc.exclusion_hits[0].lower() or "candidate" in inc.explanation.lower()


def test_standard_negative_excluded_when_prior_letters():
    base = _ci(
        case_summary={
            "candidateDisputeItemsEligibleNow": 2,
            "contradictionCount": 0,
            "totalReviewClaims": 2,
        },
        action_history=ActionHistorySummary(
            cumulative_disputed_review_claim_ids=[],
            claim_outcomes={},
            dispute_round_number=1,
            letter_count_for_scope=0,
            letter_bureaus_distinct=[],
            unresolved_disputed_ids=[],
        ),
    )
    with_letters = _ci(
        case_summary={
            "candidateDisputeItemsEligibleNow": 2,
            "contradictionCount": 0,
            "totalReviewClaims": 2,
        },
        action_history=ActionHistorySummary(
            cumulative_disputed_review_claim_ids=[],
            claim_outcomes={},
            dispute_round_number=1,
            letter_count_for_scope=1,
            letter_bureaus_distinct=["experian"],
            unresolved_disputed_ids=[],
        ),
    )
    neg_base = _by_id(evaluate_strategy_patterns(base))["pat_standard_negative_pool"]
    neg_letters = _by_id(evaluate_strategy_patterns(with_letters))["pat_standard_negative_pool"]
    assert neg_base.matched
    assert not neg_letters.matched
    assert neg_letters.exclusion_hits


def test_documentation_rich_vs_thin_changes_outcome():
    rich = _ci(
        case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1},
        documentation=DocumentationStateSummary(
            has_government_id=True,
            has_address_proof=True,
            has_signature=True,
            sufficiency="rich",
            missing_doc_flags=[],
            evidence_richness="high",
        ),
    )
    thin = _ci(
        case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1},
        documentation=DocumentationStateSummary(
            has_government_id=False,
            has_address_proof=False,
            has_signature=False,
            sufficiency="thin",
            missing_doc_flags=["government_id"],
            evidence_richness="low",
        ),
    )
    rpat = _by_id(evaluate_strategy_patterns(rich))["pat_documentation_rich_standard"]
    tpat = _by_id(evaluate_strategy_patterns(thin))["pat_documentation_rich_standard"]
    assert rpat.matched
    assert not tpat.matched
    thin_guided = _by_id(evaluate_strategy_patterns(thin))["pat_documentation_thin_guided"]
    assert thin_guided.matched


def test_objective_unknown_does_not_break_matching():
    ci = _ci(
        goal_constraints=GoalConstraintState(
            stated_objective=None,
            objective_source="unknown",
            timing_sensitivity="unknown",
            readiness_blockers=[],
            next_dependencies=[],
        ),
        case_summary={"totalReviewClaims": 1},
    )
    facts = build_case_fact_snapshot(ci)
    assert facts.objective_source == "unknown"
    bundle = evaluate_strategy_patterns(ci)
    assert len(bundle.evaluations) == 8


def test_prior_dispute_caution_and_caution_flags():
    ci = _ci(
        action_history=ActionHistorySummary(
            cumulative_disputed_review_claim_ids=[],
            claim_outcomes={},
            dispute_round_number=0,
            letter_count_for_scope=1,
            letter_bureaus_distinct=["equifax"],
            unresolved_disputed_ids=[],
        ),
        case_summary={"totalReviewClaims": 1},
    )
    p = _by_id(evaluate_strategy_patterns(ci))["pat_prior_dispute_caution"]
    assert p.matched
    assert any("prior" in c or "escalat" in c for c in p.caution_flags)


def test_duplicate_pattern_any_logic_signal_only():
    ci = _ci(
        strategy_signals=[
            StrategySignalRecord(
                name="duplicate_tradeline",
                tier="hygiene",
                detail="d",
                confidence="medium",
            )
        ],
        case_summary={
            "candidateDisputeItemsEligibleNow": 1,
            "totalReviewClaims": 1,
            "contradictionCount": 0,
        },
        contradictions=[],
    )
    d = _by_id(evaluate_strategy_patterns(ci))["pat_duplicate_tradeline_challenge"]
    assert d.matched


def test_unknown_doc_downgrades_confidence_when_matched():
    facts = build_case_fact_snapshot(
        _ci(
            documentation=DocumentationStateSummary(
                has_government_id=False,
                has_address_proof=False,
                has_signature=False,
                sufficiency="unknown",
                missing_doc_flags=[],
                evidence_richness="low",
            ),
            case_summary={"totalReviewClaims": 1},
        )
    )
    assert _gate_match_confidence("medium", facts) == "low"
    assert _gate_match_confidence("high", facts) == "medium"


def test_multi_bureau_pattern_requires_coverage_and_groups():
    two_bureau = _ci(
        identity={"bureauCoverage": [{"bureau": "experian"}, {"bureau": "equifax"}]},
        case_summary={
            "multiBureauNormalizedGroups": 1,
            "candidateDisputeItemsEligibleNow": 1,
            "totalReviewClaims": 1,
        },
    )
    m = _by_id(evaluate_strategy_patterns(two_bureau))["pat_multi_bureau_coordination"]
    assert m.matched

    one_bureau = _ci(
        identity={"bureauCoverage": [{"bureau": "experian"}]},
        case_summary={
            "multiBureauNormalizedGroups": 1,
            "candidateDisputeItemsEligibleNow": 1,
            "totalReviewClaims": 1,
        },
    )
    m1 = _by_id(evaluate_strategy_patterns(one_bureau))["pat_multi_bureau_coordination"]
    assert not m1.matched


def test_identity_pattern_case_type():
    ci = _ci(case_summary={"caseTypeSummary": "identity_cleanup_priority"})
    p = _by_id(evaluate_strategy_patterns(ci))["pat_identity_forward_review"]
    assert p.matched


def test_unresolved_dispute_caution_on_negative_family():
    ci = _ci(
        case_summary={
            "candidateDisputeItemsEligibleNow": 1,
            "contradictionCount": 0,
            "totalReviewClaims": 1,
        },
        action_history=ActionHistorySummary(
            cumulative_disputed_review_claim_ids=["rc1"],
            claim_outcomes={},
            dispute_round_number=1,
            letter_count_for_scope=0,
            letter_bureaus_distinct=[],
            unresolved_disputed_ids=["rc1"],
        ),
    )
    neg = _by_id(evaluate_strategy_patterns(ci))["pat_standard_negative_pool"]
    assert neg.matched
    assert any("unresolved" in c for c in neg.caution_flags)
