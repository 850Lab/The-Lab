"""
O.R.I.O.N. guidance evaluation — deterministic, read-mostly, no workflow writes.

V1.1: bounded event lookback + delivery contract (cooldown, channel, recommendedAction).
V1.3: customer bundle adds ``bestActionExplanation`` (deterministic; no extra history reads).
V1.4: customer bundle adds ``deliveryPrioritization`` (interpretation of bundle outputs only).
V1.5: customer bundle adds ``uxSurfaceContract`` (presentation intent; still no workflow writes).

ORION is deterministic. Do NOT inject AI logic here. AI layers must consume ORION outputs, not modify them.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.guidance.guidance_delivery import apply_delivery
from services.guidance.guidance_response_model import GuidanceResponse
from services.guidance.guidance_rules import ALL_RULES, RuleEval
from services.guidance.guidance_storage import persist_guidance_event
from services.workflow.repository import fetch_session, fetch_steps
from services.workflow.workflow_event_service import list_workflow_events

_log = logging.getLogger(__name__)

MAX_RECENT_EVENTS = 25
MAX_EVENT_LOOKBACK_HOURS = 24


def _steps_by_id(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(r.get("step_id") or ""): r for r in rows if r.get("step_id")}


def _parse_event_ts(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s)
        except Exception:
            return None
    return None


def _bounded_recent_events(workflow_id: str) -> List[Dict[str, Any]]:
    """
    Newest-first, at most MAX_RECENT_EVENTS rows, each not older than MAX_EVENT_LOOKBACK_HOURS.
    """
    raw = list_workflow_events(
        workflow_id, limit=MAX_RECENT_EVENTS, oldest_first=False
    )
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_EVENT_LOOKBACK_HOURS)
    out: List[Dict[str, Any]] = []
    for ev in raw:
        if not isinstance(ev, dict):
            continue
        t = _parse_event_ts(ev.get("createdAt"))
        if t is None:
            continue
        if t < cutoff:
            continue
        out.append(ev)
    return out[:MAX_RECENT_EVENTS]


def evaluate_guidance(
    user_id: Optional[int],
    workflow_id: str,
    latest_event: Optional[Dict[str, Any]] = None,
    *,
    persist: bool = True,
    _session: Optional[Dict[str, Any]] = None,
    _steps: Optional[List[Dict[str, Any]]] = None,
) -> Optional[GuidanceResponse]:
    """
    Observe workflow + recent events, run rules, apply delivery, optionally persist.

    Does not advance the workflow engine or mutate step rows.
    """
    wf = (workflow_id or "").strip()
    if not wf:
        return None

    try:
        session = _session if _session is not None else fetch_session(wf)
    except Exception:
        _log.debug("evaluate_guidance fetch_session failed wf=%s", wf, exc_info=True)
        return None

    if not session:
        return None

    uid = int(user_id) if user_id is not None else int(session.get("user_id") or 0)
    if uid < 1:
        return None

    overall = str(session.get("overall_status") or "")
    if overall == "completed":
        return None

    try:
        if _steps is not None:
            steps = _steps
        else:
            steps = fetch_steps(wf, session=session)
    except Exception:
        _log.debug("evaluate_guidance fetch_steps failed wf=%s", wf, exc_info=True)
        steps = []

    sbid = _steps_by_id(steps)
    try:
        events = _bounded_recent_events(wf)
    except Exception:
        events = []

    merged_latest: Optional[Dict[str, Any]] = None
    if latest_event and isinstance(latest_event, dict):
        merged_latest = dict(latest_event)
    elif events:
        merged_latest = events[0] if isinstance(events[0], dict) else None

    ctx: Dict[str, Any] = {
        "session": session,
        "steps_by_id": sbid,
        "recent_events": events,
        "latest_event": merged_latest,
    }

    best: Optional[RuleEval] = None
    for rule_fn in ALL_RULES:
        try:
            ev: RuleEval = rule_fn(ctx)
        except Exception:
            _log.debug("rule %s failed", getattr(rule_fn, "__name__", "?"), exc_info=True)
            continue
        if not ev.get("triggered"):
            continue
        if best is None or int(ev.get("priority") or 0) > int(best.get("priority") or 0):
            best = ev

    if best is None:
        return None

    step_hint = str(session.get("current_step") or "").strip() or "workflow"
    gid = str(uuid.uuid4())
    ts = datetime.now(timezone.utc)
    resp, _suppressed = apply_delivery(
        best,
        workflow_id=wf,
        ctx=ctx,
        guidance_id=gid,
        step_id=step_hint[:64],
        timestamp=ts,
    )

    if persist:
        try:
            persist_guidance_event(user_id=uid, workflow_id=wf, response=resp)
        except Exception:
            _log.debug("persist_guidance_event failed wf=%s", wf, exc_info=True)

    return resp


def guidance_for_api(
    workflow_id: Optional[str],
    user_id: Optional[int] = None,
    latest_event: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Evaluate and return user-deliverable API dict (or None)."""
    if not workflow_id or not str(workflow_id).strip():
        return None
    g = evaluate_guidance(user_id, str(workflow_id).strip(), latest_event)
    if not g:
        return None
    return g.to_user_api_dict()


