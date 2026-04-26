"""
Authoritative program brain for the consumer workflow: one JSON shape for step, routes, and CTA.
Derived from DB + integrity hints only (no client inference).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.workflow import registry as reg
from services.workflow.engine import WorkflowEngine, compute_authoritative_step
from services.workflow.home_summary_service import (
    STEP_ROUTE_HINTS,
    _next_best_action,
    build_home_summary,
)
from services.workflow.integrity_hints_service import build_integrity_hints

_VERSION = "program_state_v1"


def _canon_route(head: Optional[str], is_complete: bool) -> str:
    if is_complete or not head:
        return "/tracking"
    return STEP_ROUTE_HINTS.get(str(head), "/")


def _allowed_routes(
    head: Optional[str],
    is_complete: bool,
    mail_blocked: bool,
) -> List[str]:
    if is_complete or not head:
        return ["/tracking"]
    h = str(head)
    if h == "review_claims":
        return ["/prepare", "/analyze", "/upload"]
    if h == "mail" and mail_blocked:
        return ["/send", "/tracking"]
    return [_canon_route(head, False)]


def _action_label(
    head: Optional[str],
    head_status: Optional[str],
    phase: str,
    overall: str,
) -> str:
    if overall == "completed" or phase == "done":
        return "View tracking and responses"
    if overall == "failed":
        return "Resolve the failed step"
    if not head:
        return "Continue your program"
    st = str(head_status or "")
    name = reg.STEP_REGISTRY.get(str(head), reg.STEP_REGISTRY.get("upload"))
    title = (name.name if name else str(head))[:64]
    if st == "available":
        return f"Start: {title}"
    if st == "in_progress":
        return f"Finish: {title}"
    if st == "failed":
        return f"Retry: {title}"
    return f"Continue: {title}"


def _effective_next_target_route(
    head: Optional[str],
    phase: str,
    overall: str,
    hints: Dict[str, Any],
    canonical: str,
) -> str:
    if overall == "completed" or phase == "done":
        return "/tracking"
    h = str(head) if head else ""
    if hints.get("mailBlocked") and h == "mail":
        return "/tracking"
    if bool(hints.get("entitlementsButPaymentIncomplete")):
        return "/payment"
    if hints.get("nextRequiredAction") == "proof" and str(head) in (
        "proof_attachment",
        "mail",
    ):
        return "/proof"
    if hints.get("nextRequiredAction") in ("mail",) and h == "mail" and not hints.get(
        "mailBlocked"
    ):
        return "/send"
    return canonical


def _build_progress(
    order: Tuple[str, ...], smap: Dict[str, Dict[str, Any]], head: Optional[str]
) -> Dict[str, Any]:
    order_list = list(order)
    n = len(order_list)
    completed: List[str] = []
    for sid in order_list:
        st = (smap.get(sid) or {}).get("status")
        if str(st or "") == "completed":
            completed.append(sid)
    h_idx: Optional[int] = None
    if head in order_list:
        h_idx = order_list.index(head)
    is_done = h_idx is None and len(completed) >= n
    if h_idx is not None:
        current_1b = h_idx + 1
    elif is_done or not head:
        current_1b = n
    else:
        current_1b = max(1, min(n, len(completed) or 1))
    upcoming: List[str] = []
    if h_idx is not None:
        for j in range(h_idx + 1, n):
            sid = order_list[j]
            st = (smap.get(sid) or {}).get("status")
            if str(st or "") != "completed":
                upcoming.append(sid)
    return {
        "current": int(current_1b),
        "total": int(n),
        "completedSteps": completed,
        "upcomingSteps": upcoming,
    }


def _blocking_from_home_and_hints(
    home: Dict[str, Any], hints: Dict[str, Any]
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if bool(hints.get("workflowStepMismatch")):
        out.append(
            {
                "code": "WORKFLOW_STEP_MISMATCH",
                "message": "Workflow step state is out of sync. Refresh the page or contact support.",
                "severity": "error",
            }
        )
    if bool(hints.get("entitlementsButPaymentIncomplete")):
        out.append(
            {
                "code": "PAYMENT_ENTITLEMENT_MISMATCH",
                "message": "You have access to letters but the payment step is not marked complete. Complete or reconcile payment to continue.",
                "severity": "error",
            }
        )
    if bool(hints.get("paymentCompletedButWrongStep")):
        out.append(
            {
                "code": "PAYMENT_COMPLETION_STALE",
                "message": "Payment is recorded, but the workflow is not on the next step. This should resolve on refresh.",
                "severity": "error",
            }
        )
    if bool(hints.get("mailingDebitWithoutSend")):
        out.append(
            {
                "code": "MAILING_DEBIT_WITHOUT_SEND",
                "message": "A mailings credit was used without a confirmed send. An operator or support may need to reconcile the ledger.",
                "severity": "error",
            }
        )
    if bool(hints.get("proofIncomplete")) and bool(hints.get("nextRequiredAction") == "proof"):
        out.append(
            {
                "code": "PROOF_INCOMPLETE",
                "message": "ID and address proof (and signature) must be complete before mailing can proceed.",
                "severity": "error",
            }
        )
    if bool(hints.get("mailBlocked")) and bool(
        (home or {}).get("currentStepId") in ("mail", "proof_attachment")
    ):
        out.append(
            {
                "code": "MAIL_CARRIER_UNAVAILABLE",
                "message": "Mail sending is blocked by configuration. Continue in tracking; support may need to re-enable the carrier path.",
                "severity": "warning",
            }
        )
    if bool(home.get("failedStep")) and isinstance((home or {}).get("failedStep"), dict):
        f = (home or {}).get("failedStep")
        if isinstance(f, dict):
            msg = str(f.get("messageSafe") or "A workflow step has failed. Retry the step or contact support.")
            out.append(
                {
                    "code": "FAILED_STEP",
                    "message": msg,
                    "severity": "error",
                }
            )
    return out


def build_program_state(user_id: int, workflow_id: str) -> Dict[str, Any]:
    home = build_home_summary(workflow_id)
    if not home.get("ok"):
        return {
            "ok": False,
            "version": _VERSION,
            "error": home.get("error") or {"code": "UNAVAILABLE", "messageSafe": "Not available."},
        }

    hints = build_integrity_hints(int(user_id), str(workflow_id))
    eng = WorkflowEngine()
    _session, _steps, smap = eng.get_state_bundle(str(workflow_id))
    if not _session or not smap:
        return {
            "ok": False,
            "version": _VERSION,
            "error": {"code": "NOT_FOUND", "messageSafe": "Workflow not found or empty state."},
        }
    order = reg.linear_order_for(
        str(_session.get("workflow_type") or reg.WORKFLOW_TYPE_DEFAULT)
    )
    head, phase = compute_authoritative_step(smap, order)
    head_row = smap.get(head) if head else None
    head_status = (head_row or {}).get("status")
    if isinstance(head_status, str):
        hss = head_status
    else:
        hss = str(head_status) if head_status is not None else None
    overall = str(_session.get("overall_status") or "active")
    is_complete = phase == "done" or overall == "completed"

    canonical = _canon_route(head, is_complete)
    mail_blk = bool(hints.get("mailBlocked"))
    allowed = _allowed_routes(head, is_complete, mail_blk)
    nba_desc = _next_best_action(
        str(head) if head else None,
        hss,
        str(phase) if phase else "active",
        str(overall),
    )
    label = _action_label(
        str(head) if head else None,
        hss,
        str(phase) if phase else "active",
        str(overall),
    )
    target = _effective_next_target_route(
        str(head) if head else None,
        str(phase) if phase else "active",
        str(overall),
        hints,
        canonical,
    )
    blocking = _blocking_from_home_and_hints(home, hints)
    progress = _build_progress(
        order,
        smap,
        str(head) if head and not is_complete else None,
    )
    nba_req = not is_complete
    merged = list(allowed)
    if target and target not in merged:
        merged.append(target)
    return {
        "ok": True,
        "version": _VERSION,
        "workflowId": str(home.get("workflowId") or str(workflow_id)).strip(),
        "currentStep": (str(head) if head and not is_complete else None),
        "stepStatus": hss,
        "canonicalRoute": canonical,
        "allowedNavRoutes": merged,
        "nextBestAction": {
            "label": label,
            "description": nba_desc,
            "targetRoute": target,
            "required": nba_req,
        },
        "progress": progress,
        "blockingIssues": blocking,
        "isComplete": is_complete,
    }
