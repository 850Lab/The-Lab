"""
Build refinement evaluation context (read-only DTOs).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_refinement_context(
    *,
    workflow_id: str,
    evaluation_run_id: str,
    guidance_items: List[Dict[str, Any]],
    pivots: Optional[List[Dict[str, Any]]] = None,
    scenarios: Optional[List[Dict[str, Any]]] = None,
    step_context: Optional[Dict[str, Any]] = None,
    created_at: Optional[str] = None,
    refinement_version: Optional[str] = None,
) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {
        "workflow_id": workflow_id,
        "evaluation_run_id": evaluation_run_id,
        "guidance_items": list(guidance_items),
        "pivots": list(pivots or []),
        "scenarios": list(scenarios or []),
    }
    if step_context is not None:
        ctx["step_context"] = dict(step_context)
    if created_at is not None:
        ctx["created_at"] = created_at
    if refinement_version is not None:
        ctx["refinement_version"] = refinement_version
    return ctx
