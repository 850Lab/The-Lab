"""
Strategy scoring — dimensions, objectives, ranking, determinism.
"""

from __future__ import annotations

import json

from services.case_intelligence.models import (
    ActionHistorySummary,
    CanonicalCaseIntelligenceV1,
    DocumentationStateSummary,
    GoalConstraintState,
)
from services.strategy_paths.models import MultiPathStrategyBundle, StrategyGeneratedPath
from services.strategy_paths import generate_strategy_paths
from services.strategy_patterns import evaluate_strategy_patterns
from services.strategy_scoring import score_strategy_paths


def _ci(
    *,
    case_summary: dict | None = None,
    documentation: DocumentationStateSummary | None = None,
    action_history: ActionHistorySummary | None = None,
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
        identity={"bureauCoverage": []},
        case_summary=base_summary,
        account_groups=[],
        strategy_signals=[],
        contradictions=[],
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


def _path(**overrides) -> StrategyGeneratedPath:
    d = dict(
        path_id="path_default",
        path_name="Default",
        path_family="negative_tradeline",
        version="1.0.0",
        path_objective="test",
        source_pattern_ids=(),
        path_summary="",
        why_it_applies="",
        prerequisites=[],
        blockers=[],
        timing_class="standard",
        effort_class="medium",
        risk_class="medium",
        aggressiveness_class="standard",
        action_sequence_template=(),
        fallback_path_ids=(),
        caution_flags=[],
        readiness_state="ready_now",
        explanation="",
        suppressed=False,
        suppression_reason="",
    )
    d.update(overrides)
    return StrategyGeneratedPath(**d)


def _synthetic_bundle(paths: list[StrategyGeneratedPath]) -> MultiPathStrategyBundle:
    active = [p.path_id for p in paths if not p.suppressed and p.readiness_state != "blocked"]
    blocked = [p.path_id for p in paths if p.readiness_state == "blocked" and not p.suppressed]
    supp = [p.path_id for p in paths if p.suppressed]
    return MultiPathStrategyBundle(
        schema_version="multi_path_strategy.v1",
        case_intelligence_schema="canonical_case_intelligence.v1",
        pattern_evaluation_schema="strategy_pattern_evaluation.v1",
        pattern_library_version="strategy_patterns.v1",
        generation_version="strategy_paths.v1",
        all_paths=paths,
        active_candidate_path_ids=sorted(active),
        blocked_path_ids=sorted(blocked),
        suppressed_path_ids=sorted(supp),
        generation_notes=[],
    )


def test_faster_ready_outranks_slower_cautious_for_fastest_credible():
    ci = _ci(
        case_summary={"candidateDisputeItemsEligibleNow": 2, "totalReviewClaims": 2},
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
    fast = _path(
        path_id="path_fast_track",
        path_name="Fast",
        timing_class="expedited",
        readiness_state="ready_now",
        effort_class="low",
        risk_class="low",
    )
    slow = _path(
        path_id="path_slow_safe",
        path_name="Slow",
        timing_class="extended",
        readiness_state="conditional",
        effort_class="high",
        risk_class="high",
    )
    bundle = _synthetic_bundle([slow, fast])
    out = score_strategy_paths(ci, pb, bundle, objective="fastest_credible_result")
    by_id = {s.path_id: s for s in out.scored_paths}
    assert by_id["path_fast_track"].total_score > by_id["path_slow_safe"].total_score
    assert out.recommended_primary_path_id == "path_fast_track"


def test_blocked_paths_not_primary_and_rank_below_active():
    ci = _ci(case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1})
    pb = evaluate_strategy_patterns(ci)
    ok = _path(path_id="path_ok", readiness_state="ready_now", blockers=[])
    bad = _path(path_id="path_blocked", readiness_state="blocked", blockers=["hard_block"])
    out = score_strategy_paths(ci, pb, _synthetic_bundle([bad, ok]))
    assert out.recommended_primary_path_id == "path_ok"
    assert "path_blocked" in out.ranked_blocked_path_ids
    assert out.ranked_active_scorable_path_ids[0] == "path_ok"


def test_suppressed_path_not_primary():
    ci = _ci(case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1})
    pb = evaluate_strategy_patterns(ci)
    good = _path(path_id="path_good", suppressed=False)
    bad = _path(path_id="path_suppressed", suppressed=True, suppression_reason="policy")
    out = score_strategy_paths(ci, pb, _synthetic_bundle([bad, good]))
    assert out.recommended_primary_path_id == "path_good"
    assert "path_suppressed" in out.ranked_suppressed_path_ids


