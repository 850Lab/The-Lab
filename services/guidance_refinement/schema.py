"""
Phase 14 — guidance view schema (structured only, no UI prose in new fields).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

GUIDANCE_VIEW_VERSION = "1.0.0"
REFINEMENT_VERSION_DEFAULT = "guidance_refinement@1.0.0+rules@1.0.0"

VIS_VISIBLE = "visible"
VIS_SUPPRESSED = "suppressed"
VIS_DEFERRED = "deferred"
VIS_HIDDEN = "hidden"


def refined_item_dict(
    *,
    guidance_id: str,
    source_triggers: List[Dict[str, Any]],
    related_pivots: List[Dict[str, Any]],
    related_scenarios: List[Dict[str, Any]],
    priority: int,
    priority_tier: str,
    display_category: str,
    emphasis_level: str,
    visibility: str,
    scope_type: str,
    scope_key: str,
    original_priority: int,
    refinement_reason_codes: Optional[List[str]] = None,
    display_rank: Optional[int] = None,
    primary_groups: Optional[List[str]] = None,
    secondary_groups: Optional[List[str]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "guidance_id": guidance_id,
        "source_triggers": list(source_triggers),
        "related_pivots": list(related_pivots),
        "related_scenarios": list(related_scenarios),
        "priority": int(priority),
        "priority_tier": priority_tier,
        "display_category": display_category,
        "emphasis_level": emphasis_level,
        "visibility": visibility,
        "scope_type": scope_type,
        "scope_key": scope_key,
        "original_priority": int(original_priority),
    }
    if refinement_reason_codes:
        out["refinement_reason_codes"] = sorted(refinement_reason_codes)
    if display_rank is not None:
        out["display_rank"] = int(display_rank)
    if primary_groups:
        out["primary_groups"] = list(primary_groups)
    if secondary_groups:
        out["secondary_groups"] = list(secondary_groups)
    return out


def guidance_view_dict(
    *,
    guidance_view_id: str,
    workflow_id: str,
    grouped_guidance: List[Dict[str, Any]],
    global_priority_order: List[str],
    created_at: str,
    refinement_version: str,
    evaluation_run_id: str,
    input_digest: str,
    step_context: Optional[Dict[str, Any]] = None,
    primary_groups: Optional[List[str]] = None,
    secondary_groups: Optional[List[str]] = None,
    excluded_items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "guidance_view_id": guidance_view_id,
        "version": GUIDANCE_VIEW_VERSION,
        "workflow_id": workflow_id,
        "grouped_guidance": list(grouped_guidance),
        "global_priority_order": list(global_priority_order),
        "created_at": created_at,
        "refinement_version": refinement_version,
        "evaluation_run_id": evaluation_run_id,
        "input_digest": input_digest,
    }
    if step_context is not None:
        out["step_context"] = dict(step_context)
    if primary_groups is not None:
        out["primary_groups"] = list(primary_groups)
    if secondary_groups is not None:
        out["secondary_groups"] = list(secondary_groups)
    if excluded_items is not None:
        out["excluded_items"] = list(excluded_items)
    return out
