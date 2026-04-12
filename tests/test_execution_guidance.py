"""
Execution guidance — SPA vs docs-thin playbooks, path-driven routing, determinism.
"""

from __future__ import annotations

import json

from services.case_intelligence.models import (
    ActionHistorySummary,
    CanonicalCaseIntelligenceV1,
    DocumentationStateSummary,
    GoalConstraintState,
)
from services.execution_guidance import (
    PATH_DOCS_THIN,
    build_execution_guidance_bundle,
    resolve_playbook_id,
)
from services.execution_guidance.registry_docs_thin_v1 import PLAYBOOK_ID as DOCS_PLAYBOOK
from services.execution_guidance.registry_spa_v1 import (
    BLK_PROBE,
    GROUP_DAY1,
    PLAYBOOK_ID as SPA_PLAYBOOK,
    build_spa_blocks,
)
from services.strategy_paths import generate_strategy_paths
from services.strategy_patterns import evaluate_strategy_patterns
from services.strategy_scoring import score_strategy_paths


def _ci_rich():
    return CanonicalCaseIntelligenceV1(
        schema_version="canonical_case_intelligence.v1",
        identity={"bureauCoverage": [{"bureau": "experian"}, {"bureau": "equifax"}]},
        case_summary={
            "contradictionCount": 0,
            "multiBureauNormalizedGroups": 0,
            "candidateDisputeItemsEligibleNow": 2,
            "totalReviewClaims": 2,
            "caseTypeSummary": "",
        },
        account_groups=[],
        strategy_signals=[],
        contradictions=[],
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
            letter_count_for_scope=0,
            letter_bureaus_distinct=[],
            unresolved_disputed_ids=[],
        ),
        goal_constraints=GoalConstraintState(
            stated_objective=None,
            objective_source="unknown",
            timing_sensitivity="unknown",
            readiness_blockers=[],
            next_dependencies=[],
        ),
        confidence_notes=[],
        explainability=[],
    )


def _ci_thin():
    return CanonicalCaseIntelligenceV1(
        schema_version="canonical_case_intelligence.v1",
        identity={"bureauCoverage": []},
        case_summary={
            "contradictionCount": 0,
            "multiBureauNormalizedGroups": 0,
            "candidateDisputeItemsEligibleNow": 1,
            "totalReviewClaims": 1,
            "caseTypeSummary": "",
        },
        account_groups=[],
        strategy_signals=[],
        contradictions=[],
        documentation=DocumentationStateSummary(
            has_government_id=False,
            has_address_proof=False,
            has_signature=False,
            sufficiency="thin",
            missing_doc_flags=["government_id"],
            evidence_richness="low",
        ),
        action_history=ActionHistorySummary(
            cumulative_disputed_review_claim_ids=[],
            claim_outcomes={},
            dispute_round_number=0,
            letter_count_for_scope=0,
            letter_bureaus_distinct=[],
            unresolved_disputed_ids=[],
        ),
        goal_constraints=GoalConstraintState(
            stated_objective=None,
            objective_source="unknown",
            timing_sensitivity="unknown",
            readiness_blockers=[],
            next_dependencies=[],
        ),
        confidence_notes=[],
        explainability=[],
    )


def test_resolve_playbook_docs_thin_vs_spa_path():
    assert resolve_playbook_id(PATH_DOCS_THIN) == DOCS_PLAYBOOK
    assert resolve_playbook_id("path_standard_negative_first_pass") == SPA_PLAYBOOK
    assert resolve_playbook_id("path_identity_ownership_first") == "path_template_synthesis_v1"


def test_docs_thin_primary_gets_docs_playbook_not_spa():
    ci = _ci_thin()
    pb = evaluate_strategy_patterns(ci)
    paths = generate_strategy_paths(ci, pb)
    scored = score_strategy_paths(ci, pb, paths)
    eg = build_execution_guidance_bundle(ci, pb, paths, scored, primary_path_id=PATH_DOCS_THIN)
    assert eg.playbook_id == DOCS_PLAYBOOK
    assert any(b.block_id.startswith("dthin_") for b in eg.blocks)
    assert not any(b.block_id.startswith("spa_p") for b in eg.blocks)
    assert eg.parallel_groups == []


