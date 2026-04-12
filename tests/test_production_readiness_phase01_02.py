"""
Production readiness — Phase 1 (execution runtime) & Phase 2 (outcome logging).

Maps to implemented modules:
- services.execution_progress.engine
- services.execution_guidance (bundles)
"""

from __future__ import annotations

import copy
import json

import pytest

from services.case_intelligence.models import (
    ActionHistorySummary,
    CanonicalCaseIntelligenceV1,
    DocumentationStateSummary,
    GoalConstraintState,
)
from services.execution_guidance import build_execution_guidance_bundle
from services.execution_guidance.registry_spa_v1 import BLK_BUREAU_MAIL, BLK_CRED_VAL
from services.execution_progress import OutcomeSubmission, apply_outcome_submission, create_initial_state
from services.execution_progress.models import ExecutionProgressState, OutcomeRecord
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


def _spa_bundle():
    ci = _ci_rich()
    pb = evaluate_strategy_patterns(ci)
    paths = generate_strategy_paths(ci, pb)
    sc = score_strategy_paths(ci, pb, paths)
    return build_execution_guidance_bundle(
        ci, pb, paths, sc, primary_path_id="path_standard_negative_first_pass"
    )


class TestPhase01ExecutionRuntime:
    """Phase 1 — deterministic execution (no workflow DB)."""

    def test_identical_inputs_identical_initial_execution_state(self):
        eg = _spa_bundle()
        a = create_initial_state(eg, "run-fixed-id", workflow_id="wf-pr-01")
        b = create_initial_state(eg, "run-fixed-id", workflow_id="wf-pr-01")
        assert a.to_dict() == b.to_dict()

    def test_failed_step_recovery_double_complete_rejected_deterministically(self):
        """Duplicate completion does not append a second outcome or advance state."""
        eg = _spa_bundle()
        st = create_initial_state(eg, "r1")
        first = apply_outcome_submission(
            eg, st, OutcomeSubmission(block_id=BLK_BUREAU_MAIL, outcome_key="complete")
        )
        assert first.accepted
        dup = apply_outcome_submission(
            eg, st, OutcomeSubmission(block_id=BLK_BUREAU_MAIL, outcome_key="complete")
        )
        assert not dup.accepted
        assert any("already_completed" in e for e in dup.validation_errors)
        completed_once = sum(
            1
            for h in st.outcome_history
            if h.block_id == BLK_BUREAU_MAIL and h.outcome_key == "complete"
        )
        assert completed_once == 1

    def test_progression_path_deterministic_through_parallel_complete(self):
        eg = _spa_bundle()
        st = create_initial_state(eg, "r1")
        r1 = apply_outcome_submission(
            eg, st, OutcomeSubmission(block_id=BLK_BUREAU_MAIL, outcome_key="complete")
        )
        r2 = apply_outcome_submission(
            eg, st, OutcomeSubmission(block_id=BLK_CRED_VAL, outcome_key="complete")
        )
        assert r1.accepted and r2.accepted
        again = create_initial_state(eg, "r2")
        r1b = apply_outcome_submission(
            eg, again, OutcomeSubmission(block_id=BLK_BUREAU_MAIL, outcome_key="complete")
        )
        r2b = apply_outcome_submission(
            eg, again, OutcomeSubmission(block_id=BLK_CRED_VAL, outcome_key="complete")
        )
        assert r1b.accepted and r2b.accepted
        assert r2.state.activated_block_ids == r2b.state.activated_block_ids
        assert st.to_dict()["completedBlockIds"] == again.to_dict()["completedBlockIds"]


class TestPhase02OutcomeLogging:
    """Phase 2 — structured outcomes / reconstruction."""

    def test_outcome_record_roundtrip_preserves_structured_fields(self):
        rec = OutcomeRecord(
            block_id="blk_x",
            outcome_key="complete",
            source="user_reported",
            notes="operator note",
            matched_signal_target_ids=["s1"],
            guidance_schema_version="execution_guidance.v1",
            playbook_id="p",
            playbook_version="1.0.0",
            recorded_at="2026-01-01T00:00:00Z",
            external_flags_snapshot={"flag_a": True},
        )
        st = ExecutionProgressState(
            run_id="r1",
            workflow_id="wf1",
            guidance_schema_version="execution_guidance.v1",
            playbook_id="p",
            playbook_version="1.0.0",
            primary_path_id="path",
            completed_block_ids=[],
            completed_outcomes={},
            activated_block_ids=[],
            external_flags={},
            outcome_history=[rec],
            execution_notes=[],
            blocked_reason=None,
        )
        d = st.to_dict()
        back = ExecutionProgressState.from_dict(d)
        assert len(back.outcome_history) == 1
        h0 = back.outcome_history[0]
        assert h0.block_id == rec.block_id
        assert h0.outcome_key == rec.outcome_key
        assert h0.source == rec.source
        assert h0.external_flags_snapshot == rec.external_flags_snapshot

    def test_edge_outcome_keys_json_serializable_without_loss(self):
        eg = _spa_bundle()
        st = create_initial_state(eg, "r-edge")
        apply_outcome_submission(
            eg,
            st,
            OutcomeSubmission(
                block_id=BLK_BUREAU_MAIL,
                outcome_key="complete",
                notes="",
                external_flags={},
            ),
        )
        payload = json.loads(json.dumps(st.to_dict()))
        assert payload["runId"] == "r-edge"
        assert isinstance(payload["outcomeHistory"], list)

    def test_workflow_reconstruct_completed_blocks_from_state_dict(self):
        eg = _spa_bundle()
        st = create_initial_state(eg, "r1")
        apply_outcome_submission(eg, st, OutcomeSubmission(block_id=BLK_BUREAU_MAIL, outcome_key="complete"))
        frozen = copy.deepcopy(st.to_dict())
        restored = ExecutionProgressState.from_dict(frozen)
        assert BLK_BUREAU_MAIL in restored.completed_block_ids
        assert BLK_BUREAU_MAIL in restored.completed_outcomes
