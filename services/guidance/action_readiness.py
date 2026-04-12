"""
O.R.I.O.N. V1.2 — deterministic action readiness (not orchestration, no workflow writes).

Ranks “what should the user do next?” from session + step snapshot + optional deliverable guidance.
Does not query unbounded history (no workflow_events / guidance log reads here).

ORION is deterministic. Do NOT inject AI logic here. AI layers must consume ORION outputs, not modify them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

from services.workflow import registry as reg
from services.workflow.engine import compute_authoritative_step
from services.guidance.orion_versions import orion_versions_for_audit_response

ActionType = Literal["navigate", "retry", "review", "wait", "upload", "confirm", "resolve"]
Availability = Literal["ready", "blocked", "not_relevant"]
ActionSource = Literal["workflow_state", "guidance_rule", "step_status", "system_logic"]

# Consumer linear workflow only for rich catalog; other types get a minimal fallback.
_CONSUMER_WF = "dispute_linear_v1"

ACTION_CATALOG: Dict[str, Dict[str, Any]] = {
    "resume_upload": {
        "label": "Continue your upload",
        "description": "Finish uploading your credit report to continue.",
        "target_step_id": "upload",
        "action_type": "upload",
    },
    "retry_upload": {
        "label": "Try upload again",
        "description": "Upload hit a problem; retry with the guided steps.",
        "target_step_id": "upload",
        "action_type": "retry",
    },
    "wait_for_processing": {
        "label": "Wait for processing",
        "description": "The system is working on your file; check back shortly.",
        "target_step_id": None,
        "action_type": "wait",
    },
    "review_claims": {
        "label": "Review claims",
        "description": "Review parsed claims before selecting disputes.",
        "target_step_id": "review_claims",
        "action_type": "review",
    },
    "review_dispute_selection": {
        "label": "Review dispute selection",
        "description": "Confirm which items you want to dispute.",
        "target_step_id": "select_disputes",
        "action_type": "review",
    },
    "complete_payment": {
        "label": "Complete payment",
        "description": "Payment is required before letters are generated.",
        "target_step_id": "payment",
        "action_type": "navigate",
    },
    "review_generated_letters": {
        "label": "Review generated letters",
        "description": "Your payment is complete; review letters for the next step.",
        "target_step_id": "letter_generation",
        "action_type": "navigate",
    },
    "upload_proof_documents": {
        "label": "Upload proof documents",
        "description": "Add ID, proof of address, and signature before mailing.",
        "target_step_id": "proof_attachment",
        "action_type": "upload",
    },
    "confirm_mail_step": {
        "label": "Confirm mailing",
        "description": "Review and confirm the mail step when you are ready.",
        "target_step_id": "mail",
        "action_type": "confirm",
    },
    "check_tracking_status": {
        "label": "Check tracking status",
        "description": "Follow responses and tracking for your dispute mailings.",
        "target_step_id": "track",
        "action_type": "review",
    },
    "review_escalation_options": {
        "label": "Review escalation options",
        "description": "Escalation paths may be available for your situation.",
        "target_step_id": "track",
        "action_type": "resolve",
    },
}


@dataclass
class ActionCandidate:
    action_key: str
    label: str
    description: str
    target_step_id: Optional[str]
    action_type: ActionType
    score: int
    reason_codes: List[str] = field(default_factory=list)
    availability: Availability = "ready"
    source: ActionSource = "workflow_state"

    def to_user_dict(self) -> Dict[str, Any]:
        return {
            "actionKey": self.action_key,
            "label": self.label,
            "description": self.description,
            "targetStepId": self.target_step_id,
            "actionType": self.action_type,
            "reasonCodes": list(self.reason_codes),
            "availability": self.availability,
        }

    def to_audit_dict(self) -> Dict[str, Any]:
        d = self.to_user_dict()
        d["score"] = self.score
        d["source"] = self.source
        return d


def _steps_by_id(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        sid = str(r.get("step_id") or "").strip()
        if sid:
            out[sid] = r
    return out


def _step_status(smap: Dict[str, Dict[str, Any]], step_id: str) -> str:
    row = smap.get(step_id) or {}
    return str(row.get("status") or "not_started")


def _attempts(smap: Dict[str, Dict[str, Any]], step_id: str) -> int:
    row = smap.get(step_id) or {}
    try:
        return int(row.get("attempt_count") or 0)
    except (TypeError, ValueError):
        return 0


def _meta_escalation_eligible(session: Dict[str, Any]) -> bool:
    meta = session.get("metadata")
    if not isinstance(meta, dict):
        return False
    if meta.get("escalationEligible") is True:
        return True
    ds = meta.get("dispute_strategy") or meta.get("disputeStrategy")
    if isinstance(ds, dict) and ds.get("escalationEligible") is True:
        return True
    return False


def _from_catalog(
    action_key: str,
    *,
    score: int,
    reason_codes: List[str],
    availability: Availability,
    source: ActionSource,
) -> Optional[ActionCandidate]:
    spec = ACTION_CATALOG.get(action_key)
    if not spec:
        return None
    return ActionCandidate(
        action_key=action_key,
        label=str(spec["label"]),
        description=str(spec["description"]),
        target_step_id=spec.get("target_step_id"),
        action_type=spec["action_type"],  # type: ignore[arg-type]
        score=score,
        reason_codes=reason_codes,
        availability=availability,
        source=source,
    )


def _guidance_urgency(guidance_api: Optional[Dict[str, Any]]) -> int:
    if not guidance_api:
        return 0
    t = str(guidance_api.get("type") or "")
    if t in ("warning", "instruction"):
        return 25
    if t == "optimization":
        return 10
    return 5 if t == "nudge" else 0


def _guidance_target_step(guidance_api: Optional[Dict[str, Any]]) -> Optional[str]:
    if not guidance_api:
        return None
    ra = guidance_api.get("recommendedAction")
    if isinstance(ra, dict):
        ts = ra.get("targetStepId")
        if ts:
            return str(ts).strip() or None
    return None


def _apply_guidance_bump(c: ActionCandidate, guidance_api: Optional[Dict[str, Any]]) -> None:
    if not guidance_api:
        return
    rk = str(guidance_api.get("ruleKey") or "")
    tgt = _guidance_target_step(guidance_api)
    bump = _guidance_urgency(guidance_api)
    if not bump:
        return
    if tgt and c.target_step_id == tgt:
        c.score += bump
        c.reason_codes.append("active_guidance_reinforces_step")
        c.source = "guidance_rule"
    elif rk == "orion.repeated_upload_failure" and c.action_key == "retry_upload":
        c.score += bump
        c.reason_codes.append("guidance_upload_failure_rule")
        c.source = "guidance_rule"


def _consumer_candidates(
    head: Optional[str],
    phase: str,
    smap: Dict[str, Dict[str, Any]],
    session: Dict[str, Any],
    guidance_api: Optional[Dict[str, Any]],
) -> List[ActionCandidate]:
    out: List[ActionCandidate] = []
    if phase == "done" or not head:
        return out

    st = _step_status(smap, head)
    att = _attempts(smap, head)

    # --- upload
    if head == "upload":
        failed = st == "failed"
        retry_reasons: List[str] = []
        if failed:
            retry_reasons.append("upload_failed_recently")
        if att >= 3:
            retry_reasons.append("upload_high_attempt_count")
        if guidance_api and str(guidance_api.get("ruleKey") or "") == "orion.repeated_upload_failure":
            retry_reasons.append("guidance_upload_failure_rule")

        if retry_reasons:
            c = _from_catalog(
                "retry_upload",
                score=120,
                reason_codes=list(dict.fromkeys(retry_reasons)),
                availability="ready",
                source="step_status",
            )
            if c:
                out.append(c)
        if st in ("in_progress", "available", "not_started") and not failed:
            c2 = _from_catalog(
                "resume_upload",
                score=100 if st == "in_progress" else 85,
                reason_codes=["head_step_in_progress" if st == "in_progress" else "head_step_available"],
                availability="ready",
                source="workflow_state",
            )
            if c2:
                out.append(c2)
        elif failed and not any(x.action_key == "retry_upload" for x in out):
            c3 = _from_catalog(
                "retry_upload",
                score=120,
                reason_codes=["upload_failed_recently"],
                availability="ready",
                source="step_status",
            )
            if c3:
                out.append(c3)

    # --- parse / async-style wait
    elif head == "parse_analyze":
        c = _from_catalog(
            "wait_for_processing",
            score=110 if st == "in_progress" else 95,
            reason_codes=(
                ["awaiting_background_processing"]
                if st == "in_progress"
                else ["parse_pending"]
            ),
            availability="ready",
            source="system_logic",
        )
        if c:
            out.append(c)

    elif head == "review_claims":
        c = _from_catalog(
            "review_claims",
            score=100,
            reason_codes=["head_step_in_progress" if st == "in_progress" else "head_step_available"],
            availability="blocked" if st == "failed" else "ready",
            source="workflow_state",
        )
        if c:
            out.append(c)

    elif head == "select_disputes":
        c = _from_catalog(
            "review_dispute_selection",
            score=100,
            reason_codes=["selection_incomplete"],
            availability="blocked" if st == "failed" else "ready",
            source="workflow_state",
        )
        if c:
            out.append(c)

    elif head == "payment":
        c = _from_catalog(
            "complete_payment",
            score=100,
            reason_codes=["payment_required"],
            availability="blocked" if st == "failed" else "ready",
            source="workflow_state",
        )
        if c:
            out.append(c)

    elif head == "letter_generation":
        c = _from_catalog(
            "review_generated_letters",
            score=110 if st == "in_progress" else 100,
            reason_codes=(
                ["payment_completed_letters_pending"]
                if st != "completed"
                else ["letters_ready"]
            ),
            availability="ready",
            source="workflow_state",
        )
        if c:
            out.append(c)

    elif head == "proof_attachment":
        c = _from_catalog(
            "upload_proof_documents",
            score=100,
            reason_codes=["proof_required_before_mail"],
            availability="blocked" if st == "failed" else "ready",
            source="workflow_state",
        )
        if c:
            out.append(c)

    elif head == "mail":
        c = _from_catalog(
            "confirm_mail_step",
            score=100,
            reason_codes=["mail_pending_confirmation"],
            availability="blocked" if st == "failed" else "ready",
            source="workflow_state",
        )
        if c:
            out.append(c)

    elif head == "track":
        c = _from_catalog(
            "check_tracking_status",
            score=100,
            reason_codes=["mail_sent_tracking_active"],
            availability="ready",
            source="workflow_state",
        )
        if c:
            out.append(c)

    if _meta_escalation_eligible(session):
        c = _from_catalog(
            "review_escalation_options",
            score=35,
            reason_codes=["escalation_eligible_metadata"],
            availability="ready",
            source="system_logic",
        )
        if c:
            out.append(c)

    for c in out:
        _apply_guidance_bump(c, guidance_api)

    return out


def _fallback_candidate(head: Optional[str], phase: str) -> List[ActionCandidate]:
    if phase == "done" or not head:
        return []
    c = _from_catalog(
        "wait_for_processing",
        score=50,
        reason_codes=["non_consumer_workflow_fallback"],
        availability="ready",
        source="system_logic",
    )
    return [c] if c else []


def build_action_readiness_context(
    session: Dict[str, Any],
    steps: List[Dict[str, Any]],
    *,
    guidance_api: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compact, bounded snapshot for tests / operator tools (no I/O)."""
    wt = str(session.get("workflow_type") or reg.WORKFLOW_TYPE_DEFAULT)
    order = reg.linear_order_for(wt)
    smap = _steps_by_id(steps)
    head, phase = compute_authoritative_step(smap, order)
    return {
        "workflowType": wt,
        "overallStatus": session.get("overall_status"),
        "headStepId": head,
        "phase": phase,
        "stepStatuses": {k: _step_status(smap, k) for k in order if k in smap},
        "guidanceRuleKey": (guidance_api or {}).get("ruleKey"),
        "boundedEventHistoryUsed": False,
    }


