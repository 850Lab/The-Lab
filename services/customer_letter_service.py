"""
Rebuild dispute pipeline context from DB + workflow metadata for React letter generation.

Uses ``services.dispute_pipeline.process_dispute_pipeline`` (same orchestration as Streamlit GENERATING).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import auth
import database as db
from claims import extract_claims
from review_claims import ReviewClaim, compress_claims
from services.customer_dispute_strategy import (
    dispute_round_number_from_meta,
    parse_workflow_metadata_value,
)
from services.dispute_pipeline import process_dispute_pipeline
from services.workflow import hooks as workflow_hooks
from services.workflow.engine import compute_authoritative_step
from services.workflow.repository import fetch_steps
from services.customer_dispute_strategy import estimate_unique_bureaus_for_claims
from services.workflow_payment_service import needed_letters_from_workflow_session

_log = logging.getLogger(__name__)


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


def selected_review_claim_ids_from_workflow(session_row: Optional[Dict[str, Any]]) -> List[str]:
    if not session_row:
        return []
    meta = parse_workflow_metadata_value(session_row.get("metadata"))
    ds = meta.get("dispute_selection") or {}
    if not isinstance(ds, dict):
        return []
    raw = ds.get("selected_review_claim_ids") or []
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def build_pipeline_context_for_user(
    user_id: int,
    workflow_id: str,
    *,
    session_row: Optional[Dict[str, Any]],
    is_admin: bool,
    only_report_ids: Optional[List[int]] = None,
) -> Tuple[Dict[str, Any], List[ReviewClaim], str]:
    """
    Returns (context_dict, selected_review_claims, error_code).
    error_code empty on success.

    ``only_report_ids`` limits DB reads to those report rows (must belong to ``user_id``).
    Used by the public fixture demo so letter/plan context cannot pull other reports on the same user.
    """
    if only_report_ids is not None:
        rows = db.get_reports_with_parsed_for_user_by_ids(user_id, only_report_ids)
    else:
        rows = db.get_recent_reports_with_parsed_for_user(user_id, limit=25)
    if not rows:
        return {}, [], "no_reports"

    uploaded_reports: Dict[str, Any] = {}
    extracted_claims: Dict[str, Any] = {}
    identity_confirmed: Dict[str, bool] = {}

    all_raw: List[Any] = []
    for row in rows:
        rid = row.get("id")
        snapshot_key = f"r{rid}"
        pd = _parsed_dict(row.get("parsed_data"))
        bureau = (row.get("bureau") or "unknown").lower()
        uploaded_reports[snapshot_key] = {
            "bureau": bureau,
            "parsed_data": pd,
            "report_id": rid,
        }
        identity_confirmed[bureau] = True
        try:
            claims = extract_claims(pd, bureau)
            extracted_claims[snapshot_key] = claims
            all_raw.extend(claims)
        except Exception as exc:
            _log.warning("extract_claims failed for report %s: %s", rid, exc)

    review_claims_list: List[ReviewClaim] = compress_claims(all_raw)
    by_id = {rc.review_claim_id: rc for rc in review_claims_list}

    sel_ids = selected_review_claim_ids_from_workflow(session_row)
    if not sel_ids:
        return {}, [], "no_selection"

    selected: List[ReviewClaim] = []
    for sid in sel_ids:
        rc = by_id.get(sid)
        if rc:
            selected.append(rc)
    if not selected:
        return {}, [], "selection_not_found"

    ent = auth.get_entitlements(user_id)
    letters_bal = int(ent.get("letters", 0) or 0)
    needed = needed_letters_from_workflow_session(session_row)
    meta = parse_workflow_metadata_value(session_row.get("metadata") if session_row else {})

    ctx: Dict[str, Any] = {
        "uploaded_reports": uploaded_reports,
        "extracted_claims": extracted_claims,
        "identity_confirmed": identity_confirmed,
        "review_claim_responses": {},
        "review_claims_list": review_claims_list,
        "round_number": dispute_round_number_from_meta(meta),
        "user_id": user_id,
        "is_admin_user": is_admin,
        "persist_letters": True,
        "apply_letter_billing": True,
        "letter_count_to_deduct": needed,
        "current_letters_balance": letters_bal,
        "is_free_generation": False,
        "free_item_count": 0,
        "free_max_capacity": 0,
    }
    return ctx, selected, ""


def build_credit_command_plan_for_workflow(
    user_id: int,
    workflow_id: str,
    *,
    session_row: Dict[str, Any],
    is_admin: bool,
    record_observability_event: bool = False,
    only_report_ids: Optional[List[int]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Same deterministic 72-hour plan as Streamlit (``credit_command_plan.build_credit_command_plan``),
    from DB reports + workflow dispute selection.
    """
    from credit_command_plan import build_credit_command_plan

    ctx, selected, err = build_pipeline_context_for_user(
        user_id,
        workflow_id,
        session_row=session_row,
        is_admin=is_admin,
        only_report_ids=only_report_ids,
    )
    if err:
        return None, err
    if not selected:
        return None, "no_selection"

    items_by_type: Dict[Any, List[Any]] = {}
    for rc in selected:
        rt = rc.review_type
        if rt not in items_by_type:
            items_by_type[rt] = []
        items_by_type[rt].append(rc)

    claims_list = ctx.get("review_claims_list") or []
    by_id = {rc.review_claim_id: rc for rc in claims_list}
    sel_ids = [rc.review_claim_id for rc in selected]
    bureau_list = estimate_unique_bureaus_for_claims(by_id, sel_ids)

    plan = build_credit_command_plan(
        items_by_type=items_by_type,
        selected_count=len(selected),
        bureaus=set(bureau_list),
        parsed_reports=ctx.get("uploaded_reports"),
    )
    if record_observability_event and plan:
        from services.workflow.workflow_event_service import record_system_event

        record_system_event(
            workflow_id,
            "credit_command_plan.generated",
            actor="system",
            source="workflow",
            metadata={
                "selectedCount": len(selected),
                "bureauCount": len(bureau_list),
            },
        )
    return plan, None


