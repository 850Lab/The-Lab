"""
Customer-facing response intake list + safe JSON projection (workflow API).
"""

from __future__ import annotations

from typing import Any, Dict

from services.workflow import response_repository as rr


def _has_escalation_primary_path(esc: Any) -> bool:
    if not isinstance(esc, dict):
        return False
    p = esc.get("primary_path")
    return isinstance(p, str) and bool(p.strip())


def _iso(dt: Any) -> str:
    if dt is None:
        return ""
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def serialize_customer_response_row(row: Dict[str, Any]) -> Dict[str, Any]:
    ps = row.get("parsed_summary")
    if not isinstance(ps, dict):
        ps = {}
    esc = row.get("escalation_recommendation")
    if not isinstance(esc, dict):
        esc = {}
    summary = (ps.get("summary_safe") or "") if isinstance(ps.get("summary_safe"), str) else ""
    return {
        "responseId": row.get("response_id"),
        "receivedAt": _iso(row.get("received_at")),
        "sourceType": row.get("source_type"),
        "responseChannel": row.get("response_channel"),
        "classificationStatus": row.get("classification_status"),
        "classification": row.get("response_classification"),
        "reasoningSafe": row.get("classification_reasoning_safe"),
        "confidence": row.get("classification_confidence"),
        "recommendedNextAction": row.get("recommended_next_action"),
        "escalationRecommendation": esc,
        "summarySafePreview": summary[:800],
        "storageRef": row.get("storage_ref"),
    }


def build_customer_responses_list_payload(workflow_id: str, *, limit: int = 30) -> Dict[str, Any]:
    rows = rr.list_responses_detailed_for_workflow(workflow_id, limit=limit)
    return {
        "responses": [serialize_customer_response_row(r) for r in rows],
        "count": len(rows),
    }


def build_customer_response_guidance(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single deterministic next-step signal from intake metrics (no workflow mutation).

    Precedence (first match wins):
    1. ``no_responses_yet`` if ``totalResponses == 0``
    2. Else ``escalation_available`` if ``escalationRecommendedCount >= 1``
    3. Else ``classification_issues_present`` if ``classifiedFailureCount >= 1``
    4. Else ``pending_review`` if ``unclassifiedOrPendingCount > 0``
    5. Else ``monitoring_only``
    """
    total = int(metrics.get("totalResponses") or 0)
    esc = int(metrics.get("escalationRecommendedCount") or 0)
    fail = int(metrics.get("classifiedFailureCount") or 0)
    pending = int(metrics.get("unclassifiedOrPendingCount") or 0)

    if total == 0:
        return {
            "primaryState": "no_responses_yet",
            "title": "No responses recorded yet",
            "message": (
                "When you receive a bureau or furnisher reply, add it here so we can "
                "review the next step."
            ),
        }
    if esc >= 1:
        return {
            "primaryState": "escalation_available",
            "title": "You have escalation opportunities",
            "message": "At least one response suggests a stronger next step is available.",
            "actionLabel": "Continue to escalation",
            "actionTarget": "/escalation",
        }
    if fail >= 1:
        return {
            "primaryState": "classification_issues_present",
            "title": "Some responses need a clearer summary",
            "message": (
                "At least one response could not be classified. Review what you entered "
                "below and submit an update if needed."
            ),
        }
    if pending > 0:
        return {
            "primaryState": "pending_review",
            "title": "Some responses are still processing",
            "message": (
                "One or more submissions are not fully classified yet. Refresh in a moment "
                "or check the list below."
            ),
        }
    return {
        "primaryState": "monitoring_only",
        "title": "Keep monitoring responses",
        "message": (
            "Your recorded responses do not currently suggest an escalation step."
        ),
    }


def build_customer_response_metrics_payload(workflow_id: str) -> Dict[str, Any]:
    """
    Aggregates from persisted ``workflow_response_intake`` rows only (no audit log parsing).
    """
    rows = rr.list_response_intake_metric_rows(workflow_id)
    total = len(rows)
    classified_success = sum(
        1 for r in rows if (r.get("classification_status") or "") == "classified"
    )
    classified_failure = sum(
        1 for r in rows if (r.get("classification_status") or "") == "failed"
    )
    resolved = classified_success + classified_failure
    classification_success_rate: float | None
    if resolved > 0:
        classification_success_rate = round(classified_success / resolved, 4)
    else:
        classification_success_rate = None

    escalation_recommended = sum(
        1 for r in rows if _has_escalation_primary_path(r.get("escalation_recommendation"))
    )
    if total > 0:
        escalation_rate = round(escalation_recommended / total, 4)
    else:
        escalation_rate = None

    unclassified_or_pending = max(0, total - resolved)

    latest = rows[0] if rows else None
    latest_response_at = _iso(latest.get("received_at")) if latest else ""
    latest_classification_status = (
        str(latest.get("classification_status") or "") if latest else ""
    )
    latest_response_channel = str(latest.get("response_channel") or "") if latest else ""
    latest_source_type = str(latest.get("source_type") or "") if latest else ""
    latest_recommended_next_action = (
        str(latest.get("recommended_next_action") or "") if latest else ""
    )

    metrics_inner: Dict[str, Any] = {
        "totalResponses": total,
        "classifiedSuccessCount": classified_success,
        "classifiedFailureCount": classified_failure,
        "unclassifiedOrPendingCount": unclassified_or_pending,
        "classificationSuccessRate": classification_success_rate,
        "escalationRecommendedCount": escalation_recommended,
        "escalationRate": escalation_rate,
        "latestResponseAt": latest_response_at,
        "latestClassificationStatus": latest_classification_status or None,
        "latestResponseChannel": latest_response_channel or None,
        "latestSourceType": latest_source_type or None,
        "latestRecommendedNextAction": latest_recommended_next_action or None,
    }
    return {
        "metrics": metrics_inner,
        "guidance": build_customer_response_guidance(metrics_inner),
    }
