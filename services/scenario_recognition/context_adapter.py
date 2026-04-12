"""
Minimal helpers to build evaluation_context dicts from plain data.

Does not import workflow, execution, or law layers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_evaluation_context(
    *,
    evaluation_run_id: str,
    canonical_snapshot: Optional[Dict[str, Any]] = None,
    cross_bureau_slices: Optional[List[Dict[str, Any]]] = None,
    workflow_id: Optional[str] = None,
    detected_at: Optional[str] = None,
    detector_version: Optional[str] = None,
) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {
        "evaluation_run_id": evaluation_run_id,
        "canonical_snapshot": dict(canonical_snapshot or {}),
        "cross_bureau_slices": list(cross_bureau_slices or []),
    }
    if workflow_id is not None:
        ctx["workflow_id"] = workflow_id
    if detected_at is not None:
        ctx["detected_at"] = detected_at
    if detector_version is not None:
        ctx["detector_version"] = detector_version
    return ctx
