"""
Code-defined pattern library v1. Operator / future JSON loader can mirror this structure.

Patterns reference only fields derivable from CanonicalCaseIntelligenceV1 (v1).
"""

from __future__ import annotations

from typing import Tuple

from .models import (
    ExclusionOperator,
    ExclusionSpec,
    RequirementOperator,
    RequirementSpec,
    StrategyPatternDefinition,
)

LIBRARY_VERSION = "strategy_patterns.v1"


def load_pattern_library_v1() -> Tuple[StrategyPatternDefinition, ...]:
    return (
        StrategyPatternDefinition(
            pattern_id="pat_inconsistency_led_challenge",
            pattern_name="Inconsistency-led challenge",
            pattern_family="contradiction",
            version="1.0.0",
            description=(
                "When grounded cross-bureau or duplicate-tradeline inconsistencies exist in case "
                "intelligence, favor review that leverages factual inconsistency (not legal advice)."
            ),
            applies_when=(
                RequirementSpec(
                    req_id="r1_any_inconsistency_signal",
                    op=RequirementOperator.HAS_ANY_CONTRADICTION_TYPE,
                    field="contradictions",
                    value=[
                        "cross_bureau_balance_mismatch",
                        "cross_bureau_status_inconsistency",
                        "duplicate_tradeline_with_negatives",
                    ],
                    description="At least one contradiction record from case intelligence",
                ),
            ),
            excludes_when=(
                ExclusionSpec(
                    ex_id="x_no_candidates",
                    op=ExclusionOperator.NO_CANDIDATE_DISPUTES,
                    value=None,
                    description="Cannot pursue dispute items if none are eligible in current rules",
                ),
            ),
            required_signals=("contradiction_record_present",),
            optional_signals=("leverage_cross_bureau_balance_delta", "leverage_status_inconsistency"),
            required_documentation_states=None,
            action_sequence_template=(
                "confirm_inconsistency_against_source_documents",
                "map_items_to_review_claims",
                "select_disputes_then_generate_letters",
            ),
            fallback_pattern_ids=("pat_documentation_thin_guided",),
            timing_class="standard",
            aggressiveness_class="elevated",
            confidence_class="medium",
            notes="Grounded only on contradiction objects emitted by case intelligence; verify manually.",
            active=True,
        ),
        StrategyPatternDefinition(
            pattern_id="pat_duplicate_tradeline_challenge",
            pattern_name="Duplicate reporting challenge",
            pattern_family="duplicate",
            version="1.0.0",
            description="Duplicate tradeline surface from review compression plus optional contradiction bundle.",
            applies_when=(
                RequirementSpec(
                    req_id="r1_dup_signal",
                    op=RequirementOperator.HAS_ANY_STRATEGY_SIGNAL,
                    field="strategySignals",
                    value=["duplicate_tradeline"],
                    description="Strategy signal name contains duplicate_tradeline",
                ),
                RequirementSpec(
                    req_id="r2_dup_contradiction",
                    op=RequirementOperator.HAS_ANY_CONTRADICTION_TYPE,
                    field="contradictions",
                    value=["duplicate_tradeline_with_negatives"],
                    description="Duplicate contradiction record from case intelligence",
                ),
            ),
            applies_logic="any",
            excludes_when=(
                ExclusionSpec(
                    ex_id="x_no_candidates",
                    op=ExclusionOperator.NO_CANDIDATE_DISPUTES,
                    value=None,
                    description="No eligible dispute candidates",
                ),
            ),
            required_signals=("duplicate_tradeline_review_surface",),
            optional_signals=("duplicate_tradeline_with_negatives",),
            required_documentation_states=None,
            action_sequence_template=(
                "verify_single_obligation_story",
                "align_duplicate_items_in_review",
                "dispute_selection_for_duplicates",
            ),
            fallback_pattern_ids=("pat_standard_negative_pool",),
            timing_class="standard",
            aggressiveness_class="standard",
            confidence_class="medium",
            notes="OR logic: strategy signal OR duplicate contradiction record.",
            active=True,
        ),
        StrategyPatternDefinition(
            pattern_id="pat_documentation_rich_standard",
            pattern_name="Documentation-rich standard path",
            pattern_family="documentation",
            version="1.0.0",
            description="Strong proof attachment posture supports standard dispute progression.",
            applies_when=(
                RequirementSpec(
                    req_id="r1_doc_rich",
                    op=RequirementOperator.DOCUMENTATION_IN,
                    field="documentation",
                    value=["rich"],
                    description="Proof summary sufficiency is rich",
                ),
                RequirementSpec(
                    req_id="r2_has_candidates",
                    op=RequirementOperator.MIN_INT,
                    field="candidateDisputeItemsEligibleNow",
                    value=1,
                    description="At least one eligible dispute candidate",
                ),
            ),
            excludes_when=(
                ExclusionSpec(
                    ex_id="x_doc_thin",
                    op=ExclusionOperator.DOCUMENTATION_IN,
                    value=["thin"],
                    description="Should not label as rich-path if classified thin",
                ),
            ),
            required_signals=("proof_rich",),
            optional_signals=(),
            required_documentation_states=("rich",),
            action_sequence_template=(
                "final_proof_check",
                "review_claim_confirmation",
                "dispute_selection",
                "letter_generation",
            ),
            fallback_pattern_ids=("pat_documentation_thin_guided",),
            timing_class="standard",
            aggressiveness_class="standard",
            confidence_class="high",
            notes="Operational readiness only — not legal sufficiency.",
            active=True,
        ),
        StrategyPatternDefinition(
            pattern_id="pat_documentation_thin_guided",
            pattern_name="Documentation-thin guided path",
            pattern_family="documentation",
            version="1.0.0",
            description="Thin or partial proof posture — prioritize gathering proof before aggressive rounds.",
            applies_when=(
                RequirementSpec(
                    req_id="r1_doc_thin_or_partial",
                    op=RequirementOperator.DOCUMENTATION_IN,
                    field="documentation",
                    value=["thin", "partial", "unknown"],
                    description="Sufficiency not rich",
                ),
                RequirementSpec(
                    req_id="r2_has_candidates_or_review",
                    op=RequirementOperator.MIN_INT,
                    field="totalReviewClaims",
                    value=1,
                    description="Some review surface exists",
                ),
            ),
            excludes_when=(),
            required_signals=("proof_partial_or_thin",),
            optional_signals=(),
            required_documentation_states=None,
            action_sequence_template=(
                "complete_proof_attachment",
                "reassess_eligibility",
                "narrow_dispute_round",
            ),
            fallback_pattern_ids=("pat_prior_dispute_caution",),
            timing_class="extended",
            aggressiveness_class="conservative",
            confidence_class="medium",
            notes="Unknown documentation treated cautiously as thin/partial for matching.",
            active=True,
        ),
        StrategyPatternDefinition(
            pattern_id="pat_multi_bureau_coordination",
            pattern_name="Multi-bureau coordination",
            pattern_family="cross_bureau",
            version="1.0.0",
            description="Multiple bureaus and cross-bureau normalized groups suggest coordinated review.",
            applies_when=(
                RequirementSpec(
                    req_id="r1_multi_group",
                    op=RequirementOperator.MIN_INT,
                    field="multiBureauNormalizedGroups",
                    value=1,
                    description="At least one multi-bureau normalized account group",
                ),
                RequirementSpec(
                    req_id="r2_bureau_coverage",
                    op=RequirementOperator.MIN_BUREAU_COVERAGE_COUNT,
                    field="bureauCoverage",
                    value=2,
                    description="At least two bureau coverage entries",
                ),
            ),
            excludes_when=(
                ExclusionSpec(
                    ex_id="x_no_candidates",
                    op=ExclusionOperator.NO_CANDIDATE_DISPUTES,
                    value=None,
                    description="No eligible candidates",
                ),
            ),
            required_signals=("cross_bureau_tradeline_footprint",),
            optional_signals=("leverage_cross_bureau_balance_delta",),
            required_documentation_states=None,
            action_sequence_template=(
                "per_bureau_item_map",
                "align_normalized_groups",
                "stagger_or_batch_disputes",
            ),
            fallback_pattern_ids=("pat_inconsistency_led_challenge",),
            timing_class="standard",
            aggressiveness_class="standard",
            confidence_class="medium",
            notes="Relies on heuristic grouping from case intelligence.",
            active=True,
        ),
        StrategyPatternDefinition(
            pattern_id="pat_identity_forward_review",
            pattern_name="Identity-forward review",
            pattern_family="identity",
            version="1.0.0",
            description="Case classification emphasizes identity cleanup before heavy tradeline disputes.",
            applies_when=(
                RequirementSpec(
                    req_id="r1_case_type_identity",
                    op=RequirementOperator.CASE_TYPE_SUMMARY_CONTAINS_ANY,
                    field="caseTypeSummary",
                    value=["identity"],
                    description="caseTypeSummary contains identity",
                ),
            ),
            excludes_when=(),
            required_signals=("identity_case_classification",),
            optional_signals=(),
            required_documentation_states=None,
            action_sequence_template=(
                "resolve_identity_review_claims",
                "recompress_if_reports_change",
                "return_to_tradeline_strategy",
            ),
            fallback_pattern_ids=("pat_standard_negative_pool",),
            timing_class="extended",
            aggressiveness_class="conservative",
            confidence_class="low",
            notes="Depends on case_type_summary string from intelligence composer.",
            active=True,
        ),
        StrategyPatternDefinition(
            pattern_id="pat_standard_negative_pool",
            pattern_name="Standard negative-item pool",
            pattern_family="negative_tradeline",
            version="1.0.0",
            description="Eligible dispute candidates without contradiction-led leverage signals.",
            applies_when=(
                RequirementSpec(
                    req_id="r1_candidates",
                    op=RequirementOperator.MIN_INT,
                    field="candidateDisputeItemsEligibleNow",
                    value=1,
                    description="Has eligible candidates",
                ),
                RequirementSpec(
                    req_id="r2_no_contradictions",
                    op=RequirementOperator.MAX_INT,
                    field="contradictionCount",
                    value=0,
                    description="No contradiction records",
                ),
            ),
            excludes_when=(
                ExclusionSpec(
                    ex_id="x_prior_letters",
                    op=ExclusionOperator.MIN_PRIOR_LETTERS,
                    value=1,
                    description="Exclude pure first-round-negative label when letters already sent",
                ),
            ),
            required_signals=("eligible_dispute_pool",),
            optional_signals=("high_severity_review_items",),
            required_documentation_states=None,
            action_sequence_template=(
                "consumer_review_confirmation",
                "dispute_selection",
                "letter_generation",
            ),
            fallback_pattern_ids=("pat_prior_dispute_caution",),
            timing_class="standard",
            aggressiveness_class="standard",
            confidence_class="medium",
            notes="Excluded when prior letters exist — use caution pattern instead.",
            active=True,
        ),
        StrategyPatternDefinition(
            pattern_id="pat_prior_dispute_caution",
            pattern_name="Prior dispute / letter caution",
            pattern_family="action_history",
            version="1.0.0",
            description="Prior letters or disputed IDs require outcome awareness before new rounds.",
            applies_when=(
                RequirementSpec(
                    req_id="r1_letters",
                    op=RequirementOperator.MIN_INT,
                    field="letterCountForScope",
                    value=1,
                    description="At least one letter on scope reports",
                ),
                RequirementSpec(
                    req_id="r2_cumulative_disputed",
                    op=RequirementOperator.MIN_INT,
                    field="cumulativeDisputedCount",
                    value=1,
                    description="At least one review claim id ever selected for dispute",
                ),
            ),
            applies_logic="any",
            excludes_when=(),
            required_signals=("prior_letter_activity",),
            optional_signals=("unresolved_disputes",),
            required_documentation_states=None,
            action_sequence_template=(
                "review_claim_outcomes",
                "adjust_round_composition",
                "avoid_duplicate_challenges",
            ),
            fallback_pattern_ids=(),
            timing_class="unknown",
            aggressiveness_class="conservative",
            confidence_class="high",
            notes="Informational caution; does not block other patterns.",
            active=True,
        ),
    )
