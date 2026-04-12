"""
Synchronized Pressure Attack (SPA) — code-defined playbook v1.

Maps to multi-point timing pressure: bureau dispute mail + creditor validation same window,
creditor verification probe call, verification-boundary behavior, receipt-gated bureau calls.
"""

from __future__ import annotations

from typing import List, Tuple

from .models import ExecutionGuidanceBlock, ParallelGroup
from .signals import SignalCaptureTarget, VerificationFailureSeverity
from .triggers import TimingTrigger

PLAYBOOK_ID = "spa_synchronized_pressure_v1"
PLAYBOOK_VERSION = "1.0.0"

GROUP_DAY1 = "spa_parallel_day1"
BLK_BUREAU_MAIL = "spa_p1_bureau_certified_dispute_mail"
BLK_CRED_VAL = "spa_p1_creditor_validation_mail"
BLK_PROBE = "spa_p2_creditor_verification_probe_call"
BLK_BOUNDARY = "spa_p3_verification_boundary_hold"
BLK_WAIT_RECEIPT = "spa_p4_wait_bureau_mail_receipt_confirmed"
BLK_BUREAU_CALL = "spa_p5_bureau_followup_call"
BLK_REVIEW = "spa_p6_review_responses_branch"


def build_spa_blocks(path_id: str) -> Tuple[List[ExecutionGuidanceBlock], List[ParallelGroup], List[str], List[str]]:
    parallel = ParallelGroup(
        group_id=GROUP_DAY1,
        block_ids=[BLK_BUREAU_MAIL, BLK_CRED_VAL],
        synchronization_note=(
            "Execute both mail actions in the same calendar day when prerequisites are met. "
            "This is synchronized pressure, not a sequential-only dispute flow."
        ),
    )

    b_bureau = ExecutionGuidanceBlock(
        block_id=BLK_BUREAU_MAIL,
        path_id=path_id,
        block_type="send_certified_dispute",
        action_name="Mail certified disputes to relevant bureaus",
        actor="user",
        channel="mail_certified",
        timing_trigger=TimingTrigger("immediate", {}),
        prerequisites=["dispute_letters_prepared", "mailing_addresses_confirmed"],
        instructions=(
            "Send bureau dispute correspondence via a trackable method (e.g. certified mail with tracking). "
            "Keep copies and tracking numbers. Do not misstate facts or misrepresent your identity."
        ),
        script_objective=None,
        prohibited_actions=["misrepresentation", "fraudulent_claims"],
        caution_notes=["Follow your own prepared dispute content; this system does not provide legal advice."],
        expected_outcomes=["mail_accepted_for_mailing", "tracking_number_recorded"],
        signal_capture_targets=[],
        next_by_outcome={"complete": []},
        readiness_state="conditional",
        explanation="Opens bureau-side dispute timing aligned with SPA.",
    )

    b_cred = ExecutionGuidanceBlock(
        block_id=BLK_CRED_VAL,
        path_id=path_id,
        block_type="send_validation_letter",
        action_name="Send validation / information request to creditor or collector",
        actor="user",
        channel="mail_certified",
        timing_trigger=TimingTrigger("immediate", {}),
        prerequisites=["validation_letter_prepared", "correct_creditor_mailing_address"],
        instructions=(
            "Send validation or permissible information requests on the same day as bureau mail when appropriate. "
            "Use certified mail when you need proof of delivery. Keep copies."
        ),
        script_objective=None,
        prohibited_actions=["misrepresentation"],
        caution_notes=[],
        expected_outcomes=["mail_accepted_for_mailing", "tracking_number_recorded"],
        signal_capture_targets=[],
        next_by_outcome={"complete": []},
        readiness_state="conditional",
        explanation="Creditor-side correspondence synchronized with bureau disputes.",
    )

    b_probe = ExecutionGuidanceBlock(
        block_id=BLK_PROBE,
        path_id=path_id,
        block_type="call_creditor_probe",
        action_name="Creditor verification probe call",
        actor="user",
        channel="phone",
        timing_trigger=TimingTrigger("after_parallel_group_complete", {"groupId": GROUP_DAY1}),
        prerequisites=["parallel_day1_mail_sent_or_scheduled"],
        instructions=(
            "Call the creditor using an ordinary customer service line. "
            "Goal: observe whether they can verify the account using information they should already hold, "
            "without you supplying unnecessary additional account identifiers. "
            "Stay factual; do not lie or conceal required lawful identity verification if genuinely required."
        ),
        script_objective=(
            "Ask a neutral status/verification question; listen for whether they locate the account independently "
            "or ask you for core account details they should already have."
        ),
        prohibited_actions=[
            "misrepresentation",
            "providing_unnecessary_account_reconstruction_to_help_creditor_locate_account",
        ],
        caution_notes=[
            "This is an operational probe to capture signals, not a guarantee of any credit outcome.",
        ],
        expected_outcomes=[
            "creditor_locates_account_without_extra_identifiers",
            "creditor_requests_account_number_or_similar_core_detail",
            "creditor_cannot_locate_account",
            "inconclusive",
        ],
        signal_capture_targets=[
            SignalCaptureTarget(
                target_id="vf_requests_account_number",
                description="Representative asks you to provide full account number or similar core identifier.",
                severity_if_matched=VerificationFailureSeverity.strong.value,
                source_hint="user_reported",
            ),
            SignalCaptureTarget(
                target_id="vf_cannot_locate_account",
                description="Representative states they cannot find the account without substantial help from you.",
                severity_if_matched=VerificationFailureSeverity.strong.value,
                source_hint="user_reported",
            ),
            SignalCaptureTarget(
                target_id="vf_weak_independent_verification",
                description="Hesitation or repeated clarifications suggesting weak independent lookup.",
                severity_if_matched=VerificationFailureSeverity.weak.value,
                source_hint="user_reported",
            ),
        ],
        next_by_outcome={
            "verification_failure_strong": [BLK_BOUNDARY],
            "verification_failure_medium": [BLK_BOUNDARY],
            "verification_failure_weak": [BLK_BOUNDARY],
            "verification_ok_or_inconclusive": [BLK_WAIT_RECEIPT],
        },
        readiness_state="conditional",
        explanation="Live call functions as verification probe; outcomes branch to boundary guidance or wait-for-receipt track.",
    )

    b_boundary = ExecutionGuidanceBlock(
        block_id=BLK_BOUNDARY,
        path_id=path_id,
        block_type="verification_boundary_exit",
        action_name="Apply verification boundary — end call cleanly",
        actor="user",
        channel="phone",
        timing_trigger=TimingTrigger("conditional_on_outcome", {"fromBlockId": BLK_PROBE}),
        prerequisites=["probe_call_completed_or_abandoned_safely"],
        instructions=(
            "If the creditor appears unable to verify the account without you supplying extra reconstructive details, "
            "do not volunteer additional account identifiers beyond what ordinary identity verification requires. "
            "Do not help them rebuild their file for you. "
            "Remain polite, decline to expand beyond normal verification, and end the call cleanly. "
            "This is an operational discipline to avoid strengthening their verification posture — not encouragement "
            "to misrepresent anything or withhold lawfully required information."
        ),
        script_objective="Politely close without supplying unnecessary account reconstruction details.",
        prohibited_actions=[
            "misrepresentation",
            "fabricating_information",
            "coaching_creditor_to_fix_their_records_for_you",
            "volunteering_unnecessary_account_reconstruction_to_help_creditor_locate_account",
        ],
        caution_notes=[
            "A verification weakness signal is not a legal conclusion and does not guarantee any dispute outcome.",
        ],
        expected_outcomes=["call_ended_cleanly", "user_declined_extra_reconstructive_details"],
        signal_capture_targets=[],
        next_by_outcome={"complete": [BLK_WAIT_RECEIPT]},
        readiness_state="ready_now",
        explanation="Operator boundary: avoid repairing opposing-party verification weakness during probe.",
    )

    b_wait = ExecutionGuidanceBlock(
        block_id=BLK_WAIT_RECEIPT,
        path_id=path_id,
        block_type="wait_window",
        action_name="Wait until bureau dispute mail receipt is confirmed",
        actor="user",
        channel="internal_review",
        timing_trigger=TimingTrigger(
            "after_mail_receipt_confirmed",
            {"trackedMailBlockId": BLK_BUREAU_MAIL},
        ),
        prerequisites=["bureau_mail_tracking_available"],
        instructions=(
            "Use tracking/delivery confirmation for bureau mail. Proceed to bureau follow-up call only after you have "
            "credible evidence the dispute correspondence was received (per carrier or return receipt)."
        ),
        script_objective=None,
        prohibited_actions=[],
        caution_notes=["Timing is operational, not a legal deadline guarantee."],
        expected_outcomes=["delivery_confirmed", "delivery_delayed_retry_tracking"],
        signal_capture_targets=[],
        next_by_outcome={"delivery_confirmed": [BLK_BUREAU_CALL]},
        readiness_state="conditional",
        explanation="Receipt-gated pressure: bureau calls after confirmed intake of dispute mail.",
    )

    b_bureau_call = ExecutionGuidanceBlock(
        block_id=BLK_BUREAU_CALL,
        path_id=path_id,
        block_type="call_bureau_followup",
        action_name="Bureau follow-up call after receipt",
        actor="user",
        channel="phone",
        timing_trigger=TimingTrigger("after_block_ids", {"blockIds": [BLK_WAIT_RECEIPT]}),
        prerequisites=["bureau_dispute_mail_delivery_confirmed"],
        instructions=(
            "Call the bureau to confirm the dispute is active in their process and to apply polite, factual follow-up "
            "pressure while the investigation runs. Do not misstate facts."
        ),
        script_objective="Confirm dispute logged and reinvestigation status without supplying unnecessary new reconstructive data.",
        prohibited_actions=["misrepresentation"],
        caution_notes=[],
        expected_outcomes=["dispute_confirmed_active", "dispute_not_located_retry_written_channel"],
        signal_capture_targets=[],
        next_by_outcome={"complete": [BLK_REVIEW]},
        readiness_state="conditional",
        explanation="Manual review pressure while bureau dispute is active.",
    )

    b_review = ExecutionGuidanceBlock(
        block_id=BLK_REVIEW,
        path_id=path_id,
        block_type="review_response_and_branch",
        action_name="Review bureau/creditor responses and choose next branch",
        actor="hybrid",
        channel="internal_review",
        timing_trigger=TimingTrigger("after_block_ids", {"blockIds": [BLK_BUREAU_CALL]}),
        prerequisites=["responses_or_deadlines_observed"],
        instructions=(
            "Compare responses across bureaus and creditor where applicable. "
            "Next steps may include reinvestigation rounds, method-of-verification requests, or regulatory complaints — "
            "each requires its own prepared content and eligibility checks (not auto-generated here)."
        ),
        script_objective=None,
        prohibited_actions=[],
        caution_notes=[
            "MOV / CFPB / BBB / FTC escalation blocks are future playbooks; record outcomes before escalating.",
        ],
        expected_outcomes=["reinvestigation_needed", "mov_track", "regulatory_escalation_candidate", "resolved_or_stalled"],
        signal_capture_targets=[],
        next_by_outcome={},
        readiness_state="conditional",
        explanation="Terminal planning node for this v1 SPA playbook; ties forward to execution planning layer.",
    )

    blocks = [b_bureau, b_cred, b_probe, b_boundary, b_wait, b_bureau_call, b_review]
    entries = [BLK_BUREAU_MAIL, BLK_CRED_VAL]
    terminals = [BLK_REVIEW]
    return blocks, [parallel], entries, terminals
