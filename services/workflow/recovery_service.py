"""
Structured recovery suggestions from workflow + lifecycle signals (no automatic side effects).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.workflow.engine import WorkflowEngine, compute_authoritative_step
from services.workflow import lifecycle_rules as lr
from services.workflow import response_repository as rr


def _parse_meta(session: Dict[str, Any]) -> Dict[str, Any]:
    meta = session.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def compute_recovery_actions(workflow_id: str) -> Dict[str, Any]:
    eng = WorkflowEngine()
    session, steps, smap = eng.get_state_bundle(workflow_id)
    if not session:
        return {"ok": False, "error": {"code": "NOT_FOUND"}, "recoveryActions": []}

    head, _phase = compute_authoritative_step(smap)
    head_row = smap.get(head) if head else None
    head_status = head_row.get("status") if head_row else None
    overall = session.get("overall_status") or "active"
    waiting_on = lr.compute_waiting_attribution(head, head_status, smap)

    latest = rr.fetch_latest_response_for_workflow(workflow_id)
    latest_ts = latest.get("received_at") if latest else None
    if isinstance(latest_ts, datetime):
        latest_dt = latest_ts if latest_ts.tzinfo else latest_ts.replace(tzinfo=timezone.utc)
    else:
        latest_dt = None

    stalled, stalled_reasons = lr.compute_stalled(
        session=session,
        steps_map=smap,
        latest_response_received_at=latest_dt,
    )

    failed_id, re_entry = lr.failed_step_reentry_eligible(smap, overall)

    actions: List[Dict[str, Any]] = []
    meta = _parse_meta(session)
    mail = meta.get("mail") or {}
    if isinstance(mail, dict):
        exp = int(mail.get("expected_unique_bureau_sends") or 1)
        ok_ct = len(mail.get("confirmed_bureaus") or [])
        failed_ct = int(mail.get("failed_send_count") or 0)
        if head == "mail" and ok_ct < exp and failed_ct > 0:
            actions.append(
                {
                    "actionType": "re_run_mail_attempt",
                    "priority": "high",
                    "detailSafe": "Partial mail progress with failures recorded; retry remaining bureaus.",
                    "context": {
                        "expectedUniqueBureauSends": exp,
                        "successfulSendCount": ok_ct,
                        "failedSendCount": failed_ct,
                    },
                }
            )
        elif head == "mail" and ok_ct < exp:
            actions.append(
                {
                    "actionType": "re_run_mail_attempt",
                    "priority": "normal",
                    "detailSafe": "Not all expected bureau sends are complete.",
                    "context": {"expectedUniqueBureauSends": exp, "successfulSendCount": ok_ct},
                }
            )

    if failed_id and re_entry:
        actions.append(
            {
                "actionType": "retry_step",
                "priority": "high",
                "stepId": failed_id,
                "detailSafe": "Failed step may be retried from the app or ops recovery.",
            }
        )
    elif failed_id:
        actions.append(
            {
                "actionType": "request_manual_review",
                "priority": "high",
                "stepId": failed_id,
                "detailSafe": "Failed step is not in the standard retryable set.",
            }
        )

    if waiting_on == "waiting_on_user" and head and head_status == "available":
        actions.append(
            {
                "actionType": "resume_current_step",
                "priority": "normal",
                "stepId": head,
                "detailSafe": "User action required to continue the current step.",
            }
        )

    if waiting_on == "waiting_on_user" and head_status == "failed":
        actions.append(
            {
                "actionType": "retry_step",
                "priority": "high",
                "stepId": head,
                "detailSafe": "Head step is failed; retry or ops reopen.",
            }
        )

    if waiting_on == "waiting_on_system" and stalled:
        actions.append(
            {
                "actionType": "request_manual_review",
                "priority": "normal",
                "detailSafe": "System-owned step appears stalled; verify workers or pipelines.",
                "context": {"stalledReasons": stalled_reasons},
            }
        )

    if waiting_on == "waiting_on_external":
        actions.append(
            {
                "actionType": "upload_missing_document",
                "priority": "low",
                "detailSafe": "Upload bureau or furnisher response when received.",
            }
        )

    if head == "proof_attachment" and waiting_on == "waiting_on_user":
        actions.append(
            {
                "actionType": "upload_missing_document",
                "priority": "normal",
                "detailSafe": "Complete proof bundle (ID, address, signature) if missing.",
            }
        )

    seen = set()
    uniq: List[Dict[str, Any]] = []
    for a in actions:
        key = (a.get("actionType"), a.get("stepId"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(a)

    return {
        "ok": True,
        "workflowId": workflow_id,
        "recoveryActions": uniq,
    }
