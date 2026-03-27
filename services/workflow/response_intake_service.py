"""
Register bureau/furnisher responses, classify, escalate, and merge workflow metadata.

Only trusted server code should call this (API with user check, workers, admin).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.workflow.engine import WorkflowEngine
from services.workflow.escalation_recommendation import recommend_escalation
from services.workflow.repository import fetch_session, update_session_fields
from services.workflow.response_classification import classify_parsed_response
from services.workflow import response_repository as rr
from services.workflow.response_flow_events import (
    _summary_length_bucket,
    emit_response_flow_event,
)


def _track_completed(steps_map: Dict[str, Dict[str, Any]]) -> bool:
    t = steps_map.get("track")
    return bool(t and t.get("status") == "completed")


def merge_workflow_source_of_truth_metadata(
    workflow_id: str,
    *,
    response_id: str,
    response_classification: str,
    escalation: Dict[str, Any],
    reasoning_safe: str,
) -> None:
    """Attach last classification + escalation to session metadata (JSON merge)."""
    from services.workflow.workflow_db import get_workflow_db

    patch = {
        "lifecycle": {
            "last_response_id": response_id,
            "last_response_classification": response_classification,
            "last_escalation": escalation,
            "last_classification_reasoning_safe": (reasoning_safe or "")[:2000],
            "last_intake_at": datetime.now(timezone.utc).isoformat(),
            "source_of_truth_revision": 1,
        }
    }
    with get_workflow_db() as (conn, cur):
        update_session_fields(conn, cur, workflow_id, metadata_patch=patch)
        conn.commit()


def intake_bureau_response(
    *,
    workflow_id: str,
    user_id: int,
    source_type: str,
    response_channel: str,
    parsed_summary: Dict[str, Any],
    storage_ref: Optional[str] = None,
    linked_mailing_id: Optional[int] = None,
    linked_letter_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create intake row, classify, recommend escalation, persist, update workflow metadata.

    Returns a dict safe to JSON-serialize (no DB cursors).
    """
    session = fetch_session(workflow_id)
    if not session:
        return {"ok": False, "error": {"code": "NOT_FOUND", "messageSafe": "Workflow not found."}}
    if int(session["user_id"]) != int(user_id):
        return {"ok": False, "error": {"code": "FORBIDDEN", "messageSafe": "Workflow does not belong to this user."}}

    rid = rr.insert_response_intake(
        workflow_id=workflow_id,
        user_id=user_id,
        source_type=source_type,
        response_channel=response_channel,
        parsed_summary=parsed_summary or {},
        storage_ref=storage_ref,
        linked_mailing_id=linked_mailing_id,
        linked_letter_id=linked_letter_id,
    )

    emit_response_flow_event(
        "response_intake_stored",
        workflow_id=workflow_id,
        user_id=user_id,
        status="stored",
        source="backend",
        metadata={
            "response_id": rid,
            "source_type": (source_type or "")[:40],
            "response_channel": (response_channel or "")[:40],
            "classification_status": "pending",
            "summary_length_bucket": _summary_length_bucket(parsed_summary),
            "has_outcome_keywords": bool(
                isinstance((parsed_summary or {}).get("outcome_keywords"), list)
                and len((parsed_summary or {}).get("outcome_keywords") or []) > 0
            ),
            "has_storage_ref": bool(storage_ref),
        },
    )

    eng = WorkflowEngine()
    _, _, smap = eng.get_state_bundle(workflow_id)
    track_done = _track_completed(smap)
    overall = session.get("overall_status") or "active"

    try:
        outcome = classify_parsed_response(parsed_summary or {})
        esc = recommend_escalation(
            response_classification=outcome.classification,
            workflow_overall_status=overall,
            track_step_completed=track_done,
        )
        rr.update_response_classification(
            rid,
            classification_status="classified",
            response_classification=outcome.classification,
            classification_reasoning_safe=outcome.reasoning_safe,
            classification_confidence=outcome.confidence,
            recommended_next_action=outcome.recommended_next_action,
            escalation_recommendation=esc,
        )
        merge_workflow_source_of_truth_metadata(
            workflow_id,
            response_id=rid,
            response_classification=outcome.classification,
            escalation=esc,
            reasoning_safe=outcome.reasoning_safe,
        )
        emit_response_flow_event(
            "response_classification_succeeded",
            workflow_id=workflow_id,
            user_id=user_id,
            status="classified",
            source="backend",
            metadata={
                "response_id": rid,
                "classification": (outcome.classification or "")[:64],
                "classification_status": "classified",
                "recommended_next_action": (outcome.recommended_next_action or "")[:64],
                "confidence_bucket": (
                    "high"
                    if outcome.confidence is not None and outcome.confidence >= 0.65
                    else "low"
                    if outcome.confidence is not None
                    else "none"
                ),
            },
        )
        has_esc = bool(esc and isinstance(esc, dict) and esc.get("primary_path"))
        if has_esc:
            emit_response_flow_event(
                "response_escalation_generated",
                workflow_id=workflow_id,
                user_id=user_id,
                status="ok",
                source="backend",
                metadata={
                    "response_id": rid,
                    "has_escalation_recommendation": True,
                    "primary_path": str(esc.get("primary_path") or "")[:64],
                    "priority": str(esc.get("priority") or "")[:32],
                },
            )
        return {
            "ok": True,
            "responseId": rid,
            "classification": {
                "label": outcome.classification,
                "reasoningSafe": outcome.reasoning_safe,
                "confidence": outcome.confidence,
                "recommendedNextAction": outcome.recommended_next_action,
            },
            "escalationRecommendation": esc,
        }
    except Exception:
        msg = "Classification could not be completed; the intake row was stored for retry."
        rr.update_response_classification(
            rid,
            classification_status="failed",
            response_classification=None,
            classification_reasoning_safe=msg,
            classification_confidence=None,
            recommended_next_action="manual_review_required",
            escalation_recommendation={
                "primary_path": "manual_review_required",
                "reasoning_safe": msg,
                "factors": ["classification_error"],
                "secondary_paths": [],
                "priority": "high",
            },
        )
        emit_response_flow_event(
            "response_classification_failed",
            workflow_id=workflow_id,
            user_id=user_id,
            status="failed",
            source="backend",
            error_code="CLASSIFICATION_FAILED",
            message_safe=msg[:500],
            metadata={
                "response_id": rid,
                "classification_status": "failed",
                "recommended_next_action": "manual_review_required",
            },
        )
        return {
            "ok": True,
            "responseId": rid,
            "classification": None,
            "escalationRecommendation": None,
            "warning": {"code": "CLASSIFICATION_FAILED", "messageSafe": msg},
        }
