"""
S4 — org program participant: dispute options, selection persistence, letter generation.

Reuses ``customer_dispute_strategy`` eligibility/validation and ``process_dispute_pipeline``.
Selections are stored per (user_id, report_id), not workflow metadata.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import auth
import database as db
from claims import extract_claims
from review_claims import ReviewClaim, ReviewType, compress_claims
from services.customer_dispute_strategy import (
    estimate_unique_bureaus_for_claims,
    filter_eligible_dispute_items,
    free_mode_bureau_cap_violation,
    validate_selected_against_eligible,
)
from services.customer_letter_service import serialize_letter_row
from services.dispute_pipeline import process_dispute_pipeline
from dispute_strategy import build_deterministic_strategy

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


def resolve_report_id_for_participant(user_id: int, report_id: Optional[int]) -> Optional[int]:
    if report_id is not None:
        row = db.get_report(int(report_id), user_id=user_id)
        return int(row["id"]) if row else None
    rows = db.get_recent_reports_with_parsed_for_user(user_id, limit=1)
    return int(rows[0]["id"]) if rows else None


def load_compressed_review_claims_for_report(user_id: int, report_id: int) -> List[ReviewClaim]:
    row = db.get_report(report_id, user_id=user_id)
    if not row:
        return []
    pd = _parsed_dict(row.get("parsed_data"))
    bureau = (row.get("bureau") or "unknown").lower()
    try:
        raw = extract_claims(pd, bureau)
    except Exception as exc:
        _log.warning("extract_claims failed for report %s: %s", report_id, exc)
        return []
    return compress_claims(raw)


def build_program_dispute_options(
    user_id: int,
    report_id: Optional[int],
    *,
    session_user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Dispute-ready options for one report (same grouping shape as workflow ``disputeStrategy``).
    """
    rid = resolve_report_id_for_participant(user_id, report_id)
    if rid is None:
        return {
            "reportId": None,
            "selectionAllowed": False,
            "selectionBlockedReason": "No credit report found. Upload a report first.",
            "disputeStrategy": None,
        }

    claims = load_compressed_review_claims_for_report(user_id, rid)
    eligible = filter_eligible_dispute_items(
        claims, round_number=1, previously_disputed_ids=set()
    )
    eligible_by_id = {rc.review_claim_id: rc for rc in eligible}

    if not eligible:
        return {
            "reportId": rid,
            "selectionAllowed": False,
            "selectionBlockedReason": "No eligible dispute items on this report for round 1.",
            "disputeStrategy": None,
        }

    round_size = min(10, max(1, len(eligible)))
    det = build_deterministic_strategy(eligible, round_size=round_size, excluded_ids=[])
    suggested_ids = (
        [sc.review_claim.review_claim_id for sc in det.selected_claims] if det else []
    )

    saved = get_program_dispute_selections(user_id, rid)
    saved_ids = saved.get("selectedReviewClaimIds") if saved else None
    if isinstance(saved_ids, list) and saved_ids:
        default_selected = [str(x) for x in saved_ids if str(x) in eligible_by_id]
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
        "reportId": rid,
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


def get_program_dispute_selections(user_id: int, report_id: int) -> Optional[Dict[str, Any]]:
    with db.get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, user_id, report_id, organization_program_enrollment_id,
                   selected_review_claim_ids, created_at, updated_at
            FROM organization_program_dispute_selections
            WHERE user_id = %s AND report_id = %s
            """,
            (user_id, report_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    raw_ids = d.get("selected_review_claim_ids")
    if isinstance(raw_ids, str):
        try:
            raw_ids = json.loads(raw_ids)
        except Exception:
            raw_ids = []
    if not isinstance(raw_ids, list):
        raw_ids = []
    d["selectedReviewClaimIds"] = [str(x) for x in raw_ids if str(x).strip()]
    return d


def save_program_dispute_selections(
    user_id: int,
    report_id: int,
    organization_program_enrollment_id: Optional[int],
    selected_ids: List[str],
) -> Dict[str, Any]:
    row = db.get_report(report_id, user_id=user_id)
    if not row:
        return {"error": "Report not found or access denied."}

    claims = load_compressed_review_claims_for_report(user_id, report_id)
    eligible = filter_eligible_dispute_items(
        claims, round_number=1, previously_disputed_ids=set()
    )
    eligible_by_id = {rc.review_claim_id: rc for rc in eligible}
    eligible_ids = set(eligible_by_id.keys())
    ids = [str(x).strip() for x in selected_ids if str(x).strip()]
    ok, err = validate_selected_against_eligible(ids, eligible_ids)
    if not ok:
        return {"error": err}
    if not ids:
        return {"error": "Select at least one item."}

    payload = json.dumps(ids)
    with db.get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO organization_program_dispute_selections (
                user_id, report_id, organization_program_enrollment_id,
                selected_review_claim_ids, updated_at
            )
            VALUES (%s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, report_id) DO UPDATE SET
                selected_review_claim_ids = EXCLUDED.selected_review_claim_ids,
                organization_program_enrollment_id = EXCLUDED.organization_program_enrollment_id,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id, user_id, report_id, selected_review_claim_ids, updated_at
            """,
            (user_id, report_id, organization_program_enrollment_id, payload),
        )
        out = dict(cur.fetchone())
        conn.commit()
    out["selectedReviewClaimIds"] = ids
    return out


