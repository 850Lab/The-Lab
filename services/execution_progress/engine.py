"""
Apply outcome submissions and recompute active / waiting / blocked execution state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Set, Tuple

from services.execution_guidance.models import ExecutionGuidanceBundle, ExecutionGuidanceBlock

from .models import (
    PROGRESS_SCHEMA_VERSION,
    ExecutionProgressState,
    OutcomeRecord,
    OutcomeSubmission,
    ProgressionResult,
    mail_receipt_flag,
)
from .triggers_resolve import fixpoint_activate, partition_active_waiting
from .validation import is_valid_outcome_key


def _by_id(bundle: ExecutionGuidanceBundle) -> dict[str, ExecutionGuidanceBlock]:
    return {b.block_id: b for b in bundle.blocks}


def _version_mismatch(bundle: ExecutionGuidanceBundle, state: ExecutionProgressState) -> Optional[str]:
    if state.guidance_schema_version != bundle.schema_version:
        return "guidance_schema_version_mismatch"
    if state.playbook_id != bundle.playbook_id:
        return "playbook_id_mismatch"
    if state.playbook_version != bundle.playbook_version:
        return "playbook_version_mismatch"
    return None


def _merge_flags(base: dict, patch: dict) -> dict:
    out = dict(base)
    out.update(patch)
    return out


def _requires_mail_receipt_for_outcome(block: ExecutionGuidanceBlock, outcome_key: str) -> bool:
    if block.timing_trigger.kind != "after_mail_receipt_confirmed":
        return False
    return outcome_key == "delivery_confirmed"


def _mail_receipt_satisfied(block: ExecutionGuidanceBlock, external_flags: dict) -> bool:
    tracked = (block.timing_trigger.payload or {}).get("trackedMailBlockId")
    if not tracked:
        return False
    return bool(external_flags.get(mail_receipt_flag(str(tracked))))


def _recompute(
    bundle: ExecutionGuidanceBundle,
    state: ExecutionProgressState,
) -> Tuple[Set[str], List[str], List[str], List[str]]:
    completed = set(state.completed_block_ids)
    act = fixpoint_activate(
        bundle,
        completed,
        dict(state.completed_outcomes),
        set(state.activated_block_ids),
    )
    state.activated_block_ids = sorted(act)
    active, waiting = partition_active_waiting(bundle, completed, act, state.external_flags)
    blocked: List[str] = []
    if state.blocked_reason:
        blocked = sorted(b.block_id for b in bundle.blocks)
        active, waiting = [], []
    return act, active, waiting, blocked


def compute_execution_partition(
    bundle: ExecutionGuidanceBundle,
    state: ExecutionProgressState,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Active / waiting / blocked block ids for the current bundle + persisted progress.
    Used by HTTP execution runtime and tests.
    """
    _, active, waiting, blocked = _recompute(bundle, state)
    return list(active), list(waiting), list(blocked)


def create_initial_state(
    bundle: ExecutionGuidanceBundle,
    run_id: str,
    *,
    workflow_id: Optional[str] = None,
) -> ExecutionProgressState:
    completed: Set[str] = set()
    outcomes: dict = {}
    initial_act = set(bundle.entry_block_ids)
    activated = fixpoint_activate(bundle, completed, outcomes, initial_act)
    state = ExecutionProgressState(
        run_id=run_id,
        workflow_id=workflow_id,
        guidance_schema_version=bundle.schema_version,
        playbook_id=bundle.playbook_id,
        playbook_version=bundle.playbook_version,
        primary_path_id=bundle.primary_path_id,
        completed_block_ids=[],
        completed_outcomes={},
        activated_block_ids=sorted(activated),
        external_flags={},
        outcome_history=[],
        execution_notes=[f"init:{PROGRESS_SCHEMA_VERSION}"],
        blocked_reason=None,
    )
    _, active, waiting, _ = _recompute(bundle, state)
    state.execution_notes.append("initial_active:" + ",".join(active))
    state.execution_notes.append("initial_waiting:" + ",".join(waiting))
    return state