def customer_orion_bundle_for_api(
    workflow_id: Optional[str],
    user_id: Optional[int] = None,
    latest_event: Optional[Dict[str, Any]] = None,
    *,
    persist_guidance: bool = True,
) -> Dict[str, Any]:
    """
    Single-pass O.R.I.O.N. for customer workflow payloads: guidance + readiness + explanation + prioritization + UX contract.

    Set ``persist_guidance=False`` for read-only snapshots (e.g. ``audit_orion_bundle_for_workflow``) so guidance events are not written.
    """
    from services.guidance.action_explanation import explain_best_action_user_api
    from services.guidance.delivery_prioritization import (
        compute_delivery_prioritization_user_api,
    )
    from services.guidance.ux_surface_contract import compute_ux_surface_contract_user_api
    from services.guidance.action_readiness import (
        build_action_readiness_context,
        compute_action_readiness_for_api,
    )

    def _prioritize(
        *,
        guidance_api: Optional[Dict[str, Any]],
        ar: Dict[str, Any],
        ctx: Dict[str, Any],
        expl: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return compute_delivery_prioritization_user_api(
            guidance=guidance_api,
            best_action=ar.get("bestAction"),
            action_candidates=ar.get("actionCandidates"),
            best_action_explanation=expl,
            readiness_context=ctx,
        )

    def _ux(
        *,
        guidance_api: Optional[Dict[str, Any]],
        ar: Dict[str, Any],
        ctx: Dict[str, Any],
        expl: Optional[Dict[str, Any]],
        dp: Dict[str, Any],
    ) -> Dict[str, Any]:
        return compute_ux_surface_contract_user_api(
            guidance=guidance_api,
            best_action=ar.get("bestAction"),
            best_action_explanation=expl,
            delivery_prioritization=dp,
            readiness_context=ctx,
        )

    dp_empty = compute_delivery_prioritization_user_api(
        guidance=None,
        best_action=None,
        action_candidates=[],
        best_action_explanation=None,
        readiness_context=None,
    )
    empty: Dict[str, Any] = {
        "guidance": None,
        "bestAction": None,
        "actionCandidates": [],
        "bestActionExplanation": None,
        "deliveryPrioritization": dp_empty,
        "uxSurfaceContract": _ux(
            guidance_api=None,
            ar={"bestAction": None, "actionCandidates": []},
            ctx={},
            expl=None,
            dp=dp_empty,
        ),
    }
    if not workflow_id or not str(workflow_id).strip():
        return dict(empty)

    wf = str(workflow_id).strip()
    try:
        session = fetch_session(wf)
    except Exception:
        _log.debug("customer_orion_bundle fetch_session failed wf=%s", wf, exc_info=True)
        return dict(empty)

    if not session:
        return dict(empty)

    uid = int(user_id) if user_id is not None else int(session.get("user_id") or 0)

    try:
        steps = fetch_steps(wf, session=session)
    except Exception:
        _log.debug("customer_orion_bundle fetch_steps failed wf=%s", wf, exc_info=True)
        steps = []

    overall = str(session.get("overall_status") or "")
    if overall == "completed":
        ar = compute_action_readiness_for_api(session, steps, None)
        ctx = build_action_readiness_context(session, steps, guidance_api=None)
        expl = explain_best_action_user_api(ar.get("bestAction"), ctx)
        dp = _prioritize(guidance_api=None, ar=ar, ctx=ctx, expl=expl)
        ux = _ux(guidance_api=None, ar=ar, ctx=ctx, expl=expl, dp=dp)
        return {
            "guidance": None,
            **ar,
            "bestActionExplanation": expl,
            "deliveryPrioritization": dp,
            "uxSurfaceContract": ux,
        }

    g: Optional[GuidanceResponse] = None
    if uid >= 1:
        try:
            g = evaluate_guidance(
                uid,
                wf,
                latest_event,
                persist=persist_guidance,
                _session=session,
                _steps=steps,
            )
        except Exception:
            _log.debug("customer_orion_bundle evaluate_guidance failed wf=%s", wf, exc_info=True)

    guidance_api = g.to_user_api_dict() if g else None
    ar = compute_action_readiness_for_api(session, steps, guidance_api)
    ctx = build_action_readiness_context(session, steps, guidance_api=guidance_api)
    expl = explain_best_action_user_api(ar.get("bestAction"), ctx)
    dp = _prioritize(guidance_api=guidance_api, ar=ar, ctx=ctx, expl=expl)
    ux = _ux(guidance_api=guidance_api, ar=ar, ctx=ctx, expl=expl, dp=dp)
    return {
        "guidance": guidance_api,
        **ar,
        "bestActionExplanation": expl,
        "deliveryPrioritization": dp,
        "uxSurfaceContract": ux,
    }
