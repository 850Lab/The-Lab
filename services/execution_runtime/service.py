"""
Execution runtime orchestration: start session, load state, submit outcomes.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

from services.execution_guidance import build_execution_guidance_for_workflow
from services.execution_guidance.models import ExecutionGuidanceBlock, ExecutionGuidanceBundle
from services.execution_progress import (
    OutcomeSource,
    OutcomeSubmission,
    apply_outcome_submission,
    compute_execution_partition,
    create_initial_state,
)
from services.execution_progress.models import ExecutionProgressState
from services.execution_progress.validation import complete_always_allowed

from .hydrate import execution_guidance_bundle_from_dict
from services.workflow.observability_events import emit_observability_event

from .repository import (
    fetch_execution_run_by_id,
    fetch_latest_execution_run_for_workflow,
    insert_execution_run,
    update_execution_progress,
)

# When the block only allows ``complete``, expose the same four UX rows as the SPA (distinct ids, shared key).
_SPA_FALLBACK_OUTCOMES: Tuple[Tuple[str, str, str, str], ...] = (
    ("completed_as_expected", "I finished this step as described", "complete", ""),
    ("could_not_complete", "I couldn't complete it (blocked or unclear)", "complete", "intent:could_not_complete"),
    ("need_more_time", "I need more time — I'll come back to this", "complete", "intent:need_more_time"),
    ("got_partial_response", "I got a partial or unclear response", "complete", "intent:partial_or_unclear"),
)


def _bundle_and_state_from_row(row: Dict[str, Any]) -> Tuple[ExecutionGuidanceBundle, ExecutionProgressState]:
    bundle = execution_guidance_bundle_from_dict(row["guidance_bundle_json"])
    state = ExecutionProgressState.from_dict(row["progress_state_json"])
    return bundle, state


def build_outcome_options(block: ExecutionGuidanceBlock) -> List[Dict[str, Any]]:
    raw_keys = list(block.next_by_outcome.keys())
    only_complete = set(raw_keys) == {"complete"} or (
        not raw_keys and complete_always_allowed(block)
    )
    if only_complete:
        return [
            {
                "id": fid,
                "label": lab,
                "outcomeKey": ok,
                "defaultNotes": dn,
            }
            for fid, lab, ok, dn in _SPA_FALLBACK_OUTCOMES
        ]
    keys = sorted(set(raw_keys))
    out: List[Dict[str, Any]] = []
    for k in keys:
        label = k.replace("_", " ").strip().title() or k
        out.append({"id": k, "label": label, "outcomeKey": k, "defaultNotes": ""})
    return out


def execution_state_response(
    bundle: ExecutionGuidanceBundle,
    state: ExecutionProgressState,
) -> Dict[str, Any]:
    active, waiting, blocked = compute_execution_partition(bundle, state)
    by_id = {b.block_id: b for b in bundle.blocks}
    primary: Optional[Dict[str, Any]] = None
    outcome_options: List[Dict[str, Any]] = []
    if not state.blocked_reason and active:
        bid = active[0]
        blk = by_id.get(bid)
        if blk:
            primary = {
                "blockId": blk.block_id,
                "actionName": blk.action_name,
                "instructions": blk.instructions,
                "cautionNotes": list(blk.caution_notes),
            }
            outcome_options = build_outcome_options(blk)
    return {
        "runId": state.run_id,
        "workflowId": state.workflow_id,
        "blockedReason": state.blocked_reason,
        "activeBlockIds": active,
        "waitingBlockIds": waiting,
        "blockedBlockIds": blocked,
        "completedBlockIds": list(state.completed_block_ids),
        "primaryActiveBlock": primary,
        "outcomeOptions": outcome_options,
    }


def start_execution_session(workflow_id: str, user_id: int) -> Dict[str, Any]:
    bundle = build_execution_guidance_for_workflow(workflow_id, user_id)
    run_id = str(uuid.uuid4())
    state = create_initial_state(bundle, run_id, workflow_id=workflow_id)
    insert_execution_run(
        run_id,
        workflow_id,
        user_id,
        bundle.to_dict(),
        state.to_dict(),
    )
    return {
        "runId": run_id,
        "executionState": execution_state_response(bundle, state),
    }


def get_execution_state_for_run(run_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    row = fetch_execution_run_by_id(run_id)
    if not row:
        return None
    if int(row["user_id"]) != int(user_id):
        return None
    bundle, state = _bundle_and_state_from_row(row)
    return execution_state_response(bundle, state)


def get_execution_state_latest_for_workflow(workflow_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    row = fetch_latest_execution_run_for_workflow(workflow_id, user_id)
    if not row:
        return None
    bundle, state = _bundle_and_state_from_row(row)
    return execution_state_response(bundle, state)


def submit_execution_outcome(
    run_id: str,
    user_id: int,
    *,
    block_id: str,
    outcome_key: str,
    notes: str = "",
    external_flags: Optional[Dict[str, Any]] = None,
    source: str = "user_reported",
) -> Dict[str, Any]:
    row = fetch_execution_run_by_id(run_id)
    if not row:
        return {"ok": False, "code": "NOT_FOUND", "executionState": None, "progression": None}
    if int(row["user_id"]) != int(user_id):
        return {"ok": False, "code": "FORBIDDEN", "executionState": None, "progression": None}

    bundle, state = _bundle_and_state_from_row(row)
    try:
        src = OutcomeSource(source)
    except ValueError:
        src = OutcomeSource.user_reported
    submission = OutcomeSubmission(
        block_id=block_id,
        outcome_key=outcome_key,
        source=src,
        notes=notes or "",
        matched_signal_target_ids=[],
        external_flags=dict(external_flags or {}),
    )
    result = apply_outcome_submission(bundle, state, submission)
    update_execution_progress(run_id, result.state.to_dict())
    wf_id = str(row.get("workflow_id") or "")
    emit_observability_event(
        user_id=user_id,
        workflow_id=wf_id,
        step_id=str(block_id).strip()[:64] or None,
        event_name="outcome_submitted",
        event_category="input",
        status="success",
        metadata={
            "blockId": str(block_id).strip()[:64],
            "outcomeKey": str(outcome_key).strip()[:64],
            "outcomeSource": str(src.value),
        },
        source="execution_runtime",
    )
    return {
        "ok": True,
        "code": None,
        "executionState": execution_state_response(bundle, result.state),
        "progression": result.to_dict(),
    }
