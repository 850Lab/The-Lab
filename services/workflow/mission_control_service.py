"""
Mission Control read-only aggregates. Uses ``build_home_summary`` and DB lists — single source of truth.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.workflow.engine import WorkflowEngine
from services.workflow.home_summary_service import build_home_summary
from services.workflow.repository import fetch_session
from services.workflow import mission_control_repository as mc_repo


_SAMPLE_ACTIVE = 250


def get_overview() -> Dict[str, Any]:
    counts = mc_repo.overview_sql_counts()
    active_rows = mc_repo.list_sessions_scan(overall_status="active", limit=_SAMPLE_ACTIVE, offset=0)
    waiting_user = waiting_system = stalled_c = recovery_c = 0
    for s in active_rows:
        hs = build_home_summary(s["workflow_id"])
        if not hs.get("ok"):
            continue
        w = hs.get("waitingOn") or ""
        if w == "waiting_on_user":
            waiting_user += 1
        elif w == "waiting_on_system":
            waiting_system += 1
        if hs.get("stalled"):
            stalled_c += 1
        if hs.get("recoveryActions"):
            recovery_c += 1
    counts["waiting_on_user_in_sample"] = waiting_user
    counts["waiting_on_system_in_sample"] = waiting_system
    counts["stalled_in_active_sample"] = stalled_c
    counts["recovery_actions_non_empty_in_sample"] = recovery_c
    counts["active_sample_size"] = len(active_rows)
    return {
        "ok": True,
        "counts": counts,
        "note": "waiting_on_*, stalled, and recovery_* are computed from build_home_summary over "
        f"the {_SAMPLE_ACTIVE} most recently updated active workflows.",
    }


def _enrich_row(session_row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    wid = session_row.get("workflow_id")
    if not wid:
        return None
    hs = build_home_summary(str(wid))
    if not hs.get("ok"):
        return None
    return {
        "workflowId": hs.get("workflowId"),
        "userId": hs.get("userId"),
        "currentStepId": hs.get("currentStepId"),
        "overallStatus": hs.get("overallStatus"),
        "waitingOn": hs.get("waitingOn"),
        "stalled": hs.get("stalled"),
        "stalledReasons": hs.get("stalledReasons"),
        "escalationAvailable": hs.get("escalationAvailable"),
        "nextBestAction": hs.get("nextBestAction"),
        "failedStep": hs.get("failedStep"),
        "updatedAt": session_row.get("updated_at"),
        "linearPhase": hs.get("linearPhase"),
    }


def list_workflows(
    *,
    overall_status: Optional[str] = None,
    current_step: Optional[str] = None,
    has_failed_step: Optional[bool] = None,
    stalled: Optional[bool] = None,
    waiting_on: Optional[str] = None,
    escalation_available: Optional[bool] = None,
    limit: int = 75,
    offset: int = 0,
) -> Dict[str, Any]:
    scan_limit = min(400, max(limit * 4, limit + offset + 50))
    scan = mc_repo.list_sessions_scan(
        overall_status=overall_status,
        current_step=current_step,
        has_failed_step=has_failed_step,
        limit=scan_limit,
        offset=0,
    )
    items: List[Dict[str, Any]] = []
    skipped = 0
    for s in scan:
        row = _enrich_row(s)
        if not row:
            skipped += 1
            continue
        if stalled is True and not row.get("stalled"):
            continue
        if stalled is False and row.get("stalled"):
            continue
        if waiting_on and row.get("waitingOn") != waiting_on:
            continue
        if escalation_available is True and not row.get("escalationAvailable"):
            continue
        if escalation_available is False and row.get("escalationAvailable"):
            continue
        items.append(row)
    paged = items[offset : offset + limit]
    return {
        "ok": True,
        "items": paged,
        "returned": len(paged),
        "matchedBeforePagination": len(items),
        "scannedSessions": len(scan),
        "skippedEnrichFailures": skipped,
    }


def get_workflow_detail(workflow_id: str) -> Dict[str, Any]:
    session = fetch_session(workflow_id)
    if not session:
        return {"ok": False, "error": {"code": "NOT_FOUND"}}
    eng = WorkflowEngine()
    state = eng.get_state(workflow_id)
    hs = build_home_summary(workflow_id)
    steps = mc_repo.fetch_steps_for_workflow(workflow_id)
    audit = mc_repo.list_admin_audit(workflow_id=workflow_id, limit=100)
    meta = session.get("metadata") or {}
    if isinstance(meta, str):
        import json

        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    override_hist = (meta or {}).get("adminOverrideHistory") or []
    responses_actions = mc_repo.list_responses_recent(
        limit=40,
        offset=0,
        workflow_id=workflow_id,
        needs_review_only=False,
    )
    return {
        "ok": True,
        "session": {
            "workflowId": str(session["workflow_id"]),
            "userId": session["user_id"],
            "workflowType": session.get("workflow_type"),
            "currentStep": session.get("current_step"),
            "overallStatus": session.get("overall_status"),
            "updatedAt": session.get("updated_at"),
            "startedAt": session.get("started_at"),
            "lastErrorCode": session.get("last_error_code"),
            "lastErrorMessageSafe": session.get("last_error_message_safe"),
            "definitionVersion": session.get("definition_version"),
            "engineVersion": session.get("engine_version"),
        },
        "metadata": meta,
        "adminOverrideHistory": override_hist if isinstance(override_hist, list) else [],
        "workflowStateEnvelope": state,
        "homeSummary": hs,
        "steps": steps,
        "adminAudit": audit,
        "responsesForActions": responses_actions,
    }


def list_exceptions(limit: int = 100) -> Dict[str, Any]:
    wids = mc_repo.distinct_workflow_ids_for_exceptions(limit=200)
    out: List[Dict[str, Any]] = []
    for wid in wids[:limit]:
        hs = build_home_summary(wid)
        if not hs.get("ok"):
            continue
        reasons: List[str] = []
        if hs.get("overallStatus") == "failed":
            reasons.append("overall_failed")
        if hs.get("failedStep"):
            reasons.append("failed_step")
        if hs.get("stalled"):
            reasons.append("stalled")
        if hs.get("recoveryActions"):
            for a in hs.get("recoveryActions") or []:
                t = a.get("actionType")
                if t:
                    reasons.append(f"recovery:{t}")
        session = fetch_session(wid)
        meta = session.get("metadata") or {} if session else {}
        if isinstance(meta, str):
            import json

            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        m = (meta or {}).get("mail") or {}
        if isinstance(m, dict):
            if int(m.get("failed_send_count") or 0) > 0 and not m.get("completed_all_sends"):
                reasons.append("mail_retry_or_partial_failure")
        rs = hs.get("responseStatus") or {}
        cls = rs.get("responseClassification") or ""
        if cls == "insufficient_to_classify":
            reasons.append("unclear_classification_latest_response")
        esc = hs.get("escalationAvailable")
        if esc:
            reasons.append("escalation_available")
        if mc_repo.has_failed_reminder(wid):
            reasons.append("reminder_delivery_failed")
        if not reasons:
            continue
        out.append(
            {
                "workflowId": wid,
                "userId": hs.get("userId"),
                "reasons": sorted(set(reasons)),
                "currentStepId": hs.get("currentStepId"),
                "overallStatus": hs.get("overallStatus"),
                "waitingOn": hs.get("waitingOn"),
                "stalled": hs.get("stalled"),
                "nextBestAction": hs.get("nextBestAction"),
            }
        )
    return {"ok": True, "items": out, "returned": len(out)}


def list_responses_queue(
    *,
    limit: int = 100,
    offset: int = 0,
    needs_review_only: bool = False,
) -> Dict[str, Any]:
    rows = mc_repo.list_responses_recent(
        limit=limit,
        offset=offset,
        needs_review_only=needs_review_only,
    )
    enriched = []
    for r in rows:
        manual = False
        rna = r.get("recommended_next_action") or ""
        if rna in mc_repo.MANUAL_REVIEW_ACTIONS:
            manual = True
        if r.get("classification_status") == "failed":
            manual = True
        if r.get("response_classification") == "insufficient_to_classify":
            manual = True
        enriched.append(
            {
                **r,
                "manualReviewSuggested": manual,
            }
        )
    return {"ok": True, "items": enriched, "returned": len(enriched)}


def list_reminders_queue(
    *,
    statuses: Optional[List[str]] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    rows = mc_repo.list_reminders_global(statuses=statuses, limit=limit, offset=offset)
    return {"ok": True, "items": rows, "returned": len(rows)}


def list_admin_audit_global(
    *,
    workflow_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    rows = mc_repo.list_admin_audit(workflow_id=workflow_id, limit=limit, offset=offset)
    return {"ok": True, "items": rows, "returned": len(rows)}
