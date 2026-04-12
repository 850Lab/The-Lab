"""
Link guidance items to pivots and scenarios (read-only, rule-driven).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _item_kind(item: Dict[str, Any]) -> str:
    return str(item.get("guidance_kind") or "generic")


def _scopes_align(item: Dict[str, Any], pivot: Dict[str, Any]) -> bool:
    it = str(item.get("scope_type") or "")
    ik = str(item.get("scope_key") or "")
    pt = str(pivot.get("scope_type") or "")
    pk = str(pivot.get("scope_key") or "")
    if pt == "workflow":
        return True
    return it == pt and ik == pk


def link_pivots_for_item(
    item: Dict[str, Any],
    pivots: List[Dict[str, Any]],
    pivot_link_rules: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Returns (related_pivots entries, refinement_reason_codes from linking).
    """
    related: List[Dict[str, Any]] = []
    reasons: List[str] = []
    kind = _item_kind(item)
    for rule in pivot_link_rules:
        if not isinstance(rule, dict):
            continue
        ptypes = rule.get("pivot_types") or []
        gk = str(rule.get("guidance_kind") or "")
        if gk != "*" and gk != kind:
            continue
        lk = str(rule.get("link_kind") or "elevate")
        for p in pivots:
            if p.get("suppressed_by"):
                continue
            if str(p.get("pivot_type") or "") not in {str(x) for x in ptypes}:
                continue
            if not _scopes_align(item, p):
                continue
            related.append(
                {
                    "pivot_id": p.get("pivot_id"),
                    "pivot_type": p.get("pivot_type"),
                    "link_kind": lk,
                    "rule_id": rule.get("rule_id"),
                }
            )
            reasons.append(f"link:{rule.get('rule_id')}")
    # dedupe pivot_id
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for r in related:
        pid = r.get("pivot_id")
        if pid in seen:
            continue
        seen.add(pid)
        deduped.append(r)
    return deduped, sorted(set(reasons))


def link_scenarios_for_item(
    item: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    *,
    allowed_statuses: Tuple[str, ...] = ("detected",),
) -> Tuple[List[Dict[str, Any]], List[str]]:
    related: List[Dict[str, Any]] = []
    reasons: List[str] = []
    it = str(item.get("scope_type") or "")
    ik = str(item.get("scope_key") or "")
    for s in scenarios:
        if str(s.get("status") or "") not in allowed_statuses:
            continue
        st = str(s.get("scope_type") or "")
        sk = str(s.get("scope_key") or "")
        if st == "workflow":
            related.append(
                {
                    "scenario_id": s.get("scenario_id"),
                    "scenario_type": s.get("scenario_type"),
                    "link_kind": "workflow_context",
                }
            )
            reasons.append("scenario:workflow")
        elif st == it and sk == ik:
            related.append(
                {
                    "scenario_id": s.get("scenario_id"),
                    "scenario_type": s.get("scenario_type"),
                    "link_kind": "scope_match",
                }
            )
            reasons.append("scenario:scope_match")
    seen = set()
    out: List[Dict[str, Any]] = []
    for r in related:
        sid = r.get("scenario_id")
        if sid in seen:
            continue
        seen.add(sid)
        out.append(r)
    return out, sorted(set(reasons))


def pivot_relevance_label(related_pivots: List[Dict[str, Any]]) -> str:
    if not related_pivots:
        return "none"
    kinds = {str(p.get("link_kind") or "") for p in related_pivots}
    if len(related_pivots) > 1:
        return "multi_pivot"
    # infer workflow vs account from pivot_type prefix not reliable; use link presence
    if "elevate" in kinds or "deemphasize" in kinds:
        return "account_pivot" if related_pivots else "none"
    return "workflow_pivot" if related_pivots else "none"


def pivot_relevance_detailed(
    item: Dict[str, Any],
    related_pivots: List[Dict[str, Any]],
    pivots_by_id: Dict[str, Dict[str, Any]],
) -> str:
    if not related_pivots:
        return "none"
    if len(related_pivots) > 1:
        return "multi_pivot"
    pid = related_pivots[0].get("pivot_id")
    p = pivots_by_id.get(str(pid)) if pid else None
    if not p:
        return "workflow_pivot"
    if str(p.get("scope_type") or "") == "workflow":
        return "workflow_pivot"
    return "account_pivot"