def apply_outcome_submission(
    bundle: ExecutionGuidanceBundle,
    state: ExecutionProgressState,
    submission: OutcomeSubmission,
) -> ProgressionResult:
    """
    Validate submission, record outcome when applicable, merge flags, recompute activation.
    """
    errors: List[str] = []
    transition_notes: List[str] = []
    by = _by_id(bundle)

    if state.blocked_reason:
        _, _, _, blocked = _recompute(bundle, state)
        return ProgressionResult(
            accepted=False,
            validation_errors=["execution_blocked:" + state.blocked_reason],
            state=state,
            active_block_ids=[],
            waiting_block_ids=[],
            blocked_block_ids=blocked,
            newly_activated_block_ids=[],
            transition_notes=["rejected_already_blocked"],
        )

    if submission.external_flags:
        state.external_flags = _merge_flags(state.external_flags, submission.external_flags)
        transition_notes.append("merged_external_flags")

    vm = _version_mismatch(bundle, state)
    if vm:
        state.blocked_reason = vm
        _, _, _, blocked = _recompute(bundle, state)
        transition_notes.append("blocked:" + vm)
        return ProgressionResult(
            accepted=False,
            validation_errors=[vm],
            state=state,
            active_block_ids=[],
            waiting_block_ids=[],
            blocked_block_ids=blocked,
            newly_activated_block_ids=[],
            transition_notes=transition_notes,
        )

    if (submission.block_id is not None) ^ (submission.outcome_key is not None):
        _, active, waiting, blocked = _recompute(bundle, state)
        return ProgressionResult(
            accepted=False,
            validation_errors=["block_id_and_outcome_key_must_be_together"],
            state=state,
            active_block_ids=active,
            waiting_block_ids=waiting,
            blocked_block_ids=blocked,
            newly_activated_block_ids=[],
            transition_notes=transition_notes,
        )

    if not submission.has_completion():
        if submission.has_flags_only():
            act_before = set(state.activated_block_ids)
            _, active, waiting, blocked = _recompute(bundle, state)
            new_act = sorted(set(state.activated_block_ids) - act_before)
            return ProgressionResult(
                accepted=True,
                validation_errors=[],
                state=state,
                active_block_ids=active,
                waiting_block_ids=waiting,
                blocked_block_ids=blocked,
                newly_activated_block_ids=new_act,
                transition_notes=transition_notes,
            )
        return ProgressionResult(
            accepted=False,
            validation_errors=["must_provide_block_id_and_outcome_key_or_external_flags"],
            state=state,
            active_block_ids=[],
            waiting_block_ids=[],
            blocked_block_ids=[],
            newly_activated_block_ids=[],
            transition_notes=transition_notes,
        )

    assert submission.block_id is not None and submission.outcome_key is not None
    bid = submission.block_id
    okey = submission.outcome_key

    act_before = set(state.activated_block_ids)
    _, active_pre, _, _ = _recompute(bundle, state)

    if bid not in active_pre:
        errors.append(f"block_not_active:{bid}")

    blk = by.get(bid)
    if not blk:
        errors.append("unknown_block_id")
    else:
        if not is_valid_outcome_key(blk, okey):
            errors.append(f"invalid_outcome_key:{okey}")
        if _requires_mail_receipt_for_outcome(blk, okey) and not _mail_receipt_satisfied(blk, state.external_flags):
            errors.append("mail_receipt_not_confirmed:" + mail_receipt_flag(str((blk.timing_trigger.payload or {}).get("trackedMailBlockId", ""))))

    if bid in state.completed_block_ids:
        errors.append("block_already_completed")

    if errors:
        _, active, waiting, blocked = _recompute(bundle, state)
        return ProgressionResult(
            accepted=False,
            validation_errors=errors,
            state=state,
            active_block_ids=active,
            waiting_block_ids=waiting,
            blocked_block_ids=blocked,
            newly_activated_block_ids=[],
            transition_notes=transition_notes,
        )

    state.completed_block_ids = list(state.completed_block_ids) + [bid]
    state.completed_outcomes = dict(state.completed_outcomes)
    state.completed_outcomes[bid] = okey
    recorded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    state.outcome_history.append(
        OutcomeRecord(
            block_id=bid,
            outcome_key=okey,
            source=submission.source.value,
            notes=submission.notes,
            matched_signal_target_ids=list(submission.matched_signal_target_ids),
            guidance_schema_version=bundle.schema_version,
            playbook_id=bundle.playbook_id,
            playbook_version=bundle.playbook_version,
            recorded_at=recorded_at,
            external_flags_snapshot=dict(submission.external_flags or {}),
        )
    )
    transition_notes.append(f"completed:{bid}:{okey}")

    act_after = fixpoint_activate(
        bundle,
        set(state.completed_block_ids),
        dict(state.completed_outcomes),
        set(state.activated_block_ids),
    )
    state.activated_block_ids = sorted(act_after)
    newly = sorted(act_after - act_before)

    _, active, waiting, blocked = _recompute(bundle, state)

    return ProgressionResult(
        accepted=True,
        validation_errors=[],
        state=state,
        active_block_ids=active,
        waiting_block_ids=waiting,
        blocked_block_ids=blocked,
        newly_activated_block_ids=newly,
        transition_notes=transition_notes,
    )