def test_spa_playbook_for_standard_negative_path():
    ci = _ci_rich()
    pb = evaluate_strategy_patterns(ci)
    paths = generate_strategy_paths(ci, pb)
    scored = score_strategy_paths(ci, pb, paths)
    # Force standard path to prove SPA mapping (path-driven, not default primary)
    eg = build_execution_guidance_bundle(
        ci, pb, paths, scored, primary_path_id="path_standard_negative_first_pass"
    )
    assert eg.playbook_id == SPA_PLAYBOOK
    assert len(eg.parallel_groups) == 1
    assert eg.parallel_groups[0].group_id == GROUP_DAY1
    ids = {b.block_id for b in eg.blocks}
    assert BLK_PROBE in ids
    probe = next(b for b in eg.blocks if b.block_id == BLK_PROBE)
    assert probe.channel == "phone"
    assert probe.signal_capture_targets
    assert "verification_failure_strong" in probe.next_by_outcome
    boundary = next(b for b in eg.blocks if b.block_type == "verification_boundary_exit")
    boundary_text = (boundary.instructions + " " + " ".join(boundary.prohibited_actions)).lower()
    assert "unnecessary" in boundary_text and "reconstruct" in boundary_text


def test_spa_probe_branch_skips_boundary_on_ok_outcome():
    blocks, _, _, _ = build_spa_blocks("path_standard_negative_first_pass")
    probe = next(b for b in blocks if b.block_id == BLK_PROBE)
    assert "verification_ok_or_inconclusive" in probe.next_by_outcome
    ok_next = probe.next_by_outcome["verification_ok_or_inconclusive"]
    assert ok_next and ok_next[0].startswith("spa_p4_")


def test_deterministic_json_bundle():
    ci = _ci_rich()
    pb = evaluate_strategy_patterns(ci)
    paths = generate_strategy_paths(ci, pb)
    scored = score_strategy_paths(ci, pb, paths)
    a = build_execution_guidance_bundle(
        ci, pb, paths, scored, primary_path_id="path_standard_negative_first_pass"
    ).to_dict()
    b = build_execution_guidance_bundle(
        ci, pb, paths, scored, primary_path_id="path_standard_negative_first_pass"
    ).to_dict()
    assert a == b
    json.dumps(a)


def test_no_primary_empty_bundle():
    ci = CanonicalCaseIntelligenceV1(
        schema_version="canonical_case_intelligence.v1",
        identity={"bureauCoverage": []},
        case_summary={
            "contradictionCount": 0,
            "multiBureauNormalizedGroups": 0,
            "candidateDisputeItemsEligibleNow": 0,
            "totalReviewClaims": 0,
            "caseTypeSummary": "",
        },
        account_groups=[],
        strategy_signals=[],
        contradictions=[],
        documentation=DocumentationStateSummary(
            has_government_id=False,
            has_address_proof=False,
            has_signature=False,
            sufficiency="unknown",
            missing_doc_flags=[],
            evidence_richness="low",
        ),
        action_history=ActionHistorySummary(
            cumulative_disputed_review_claim_ids=[],
            claim_outcomes={},
            dispute_round_number=0,
            letter_count_for_scope=0,
            letter_bureaus_distinct=[],
            unresolved_disputed_ids=[],
        ),
        goal_constraints=GoalConstraintState(
            stated_objective=None,
            objective_source="unknown",
            timing_sensitivity="unknown",
            readiness_blockers=[],
            next_dependencies=[],
        ),
        confidence_notes=[],
        explainability=[],
    )
    pb = evaluate_strategy_patterns(ci)
    paths = generate_strategy_paths(ci, pb)
    scored = score_strategy_paths(ci, pb, paths)
    assert scored.recommended_primary_path_id is None
    eg = build_execution_guidance_bundle(ci, pb, paths, scored)
    assert eg.blocks == []
    assert eg.primary_path_id is None
