"""
Documentation-thin conservative dispute path — execution playbook v1.

Aligns with strategy path ``path_docs_thin_conservative_first``: strengthen proof, reassess,
narrow first dispute round, then trackable bureau mail. No creditor verification probe in v1.
"""

from __future__ import annotations

from typing import List, Tuple

from .models import ExecutionGuidanceBlock, ParallelGroup
from .triggers import TimingTrigger

PLAYBOOK_ID = "docs_thin_standard_dispute_v1"
PLAYBOOK_VERSION = "1.0.0"

BLK_GATHER = "dthin_01_gather_proof_documentation"
BLK_REASSESS = "dthin_02_reassess_eligibility"
BLK_NARROW = "dthin_03_narrow_first_dispute_round"
BLK_MAIL = "dthin_04_mail_bureau_disputes_trackable"
BLK_WAIT = "dthin_05_wait_response_window"
BLK_REVIEW = "dthin_06_review_responses_next_steps"


def build_docs_thin_blocks(path_id: str) -> Tuple[List[ExecutionGuidanceBlock], List[ParallelGroup], List[str], List[str]]:
    b1 = ExecutionGuidanceBlock(
        block_id=BLK_GATHER,
        path_id=path_id,
        block_type="upload_supporting_docs",
        action_name="Gather and organize proof documentation",
        actor="user",
        channel="upload",
        timing_trigger=TimingTrigger("immediate", {}),
        prerequisites=["list_missing_proof_from_case_intelligence"],
        instructions=(
            "Complete government ID, address, and signature artifacts as required by your workflow. "
            "Attach only truthful, accurate documents. Re-run case intelligence / eligibility after uploads."
        ),
        script_objective=None,
        prohibited_actions=["misrepresentation", "fabricated_documents"],
        caution_notes=[
            "Thin documentation posture increases reinvestigation friction; prioritize proof before broad multi-item waves.",
        ],
        expected_outcomes=["proof_bundle_improved", "still_partial_continue_prereqs"],
        signal_capture_targets=[],
        next_by_outcome={"complete": [BLK_REASSESS]},
        readiness_state="conditional",
        explanation="Grounded in documentation-thin strategy path: proof before aggressive rounds.",
    )

    b2 = ExecutionGuidanceBlock(
        block_id=BLK_REASSESS,
        path_id=path_id,
        block_type="review_response_and_branch",
        action_name="Reassess dispute eligibility after proof update",
        actor="hybrid",
        channel="internal_review",
        timing_trigger=TimingTrigger("after_block_ids", {"blockIds": [BLK_GATHER]}),
        prerequisites=["documentation_state_refreshed"],
        instructions=(
            "Refresh review-claim selection and eligible dispute pool using your existing tools. "
            "Narrow the first round to the strongest, best-supported items."
        ),
        script_objective=None,
        prohibited_actions=[],
        caution_notes=[],
        expected_outcomes=["eligible_pool_updated"],
        signal_capture_targets=[],
        next_by_outcome={"eligible_pool_updated": [BLK_NARROW]},
        readiness_state="conditional",
        explanation="Ties execution to path template reassess_eligibility.",
    )

    b3 = ExecutionGuidanceBlock(
        block_id=BLK_NARROW,
        path_id=path_id,
        block_type="prepare_dispute_selection",
        action_name="Select a narrow first dispute round",
        actor="user",
        channel="internal_review",
        timing_trigger=TimingTrigger("after_block_ids", {"blockIds": [BLK_REASSESS]}),
        prerequisites=["at_least_one_eligible_candidate_if_available"],
        instructions=(
            "Choose a limited set of disputes aligned with your prepared proof. "
            "Avoid maximizing item count while documentation is still thin."
        ),
        script_objective=None,
        prohibited_actions=[],
        caution_notes=[],
        expected_outcomes=["selection_confirmed"],
        signal_capture_targets=[],
        next_by_outcome={"selection_confirmed": [BLK_MAIL]},
        readiness_state="conditional",
        explanation="Matches path action narrow_dispute_round.",
    )

    b4 = ExecutionGuidanceBlock(
        block_id=BLK_MAIL,
        path_id=path_id,
        block_type="send_certified_dispute",
        action_name="Mail bureau disputes with tracking",
        actor="user",
        channel="mail_certified",
        timing_trigger=TimingTrigger("after_block_ids", {"blockIds": [BLK_NARROW]}),
        prerequisites=["dispute_letters_finalized", "addresses_verified"],
        instructions=(
            "Send disputes via certified mail (or equivalent trackable service). "
            "Retain copies and tracking. Content must be truthful."
        ),
        script_objective=None,
        prohibited_actions=["misrepresentation"],
        caution_notes=[],
        expected_outcomes=["mail_sent", "tracking_recorded"],
        signal_capture_targets=[],
        next_by_outcome={"complete": [BLK_WAIT]},
        readiness_state="conditional",
        explanation="Conservative first pass: trackable written bureau channel only in this playbook v1.",
    )

    b5 = ExecutionGuidanceBlock(
        block_id=BLK_WAIT,
        path_id=path_id,
        block_type="wait_window",
        action_name="Wait for initial bureau processing window",
        actor="user",
        channel="internal_review",
        timing_trigger=TimingTrigger("after_calendar_days", {"days": 30, "informational_only": True}),
        prerequisites=["mail_sent"],
        instructions=(
            "Allow time for mail delivery and initial bureau handling. "
            "30 days is a common operational planning horizon; it is not a guarantee of outcome or a legal deadline."
        ),
        script_objective=None,
        prohibited_actions=[],
        caution_notes=["Adjust calendar if your tracking shows delivery delays."],
        expected_outcomes=["window_elapsed_or_responses_received_earlier"],
        signal_capture_targets=[],
        next_by_outcome={"complete": [BLK_REVIEW]},
        readiness_state="conditional",
        explanation="Operational wait — aligns with common manual workflow pacing without claiming legal timing.",
    )

    b6 = ExecutionGuidanceBlock(
        block_id=BLK_REVIEW,
        path_id=path_id,
        block_type="review_response_and_branch",
        action_name="Review responses and plan next round or escalation",
        actor="hybrid",
        channel="internal_review",
        timing_trigger=TimingTrigger("after_block_ids", {"blockIds": [BLK_WAIT]}),
        prerequisites=["mailing_and_responses_tracked"],
        instructions=(
            "Review bureau outcomes. Next steps may include reinvestigation, MOV, or regulatory paths — "
            "select based on responses and your prepared materials (future execution planning)."
        ),
        script_objective=None,
        prohibited_actions=[],
        caution_notes=[],
        expected_outcomes=["continue_round_2", "mov_track", "escalation_candidate", "stall"],
        signal_capture_targets=[],
        next_by_outcome={},
        readiness_state="conditional",
        explanation="Terminal node for docs-thin v1 playbook.",
    )

    blocks = [b1, b2, b3, b4, b5, b6]
    return blocks, [], [BLK_GATHER], [BLK_REVIEW]
