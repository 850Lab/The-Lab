"""
Workflow-bound escalation: turns item-level failure patterns into structured next steps.

All state lives on ``workflow_sessions.metadata.dispute_selection`` — no new workflows
or tables. Complements document-level ``escalation_recommendation`` (response intake).

Triggers (item / history–based):
  * ``no_response`` — bureau outcome bucket (already ``needs_escalation`` disposition).
  * ``repeated_verified`` — same review claim recorded as ``verified`` in 2+ intake snapshots.
  * ``insufficient_update`` — outcome ``updated`` while program round >= 2 (partial fix loop).

Action ``type`` values (stable for clients): ``method_of_verification``, ``furnisher_dispute``,
``cfpb_complaint``, ``call_script``.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple

from services.workflow.repository import merge_into_workflow_metadata

from services.workflow.dispute_round_execution import (
    _claim_outcomes_from_ds,
    _cumulative_from_ds,
    _ds_from_meta,
    _round_from_ds,
    item_disposition,
    normalize_bureau_item_outcome,
)

ESCALATION_ACTION_TYPES: Tuple[str, ...] = (
    "method_of_verification",
    "furnisher_dispute",
    "cfpb_complaint",
    "call_script",
)

TRIGGER_NO_RESPONSE = "no_response"
TRIGGER_REPEATED_VERIFIED = "repeated_verified"
TRIGGER_INSUFFICIENT_UPDATE = "insufficient_update"

STATUS_NONE = "none"
STATUS_ACTION_REQUIRED = "action_required"


def _stable_action_id(parts: Tuple[str, ...]) -> str:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"esc_{h}"


def _prior_list(ds: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = ds.get("prior_outcomes")
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]


def verified_snapshot_count_for_claim(prior: List[Dict[str, Any]], claim_id: str) -> int:
    """How many ``response_intake`` snapshots recorded this claim as ``verified``."""
    n = 0
    cid = str(claim_id).strip()
    for entry in prior:
        if entry.get("kind") != "response_intake":
            continue
        snap = entry.get("claimOutcomeSnapshot")
        if not isinstance(snap, dict):
            continue
        v = snap.get(cid)
        if v is None:
            continue
        if normalize_bureau_item_outcome(str(v)) == "verified":
            n += 1
    return n


def updated_across_round_transitions(prior: List[Dict[str, Any]], claim_id: str) -> int:
    """Count ``round_transition`` snapshots where this claim was ``updated``."""
    n = 0
    cid = str(claim_id).strip()
    for entry in prior:
        if entry.get("kind") != "round_transition":
            continue
        snap = entry.get("claimOutcomesSnapshot")
        if not isinstance(snap, dict):
            continue
        v = snap.get(cid)
        if v is None:
            continue
        if normalize_bureau_item_outcome(str(v)) == "updated":
            n += 1
    return n


def collect_escalation_triggers(ds: Dict[str, Any]) -> Dict[str, Set[str]]:
    """
    Map trigger reason -> set of review_claim_ids.
    """
    prior = _prior_list(ds)
    cumulative = _cumulative_from_ds(ds)
    outcomes = _claim_outcomes_from_ds(ds)
    rnd = _round_from_ds(ds)
    out: Dict[str, Set[str]] = {
        TRIGGER_NO_RESPONSE: set(),
        TRIGGER_REPEATED_VERIFIED: set(),
        TRIGGER_INSUFFICIENT_UPDATE: set(),
    }

    for cid in cumulative:
        oc = normalize_bureau_item_outcome(str(outcomes.get(cid) or ""))
        disp = item_disposition(oc)
        if disp == "needs_escalation" or oc == "no_response":
            out[TRIGGER_NO_RESPONSE].add(cid)
        if verified_snapshot_count_for_claim(prior, cid) >= 2:
            out[TRIGGER_REPEATED_VERIFIED].add(cid)
        if oc == "updated" and rnd >= 2:
            out[TRIGGER_INSUFFICIENT_UPDATE].add(cid)
        if oc == "updated" and updated_across_round_transitions(prior, cid) >= 1:
            out[TRIGGER_INSUFFICIENT_UPDATE].add(cid)

    return out


def _mov_script_bullets(audience: str) -> List[str]:
    if audience == "furnisher":
        return [
            "State your name and that you are calling about your dispute under the FCRA.",
            "Reference the account or tradeline and the bureau you disputed with.",
            "Ask whether the furnisher verified with the bureau and request the method of verification.",
            "If blocked, ask for a written summary of investigation results.",
        ]
    return [
        "Identify your dispute reference or confirmation number if you have one.",
        "Ask what specific procedure was used to verify the disputed information.",
        "Request the name of the furnisher or source contacted and dates of contact.",
        "If the representative cannot answer, ask for a supervisor or written response.",
    ]


def _build_action(
    *,
    action_type: str,
    claim_ids: List[str],
    trigger: str,
    title: str,
    summary_safe: str,
    priority: int,
    call_audience: str = "bureau",
) -> Dict[str, Any]:
    cid_key = ",".join(sorted(claim_ids))[:200]
    aid = _stable_action_id((action_type, trigger, cid_key))
    row: Dict[str, Any] = {
        "id": aid,
        "type": action_type,
        "priority": priority,
        "triggerReason": trigger,
        "reviewClaimIds": claim_ids[:100],
        "title": title,
        "summarySafe": summary_safe[:800],
        "metadata": {},
    }
    if action_type == "call_script":
        row["metadata"] = {
            "audience": call_audience,
            "bullets": _mov_script_bullets(call_audience),
        }
    return row


def build_escalation_actions_from_triggers(triggers: Dict[str, Set[str]]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    # no_response → MOV + furnisher + CFPB + bureau call script
    ids = sorted(triggers.get(TRIGGER_NO_RESPONSE) or [])
    if ids:
        actions.append(
            _build_action(
                action_type="method_of_verification",
                claim_ids=ids,
                trigger=TRIGGER_NO_RESPONSE,
                title="Request method of verification",
                summary_safe=(
                    "Bureau(s) did not substantively respond or stalled; request how disputed "
                    "items were verified, in writing, per FCRA."
                ),
                priority=10,
            )
        )
        actions.append(
            _build_action(
                action_type="furnisher_dispute",
                claim_ids=ids,
                trigger=TRIGGER_NO_RESPONSE,
                title="Direct furnisher dispute",
                summary_safe=(
                    "If the bureau is non-responsive, dispute directly with the data furnisher "
                    "and preserve mailing proof."
                ),
                priority=20,
            )
        )
        actions.append(
            _build_action(
                action_type="cfpb_complaint",
                claim_ids=ids,
                trigger=TRIGGER_NO_RESPONSE,
                title="CFPB complaint (optional)",
                summary_safe=(
                    "After documenting attempts, a CFPB complaint can be filed with your "
                    "timeline and correspondence summary."
                ),
                priority=30,
            )
        )
        actions.append(
            _build_action(
                action_type="call_script",
                claim_ids=ids,
                trigger=TRIGGER_NO_RESPONSE,
                title="Bureau call outline",
                summary_safe="Use when calling the bureau about non-response or verification.",
                priority=15,
                call_audience="bureau",
            )
        )

    # repeated verified → MOV-heavy + CFPB + furnisher script
    rv = sorted(triggers.get(TRIGGER_REPEATED_VERIFIED) or [])
    if rv:
        actions.append(
            _build_action(
                action_type="method_of_verification",
                claim_ids=rv,
                trigger=TRIGGER_REPEATED_VERIFIED,
                title="Challenge repeated verification",
                summary_safe=(
                    "Multiple bureau responses verified the same items; request detailed "
                    "method-of-verification and reinvestigation."
                ),
                priority=10,
            )
        )
        actions.append(
            _build_action(
                action_type="cfpb_complaint",
                claim_ids=rv,
                trigger=TRIGGER_REPEATED_VERIFIED,
                title="CFPB / regulatory path",
                summary_safe=(
                    "Pattern of verify-without-deletion may support escalation after MOV requests "
                    "are documented."
                ),
                priority=25,
            )
        )
        actions.append(
            _build_action(
                action_type="call_script",
                claim_ids=rv,
                trigger=TRIGGER_REPEATED_VERIFIED,
                title="Furnisher call outline",
                summary_safe="Script for contacting the furnisher after repeated bureau verification.",
                priority=18,
                call_audience="furnisher",
            )
        )

    # insufficient partial updates
    iu = sorted(triggers.get(TRIGGER_INSUFFICIENT_UPDATE) or set())
    if iu:
        actions.append(
            _build_action(
                action_type="method_of_verification",
                claim_ids=list(iu),
                trigger=TRIGGER_INSUFFICIENT_UPDATE,
                title="MOV after partial update",
                summary_safe=(
                    "Bureau updated some fields but left negative or disputed data; request "
                    "verification method for what remains."
                ),
                priority=12,
            )
        )
        actions.append(
            _build_action(
                action_type="furnisher_dispute",
                claim_ids=list(iu),
                trigger=TRIGGER_INSUFFICIENT_UPDATE,
                title="Furnisher follow-up",
                summary_safe=(
                    "Parallel furnisher dispute can address incomplete bureau corrections."
                ),
                priority=22,
            )
        )

    actions.sort(key=lambda x: (x.get("priority") or 99, x.get("id") or ""))
    return actions


def compute_escalation_block(ds: Dict[str, Any]) -> Dict[str, Any]:
    triggers_map = collect_escalation_triggers(ds)
    triggers_fired = sorted({k for k, v in triggers_map.items() if v})
    actions = build_escalation_actions_from_triggers(triggers_map)
    status = STATUS_ACTION_REQUIRED if actions else STATUS_NONE
    return {
        "escalation_status": status,
        "escalation_actions": actions,
        "escalation_triggers": triggers_fired,
        "escalation_trigger_claims": {
            k: sorted(v) for k, v in triggers_map.items() if v
        },
        "escalation_computed_at": datetime.now(timezone.utc).isoformat(),
    }


def apply_escalation_fields_to_ds(ds: Dict[str, Any]) -> Dict[str, Any]:
    block = compute_escalation_block(ds)
    ds = dict(ds)
    ds["escalation_status"] = block["escalation_status"]
    ds["escalation_actions"] = block["escalation_actions"]
    ds["escalation_triggers"] = block["escalation_triggers"]
    ds["escalation_trigger_claims"] = block["escalation_trigger_claims"]
    ds["escalation_computed_at"] = block["escalation_computed_at"]
    return ds


def recompute_escalation_for_workflow(workflow_id: str) -> None:
    """Refresh escalation_* keys from current ``dispute_selection`` (call after outcomes change)."""

    def _mut(meta: Dict[str, Any]) -> None:
        if meta.get("dispute_selection") is None:
            return
        ds = _ds_from_meta(meta)
        meta["dispute_selection"] = apply_escalation_fields_to_ds(ds)

    merge_into_workflow_metadata(workflow_id, _mut)


def escalation_public_view(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Always derived from current ``dispute_selection`` (same rules as persisted snapshot).
    """
    ds = _ds_from_meta(meta)
    block = compute_escalation_block(ds)
    return {
        "status": block["escalation_status"],
        "actions": block["escalation_actions"],
        "triggers": block["escalation_triggers"],
        "triggerClaims": block["escalation_trigger_claims"],
        "computedAt": block["escalation_computed_at"],
    }


def escalation_summary_for_progression(meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Small slice for ``canonicalProgression.context``."""
    ev = escalation_public_view(meta)
    if ev.get("status") == STATUS_NONE and not ev.get("actions"):
        return None
    acts = ev.get("actions") or []
    primary_type = None
    primary_id = None
    if acts:
        first = acts[0] or {}
        primary_type = str(first.get("type") or "")
        primary_id = str(first.get("id") or "").strip() or None
    return {
        "status": ev.get("status"),
        "actionCount": len(acts),
        "primaryActionType": primary_type,
        "primaryActionId": primary_id,
        "triggers": ev.get("triggers") or [],
    }
