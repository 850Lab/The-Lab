"""
Deterministic integer priority refinement (no floats, no ML).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _tier_for_priority(priority: int, bands: List[Dict[str, Any]]) -> str:
    for b in bands:
        lo = int(b.get("min") or 0)
        hi = int(b.get("max") or 9999)
        if lo <= priority <= hi:
            return str(b.get("tier") or "P3")
    return "P3"


def compute_refined_priority(
    item: Dict[str, Any],
    related_pivots: List[Dict[str, Any]],
    related_scenarios: List[Dict[str, Any]],
    rules: Dict[str, Any],
    *,
    step_context: Dict[str, Any] | None,
) -> Tuple[int, str, List[str]]:
    """
    Returns (refined_priority, priority_tier, reason_codes).
    """
    reasons: List[str] = []
    bounds = rules.get("priority_bounds") or {}
    lo = int(bounds.get("min") or 0)
    hi = int(bounds.get("max") or 200)
    orig = int(item.get("original_priority") or item.get("priority") or 50)
    working = orig

    pivot_rules = rules.get("pivot_link_rules") or []
    pr_by_id = {str(r.get("rule_id")): r for r in pivot_rules if isinstance(r, dict)}
    total_cap = int(rules.get("pivot_priority_total_cap") or 32)
    total_abs_applied = 0

    for rp in sorted(related_pivots, key=lambda x: str(x.get("pivot_id") or "")):
        rid = str(rp.get("rule_id") or "")
        pr = pr_by_id.get(rid)
        if not pr:
            continue
        delta = int(pr.get("priority_delta") or 0)
        per_rule_cap = int(pr.get("max_accumulated_delta") or total_cap)
        lk = str(rp.get("link_kind") or "")
        if lk == "elevate":
            adj = -delta
        elif lk == "deemphasize":
            adj = delta
        else:
            adj = 0
        step_abs = abs(adj)
        if step_abs > per_rule_cap:
            adj = 0
            step_abs = 0
        if total_abs_applied + step_abs > total_cap:
            adj = 0
        else:
            total_abs_applied += step_abs
        working += adj
        if adj != 0:
            reasons.append(f"prio_pivot:{rid}")

    sev_map = rules.get("scenario_severity_tier") or {}
    delta_map = rules.get("severity_priority_delta") or {}
    linked_types = {str(s.get("scenario_type") or "") for s in related_scenarios}
    for st in sorted(linked_types):
        tier = str(sev_map.get(st) or "P3")
        d = int(delta_map.get(tier, 0))
        if d != 0:
            working += d
            reasons.append(f"prio_scenario:{st}:{tier}")

    # step scope: boost primary alignment (negative = more important)
    if step_context:
        mode = str(step_context.get("step_scope_mode") or "")
        policies = rules.get("step_scope_policies") or {}
        pol = policies.get(mode) if isinstance(policies, dict) else None
        if isinstance(pol, dict):
            primary = set(pol.get("primary_scope_types") or [])
            it = str(item.get("scope_type") or "")
            if primary and it in primary:
                working -= 2
                reasons.append("prio_step_primary_scope")

    working = max(lo, min(hi, working))
    bands = rules.get("priority_tier_bands") or []
    tier = _tier_for_priority(working, bands if isinstance(bands, list) else [])
    return working, tier, sorted(set(reasons))


_EMPHASIS_RANK = {"primary": 0, "secondary": 1, "standard": 2, "muted": 3}


def compute_emphasis(
    item: Dict[str, Any],
    related_pivots: List[Dict[str, Any]],
    rules: Dict[str, Any],
    default_emphasis: str,
) -> Tuple[str, List[str]]:
    reasons: List[str] = []
    emphasis = default_emphasis
    best_rank = _EMPHASIS_RANK.get(emphasis, 99)
    best_rule = ""
    pivot_rules = {str(r.get("rule_id")): r for r in (rules.get("pivot_link_rules") or []) if isinstance(r, dict)}
    for rp in sorted(related_pivots, key=lambda x: str(x.get("pivot_id") or "")):
        pr = pivot_rules.get(str(rp.get("rule_id") or ""))
        if not pr:
            continue
        el = pr.get("emphasis_level")
        if not el:
            continue
        el_s = str(el)
        rnk = _EMPHASIS_RANK.get(el_s, 99)
        rid = str(rp.get("rule_id") or "")
        if rnk < best_rank or (rnk == best_rank and (not best_rule or rid < best_rule)):
            best_rank = rnk
            emphasis = el_s
            best_rule = rid
            reasons = [f"emphasis:{rid}"]
    return emphasis, sorted(set(reasons))
