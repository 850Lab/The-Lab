"""
Deterministic dedupe, exclusive-pair suppression, and per-scope directive precedence.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Set, Tuple


def _pivot_key(p: Dict[str, Any]) -> Tuple[str, str, str, str]:
    return (
        str(p.get("rule_id") or ""),
        str(p.get("scope_type") or ""),
        str(p.get("scope_key") or ""),
        str(p.get("pivot_type") or ""),
    )


def dedupe_rule_scope_pivot_type(pivots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge pivots that share rule_id + scope + pivot_type (union source_scenarios, merged_from).
    """
    buckets: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    order: List[Tuple[str, str, str, str]] = []
    for p in pivots:
        k = _pivot_key(p)
        if k not in buckets:
            buckets[k] = copy.deepcopy(p)
            order.append(k)
            buckets[k]["merged_from"] = []
        else:
            base = buckets[k]
            seen = {x.get("scenario_id") for x in base.get("source_scenarios") or []}
            for s in p.get("source_scenarios") or []:
                sid = s.get("scenario_id")
                if sid not in seen:
                    base.setdefault("source_scenarios", []).append(copy.deepcopy(s))
                    seen.add(sid)
            base["merged_from"].append(p.get("pivot_id"))
    return [buckets[k] for k in order]


def apply_exclusive_pairs(
    pivots: List[Dict[str, Any]],
    matrix: Dict[str, Any],
) -> List[Dict[str, Any]]:
    pairs = matrix.get("exclusive_pivot_pairs") or []
    if not isinstance(pairs, list):
        return pivots
    out = copy.deepcopy(pivots)
    suppressed_ids: Set[str] = set()

    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            continue
        ta, tb = str(pair[0]), str(pair[1])
        by_scope: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for p in out:
            if p.get("pivot_id") in suppressed_ids:
                continue
            key = (str(p.get("scope_type") or ""), str(p.get("scope_key") or ""))
            by_scope.setdefault(key, []).append(p)

        for _scope, group in by_scope.items():
            pa = [x for x in group if x.get("pivot_type") == ta]
            pb = [x for x in group if x.get("pivot_type") == tb]
            if not pa or not pb:
                continue
            # Choose global winner: min priority across all pa+pb, tie rule_id
            combined = pa + pb
            winner = sorted(
                combined,
                key=lambda x: (int(x.get("priority") or 999), str(x.get("rule_id") or ""), str(x.get("pivot_id") or "")),
            )[0]
            wid = winner["pivot_id"]
            for p in combined:
                if p["pivot_id"] != wid:
                    p["suppressed_by"] = [wid]
                    p["strategy_directives"] = []
                    suppressed_ids.add(p["pivot_id"])

    return out


def apply_directive_category_precedence(pivots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Same (scope_type, scope_key): lower pivot priority number wins each directive category.
    Strips duplicate categories from lower-precedence pivots (directives removed, pivot kept for audit).
    """
    out = copy.deepcopy(pivots)
    by_scope: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for p in out:
        if p.get("suppressed_by"):
            continue
        k = (str(p.get("scope_type") or ""), str(p.get("scope_key") or ""))
        by_scope.setdefault(k, []).append(p)

    for _k, group in by_scope.items():
        ranked = sorted(
            group,
            key=lambda x: (int(x.get("priority") or 999), str(x.get("rule_id") or ""), str(x.get("pivot_id") or "")),
        )
        taken: Set[str] = set()
        for p in ranked:
            dirs = p.get("strategy_directives") or []
            if not isinstance(dirs, list):
                continue
            new_dirs: List[Dict[str, Any]] = []
            for d in dirs:
                if not isinstance(d, dict):
                    continue
                cat = str(d.get("category") or "")
                if cat in taken:
                    continue
                taken.add(cat)
                new_dirs.append(d)
            p["strategy_directives"] = new_dirs
    return out


def apply_conflict_pipeline(
    pivots: List[Dict[str, Any]],
    matrix: Dict[str, Any],
) -> List[Dict[str, Any]]:
    d = dedupe_rule_scope_pivot_type(pivots)
    d = apply_exclusive_pairs(d, matrix)
    d = apply_directive_category_precedence(d)
    return d