def letter_generation_head_state(workflow_id: str) -> Tuple[Optional[str], str, Optional[Dict[str, Any]]]:
    steps = fetch_steps(workflow_id)
    smap = {s["step_id"]: s for s in steps}
    head, phase = compute_authoritative_step(smap)
    row = smap.get("letter_generation")
    return head, phase, row


def serialize_letter_row(row: Dict[str, Any], *, preview_len: int = 320) -> Dict[str, Any]:
    meta_raw = row.get("metadata")
    meta: Dict[str, Any] = {}
    if isinstance(meta_raw, str):
        try:
            meta = json.loads(meta_raw)
        except Exception:
            meta = {}
    elif isinstance(meta_raw, dict):
        meta = dict(meta_raw)
    text = row.get("letter_text") or ""
    preview = text[:preview_len] + ("…" if len(text) > preview_len else "")
    return {
        "id": row.get("id"),
        "reportId": row.get("report_id"),
        "bureau": (row.get("bureau") or "").lower(),
        "bureauDisplay": (row.get("bureau") or "").title(),
        "createdAt": row.get("created_at").isoformat()
        if hasattr(row.get("created_at"), "isoformat")
        else str(row.get("created_at") or ""),
        "violationCount": int(meta.get("violation_count") or 0),
        "categories": meta.get("categories") if isinstance(meta.get("categories"), list) else [],
        "preview": preview,
        "charCount": len(text),
    }


def list_letters_for_workflow_customer(
    user_id: int,
    *,
    only_report_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """Latest letters per (report_id, bureau) for display."""
    rows = db.get_all_letters_for_user(user_id)
    if not rows:
        return []
    allowed: Optional[set] = None
    if only_report_ids is not None:
        allowed = set()
        for x in only_report_ids:
            try:
                allowed.add(int(x))
            except (TypeError, ValueError):
                pass
    dedup: Dict[Tuple[Any, str], Dict[str, Any]] = {}
    for row in rows:
        if allowed is not None:
            try:
                rid = int(row.get("report_id"))
            except (TypeError, ValueError):
                continue
            if rid not in allowed:
                continue
        key = (row.get("report_id"), (row.get("bureau") or "").lower())
        if key[1] and key not in dedup:
            dedup[key] = row
    out = [serialize_letter_row(r) for r in dedup.values()]
    out.sort(key=lambda x: (x.get("bureau") or ""))
    return out


def get_letter_body_for_user(user_id: int, letter_id: int) -> Optional[str]:
    with db.get_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT l.letter_text FROM letters l
            JOIN reports r ON l.report_id = r.id
            WHERE l.id = %s AND r.user_id = %s
            """,
            (letter_id, user_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    return row.get("letter_text") or ""


def run_letter_generation(
    user_id: int,
    workflow_id: str,
    *,
    session_row: Dict[str, Any],
    is_admin: bool,
    only_report_ids: Optional[List[int]] = None,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Run pipeline and complete workflow step on success.
    Returns (result_dict, error_message_safe).
    """
    head, phase, _ = letter_generation_head_state(workflow_id)
    if phase == "done" or head != "letter_generation":
        return {}, "Letter generation is not the current workflow step."

    ctx, selected, err = build_pipeline_context_for_user(
        user_id,
        workflow_id,
        session_row=session_row,
        is_admin=is_admin,
        only_report_ids=only_report_ids,
    )
    if err == "no_reports":
        return {}, "No parsed credit reports found. Upload a report first."
    if err == "no_selection":
        return {}, "No dispute selection found for this workflow. Complete strategy selection first."
    if err == "selection_not_found":
        return {}, "Saved dispute items no longer match your reports. Re-run strategy selection."

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

    letters = result.get("letters") or {}
    bureaus = [str(b).lower() for b in letters.keys() if b]
    if not bureaus:
        return result, "No letters were saved."

    ok = workflow_hooks.complete_letter_generation_step(
        user_id,
        workflow_id,
        bureaus,
        audit_source="api:letter_generation",
    )
    if not ok:
        return result, "Letters were generated but the workflow step could not be marked complete."

    from services.workflow.workflow_event_service import record_system_event

    record_system_event(
        workflow_id,
        "letters.generated",
        actor="system",
        source="api:letter_generation",
        metadata={"bureauCount": len(bureaus), "bureaus": bureaus},
    )
    return result, None
