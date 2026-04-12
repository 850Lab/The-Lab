"""
Multi-Path Strategy Generator — composition, blockers, stability (no DB).
"""

from __future__ import annotations

import json
from unittest.mock import patch

from services.case_intelligence.models import (
    ActionHistorySummary,
    CanonicalCaseIntelligenceV1,
    ContradictionRecord,
    DocumentationStateSummary,
    GoalConstraintState,
    StrategySignalRecord,
)
from services.strategy_paths import generate_strategy_paths
from services.strategy_paths.generator import PATH_CROSS, PATH_STANDARD
from services.strategy_patterns import evaluate_strategy_patterns


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


def _paths_by_id(bundle):
    return {p.path_id: p for p in bundle.all_paths}


def test_compose_cross_bureau_inconsistency_two_source_patterns():
    ci = _ci(
        identity={"bureauCoverage": [{"bureau": "experian"}, {"bureau": "equifax"}]},
        contradictions=[
            ContradictionRecord(
                signal_type="cross_bureau_balance_mismatch",
                description="d",
                grounded_in="t",
            )
        ],
        case_summary={
            "contradictionCount": 1,
            "multiBureauNormalizedGroups": 1,
            "candidateDisputeItemsEligibleNow": 2,
            "totalReviewClaims": 2,
        },
    )
    pb = evaluate_strategy_patterns(ci)
    out = generate_strategy_paths(ci, pb)
    cross = _paths_by_id(out)[PATH_CROSS]
    assert len(cross.source_pattern_ids) == 2
    assert "composed" in cross.path_family or cross.path_family == "composed_contradiction"
    assert "explicit composition" in cross.explanation.lower()


def test_docs_rich_vs_thin_changes_path_shape():
    rich_ci = _ci(
        case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1, "contradictionCount": 0},
        documentation=DocumentationStateSummary(
            has_government_id=True,
            has_address_proof=True,
            has_signature=True,
            sufficiency="rich",
            missing_doc_flags=[],
            evidence_richness="high",
        ),
    )
    thin_ci = _ci(
        case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1, "contradictionCount": 0},
        documentation=DocumentationStateSummary(
            has_government_id=False,
            has_address_proof=False,
            has_signature=False,
            sufficiency="thin",
            missing_doc_flags=["government_id"],
            evidence_richness="low",
        ),
    )
    br = generate_strategy_paths(rich_ci, evaluate_strategy_patterns(rich_ci))
    bt = generate_strategy_paths(thin_ci, evaluate_strategy_patterns(thin_ci))
    rich_ids = {p.path_id for p in br.all_paths}
    thin_ids = {p.path_id for p in bt.all_paths}
    assert "path_docs_supported_standard" in rich_ids
    assert "path_docs_thin_conservative_first" in thin_ids
    assert "path_docs_thin_conservative_first" not in rich_ids
    assert "path_docs_supported_standard" not in thin_ids


def test_identity_suppresses_standard_tradeline_path():
    ci = _ci(
        case_summary={
            "caseTypeSummary": "identity_cleanup_priority",
            "candidateDisputeItemsEligibleNow": 2,
            "totalReviewClaims": 2,
            "contradictionCount": 0,
        },
    )
    pb = evaluate_strategy_patterns(ci)
    out = generate_strategy_paths(ci, pb)
    std = _paths_by_id(out)[PATH_STANDARD]
    assert std.suppressed
    assert "identity" in std.suppression_reason


def test_prior_history_makes_challenge_conditional_not_blocked_when_candidates_exist():
    ci = _ci(
        case_summary={
            "candidateDisputeItemsEligibleNow": 2,
            "totalReviewClaims": 2,
            "contradictionCount": 0,
        },
        action_history=ActionHistorySummary(
            cumulative_disputed_review_claim_ids=[],
            claim_outcomes={},
            dispute_round_number=1,
            letter_count_for_scope=1,
            letter_bureaus_distinct=["experian"],
            unresolved_disputed_ids=[],
        ),
        documentation=DocumentationStateSummary(
            has_government_id=True,
            has_address_proof=True,
            has_signature=True,
            sufficiency="rich",
            missing_doc_flags=[],
            evidence_richness="high",
        ),
    )
    pb = evaluate_strategy_patterns(ci)
    out = generate_strategy_paths(ci, pb)
    doc_path = _paths_by_id(out)["path_docs_supported_standard"]
    assert doc_path.readiness_state == "conditional"
    assert any("prior" in b.lower() for b in doc_path.blockers)


def test_low_signal_emits_single_structural_path_not_variety():
    ci = _ci()
    pb = evaluate_strategy_patterns(ci)
    out = generate_strategy_paths(ci, pb)
    assert len(out.all_paths) == 1
    assert out.all_paths[0].path_id == "path_await_case_signals"
    assert out.all_paths[0].readiness_state == "blocked"
    families = {p.path_family for p in out.all_paths}
    assert len(families) == 1