def build_program_pipeline_context(
    user_id: int,
    report_id: int,
    selected_ids: List[str],
    *,
    is_admin: bool,
) -> Tuple[Dict[str, Any], List[ReviewClaim], str]:
    """Single-report context for ``process_dispute_pipeline`` (no workflow session)."""
    row = db.get_report(report_id, user_id=user_id)
    if not row:
        return {}, [], "no_reports"

    snapshot_key = f"r{report_id}"
    pd = _parsed_dict(row.get("parsed_data"))
    bureau = (row.get("bureau") or "unknown").lower()
    uploaded_reports: Dict[str, Any] = {
        snapshot_key: {
            "bureau": bureau,
            "parsed_data": pd,
            "report_id": report_id,
        }
    }
    extracted_claims: Dict[str, Any] = {}
    identity_confirmed: Dict[str, bool] = {bureau: True}
    try:
        claims = extract_claims(pd, bureau)
        extracted_claims[snapshot_key] = claims
    except Exception as exc:
        _log.warning("extract_claims failed: %s", exc)
        return {}, [], "no_reports"

    review_claims_list = compress_claims(claims)
    by_id = {rc.review_claim_id: rc for rc in review_claims_list}
    selected: List[ReviewClaim] = []
    for sid in selected_ids:
        rc = by_id.get(str(sid).strip())
        if rc:
            selected.append(rc)
    if not selected:
        return {}, [], "selection_not_found"

    ent = auth.get_entitlements(user_id)
    letters_bal = int(ent.get("letters", 0) or 0)
    bureaus = estimate_unique_bureaus_for_claims(by_id, [rc.review_claim_id for rc in selected])
    letter_deduct = max(1, min(len(bureaus), 12)) if bureaus else 1

    ctx: Dict[str, Any] = {
        "uploaded_reports": uploaded_reports,
        "extracted_claims": extracted_claims,
        "identity_confirmed": identity_confirmed,
        "review_claim_responses": {},
        "review_claims_list": review_claims_list,
        "round_number": 1,
        "user_id": user_id,
        "is_admin_user": is_admin,
        "persist_letters": True,
        "apply_letter_billing": True,
        "letter_count_to_deduct": letter_deduct,
        "current_letters_balance": letters_bal,
        "is_free_generation": False,
        "free_item_count": 0,
        "free_max_capacity": 0,
    }
    return ctx, selected, ""


def run_program_letter_generation(
    user_id: int,
    report_id: int,
    *,
    is_admin: bool,
    session_user: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Run ``process_dispute_pipeline`` from saved program selections; does not touch workflow steps.
    """
    saved = get_program_dispute_selections(user_id, report_id)
    if not saved:
        return {}, "No saved dispute selection for this report."
    ids = saved.get("selectedReviewClaimIds") or []
    if not ids:
        return {}, "No saved dispute selection for this report."

    claims = load_compressed_review_claims_for_report(user_id, report_id)
    eligible = filter_eligible_dispute_items(
        claims, round_number=1, previously_disputed_ids=set()
    )
    eligible_by_id = {rc.review_claim_id: rc for rc in eligible}
    ok, err = validate_selected_against_eligible(ids, set(eligible_by_id.keys()))
    if not ok:
        return {}, err

    user = session_user or {}
    is_adm = is_admin or auth.is_admin(user)
    ent = auth.get_entitlements(user_id)
    letters_balance = int(ent.get("letters", 0) or 0)
    has_used_free = auth.has_used_free_letters(user_id) if not is_adm else False
    using_free_mode = not is_adm and letters_balance == 0 and not has_used_free
    cap_msg = free_mode_bureau_cap_violation(
        eligible_by_id, ids, using_free_mode=using_free_mode
    )
    if cap_msg:
        return {}, cap_msg

    ctx, selected, err_code = build_program_pipeline_context(
        user_id, report_id, ids, is_admin=is_adm
    )
    if err_code:
        if err_code == "no_reports":
            return {}, "No parsed credit report found."
        return {}, "Saved dispute items no longer match this report."

    result = process_dispute_pipeline(selected, ctx)
    if result.get("error"):
        code = result["error"]
        if code == "blocked":
            return result, "No items passed readiness for letter generation."
        if code == "no_letters":
            return result, "Letter generation produced no bureau letters (blocked or filtered)."
        if code == "no_selected_claims":
            return result, "No claims to generate from."
        return result, f"Letter generation could not complete ({code})."

    billing = result.get("billing") or {}
    if billing.get("letter_spend_failed"):
        return result, "Not enough letter credits to generate (or free-letter rules failed)."

    letters_out = result.get("letters") or {}
    if not letters_out:
        return result, "No letters were saved."

    all_rows = db.get_all_letters_for_user(user_id)
    fresh = [r for r in all_rows if int(r.get("report_id") or 0) == int(report_id)]
    fresh.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    serialized = [serialize_letter_row(r) for r in fresh[:20]]

    return {
        **result,
        "_serialized_letters": serialized,
        "_selected_item_count": len(selected),
    }, None


def get_dispute_selections_response(user_id: int, report_id: Optional[int]) -> Dict[str, Any]:
    rid = resolve_report_id_for_participant(user_id, report_id)
    if rid is None:
        return {"reportId": None, "selectedReviewClaimIds": [], "updatedAt": None}
    saved = get_program_dispute_selections(user_id, rid)
    if not saved:
        return {"reportId": rid, "selectedReviewClaimIds": [], "updatedAt": None}
    return {
        "reportId": rid,
        "selectedReviewClaimIds": saved.get("selectedReviewClaimIds") or [],
        "updatedAt": saved.get("updated_at"),
    }
