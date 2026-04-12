"""
Dispute strategy / selection payload for the React workflow API.

Eligibility: high-confidence claims; round 1 excludes ownership-only posture; later rounds
also re-include previously disputed items unless ``claim_outcomes`` marks them resolved
(``deleted`` or ``verified``).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Final, List, Optional, Set, Tuple

import auth
import database as db
from claims import extract_claims
from dispute_strategy import build_deterministic_strategy
from review_claims import ReviewClaim, ReviewType, compress_claims
from services.law_bank.resolve import resolve_law_units
from services.law_bank.schema import LAW_RESOLUTION_CONTEXT_SCHEMA_VERSION
from services.workflow.dispute_round_execution import (
    normalize_bureau_item_outcome,
    round_execution_public_view,
)
from services.workflow.observability_events import emit_observability_event
from services.workflow.escalation_engine import escalation_public_view
from services.workflow.engine import compute_authoritative_step
from services.workflow.repository import fetch_session, fetch_steps

_log = logging.getLogger(__name__)

_TYPE_ORDER = [
    ReviewType.NEGATIVE_IMPACT,
    ReviewType.ACCURACY_VERIFICATION,
    ReviewType.DUPLICATE_ACCOUNT,
    ReviewType.UNVERIFIABLE_INFORMATION,
    ReviewType.ACCOUNT_OWNERSHIP,
]


def _parsed_dict(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def load_compressed_review_claims_for_user(
    user_id: int,
    *,
    report_limit: int = 25,
    only_report_ids: Optional[List[int]] = None,
) -> List[ReviewClaim]:
    if only_report_ids is not None:
        rows = db.get_reports_with_parsed_for_user_by_ids(user_id, only_report_ids)
    else:
        rows = db.get_recent_reports_with_parsed_for_user(user_id, limit=report_limit)
    all_raw: List[Any] = []
    for row in rows:
        pd = _parsed_dict(row.get("parsed_data"))
        bureau = (row.get("bureau") or "unknown").lower()
        rid = row.get("id")
        try:
            all_raw.extend(extract_claims(pd, bureau))
        except Exception as exc:
            _log.warning("extract_claims failed for report %s: %s", rid, exc)
    return compress_claims(all_raw)


# User- or operator-supplied per-claim outcomes (see response intake ``claim_outcomes`` /
# ``item_outcomes``). Normalized buckets: deleted | updated | verified | no_response.
# Only deleted + verified remove an item from the next round pool; updated / no_response stay eligible.
RESOLVED_DISPUTE_OUTCOMES: Final = frozenset({"deleted", "verified"})


def filter_eligible_dispute_items(
    review_claims: List[ReviewClaim],
    *,
    round_number: int = 1,
    cumulative_disputed_ids: Optional[Set[str]] = None,
    claim_outcomes: Optional[Dict[str, str]] = None,
    previously_disputed_ids: Optional[Set[str]] = None,
) -> List[ReviewClaim]:
    """
    Eligible items for the current dispute round.

    * Never disputed: same high-confidence rules as round 1 (ownership excluded on round 1 only).
    * Previously disputed: included unless ``claim_outcomes[id]`` is a resolved bucket
      (``deleted`` or ``verified``). Missing outcome ⇒ still in play (unresolved).
    """
    cumulative = cumulative_disputed_ids
    if cumulative is None:
        cumulative = previously_disputed_ids or set()
    outcomes = claim_outcomes or {}
    eligible: List[ReviewClaim] = []
    seen: Set[str] = set()
    for rc in review_claims:
        if rc.review_type == ReviewType.IDENTITY_VERIFICATION:
            continue
        cid = rc.review_claim_id
        if cid in cumulative:
            oc = (outcomes.get(cid) or "").strip().lower()
            if oc in RESOLVED_DISPUTE_OUTCOMES:
                continue
        elif round_number == 1 and rc.review_type == ReviewType.ACCOUNT_OWNERSHIP:
            continue
        if cid in seen:
            continue
        conf = (
            rc.evidence_summary.claim_confidence_summary if rc.evidence_summary else None
        )
        if not conf or conf.high == 0:
            continue
        seen.add(cid)
        eligible.append(rc)
    return eligible


def _steps_map(workflow_id: str) -> Dict[str, Dict[str, Any]]:
    steps = fetch_steps(workflow_id)
    return {s["step_id"]: s for s in steps}


def workflow_head_step_id(workflow_id: str) -> Tuple[Optional[str], str]:
    smap = _steps_map(workflow_id)
    return compute_authoritative_step(smap)


def parse_workflow_metadata_value(meta: Any) -> Dict[str, Any]:
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return dict(meta)
    if isinstance(meta, str):
        try:
            return json.loads(meta)
        except Exception:
            return {}
    return {}


def cumulative_disputed_review_claim_ids_from_meta(meta: Dict[str, Any]) -> Set[str]:
    ds = meta.get("dispute_selection") or {}
    if not isinstance(ds, dict):
        return set()
    raw = ds.get("cumulative_disputed_review_claim_ids")
    if isinstance(raw, list):
        return {str(x) for x in raw if x}
    raw2 = ds.get("previously_disputed_claim_ids") or []
    if isinstance(raw2, list):
        return {str(x) for x in raw2 if x}
    return set()


def previously_disputed_claim_ids_from_meta(meta: Dict[str, Any]) -> Set[str]:
    """Alias: ids selected in any dispute round (legacy metadata key supported)."""
    return cumulative_disputed_review_claim_ids_from_meta(meta)


def dispute_round_number_from_meta(meta: Dict[str, Any]) -> int:
    ds = meta.get("dispute_selection") or {}
    if not isinstance(ds, dict):
        return 1
    try:
        return max(1, int(ds.get("dispute_round_number") or 1))
    except (TypeError, ValueError):
        return 1


def claim_outcomes_from_meta(meta: Dict[str, Any]) -> Dict[str, str]:
    ds = meta.get("dispute_selection") or {}
    if not isinstance(ds, dict):
        return {}
    raw = ds.get("claim_outcomes") or {}
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in raw.items():
        if k is None or v is None:
            continue
        key = str(k).strip()
        if not key:
            continue
        out[key] = normalize_bureau_item_outcome(str(v).strip().lower())
    return out


def dispute_selection_context_from_meta(meta: Dict[str, Any]) -> Tuple[int, Set[str], Dict[str, str]]:
    return (
        dispute_round_number_from_meta(meta),
        cumulative_disputed_review_claim_ids_from_meta(meta),
        claim_outcomes_from_meta(meta),
    )


def _subject_matter_tags_present_for_law(eligible: List[ReviewClaim]) -> List[str]:
    """Structured tags only — no note text or free-form mining."""
    tags: Set[str] = set()
    for rc in eligible:
        rt = rc.review_type
        if rt in (
            ReviewType.ACCURACY_VERIFICATION,
            ReviewType.DUPLICATE_ACCOUNT,
            ReviewType.UNVERIFIABLE_INFORMATION,
            ReviewType.NEGATIVE_IMPACT,
        ):
            tags.add("accuracy")
            tags.add("investigation")
        if rt == ReviewType.NEGATIVE_IMPACT:
            tags.add("collection_conduct")
        if rt == ReviewType.ACCOUNT_OWNERSHIP:
            tags.add("ownership")
            if "inquiry_" in (rc.review_claim_id or ""):
                tags.add("inquiry")
    return sorted(tags)


def _has_bureau_target(eligible: List[ReviewClaim]) -> bool:
    if not eligible:
        return False
    return any(bool((rc.entities.get("bureau") or "").strip()) for rc in eligible)


def _has_furnisher_target(eligible: List[ReviewClaim], actions: List[Dict[str, Any]]) -> bool:
    if any(a.get("type") == "furnisher_dispute" for a in actions):
        return True
    for rc in eligible:
        if rc.review_type in (
            ReviewType.ACCURACY_VERIFICATION,
            ReviewType.DUPLICATE_ACCOUNT,
            ReviewType.NEGATIVE_IMPACT,
            ReviewType.UNVERIFIABLE_INFORMATION,
        ):
            return True
    return False


def _identity_context_from_claims(claims: List[ReviewClaim]) -> bool:
    return any(rc.review_type == ReviewType.IDENTITY_VERIFICATION for rc in claims)


def _has_collection_account_signals(eligible: List[ReviewClaim]) -> bool:
    return any(rc.review_type == ReviewType.NEGATIVE_IMPACT for rc in eligible)


def _has_inquiry_signals(eligible: List[ReviewClaim]) -> bool:
    for rc in eligible:
        if rc.review_type == ReviewType.ACCOUNT_OWNERSHIP and "inquiry_" in (
            rc.review_claim_id or ""
        ):
            return True
    return False


def build_law_resolution_context(
    *,
    claims: List[ReviewClaim],
    eligible: List[ReviewClaim],
    dispute_round: int,
    authoritative_step_id: Optional[str],
    escalation_view: Dict[str, Any],
) -> Dict[str, Any]:
    actions = [
        a for a in (escalation_view.get("actions") or []) if isinstance(a, dict)
    ]
    has_esc = bool(actions)
    tags = _subject_matter_tags_present_for_law(eligible)
    identity_ctx = _identity_context_from_claims(claims)
    op_cfpb = any(a.get("type") == "cfpb_complaint" for a in actions)
    return {
        "schemaVersion": LAW_RESOLUTION_CONTEXT_SCHEMA_VERSION,
        "disputeRound": int(dispute_round),
        "authoritativeStepId": str(authoritative_step_id or ""),
        "hasBureauTarget": _has_bureau_target(eligible),
        "hasFurnisherTarget": _has_furnisher_target(eligible, actions),
        "identityContext": identity_ctx,
        "escalationEligible": has_esc,
        "hasCollectionAccountSignals": _has_collection_account_signals(eligible),
        "hasInquirySignals": _has_inquiry_signals(eligible),
        "subjectMatterTagsPresent": tags,
        "outcomePatternFlags": {
            "op_dispute_round_active": dispute_round >= 1,
            "op_escalation_signal_present": has_esc,
            "op_eligible_pool_non_empty": len(eligible) > 0,
            "op_collections_signal": _has_collection_account_signals(eligible),
            "op_cfpb_action_available": op_cfpb,
            "op_identity_context": identity_ctx,
        },
    }


def build_dispute_strategy_payload(
    user_id: int,
    workflow_id: str,
    *,
    session_user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Returns disputeStrategy dict plus flags; caller merges with workflow resume envelope.
    """
    head, phase = workflow_head_step_id(workflow_id)
    if phase == "done" or head != "select_disputes":
        emit_observability_event(
            user_id=user_id,
            workflow_id=workflow_id,
            step_id=str(head or "")[:64] or None,
            event_name="strategy_generated",
            event_category="processing",
            status="info",
            metadata={"selectionAllowed": False},
            source="strategy",
        )
        return {
            "selectionAllowed": False,
            "selectionBlockedReason": (
                "This step is not available yet, or this workflow has already moved past dispute selection."
                if head != "select_disputes"
                else "This workflow is already complete."
            ),
            "disputeStrategy": None,
            "lawContextRefs": [],
        }

    claims = load_compressed_review_claims_for_user(user_id)
    sess = fetch_session(workflow_id)
    meta = parse_workflow_metadata_value(sess.get("metadata") if sess else {})
    rnd, cumulative, outcomes = dispute_selection_context_from_meta(meta)
    eligible = filter_eligible_dispute_items(
        claims,
        round_number=rnd,
        cumulative_disputed_ids=cumulative,
        claim_outcomes=outcomes,
    )

    eligible_by_id = {rc.review_claim_id: rc for rc in eligible}

    round_size = min(10, max(1, len(eligible))) if eligible else 1
    det = (
        build_deterministic_strategy(eligible, round_size=round_size, excluded_ids=[])
        if eligible
        else None
    )
    suggested_ids = (
        [sc.review_claim.review_claim_id for sc in det.selected_claims] if det else []
    )

    ds_meta = meta.get("dispute_selection") or {}
    draft = ds_meta.get("draft_selected_review_claim_ids")
    if isinstance(draft, list) and draft:
        default_selected = [str(x) for x in draft if str(x) in eligible_by_id]
    else:
        default_selected = [rc.review_claim_id for rc in eligible]

    groups: List[Dict[str, Any]] = []
    for rt in _TYPE_ORDER:
        items = [rc for rc in eligible if rc.review_type == rt]
        if not items:
            continue
        groups.append(
            {
                "reviewType": rt.value,
                "items": [rc.to_dict() for rc in items],
            }
        )

    user = session_user or {}
    is_admin = auth.is_admin(user)
    ent = auth.get_entitlements(user_id) if user_id else {}
    letters_balance = int(ent.get("letters", 0) or 0)
    has_used_free = auth.has_used_free_letters(user_id) if user_id and not is_admin else False
    using_free_mode = not is_admin and letters_balance == 0 and not has_used_free

    esc = escalation_public_view(meta)
    has_esc = bool(esc.get("actions"))

    law_ctx = build_law_resolution_context(
        claims=claims,
        eligible=eligible,
        dispute_round=rnd,
        authoritative_step_id=head,
        escalation_view=esc,
    )
    law_refs = resolve_law_units(law_ctx)
    path_guidance = (
        "escalation_and_next_round"
        if has_esc and len(eligible) > 0
        else "escalation_focus"
        if has_esc
        else "next_round_primary"
    )
    from services.workflow.escalation_ux_payload import build_program_escalation_ux_payload

    program_escalation = build_program_escalation_ux_payload(user_id, meta)

    emit_observability_event(
        user_id=user_id,
        workflow_id=workflow_id,
        step_id=str(head or "")[:64] or None,
        event_name="strategy_generated",
        event_category="processing",
        status="success",
        metadata={
            "selectionAllowed": True,
            "eligibleCount": len(eligible),
            "roundNumber": rnd,
        },
        source="strategy",
    )
    if has_esc:
        tr_raw = esc.get("triggers") or []
        triggers = [str(x) for x in tr_raw if x is not None][:16]
        emit_observability_event(
            user_id=user_id,
            workflow_id=workflow_id,
            step_id=str(head or "")[:64] or None,
            event_name="escalation_triggered",
            event_category="decision",
            status="info",
            metadata={
                "actionCount": len(esc.get("actions") or []),
                "triggers": triggers,
            },
            source="strategy",
        )

    return {
        "selectionAllowed": True,
        "selectionBlockedReason": None,
        "lawContextRefs": law_refs,
        "escalationGuide": {
            "pathGuidance": path_guidance,
            "escalation": esc,
            "programEscalation": program_escalation,
            "nextRoundDispute": {
                "eligibleItemCount": len(eligible),
                "summarySafe": (
                    "Continue the in-app dispute letter cycle for this same workflow when "
                    "you are ready for another bureau mailing round."
                ),
            },
            "differentiationNote": (
                "Escalation actions (MOV, furnisher, CFPB, call outlines) are parallel "
                "next steps outside or alongside the next bureau letter round; they do "
                "not replace the canonical workflow engine."
            ),
        },
        "disputeStrategy": {
            "roundNumber": rnd,
            "eligibleCount": len(eligible),
            "groups": groups,
            "eligibleReviewClaimIds": list(eligible_by_id.keys()),
            "defaultSelectedReviewClaimIds": default_selected,
            "suggestedReviewClaimIds": suggested_ids,
            "roundExecution": round_execution_public_view(meta),
            "escalationRecommendations": esc,
            "deterministic": (
                {
                    "source": det.source,
                    "rationale": det.rationale,
                    "roundSummary": det.round_summary,
                }
                if det
                else None
            ),
            "constraints": {
                "freePerBureauLimit": auth.FREE_PER_BUREAU_LIMIT,
                "lettersBalance": letters_balance,
                "isAdmin": is_admin,
                "usingFreeMode": using_free_mode,
                "hasUsedFreeLetters": has_used_free,
            },
        },
    }


