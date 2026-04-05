"""
Shared escalation UX JSON for strategy + escalation layer (same workflow session).

Builds grouped actions with claim lines and copy-paste drafts — metadata only for state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from review_claims import ReviewClaim

from services.customer_dispute_strategy import load_compressed_review_claims_for_user
from services.workflow.dispute_round_execution import _ds_from_meta
from services.workflow.escalation_draft_text import draft_for_escalation_action
from services.workflow.escalation_engine import escalation_public_view

TRIGGER_LABELS: Dict[str, str] = {
    "no_response": "No response",
    "repeated_verified": "Repeated verification",
    "insufficient_update": "Insufficient update",
}

TRIGGER_WHY: Dict[str, str] = {
    "no_response": "The bureau did not give a substantive answer (or you recorded a no-response outcome) for one or more disputed items.",
    "repeated_verified": "The same item(s) were marked verified more than once across saved responses — a common signal to push method-of-verification and furnisher pressure.",
    "insufficient_update": "The bureau partially updated reporting but disputed negatives may still remain — worth parallel MOV and furnisher follow-up.",
}


def _claim_line(rc: ReviewClaim) -> str:
    s = (rc.summary or rc.question or rc.review_claim_id or "").strip()
    b = (rc.entities.get("bureau") or "").strip()
    return f"{s} ({b})" if b else s


def _ux_states(meta: Dict[str, Any]) -> Dict[str, Any]:
    ds = _ds_from_meta(meta)
    raw = ds.get("escalation_ux")
    if not isinstance(raw, dict):
        return {}
    st = raw.get("actionStates")
    return st if isinstance(st, dict) else {}


def persist_escalation_ux_state(
    workflow_id: str,
    action_id: str,
    *,
    reviewed: bool = False,
    proceeded: bool = False,
) -> None:
    from services.workflow.escalation_draft_text import merge_escalation_ux_state
    from services.workflow.repository import merge_into_workflow_metadata

    aid = (action_id or "").strip()
    if not aid:
        return

    def _mut(meta: Dict[str, Any]) -> None:
        ds = meta.get("dispute_selection")
        if not isinstance(ds, dict):
            ds = {}
        else:
            ds = dict(ds)
        eu = ds.get("escalation_ux")
        ds["escalation_ux"] = merge_escalation_ux_state(
            eu if isinstance(eu, dict) else {},
            aid,
            reviewed=reviewed,
            proceeded=proceeded,
        )
        meta["dispute_selection"] = ds

    merge_into_workflow_metadata(workflow_id, _mut)


def build_program_escalation_ux_payload(user_id: int, meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ev = escalation_public_view(meta)
    acts = ev.get("actions") or []
    if not isinstance(acts, list) or not acts:
        return None

    claims = load_compressed_review_claims_for_user(user_id)
    by_id = {c.review_claim_id: c for c in claims}
    states = _ux_states(meta)

    enriched_by_trigger: Dict[str, List[Dict[str, Any]]] = {}
    for a in acts:
        if not isinstance(a, dict):
            continue
        tr = str(a.get("triggerReason") or "unknown").strip() or "unknown"
        ids = a.get("reviewClaimIds") or []
        if not isinstance(ids, list):
            ids = []
        id_strs = [str(x) for x in ids if x][:100]
        lines = [_claim_line(by_id[i]) for i in id_strs if i in by_id]
        aid = str(a.get("id") or "")
        st = states.get(aid) if aid else None
        reviewed = bool(isinstance(st, dict) and st.get("reviewed"))
        proceeded = bool(isinstance(st, dict) and st.get("proceeded"))
        atype = str(a.get("type") or "")
        draft = draft_for_escalation_action(atype, lines)
        meta_m = a.get("metadata") if isinstance(a.get("metadata"), dict) else {}
        bullets = meta_m.get("bullets")
        if not isinstance(bullets, list):
            bullets = []
        row = {
            **a,
            "affectedItems": [{"reviewClaimId": i, "line": _claim_line(by_id[i])} for i in id_strs if i in by_id],
            "claimSummaryLines": lines,
            "documentDraft": draft,
            "callBullets": [str(x) for x in bullets if x is not None][:20],
            "userMarkedReviewed": reviewed,
            "userMarkedProceeded": proceeded,
        }
        enriched_by_trigger.setdefault(tr, []).append(row)

    groups: List[Dict[str, Any]] = []
    for tr, rows in sorted(enriched_by_trigger.items(), key=lambda x: x[0]):
        groups.append(
            {
                "triggerKey": tr,
                "triggerLabel": TRIGGER_LABELS.get(tr, tr.replace("_", " ").title()),
                "why": TRIGGER_WHY.get(tr, "Escalation is suggested based on your saved outcomes."),
                "actions": rows,
            }
        )

    return {
        "model": "escalation_ux_v1",
        "status": ev.get("status"),
        "triggers": ev.get("triggers") or [],
        "groups": groups,
        "continueProgramNote": (
            "Escalation steps run alongside your 850 Lab program: finish this round’s dispute "
            "selection and letters when you’re ready — these actions are extra leverage, not a "
            "separate workflow."
        ),
        "differentiationNote": (
            "Next dispute round = another bureau letter cycle inside this same workflow. "
            "Escalation = MOV, furnisher, CFPB outline, and call scripts you execute outside "
            "the app (or with your own mail)."
        ),
    }