def compute_action_readiness(
    session: Dict[str, Any],
    steps: List[Dict[str, Any]],
    guidance_api: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[ActionCandidate], List[ActionCandidate]]:
    """
    Deterministic rank. Uses only session + steps + optional user-facing guidance dict.
    """
    overall = str(session.get("overall_status") or "")
    if overall == "completed":
        return None, []

    wt = str(session.get("workflow_type") or reg.WORKFLOW_TYPE_DEFAULT)
    order = reg.linear_order_for(wt)
    smap = _steps_by_id(steps)
    head, phase = compute_authoritative_step(smap, order)

    if wt == _CONSUMER_WF:
        raw = _consumer_candidates(head, phase, smap, session, guidance_api)
    else:
        raw = _fallback_candidate(head, phase)

    # De-dupe by action_key (merge scores / reasons)
    merged: Dict[str, ActionCandidate] = {}
    for c in raw:
        if c.action_key not in merged or c.score > merged[c.action_key].score:
            merged[c.action_key] = c
    ranked = sorted(merged.values(), key=lambda x: (-x.score, x.action_key))

    ready = [c for c in ranked if c.availability == "ready"]
    blocked = [c for c in ranked if c.availability == "blocked"]
    best: Optional[ActionCandidate] = None
    if ready:
        best = ready[0]
    elif blocked:
        best = blocked[0]

    return best, ranked


