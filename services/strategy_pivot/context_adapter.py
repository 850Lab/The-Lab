"""
Build pivot evaluation_context from Phase 12 scenario outputs (read-only).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_pivot_evaluation_context(
    *,
    evaluation_run_id: str,
    scenarios: List[Dict[str, Any]],
    as_of: str,
    canonical_snapshot: Optional[Dict[str, Any]] = None,
    pivot_engine_version: Optional[str] = None,
) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {
        "evaluation_run_id": evaluation_run_id,
        "as_of": as_of,
        "scenarios": list(scenarios),
    }
    if canonical_snapshot is not None:
        ctx["canonical_snapshot"] = dict(canonical_snapshot)
    if pivot_engine_version is not None:
        ctx["pivot_engine_version"] = pivot_engine_version
    return ctx