def validate_selected_against_eligible(
    selected_ids: List[str],
    eligible_ids: Set[str],
) -> Tuple[bool, str]:
    seen: Set[str] = set()
    for rid in selected_ids:
        s = str(rid).strip()
        if not s:
            return False, "Empty review claim id in selection."
        if s in seen:
            return False, "Duplicate review claim id in selection."
        seen.add(s)
        if s not in eligible_ids:
            return False, f"Not an eligible item: {s}"
    return True, ""


def estimate_unique_bureaus_for_claims(
    claims_by_id: Dict[str, ReviewClaim],
    selected_ids: List[str],
) -> List[str]:
    bureaus: Set[str] = set()
    for rid in selected_ids:
        rc = claims_by_id.get(str(rid))
        if not rc:
            continue
        b = (rc.entities.get("bureau") or "").strip().lower()
        if b:
            bureaus.add(b)
    return sorted(bureaus)


def save_dispute_selection_draft(workflow_id: str, draft_ids: List[str]) -> None:
    """Persist draft checkboxes under ``metadata.dispute_selection`` (merge-safe)."""
    from services.workflow.repository import merge_into_workflow_metadata

    capped = [str(x) for x in draft_ids[:500]]

    def _mut(meta: Dict[str, Any]) -> None:
        ds = meta.get("dispute_selection")
        if not isinstance(ds, dict):
            ds = {}
        else:
            ds = dict(ds)
        ds["draft_selected_review_claim_ids"] = capped
        meta["dispute_selection"] = ds

    merge_into_workflow_metadata(workflow_id, _mut)


def free_mode_bureau_cap_violation(
    claims_by_id: Dict[str, ReviewClaim],
    selected_ids: List[str],
    *,
    using_free_mode: bool,
) -> Optional[str]:
    """Mirror Streamlit free plan: max items per bureau (``auth.FREE_PER_BUREAU_LIMIT``)."""
    if not using_free_mode:
        return None
    per_bureau: Dict[str, int] = {}
    for rid in selected_ids:
        rc = claims_by_id.get(str(rid))
        if not rc:
            continue
        b = (rc.entities.get("bureau") or "unknown").strip().lower() or "unknown"
        per_bureau[b] = per_bureau.get(b, 0) + 1
    for b, c in per_bureau.items():
        if c > auth.FREE_PER_BUREAU_LIMIT:
            return (
                f"Free plan allows up to {auth.FREE_PER_BUREAU_LIMIT} items per bureau; "
                f"{b.title()} has {c} selected."
            )
    return None
