"""
Deterministic grouping axes: scope_type, scope_key, pivot_relevance, display_category.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Tuple

_SCOPE_TYPE_ORDER = {"workflow": 0, "account_fingerprint": 1, "bureau": 2}
_PIVOT_REL_ORDER = {"none": 0, "workflow_pivot": 1, "account_pivot": 2, "multi_pivot": 3}
_DISPLAY_CAT_ORDER = {"escalation": 0, "execution": 1, "timing": 2, "generic": 3}


def build_group_id(
    scope_type: str,
    scope_key: str,
    pivot_relevance: str,
    display_category: str,
) -> str:
    payload = json.dumps(
        [scope_type, scope_key, pivot_relevance, display_category],
        separators=(",", ":"),
    )
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"grp_{h}"


def group_sort_key(
    scope_type: str,
    scope_key: str,
    pivot_relevance: str,
    display_category: str,
) -> Tuple[int, str, int, int, str]:
    st = _SCOPE_TYPE_ORDER.get(scope_type, 99)
    pr = _PIVOT_REL_ORDER.get(pivot_relevance, 99)
    dc = _DISPLAY_CAT_ORDER.get(display_category, 99)
    return (st, scope_key, pr, dc, display_category)


def sort_items_in_group(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        items,
        key=lambda x: (int(x.get("priority") or 0), str(x.get("guidance_id") or "")),
    )


def build_grouped_guidance(
    refined_items: List[Dict[str, Any]],
    *,
    include_visibility: Tuple[str, ...] = ("visible", "deferred"),
) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """
    Returns (group rows for the view, map group_id -> ordered items).
    Only items whose visibility is in include_visibility are grouped.
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    meta: Dict[str, Tuple[str, str, str, str]] = {}

    for it in refined_items:
        vis = str(it.get("visibility") or "")
        if vis not in include_visibility:
            continue
        st = str(it.get("scope_type") or "")
        sk = str(it.get("scope_key") or "")
        pr = str(it.get("pivot_relevance") or "none")
        dc = str(it.get("display_category") or "generic")
        gid = build_group_id(st, sk, pr, dc)
        if gid not in buckets:
            meta[gid] = (st, sk, pr, dc)
        buckets.setdefault(gid, []).append(it)

    group_ids = sorted(
        buckets.keys(),
        key=lambda g: group_sort_key(*meta[g]),
    )

    grouped: List[Dict[str, Any]] = []
    ordered_map: Dict[str, List[Dict[str, Any]]] = {}
    for gid in group_ids:
        st, sk, pr, dc = meta[gid]
        ordered = sort_items_in_group(buckets[gid])
        ordered_map[gid] = ordered
        grouped.append(
            {
                "group_id": gid,
                "scope_type": st,
                "scope_key": sk,
                "pivot_relevance": pr,
                "display_category": dc,
                "guidance_ids": [str(x.get("guidance_id") or "") for x in ordered],
                "items": ordered,
            }
        )
    return grouped, ordered_map
