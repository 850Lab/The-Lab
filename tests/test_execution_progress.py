"""
Execution progress — outcomes, triggers, mail receipt flags, version gate.
"""

from __future__ import annotations

import copy

from services.case_intelligence.models import (
    ActionHistorySummary,
    CanonicalCaseIntelligenceV1,
    DocumentationStateSummary,
    GoalConstraintState,
)
from services.execution_guidance import build_execution_guidance_bundle
from services.execution_guidance.registry_spa_v1 import (
    BLK_BUREAU_MAIL,
    BLK_BOUNDARY,
    BLK_CRED_VAL,
    BLK_PROBE,
    BLK_REVIEW,
    BLK_WAIT_RECEIPT,
)
from services.execution_guidance.registry_docs_thin_v1 import BLK_GATHER as DTHIN_GATHER
from services.execution_guidance.registry_docs_thin_v1 import BLK_MAIL as DTHIN_MAIL
from services.execution_progress import (
    OutcomeSubmission,
    apply_outcome_submission,
    create_initial_state,
    mail_receipt_flag,
)
from services.execution_progress.validation import complete_always_allowed, is_valid_outcome_key
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


def _spa_bundle():
    ci = _ci_rich()
    pb = evaluate_strategy_patterns(ci)
    paths = generate_strategy_paths(ci, pb)
    sc = score_strategy_paths(ci, pb, paths)
    return build_execution_guidance_bundle(ci, pb, paths, sc, primary_path_id="path_standard_negative_first_pass")


def _docs_thin_bundle():
    ci = _ci_thin()
    pb = evaluate_strategy_patterns(ci)
    paths = generate_strategy_paths(ci, pb)
    sc = score_strategy_paths(ci, pb, paths)
    return build_execution_guidance_bundle(ci, pb, paths, sc, primary_path_id="path_docs_thin_conservative_first")


def test_validation_complete_always_for_empty_or_complete_empty():
    from services.execution_guidance.registry_spa_v1 import build_spa_blocks

    blocks, _, _, _ = build_spa_blocks("p")
    bureau = next(b for b in blocks if b.block_id.endswith("bureau_certified_dispute_mail"))
    assert complete_always_allowed(bureau)
    assert is_valid_outcome_key(bureau, "complete")
    review = next(b for b in blocks if b.block_id.endswith("review_responses_branch"))
    assert complete_always_allowed(review)
    assert is_valid_outcome_key(review, "complete")


def test_spa_parallel_then_probe_active():
    eg = _spa_bundle()
    st = create_initial_state(eg, "r1")
    assert BLK_BUREAU_MAIL in st.activated_block_ids and BLK_CRED_VAL in st.activated_block_ids
    assert BLK_PROBE not in st.activated_block_ids
    r1 = apply_outcome_submission(
        eg, st, OutcomeSubmission(block_id=BLK_BUREAU_MAIL, outcome_key="complete")
    )
    assert r1.accepted
    assert BLK_PROBE not in r1.state.activated_block_ids
    r2 = apply_outcome_submission(
        eg, st, OutcomeSubmission(block_id=BLK_CRED_VAL, outcome_key="complete")
    )
    assert r2.accepted
    assert BLK_PROBE in r2.state.activated_block_ids
    assert BLK_PROBE in r2.active_block_ids


def test_probe_failure_reaches_boundary():
    eg = _spa_bundle()
    st = create_initial_state(eg, "r1")
    apply_outcome_submission(eg, st, OutcomeSubmission(block_id=BLK_BUREAU_MAIL, outcome_key="complete"))
    apply_outcome_submission(eg, st, OutcomeSubmission(block_id=BLK_CRED_VAL, outcome_key="complete"))
    r = apply_outcome_submission(
        eg,
        st,
        OutcomeSubmission(block_id=BLK_PROBE, outcome_key="verification_failure_strong"),
    )
    assert r.accepted
    assert BLK_BOUNDARY in r.state.activated_block_ids
    assert BLK_BOUNDARY in r.active_block_ids


def test_probe_ok_wait_requires_mail_receipt_flag_then_delivery():
    eg = _spa_bundle()
    st = create_initial_state(eg, "r1")
    apply_outcome_submission(eg, st, OutcomeSubmission(block_id=BLK_BUREAU_MAIL, outcome_key="complete"))
    apply_outcome_submission(eg, st, OutcomeSubmission(block_id=BLK_CRED_VAL, outcome_key="complete"))
    apply_outcome_submission(
        eg, st, OutcomeSubmission(block_id=BLK_PROBE, outcome_key="verification_ok_or_inconclusive")
    )
    assert BLK_WAIT_RECEIPT in st.activated_block_ids
    bad = apply_outcome_submission(
        eg,
        st,
        OutcomeSubmission(block_id=BLK_WAIT_RECEIPT, outcome_key="delivery_confirmed"),
    )
    assert not bad.accepted
    assert any("mail_receipt_not_confirmed" in e for e in bad.validation_errors)
    key = mail_receipt_flag(BLK_BUREAU_MAIL)
    assert key == f"mail_receipt_confirmed_{BLK_BUREAU_MAIL}"
    good_flag = apply_outcome_submission(
        eg, st, OutcomeSubmission(external_flags={key: True})
    )
    assert good_flag.accepted
    assert BLK_WAIT_RECEIPT in good_flag.active_block_ids
    fin = apply_outcome_submission(
        eg,
        st,
        OutcomeSubmission(block_id=BLK_WAIT_RECEIPT, outcome_key="delivery_confirmed"),
    )
    assert fin.accepted


