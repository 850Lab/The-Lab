"""
Deterministic visibility: visible | deferred | hidden | suppressed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .schema import VIS_DEFERRED, VIS_HIDDEN, VIS_SUPPRESSED, VIS_VISIBLE


def apply_pivot_suppress_rules(
    item: Dict[str, Any],
    pivots: List[Dict[str, Any]],
    suppress_rules: List[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    """Return (visibility, reason_codes)."""
    kind = str(item.get("guidance_kind") or "generic")
    active_pivots = [p for p in pivots if not p.get("suppressed_by")]
    ptypes = {str(p.get("pivot_type") or "") for p in active_pivots}
    reasons: List[str] = []
    for rule in suppress_rules:
        if not isinstance(rule, dict):
            continue
        when = rule.get("when_pivot_types") or []
        if not set(when) & ptypes:
            continue
        if str(rule.get("guidance_kind") or "") != kind:
            continue
        vis = str(rule.get("visibility") or VIS_SUPPRESSED)
        rc = str(rule.get("reason_code") or "SUPPRESS_RULE")
        reasons.append(rc)
        return vis, reasons
    return VIS_VISIBLE, []


def apply_step_scope_visibility(
    item: Dict[str, Any],
    step_context: Dict[str, Any] | None,
    policies: Dict[str, Any],
) -> Tuple[str, List[str]]:
    if not step_context:
        return VIS_VISIBLE, []
    mode = str(step_context.get("step_scope_mode") or "")
    if not mode or not isinstance(policies, dict):
        return VIS_VISIBLE, []
    pol = policies.get(mode)
    if not isinstance(pol, dict):
        return VIS_VISIBLE, []
    primary = set(pol.get("primary_scope_types") or [])
    if not primary:
        return VIS_VISIBLE, []
    it = str(item.get("scope_type") or "")
    if it in primary:
        return VIS_VISIBLE, []
    vis = str(pol.get("non_primary_visibility") or VIS_DEFERRED)
    if vis == VIS_VISIBLE:
        return VIS_VISIBLE, []
    rc = pol.get("reason_code")
    reasons = [str(rc)] if rc else ["step_scope_non_primary"]
    return vis, reasons


def apply_scope_focus_rules(
    item: Dict[str, Any],
    step_context: Dict[str, Any] | None,
    focus_rules: List[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    if not step_context or not focus_rules:
        return VIS_VISIBLE, []
    mode = str(step_context.get("step_scope_mode") or "")
    for rule in focus_rules:
        if not isinstance(rule, dict):
            continue
        if str(rule.get("when_step_scope_mode") or "") != mode:
            continue
        applies = set(rule.get("applies_to_scope_types") or [])
        it = str(item.get("scope_type") or "")
        if it not in applies:
            continue
        ctx_key = str(rule.get("require_matching_scope_key_from_context_key") or "")
        required = str(step_context.get(ctx_key) or "")
        if not required:
            continue
        if str(item.get("scope_key") or "") == required:
            return VIS_VISIBLE, []
        vis = str(rule.get("mismatch_visibility") or VIS_HIDDEN)
        rc = str(rule.get("reason_code") or "SCOPE_FOCUS_MISMATCH")
        return vis, [rc]
    return VIS_VISIBLE, []


def combine_visibility(*visibilities: str) -> str:
    order = {VIS_VISIBLE: 0, VIS_DEFERRED: 1, VIS_HIDDEN: 2, VIS_SUPPRESSED: 3}
    return max(visibilities, key=lambda v: order.get(v, 0))
