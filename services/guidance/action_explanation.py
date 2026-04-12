"""
O.R.I.O.N. V1.3 — deterministic action explanation (not orchestration, no AI).

Explains why ``bestAction`` is recommended from compact readiness context + the action dict.
Does not scan workflow event history.

ORION is deterministic. Do NOT inject AI logic here. AI layers must consume ORION outputs, not modify them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

ACTION_EXPLANATION_VERSION = "orion_action_explanation_v1"

ExplanationType = Literal["progress", "warning", "waiting", "requirement", "review"]


@dataclass
class BestActionExplanation:
    summary: str
    why_now: str
    what_it_unlocks: str
    blocking_context: Optional[str]
    explanation_type: ExplanationType
    reason_codes: List[str] = field(default_factory=list)
    source_action_key: Optional[str] = None
    action_explanation_version: str = ACTION_EXPLANATION_VERSION

    def to_user_api_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "whyNow": self.why_now,
            "whatItUnlocks": self.what_it_unlocks,
            "blockingContext": self.blocking_context,
            "explanationType": self.explanation_type,
        }

    def to_audit_dict(self) -> Dict[str, Any]:
        d = self.to_user_api_dict()
        d["reasonCodes"] = list(self.reason_codes)
        d["sourceActionKey"] = self.source_action_key
        d["actionExplanationVersion"] = self.action_explanation_version
        return d


def _reason_codes(best_action: Dict[str, Any]) -> List[str]:
    raw = best_action.get("reasonCodes")
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if x is not None and str(x).strip()]


def _availability(best_action: Dict[str, Any]) -> str:
    return str(best_action.get("availability") or "ready")


def _step_statuses(ctx: Dict[str, Any]) -> Dict[str, str]:
    ss = ctx.get("stepStatuses")
    if not isinstance(ss, dict):
        return {}
    return {str(k): str(v) for k, v in ss.items()}


def _head_step(ctx: Dict[str, Any]) -> Optional[str]:
    h = ctx.get("headStepId")
    if h is None:
        return None
    s = str(h).strip()
    return s or None


def _retry_upload_blocking(reason_codes: List[str]) -> Optional[str]:
    parts: List[str] = []
    if "upload_failed_recently" in reason_codes:
        parts.append("Your most recent upload did not complete successfully.")
    if "upload_high_attempt_count" in reason_codes:
        parts.append("Several recent attempts have not completed successfully.")
    if "guidance_upload_failure_rule" in reason_codes:
        parts.append("The workflow has flagged repeated upload difficulty.")
    if not parts:
        return None
    return " ".join(parts)


def _blocked_step_message(action_key: str) -> str:
    return {
        "complete_payment": "The payment step needs attention before letter generation and the send flow can continue.",
        "upload_proof_documents": "The proof step needs attention before mailing can continue.",
        "review_claims": "Claims review needs attention before dispute selection can continue.",
        "review_dispute_selection": "Dispute selection needs attention before payment and letter preparation can continue.",
        "confirm_mail_step": "The mail step needs attention before live mailing and tracking can proceed.",
    }.get(
        action_key,
        "This step needs attention before the workflow can move forward.",
    )


def _build_for_action(
    action_key: str,
    best_action: Dict[str, Any],
    ctx: Dict[str, Any],
) -> BestActionExplanation:
    rc = _reason_codes(best_action)
    avail = _availability(best_action)
    head = _head_step(ctx)
    statuses = _step_statuses(ctx)
    blocked = avail == "blocked"
    blocking: Optional[str] = None

    if action_key == "resume_upload":
        return BestActionExplanation(
            summary="You still need to upload a valid credit report.",
            why_now="The workflow cannot move into analysis until report intake is completed.",
            what_it_unlocks="Parsing and analysis of your report.",
            blocking_context=None,
            explanation_type="progress",
            reason_codes=rc,
            source_action_key=action_key,
        )

    if action_key == "retry_upload":
        blocking = _retry_upload_blocking(rc)
        return BestActionExplanation(
            summary="Previous upload attempts did not complete successfully.",
            why_now="The workflow is still blocked at report intake until a valid upload is accepted.",
            what_it_unlocks="Parsing and analysis once a valid upload is accepted.",
            blocking_context=blocking,
            explanation_type="warning",
            reason_codes=rc,
            source_action_key=action_key,
        )

    if action_key == "wait_for_processing":
        why = "Required analysis is not finished yet."
        if head == "parse_analyze" and statuses.get("parse_analyze") == "in_progress":
            why = "Your report is still being processed; required analysis is not finished yet."
        elif "parse_pending" in rc:
            why = "Parsing and analysis have not finished yet."
        return BestActionExplanation(
            summary="The system is still processing the report or preparing results.",
            why_now=why,
            what_it_unlocks="Review and dispute selection once results are ready.",
            blocking_context=None,
            explanation_type="waiting",
            reason_codes=rc,
            source_action_key=action_key,
        )

    if action_key == "review_claims":
        if blocked:
            blocking = _blocked_step_message(action_key)
        return BestActionExplanation(
            summary="Claims are available for review.",
            why_now="Findings are ready, and reviewing them is the next meaningful step.",
            what_it_unlocks="Dispute selection and execution decisions.",
            blocking_context=blocking,
            explanation_type="review",
            reason_codes=rc,
            source_action_key=action_key,
        )

    if action_key == "review_dispute_selection":
        if blocked:
            blocking = _blocked_step_message(action_key)
        return BestActionExplanation(
            summary="Dispute selection needs review before payment and execution.",
            why_now="What you select determines what the system prepares next.",
            what_it_unlocks="Payment and downstream letter generation.",
            blocking_context=blocking,
            explanation_type="review",
            reason_codes=rc,
            source_action_key=action_key,
        )

    if action_key == "complete_payment":
        if blocked:
            blocking = _blocked_step_message(action_key)
        return BestActionExplanation(
            summary="Payment is required before execution can continue.",
            why_now="Selected disputes are ready, but the paid execution path has not started.",
            what_it_unlocks="Letter generation and the remaining send flow.",
            blocking_context=blocking,
            explanation_type="requirement",
            reason_codes=rc,
            source_action_key=action_key,
        )

    if action_key == "review_generated_letters":
        unlock = "Proof attachment and mailing progression."
        if "letters_ready" in rc:
            unlock = "Proof attachment, mailing confirmation, and tracking."
        return BestActionExplanation(
            summary="Letters are ready for the next stage of execution.",
            why_now="Payment is complete and prepared letters are the next immediate output to review.",
            what_it_unlocks=unlock,
            blocking_context=None,
            explanation_type="progress",
            reason_codes=rc,
            source_action_key=action_key,
        )

    if action_key == "upload_proof_documents":
        if blocked:
            blocking = _blocked_step_message(action_key)
        return BestActionExplanation(
            summary="Proof documents are required before mailing can continue.",
            why_now="Your letters are ready, but mailing cannot move forward until proof is attached.",
            what_it_unlocks="Completing this step allows the mail step to move forward.",
            blocking_context=blocking,
            explanation_type="requirement",
            reason_codes=rc,
            source_action_key=action_key,
        )

    if action_key == "confirm_mail_step":
        if blocked:
            blocking = _blocked_step_message(action_key)
        return BestActionExplanation(
            summary="The case is ready to move into mailing.",
            why_now="Letters and required proof are in place; mailing is the next step to confirm.",
            what_it_unlocks="Live mailing and tracking visibility.",
            blocking_context=blocking,
            explanation_type="progress",
            reason_codes=rc,
            source_action_key=action_key,
        )

    if action_key == "check_tracking_status":
        track_st = statuses.get("track", "")
        if track_st == "available":
            expl_type: ExplanationType = "progress"
            why = "Tracking is available now that preparation steps are far enough along."
        else:
            expl_type = "waiting"
            why = "The workflow has moved into post-send monitoring; checking tracking is the most relevant next view."
        return BestActionExplanation(
            summary="Mailing is in progress or completed, and tracking is the next relevant view.",
            why_now=why,
            what_it_unlocks="Visibility into delivery status and timeline progress.",
            blocking_context=None,
            explanation_type=expl_type,
            reason_codes=rc,
            source_action_key=action_key,
        )

    if action_key == "review_escalation_options":
        return BestActionExplanation(
            summary="Escalation options are available for review.",
            why_now="Your workflow posture indicates escalation may be appropriate to consider.",
            what_it_unlocks="Next-round actions beyond the initial dispute flow.",
            blocking_context=None,
            explanation_type="review",
            reason_codes=rc,
            source_action_key=action_key,
        )

    # Unknown action key: still deterministic, uses surfaced labels only.
    label = str(best_action.get("label") or "Next step").strip()
    desc = str(best_action.get("description") or "").strip()
    why = desc if desc else f"{label} is the recommended next step based on current workflow state."
    return BestActionExplanation(
        summary=label,
        why_now=why,
        what_it_unlocks="The next available workflow step once this action is completed.",
        blocking_context=_blocked_step_message(action_key) if blocked else None,
        explanation_type="progress",
        reason_codes=rc,
        source_action_key=action_key or None,
    )


def explain_best_action(
    best_action: Optional[Dict[str, Any]],
    readiness_context: Dict[str, Any],
) -> Optional[BestActionExplanation]:
    """
    Deterministic explanation for the current best action.

    ``readiness_context`` should match :func:`build_action_readiness_context` output
    (``headStepId``, ``stepStatuses``, ``phase``, etc.).
    """
    if not best_action or not isinstance(best_action, dict):
        return None
    key = str(best_action.get("actionKey") or "").strip()
    if not key:
        return None
    if not isinstance(readiness_context, dict):
        readiness_context = {}
    return _build_for_action(key, best_action, readiness_context)


def explain_best_action_user_api(
    best_action: Optional[Dict[str, Any]],
    readiness_context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    exp = explain_best_action(best_action, readiness_context)
    return exp.to_user_api_dict() if exp else None


def explain_best_action_audit(
    best_action: Optional[Dict[str, Any]],
    readiness_context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    exp = explain_best_action(best_action, readiness_context)
    return exp.to_audit_dict() if exp else None