def test_invalid_outcome_key_rejected():
    eg = _spa_bundle()
    st = create_initial_state(eg, "r1")
    r = apply_outcome_submission(
        eg, st, OutcomeSubmission(block_id=BLK_BUREAU_MAIL, outcome_key="nonsense_outcome")
    )
    assert not r.accepted
    assert any("invalid_outcome_key" in e for e in r.validation_errors)


def test_double_complete_rejected():
    eg = _spa_bundle()
    st = create_initial_state(eg, "r1")
    apply_outcome_submission(eg, st, OutcomeSubmission(block_id=BLK_BUREAU_MAIL, outcome_key="complete"))
    r = apply_outcome_submission(
        eg, st, OutcomeSubmission(block_id=BLK_BUREAU_MAIL, outcome_key="complete")
    )
    assert not r.accepted
    assert any("already_completed" in e for e in r.validation_errors)


def test_version_mismatch_blocks_all_ids():
    eg = _spa_bundle()
    st = create_initial_state(eg, "r1")
    eg2 = copy.copy(eg)
    eg2.playbook_version = "99.0.0"
    r = apply_outcome_submission(
        eg2, st, OutcomeSubmission(block_id=BLK_CRED_VAL, outcome_key="complete")
    )
    assert not r.accepted
    assert st.blocked_reason
    assert len(r.blocked_block_ids) == len(eg.blocks)
    assert r.active_block_ids == [] and r.waiting_block_ids == []


def test_docs_thin_path_playbook_progression():
    eg = _docs_thin_bundle()
    st = create_initial_state(eg, "r1")
    assert DTHIN_GATHER in st.activated_block_ids
    r = apply_outcome_submission(
        eg, st, OutcomeSubmission(block_id=DTHIN_GATHER, outcome_key="complete")
    )
    assert r.accepted
    assert any("dthin_02" in bid for bid in r.active_block_ids)


def test_partial_submission_rejected():
    eg = _spa_bundle()
    st = create_initial_state(eg, "r1")
    r = apply_outcome_submission(eg, st, OutcomeSubmission(block_id=BLK_BUREAU_MAIL))
    assert not r.accepted


def test_state_roundtrip_dict():
    eg = _docs_thin_bundle()
    st = create_initial_state(eg, "r1")
    from services.execution_progress.models import ExecutionProgressState

    st2 = ExecutionProgressState.from_dict(st.to_dict())
    assert st2.run_id == st.run_id
    assert st2.activated_block_ids == st.activated_block_ids


def test_outcome_history_backward_compat_missing_recorded_at_and_snapshot():
    from services.execution_progress.models import ExecutionProgressState

    d = {
        "runId": "r-old",
        "workflowId": "wf",
        "guidanceSchemaVersion": "g.v1",
        "playbookId": "pb",
        "playbookVersion": "1",
        "completedBlockIds": [],
        "completedOutcomes": {},
        "activatedBlockIds": [],
        "externalFlags": {},
        "outcomeHistory": [
            {
                "blockId": "blk",
                "outcomeKey": "complete",
                "source": "user_reported",
                "notes": "legacy",
                "matchedSignalTargetIds": [],
                "guidanceSchemaVersion": "g.v1",
                "playbookId": "pb",
                "playbookVersion": "1",
            }
        ],
        "executionNotes": [],
    }
    st = ExecutionProgressState.from_dict(d)
    assert len(st.outcome_history) == 1
    rec = st.outcome_history[0]
    assert rec.recorded_at == ""
    assert rec.external_flags_snapshot == {}
    d2 = st.to_dict()
    assert "recordedAt" in d2["outcomeHistory"][0]
    assert d2["outcomeHistory"][0]["recordedAt"] == ""
    assert d2["outcomeHistory"][0]["externalFlagsSnapshot"] == {}


def test_apply_outcome_sets_recorded_at_and_external_flags_snapshot():
    eg = _spa_bundle()
    st = create_initial_state(eg, "r1")
    r = apply_outcome_submission(
        eg,
        st,
        OutcomeSubmission(
            block_id=BLK_BUREAU_MAIL,
            outcome_key="complete",
            notes="other text",
            external_flags={"notSure": True},
        ),
    )
    assert r.accepted
    hist = r.state.outcome_history
    assert len(hist) == 1
    rec = hist[0]
    assert rec.notes == "other text"
    assert rec.recorded_at
    assert rec.recorded_at.endswith("Z")
    assert rec.external_flags_snapshot.get("notSure") is True
