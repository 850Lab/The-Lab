"""
Pure builder: guidance_items + pivots + scenarios -> GuidanceView.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .digest import compute_refinement_input_digest
from .filter_visibility import (
    apply_pivot_suppress_rules,
    apply_scope_focus_rules,
    apply_step_scope_visibility,
    combine_visibility,
)
from .group import build_grouped_guidance
from .linking import (
    link_pivots_for_item,
    link_scenarios_for_item,
    pivot_relevance_detailed,
)
from .prioritize import compute_emphasis, compute_refined_priority
from .schema import REFINEMENT_VERSION_DEFAULT, VIS_DEFERRED, VIS_VISIBLE, guidance_view_dict, refined_item_dict

_RULES_PATH = Path(__file__).resolve().parent / "registry" / "v1" / "refinement_rules.json"


def load_refinement_rules() -> Dict[str, Any]:
    with open(_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _view_id(workflow_id: str, evaluation_run_id: str, digest: str) -> str:
    raw = f"{workflow_id}|{evaluation_run_id}|{digest}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"gv_{h}"


def _merge_reasons(*parts: List[str]) -> List[str]:
    out: List[str] = []
    for p in parts:
        out.extend(p)
    return sorted(set(out))


def _primary_scope_types(step_context: Dict[str, Any] | None, rules: Dict[str, Any]) -> set[str]:
    if not step_context:
        return set()
    mode = str(step_context.get("step_scope_mode") or "")
    policies = rules.get("step_scope_policies") or {}
    pol = policies.get(mode) if isinstance(policies, dict) else None
    if not isinstance(pol, dict):
        return set()
    return set(pol.get("primary_scope_types") or [])


def build_guidance_view(
    context: Dict[str, Any],
    _rules: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Pure, deterministic. Context keys:
    workflow_id, evaluation_run_id, guidance_items, pivots, scenarios,
    optional step_context, created_at, refinement_version.
    """
    rules = _rules if _rules is not None else load_refinement_rules()
    rules_version = str(rules.get("rules_version") or "refinement_rules@unknown")

    workflow_id = str(context.get("workflow_id") or "")
    run_id = str(context.get("evaluation_run_id") or "")
    step_context = context.get("step_context")
    if step_context is not None:
        step_context = dict(step_context)
    items = sorted(
        list(context.get("guidance_items") or []),
        key=lambda x: str(x.get("guidance_id") or ""),
    )
    pivots = list(context.get("pivots") or [])
    scenarios = list(context.get("scenarios") or [])
    pivots_by_id = {str(p.get("pivot_id") or ""): p for p in pivots}

    digest = compute_refinement_input_digest(context, rules_version)
    view_id = _view_id(workflow_id, run_id, digest)

    ref_ver = str(context.get("refinement_version") or "")
    if not ref_ver:
        ref_ver = f"{REFINEMENT_VERSION_DEFAULT.split('+')[0]}+{rules_version}"

    pivot_link_rules = rules.get("pivot_link_rules") or []
    suppress_rules = rules.get("pivot_suppress_rules") or []
    focus_rules = rules.get("scope_focus_rules") or []
    kind_to_cat = rules.get("guidance_kind_display_category") or {}
    default_cat = str(rules.get("default_display_category") or "execution")
    default_emphasis = str(rules.get("default_emphasis_level") or "standard")

    primary_scopes = _primary_scope_types(step_context, rules)

    refined_rows: List[Dict[str, Any]] = []

    for raw in items:
        item = dict(raw)
        gid = str(item.get("guidance_id") or "")
        kind = str(item.get("guidance_kind") or "generic")
        st = str(item.get("scope_type") or "")
        sk = str(item.get("scope_key") or "")
        triggers = list(item.get("source_triggers") or [])

        related_pivots, link_reasons = link_pivots_for_item(item, pivots, pivot_link_rules)
        related_scenarios, scen_reasons = link_scenarios_for_item(item, scenarios)

        prio, tier, prio_reasons = compute_refined_priority(
            item,
            related_pivots,
            related_scenarios,
            rules,
            step_context=step_context,
        )
        emphasis, emph_reasons = compute_emphasis(item, related_pivots, rules, default_emphasis)

        display_cat = str(kind_to_cat.get(kind) or default_cat)
        pivot_rel = pivot_relevance_detailed(item, related_pivots, pivots_by_id)

        sup_vis, sup_r = apply_pivot_suppress_rules(item, pivots, suppress_rules)
        step_vis, step_r = apply_step_scope_visibility(item, step_context, rules.get("step_scope_policies") or {})
        focus_vis, focus_r = apply_scope_focus_rules(item, step_context, focus_rules)
        visibility = combine_visibility(VIS_VISIBLE, sup_vis, step_vis, focus_vis)
        vis_reasons = list(sup_r) + list(step_r) + list(focus_r)

        all_reasons = _merge_reasons(link_reasons, scen_reasons, prio_reasons, emph_reasons, vis_reasons)

        row = refined_item_dict(
            guidance_id=gid,
            source_triggers=triggers,
            related_pivots=related_pivots,
            related_scenarios=related_scenarios,
            priority=prio,
            priority_tier=tier,
            display_category=display_cat,
            emphasis_level=emphasis,
            visibility=visibility,
            scope_type=st,
            scope_key=sk,
            original_priority=int(item.get("original_priority") or item.get("priority") or 50),
            refinement_reason_codes=all_reasons,
        )
        row["pivot_relevance"] = pivot_rel
        refined_rows.append(row)

    global_priority_order = [
        str(x.get("guidance_id") or "")
        for x in sorted(
            refined_rows,
            key=lambda x: (int(x.get("priority") or 0), str(x.get("guidance_id") or "")),
        )
    ]

    for i, gid in enumerate(global_priority_order):
        for r in refined_rows:
            if str(r.get("guidance_id") or "") == gid:
                r["display_rank"] = i
                break

    grouped, ordered_map = build_grouped_guidance(
        refined_rows,
        include_visibility=(VIS_VISIBLE, VIS_DEFERRED),
    )

    excluded = [dict(x) for x in refined_rows if str(x.get("visibility") or "") not in (VIS_VISIBLE, VIS_DEFERRED)]

    primary_group_ids: List[str] = []
    secondary_group_ids: List[str] = []
    for g in grouped:
        gitems = ordered_map.get(str(g.get("group_id") or ""), [])
        if any(str(it.get("scope_type") or "") in primary_scopes for it in gitems):
            primary_group_ids.append(str(g["group_id"]))
        else:
            secondary_group_ids.append(str(g["group_id"]))
    primary_group_ids = sorted(primary_group_ids)
    secondary_group_ids = sorted(secondary_group_ids)

    for r in refined_rows:
        gid_item = str(r.get("guidance_id") or "")
        vis = str(r.get("visibility") or "")
        if vis not in (VIS_VISIBLE, VIS_DEFERRED):
            continue
        for g in grouped:
            gids = g.get("guidance_ids") or []
            if gid_item in gids:
                g_id = str(g.get("group_id") or "")
                if g_id in primary_group_ids:
                    r["primary_groups"] = [g_id]
                    r["secondary_groups"] = []
                else:
                    r["primary_groups"] = []
                    r["secondary_groups"] = [g_id]
                break

    created_at = str(context.get("created_at") or "")

    return guidance_view_dict(
        guidance_view_id=view_id,
        workflow_id=workflow_id,
        grouped_guidance=grouped,
        global_priority_order=global_priority_order,
        created_at=created_at,
        refinement_version=ref_ver,
        evaluation_run_id=run_id,
        input_digest=digest,
        step_context=step_context,
        primary_groups=primary_group_ids,
        secondary_groups=secondary_group_ids,
        excluded_items=excluded or None,
    )