def test_multiple_paths_meaningfully_distinct_families():
    ci = _ci(
        identity={"bureauCoverage": [{"bureau": "experian"}, {"bureau": "equifax"}]},
        contradictions=[
            ContradictionRecord(
                signal_type="cross_bureau_balance_mismatch",
                description="d",
                grounded_in="t",
            )
        ],
        strategy_signals=[
            StrategySignalRecord(
                name="duplicate_tradeline",
                tier="hygiene",
                detail="d",
                confidence="medium",
            )
        ],
        case_summary={
            "contradictionCount": 1,
            "multiBureauNormalizedGroups": 1,
            "candidateDisputeItemsEligibleNow": 2,
            "totalReviewClaims": 2,
        },
        documentation=DocumentationStateSummary(
            has_government_id=True,
            has_address_proof=True,
            has_signature=True,
            sufficiency="rich",
            missing_doc_flags=[],
            evidence_richness="high",
        ),
        action_history=ActionHistorySummary(
            cumulative_disputed_review_claim_ids=[],
            claim_outcomes={},
            dispute_round_number=0,
            letter_count_for_scope=1,
            letter_bureaus_distinct=["equifax"],
            unresolved_disputed_ids=[],
        ),
    )
    pb = evaluate_strategy_patterns(ci)
    out = generate_strategy_paths(ci, pb)
    families = {p.path_family for p in out.all_paths if not p.suppressed}
    assert len(families) >= 2
    assert any(len(p.source_pattern_ids) > 1 for p in out.all_paths)


def test_stable_ordering_and_json_roundtrip():
    ci = _ci(
        case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1, "contradictionCount": 0},
        documentation=DocumentationStateSummary(
            has_government_id=True,
            has_address_proof=True,
            has_signature=True,
            sufficiency="rich",
            missing_doc_flags=[],
            evidence_richness="high",
        ),
    )
    pb = evaluate_strategy_patterns(ci)
    a = generate_strategy_paths(ci, pb).to_dict()
    b = generate_strategy_paths(ci, pb).to_dict()
    assert a == b
    ids = [p["pathId"] for p in a["allPaths"]]
    assert ids == sorted(ids)
    assert a["activeCandidatePathIds"] == sorted(a["activeCandidatePathIds"])
    json.dumps(a)


def test_cap_suppresses_lower_priority_paths():
    ci = _ci(
        case_summary={
            "caseTypeSummary": "identity_cleanup_priority",
            "candidateDisputeItemsEligibleNow": 2,
            "totalReviewClaims": 2,
            "contradictionCount": 0,
        },
        documentation=DocumentationStateSummary(
            has_government_id=True,
            has_address_proof=True,
            has_signature=True,
            sufficiency="rich",
            missing_doc_flags=[],
            evidence_richness="high",
        ),
        action_history=ActionHistorySummary(
            cumulative_disputed_review_claim_ids=[],
            claim_outcomes={},
            dispute_round_number=1,
            letter_count_for_scope=1,
            letter_bureaus_distinct=["experian"],
            unresolved_disputed_ids=[],
        ),
    )
    pb = evaluate_strategy_patterns(ci)
    with patch("services.strategy_paths.generator.MAX_ACTIVE_PATHS", 2):
        out = generate_strategy_paths(ci, pb)
    nonsup = [p for p in out.all_paths if not p.suppressed]
    assert len(nonsup) <= 2
    assert any(p.suppression_reason == "lower_priority_within_max_paths" for p in out.all_paths)


def test_identity_path_blocked_without_review_surface():
    ci = _ci(
        case_summary={
            "caseTypeSummary": "identity_cleanup_priority",
            "totalReviewClaims": 0,
            "candidateDisputeItemsEligibleNow": 0,
        },
    )
    pb = evaluate_strategy_patterns(ci)
    out = generate_strategy_paths(ci, pb)
    ident = _paths_by_id(out)["path_identity_ownership_first"]
    assert ident.readiness_state == "blocked"
    assert any("no_review_claim" in b for b in ident.blockers)


def test_readiness_blockers_from_goals_surface_on_paths():
    ci = _ci(
        case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1, "contradictionCount": 0},
        documentation=DocumentationStateSummary(
            has_government_id=True,
            has_address_proof=True,
            has_signature=True,
            sufficiency="rich",
            missing_doc_flags=[],
            evidence_richness="high",
        ),
        goal_constraints=GoalConstraintState(
            stated_objective=None,
            objective_source="unknown",
            timing_sensitivity="unknown",
            readiness_blockers=["missing_payment_method"],
            next_dependencies=[],
        ),
    )
    pb = evaluate_strategy_patterns(ci)
    out = generate_strategy_paths(ci, pb)
    p = _paths_by_id(out)["path_docs_supported_standard"]
    assert any("goal_readiness" in b for b in p.blockers)
