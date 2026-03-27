"""
Dispute strategy / selection payload for the React workflow API.

Eligibility rules mirror ``app.py`` DISPUTES (round 1, high-confidence claims, etc.).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import auth
import database as db
from claims import extract_claims
from dispute_strategy import build_deterministic_strategy
from review_claims import ReviewClaim, ReviewType, compress_claims
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


def load_compressed_review_claims_for_user(user_id: int, *, report_limit: int = 25) -> List[ReviewClaim]:
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


def filter_eligible_dispute_items(
    review_claims: List[ReviewClaim],
    *,
    round_number: int = 1,
    previously_disputed_ids: Optional[Set[str]] = None,
) -> List[ReviewClaim]:
    prev = previously_disputed_ids or set()
    eligible: List[ReviewClaim] = []
    seen: Set[str] = set()
    for rc in review_claims:
        if rc.review_type == ReviewType.IDENTITY_VERIFICATION:
            continue
        if round_number == 1 and rc.review_type == ReviewType.ACCOUNT_OWNERSHIP:
            continue
        if rc.review_claim_id in prev:
            continue
        if rc.review_claim_id in seen:
            continue
        conf = (
            rc.evidence_summary.claim_confidence_summary if rc.evidence_summary else None
        )
        if not conf or conf.high == 0:
            continue
        seen.add(rc.review_claim_id)
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


def previously_disputed_claim_ids_from_meta(meta: Dict[str, Any]) -> Set[str]:
    ds = meta.get("dispute_selection") or {}
    raw = ds.get("previously_disputed_claim_ids") or []
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw if x}


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
        return {
            "selectionAllowed": False,
            "selectionBlockedReason": (
                "This step is not available yet, or this workflow has already moved past dispute selection."
                if head != "select_disputes"
                else "This workflow is already complete."
            ),
            "disputeStrategy": None,
        }

    claims = load_compressed_review_claims_for_user(user_id)
    sess = fetch_session(workflow_id)
    meta = parse_workflow_metadata_value(sess.get("metadata") if sess else {})
    prev = previously_disputed_claim_ids_from_meta(meta)
    eligible = filter_eligible_dispute_items(
        claims, round_number=1, previously_disputed_ids=prev
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

    return {
        "selectionAllowed": True,
        "selectionBlockedReason": None,
        "disputeStrategy": {
            "roundNumber": 1,
            "eligibleCount": len(eligible),
            "groups": groups,
            "eligibleReviewClaimIds": list(eligible_by_id.keys()),
            "defaultSelectedReviewClaimIds": default_selected,
            "suggestedReviewClaimIds": suggested_ids,
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