def test_docs_thin_lowers_evidence_vs_rich_same_path_profile():
    ci_rich = _ci(
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
    ci_thin = _ci(
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
    pb_r = evaluate_strategy_patterns(ci_rich)
    pb_t = evaluate_strategy_patterns(ci_thin)
    p = _path(path_id="path_doc_shape", path_family="documentation", path_name="Doc path")
    out_r = score_strategy_paths(ci_rich, pb_r, _synthetic_bundle([p]))
    out_t = score_strategy_paths(ci_thin, pb_t, _synthetic_bundle([p]))
    dr = next(s for s in out_r.scored_paths if s.path_id == "path_doc_shape").dimension_scores.evidence_strength_score
    dt = next(s for s in out_t.scored_paths if s.path_id == "path_doc_shape").dimension_scores.evidence_strength_score
    assert dr > dt


def test_prior_action_history_reduces_prior_action_favor_dimension():
    ci_clean = _ci(case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1})
    ci_busy = _ci(
        case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1},
        action_history=ActionHistorySummary(
            cumulative_disputed_review_claim_ids=["x"],
            claim_outcomes={},
            dispute_round_number=2,
            letter_count_for_scope=2,
            letter_bureaus_distinct=["a", "b"],
            unresolved_disputed_ids=["u1"],
        ),
    )
    pb_c = evaluate_strategy_patterns(ci_clean)
    pb_b = evaluate_strategy_patterns(ci_busy)
    p = _path(path_id="path_p")
    s_clean = score_strategy_paths(ci_clean, pb_c, _synthetic_bundle([p]))
    s_busy = score_strategy_paths(ci_busy, pb_b, _synthetic_bundle([p]))
    d_clean = s_clean.scored_paths[0].dimension_scores.prior_action_favor_score
    d_busy = s_busy.scored_paths[0].dimension_scores.prior_action_favor_score
    assert d_clean > d_busy


def test_tie_break_deterministic_by_path_id():
    ci = _ci(case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1})
    pb = evaluate_strategy_patterns(ci)
    a = _path(path_id="path_m_tie")
    z = _path(path_id="path_z_tie")
    out = score_strategy_paths(ci, pb, _synthetic_bundle([z, a]))
    ids = [s.path_id for s in out.scored_paths]
    assert ids == sorted(ids)
    assert out.recommended_primary_path_id == "path_m_tie"


def test_low_signal_no_primary_and_machine_readable_bundle():
    ci = _ci()
    pb = evaluate_strategy_patterns(ci)
    paths = generate_strategy_paths(ci, pb)
    out = score_strategy_paths(ci, pb, paths, objective="fastest_credible_result")
    assert out.recommended_primary_path_id is None
    assert "no_active_scorable_path_primary_left_empty" in out.scoring_notes
    json.dumps(out.to_dict())


def test_integration_identity_suppressed_standard_not_primary():
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
    )
    pb = evaluate_strategy_patterns(ci)
    paths = generate_strategy_paths(ci, pb)
    out = score_strategy_paths(ci, pb, paths)
    assert out.recommended_primary_path_id != "path_standard_negative_first_pass"
    std = next(p for p in out.scored_paths if p.path_id == "path_standard_negative_first_pass")
    assert std.ranking_bucket == "suppressed"


def test_score_breakdown_not_opaque_single_number():
    ci = _ci(case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1})
    pb = evaluate_strategy_patterns(ci)
    out = score_strategy_paths(ci, pb, _synthetic_bundle([_path(path_id="path_x")]))
    sp = out.scored_paths[0]
    d = sp.dimension_scores.to_dict()
    assert len(d) >= 8
    assert sp.weighted_contributions
    assert sum(sp.weighted_contributions.values()) > 0


def test_unknown_objective_defaults_and_notes():
    ci = _ci(case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1})
    pb = evaluate_strategy_patterns(ci)
    out = score_strategy_paths(ci, pb, _synthetic_bundle([_path(path_id="path_q")]), objective="not_a_real_objective_yet")
    assert out.objective_id == "fastest_credible_result"
    assert any("unknown_objective" in n for n in out.scoring_notes)


def test_deterministic_bundle_equality():
    ci = _ci(case_summary={"candidateDisputeItemsEligibleNow": 1, "totalReviewClaims": 1})
    pb = evaluate_strategy_patterns(ci)
    b = _synthetic_bundle([_path(path_id="path_a"), _path(path_id="path_b")])
    x = score_strategy_paths(ci, pb, b).to_dict()
    y = score_strategy_paths(ci, pb, b).to_dict()
    assert x == y
