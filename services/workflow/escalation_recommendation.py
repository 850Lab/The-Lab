"""
Backend-owned escalation hints from classification + coarse workflow posture.

Returns structured JSON safe for persistence and UI (no raw model output).
"""

from __future__ import annotations

from typing import Any, Dict, Final, Optional, Tuple

from services.workflow.response_classification import RESPONSE_CLASSIFICATIONS

ESCALATION_PATHS: Final[Tuple[str, ...]] = (
    "wait",
    "upload_more_proof",
    "mov_path",
    "cfpb_path",
    "executive_escalation",
    "manual_review_required",
)


def recommend_escalation(
    *,
    response_classification: str,
    workflow_overall_status: str,
    track_step_completed: bool,
    latest_response_classification: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produce escalation_recommendation JSON and a single primary path.

    workflow_overall_status: active | failed | completed
    track_step_completed: True if linear 'track' step is completed (mail cycle done).
    """
    cls = response_classification if response_classification in RESPONSE_CLASSIFICATIONS else "insufficient_to_classify"
    factors: list[str] = []

    if workflow_overall_status == "failed":
        return {
            "primary_path": "manual_review_required",
            "reasoning_safe": "The workflow has a failed step; resolve or retry that step before escalating the bureau response.",
            "factors": ["workflow_failed"],
            "secondary_paths": [],
            "priority": "high",
        }

    if not track_step_completed:
        factors.append("dispute_mail_cycle_incomplete")
        return {
            "primary_path": "wait",
            "reasoning_safe": "Finish mailing and tracking before bureau-response escalation paths are fully applicable.",
            "factors": factors,
            "secondary_paths": ["manual_review_required"],
            "priority": "normal",
        }

    if cls == "favorable_resolved":
        return {
            "primary_path": "wait",
            "reasoning_safe": "Favorable or deletion-oriented language suggests waiting for the next reporting cycle and re-pulling credit.",
            "factors": ["classification_favorable"],
            "secondary_paths": [],
            "priority": "low",
        }

    if cls == "partial_resolution":
        factors.append("partial_resolution")
        return {
            "primary_path": "mov_path",
            "reasoning_safe": "Partial updates may warrant a Method of Verification follow-up on remaining tradelines.",
            "factors": factors,
            "secondary_paths": ["upload_more_proof", "cfpb_path"],
            "priority": "normal",
        }

    if cls == "verification_only":
        return {
            "primary_path": "mov_path",
            "reasoning_safe": "Verification-only outcomes are a common trigger for MOV-focused follow-up.",
            "factors": ["classification_verification"],
            "secondary_paths": ["cfpb_path", "manual_review_required"],
            "priority": "normal",
        }

    if cls == "stall_or_non_answer":
        return {
            "primary_path": "upload_more_proof",
            "reasoning_safe": "Stall or non-answer patterns often improve after supplying clearer documentation, then timed follow-up.",
            "factors": ["classification_stall"],
            "secondary_paths": ["cfpb_path", "wait"],
            "priority": "normal",
        }

    if cls == "adverse_or_rejected":
        return {
            "primary_path": "cfpb_path",
            "reasoning_safe": "Adverse or rejection language may warrant regulatory or formal escalation after documentation is organized.",
            "factors": ["classification_adverse"],
            "secondary_paths": ["executive_escalation", "manual_review_required"],
            "priority": "high",
        }

    # insufficient_to_classify or unknown
    if latest_response_classification and latest_response_classification == cls:
        factors.append("repeat_unclassified")
    return {
        "primary_path": "manual_review_required",
        "reasoning_safe": "The response could not be classified confidently; a human should review the document and choose a path.",
        "factors": factors or ["insufficient_signal"],
        "secondary_paths": ["upload_more_proof", "wait"],
        "priority": "normal",
    }
