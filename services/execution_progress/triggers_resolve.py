"""
Resolve timing triggers against completed blocks and external_flags.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from services.execution_guidance.models import ExecutionGuidanceBundle, ExecutionGuidanceBlock

from .models import mail_receipt_flag


def parallel_group_satisfied(bundle: ExecutionGuidanceBundle, group_id: str, completed: Set[str]) -> bool:
    for g in bundle.parallel_groups:
        if g.group_id == group_id:
            return all(bid in completed for bid in g.block_ids)
    return False


def should_activate_via_trigger(
    block: ExecutionGuidanceBlock,
    bundle: ExecutionGuidanceBundle,
    completed: Set[str],
    activated: Set[str],
) -> bool:
    """Whether a not-yet-activated block becomes activated from trigger rules only."""
    if block.block_id in completed or block.block_id in activated:
        return False
    tt = block.timing_trigger
    kind = tt.kind
    payload = tt.payload or {}

    if kind == "immediate":
        return block.block_id in bundle.entry_block_ids

    if kind == "after_parallel_group_complete":
        gid = payload.get("groupId")
        if not gid:
            return False
        return parallel_group_satisfied(bundle, gid, completed)

    if kind == "after_block_ids":
        preds = payload.get("blockIds") or []
        return bool(preds) and all(bid in completed for bid in preds)

    # after_mail_receipt_confirmed, conditional_on_outcome: activation via graph edges, not standalone trigger
    return False


def is_waiting_on_mail_receipt(
    block: ExecutionGuidanceBlock,
    external_flags: Dict[str, Any],
) -> bool:
    tt = block.timing_trigger
    if tt.kind != "after_mail_receipt_confirmed":
        return False
    tracked = (tt.payload or {}).get("trackedMailBlockId")
    if not tracked:
        return True
    key = mail_receipt_flag(str(tracked))
    return not bool(external_flags.get(key))


def is_waiting_on_triggers(
    block: ExecutionGuidanceBlock,
    bundle: ExecutionGuidanceBundle,
    completed: Set[str],
    external_flags: Dict[str, Any],
) -> bool:
    """
    Block is in activated\\completed but not yet actionable.
    Most non-ready states use waiting (not blocked).
    """
    tt = block.timing_trigger
    kind = tt.kind
    payload = tt.payload or {}

    if kind == "after_mail_receipt_confirmed":
        return is_waiting_on_mail_receipt(block, external_flags)

    if kind == "after_parallel_group_complete":
        gid = payload.get("groupId")
        if gid and not parallel_group_satisfied(bundle, gid, completed):
            return True

    if kind == "after_block_ids":
        preds = payload.get("blockIds") or []
        if preds and not all(bid in completed for bid in preds):
            return True

    if kind == "conditional_on_outcome":
        fb = payload.get("fromBlockId")
        if fb and fb not in completed:
            return True

    return False


def expand_activations_from_graph(
    bundle: ExecutionGuidanceBundle,
    completed_outcomes: Dict[str, str],
    activated: Set[str],
) -> Set[str]:
    """Add blocks reachable from recorded next_by_outcome edges."""
    by_id = {b.block_id: b for b in bundle.blocks}
    out = set(activated)
    for bid, okey in completed_outcomes.items():
        b = by_id.get(bid)
        if not b:
            continue
        nxt = b.next_by_outcome.get(okey)
        if not nxt:
            continue
        for nid in nxt:
            out.add(nid)
    return out


def expand_activations_from_triggers(
    bundle: ExecutionGuidanceBundle,
    completed: Set[str],
    activated: Set[str],
) -> Tuple[Set[str], bool]:
    """Single pass: activate any block that matches trigger rules."""
    new_act = set(activated)
    changed = False
    for b in bundle.blocks:
        if should_activate_via_trigger(b, bundle, completed, new_act):
            if b.block_id not in new_act:
                new_act.add(b.block_id)
                changed = True
    return new_act, changed


def fixpoint_activate(
    bundle: ExecutionGuidanceBundle,
    completed: Set[str],
    completed_outcomes: Dict[str, str],
    initial_activated: Set[str],
) -> Set[str]:
    """Apply graph edges + trigger expansion until stable."""
    act = set(initial_activated)
    act |= expand_activations_from_graph(bundle, completed_outcomes, act)
    for _ in range(len(bundle.blocks) + 2):
        act, trig_changed = expand_activations_from_triggers(bundle, completed, act)
        act |= expand_activations_from_graph(bundle, completed_outcomes, act)
        if not trig_changed:
            break
    return act


def partition_active_waiting(
    bundle: ExecutionGuidanceBundle,
    completed: Set[str],
    activated: Set[str],
    external_flags: Dict[str, Any],
) -> Tuple[List[str], List[str]]:
    by_id = {b.block_id: b for b in bundle.blocks}
    active: List[str] = []
    waiting: List[str] = []
    for bid in sorted(activated - completed):
        b = by_id[bid]
        if is_waiting_on_triggers(b, bundle, completed, external_flags):
            waiting.append(bid)
        else:
            active.append(bid)
    return active, waiting