def compute_action_readiness_for_api(
    session: Dict[str, Any],
    steps: List[Dict[str, Any]],
    guidance_api: Optional[Dict[str, Any]] = None,
    *,
    max_candidates: int = 3,
) -> Dict[str, Any]:
    """User-facing bundle fragment: bestAction + actionCandidates (cap 3, ready/blocked only)."""
    best, ranked = compute_action_readiness(session, steps, guidance_api)
    user_pool = [c for c in ranked if c.availability in ("ready", "blocked")]
    cap = max(0, min(3, int(max_candidates)))
    top = user_pool[:cap] if cap else []

    return {
        "bestAction": best.to_user_dict() if best else None,
        "actionCandidates": [c.to_user_dict() for c in top],
    }


def audit_action_readiness_for_workflow(
    workflow_id: str,
    *,
    guidance_api: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Operator-facing recompute (no UI). Includes scores, sources, full ranked list.

    Pass ``guidance_api`` to mirror the same deliverable guidance dict used on customer APIs
    (e.g. from ``GuidanceResponse.to_user_api_dict()``).
    """
    from services.workflow.repository import fetch_session, fetch_steps

    wf = (workflow_id or "").strip()
    if not wf:
        return {
            "workflowId": None,
            "context": {},
            "best": None,
            "ranked": [],
            "deliveryPrioritizationAudit": None,
            "uxSurfaceContractAudit": None,
            "orionLayerVersions": orion_versions_for_audit_response(),
        }

    session = fetch_session(wf)
    if not session:
        return {
            "workflowId": wf,
            "context": {},
            "best": None,
            "ranked": [],
            "deliveryPrioritizationAudit": None,
            "uxSurfaceContractAudit": None,
            "orionLayerVersions": orion_versions_for_audit_response(),
        }

    steps = fetch_steps(wf, session=session)
    ctx = build_action_readiness_context(session, steps, guidance_api=guidance_api)
    best, ranked = compute_action_readiness(session, steps, guidance_api)
    from services.guidance.action_explanation import explain_best_action_audit

    best_user = best.to_user_dict() if best else None
    expl_audit = explain_best_action_audit(best_user, ctx)
    from services.guidance.action_explanation import explain_best_action_user_api
    from services.guidance.delivery_prioritization import (
        audit_delivery_prioritization_for_bundle_inputs,
    )
    from services.guidance.ux_surface_contract import audit_ux_surface_contract_for_bundle_inputs

    ar_api = compute_action_readiness_for_api(session, steps, guidance_api)
    expl_user = explain_best_action_user_api(ar_api.get("bestAction"), ctx)
    dp_audit = audit_delivery_prioritization_for_bundle_inputs(
        guidance=guidance_api,
        best_action=ar_api.get("bestAction"),
        action_candidates=ar_api.get("actionCandidates"),
        best_action_explanation=expl_user,
        readiness_context=ctx,
    )
    ux_audit = audit_ux_surface_contract_for_bundle_inputs(
        guidance=guidance_api,
        best_action=ar_api.get("bestAction"),
        best_action_explanation=expl_user,
        delivery_prioritization=dp_audit.get("deliveryPrioritization"),
        readiness_context=ctx,
    )
    return {
        "workflowId": wf,
        "context": ctx,
        "best": best.to_audit_dict() if best else None,
        "ranked": [c.to_audit_dict() for c in ranked],
        "bestActionExplanation": expl_audit,
        "actionExplanationVersion": expl_audit.get("actionExplanationVersion")
        if expl_audit
        else None,
        "deliveryPrioritizationAudit": dp_audit,
        "uxSurfaceContractAudit": ux_audit,
        "orionLayerVersions": orion_versions_for_audit_response(),
    }
