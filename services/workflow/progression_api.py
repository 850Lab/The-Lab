"""
Canonical API slice for workflow progression (consumer, org program, public demo).

**Reader contract:** Prefer ``canonicalProgression`` (from
``build_canonical_progression_envelope_from_resume``) as the only authoritative
client-facing progression shape. Slim ``progression`` mirrors the same engine state.

Authority: ``workflow_sessions`` + ``workflow_steps`` (``WorkflowEngine``). This module
builds stable JSON; ``organization_program_progress`` and similar tables are
**non-authoritative** delivery / instructor-overlay / mirrored caches (see
``services.program_progress_service``).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.workflow.engine import compute_authoritative_step
from services.workflow.registry import WORKFLOW_TYPE_DEFAULT, linear_order_for


def surface_from_workflow_metadata(metadata: Any) -> str:
    if not isinstance(metadata, dict):
        return "consumer"
    if metadata.get("programContext") == "org":
        return "org_program"
    if metadata.get("public_demo") is True:
        return "public_demo"
    return "consumer"


def build_canonical_progression_envelope_from_resume(
    envelope: Dict[str, Any],
    *,
    surface_override: Optional[str] = None,
    include_integrity_hints: bool = True,
) -> Dict[str, Any]:
    """
    Single authoritative progression shape for consumer, org program, and public demo.

    Fields mirror the workflow resume envelope plus optional ``integrityHints`` from
    ``build_integrity_hints`` (consumer-oriented signals; org workflows may return
    mostly-false flags where step ids do not match consumer linear semantics).
    """
    from services.workflow.integrity_hints_service import build_integrity_hints

    ws = envelope.get("workflowState") or {}
    wf_id = str(ws.get("workflowId") or "").strip() or None
    slim = unified_progression_from_workflow_envelope(envelope)
    meta = ws.get("metadata") if isinstance(ws.get("metadata"), dict) else {}
    surf = (surface_override or surface_from_workflow_metadata(meta) or "consumer").strip()

    ctx: Dict[str, Any] = {"surface": surf}
    eid = meta.get("organizationProgramEnrollmentId")
    if eid is not None:
        ctx["organizationProgramEnrollmentId"] = eid
    oid = meta.get("organizationId")
    if oid is not None:
        ctx["organizationId"] = oid
    if meta.get("public_demo") is True and meta.get("public_demo_scenario"):
        ctx["publicDemoScenarioId"] = meta.get("public_demo_scenario")

    from services.workflow.escalation_engine import escalation_summary_for_progression

    esc = escalation_summary_for_progression(meta)
    if esc:
        ctx["escalation"] = esc

    if not wf_id:
        return {
            "model": "canonical_progression_v1",
            "context": ctx,
            "workflowId": None,
            "workflowType": None,
            "overallStatus": None,
            "currentStep": None,
            "stepStatus": [],
            "nextAvailableActions": envelope.get("nextAvailableActions") or [],
            "integrityHints": None,
            "actionResult": envelope.get("actionResult"),
            "userMessage": envelope.get("userMessage"),
            "error": envelope.get("error") or slim.get("error"),
            "progression": slim,
        }

    uid = ws.get("userId")
    hints = None
    if include_integrity_hints and uid is not None:
        try:
            hints = build_integrity_hints(int(uid), wf_id)
        except Exception:
            hints = None

    return {
        "model": "canonical_progression_v1",
        "context": ctx,
        "workflowId": wf_id,
        "workflowType": slim.get("workflowType"),
        "overallStatus": ws.get("overallStatus"),
        "currentStep": slim.get("headStepId"),
        "stepStatus": envelope.get("stepStatus") or [],
        "nextAvailableActions": envelope.get("nextAvailableActions") or [],
        "integrityHints": hints,
        "actionResult": envelope.get("actionResult"),
        "userMessage": envelope.get("userMessage"),
        "error": envelope.get("error"),
        "progression": slim,
    }


def unified_progression_from_workflow_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stable progression contract (``model``: ``workflow_session_v1``).

    Derived from the same fields as ``/api/workflows/{id}/resume`` (``workflowState``,
    ``stepStatus``, ``nextAvailableActions``) so consumer, org, and demo align without
    replacing the legacy envelope yet.
    """
    ws = envelope.get("workflowState") or {}
    wf_id = str(ws.get("workflowId") or "").strip() or None
    if not wf_id:
        ar = envelope.get("actionResult")
        return {
            "model": "workflow_session_v1",
            "surface": "unknown",
            "actionResult": ar,
            "workflowId": None,
            "workflowType": None,
            "overallStatus": None,
            "headStepId": None,
            "phase": "error" if envelope.get("error") or ar == "error" else "unknown",
            "linearOrder": [],
            "completedStepIds": [],
            "nextAvailableActions": envelope.get("nextAvailableActions") or [],
            "error": envelope.get("error"),
        }

    wf_type = str(ws.get("workflowType") or WORKFLOW_TYPE_DEFAULT).strip()
    order = linear_order_for(wf_type)
    raw_steps = envelope.get("stepStatus") or []
    smap: Dict[str, Dict[str, Any]] = {}
    for row in raw_steps:
        sid = row.get("stepId")
        if sid:
            smap[str(sid)] = {"status": row.get("status")}
    head, phase = compute_authoritative_step(smap, order)
    completed = [
        sid for sid in order if str((smap.get(sid) or {}).get("status")) == "completed"
    ]
    meta = ws.get("metadata") if isinstance(ws.get("metadata"), dict) else {}
    surface = surface_from_workflow_metadata(meta)

    return {
        "model": "workflow_session_v1",
        "surface": surface,
        "actionResult": envelope.get("actionResult"),
        "workflowId": wf_id,
        "workflowType": wf_type,
        "overallStatus": ws.get("overallStatus"),
        "headStepId": head,
        "phase": phase,
        "linearOrder": list(order),
        "completedStepIds": completed,
        "nextAvailableActions": envelope.get("nextAvailableActions") or [],
        "error": envelope.get("error"),
    }


def build_org_participant_progression_bundle(
    user_id: int, enrollment_id: int
) -> Optional[Dict[str, Any]]:
    """
    Canonical read bundle for an org enrollment: one ``WorkflowEngine.resume`` on
    ``program_workflow_id``. Returns ``None`` if no workflow is bound yet.

    Use this anywhere org participant/instructor APIs expose progression so clients
    do not rely on milestone projection rows as truth.
    """
    from services.program_enrollment_service import get_program_workflow_id_for_enrollment
    from services.workflow.engine import WorkflowEngine

    wid = get_program_workflow_id_for_enrollment(int(enrollment_id))
    if not wid:
        return None
    env = WorkflowEngine().resume(wid)
    return {
        "progression": unified_progression_from_workflow_envelope(env),
        "canonicalProgression": build_canonical_progression_envelope_from_resume(
            env, surface_override="org_program"
        ),
    }
