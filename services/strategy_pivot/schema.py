"""
Phase 13 — strategy pivot object schema (structured only).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

PIVOT_OBJECT_VERSION = "1.0.0"
PIVOT_ENGINE_VERSION_DEFAULT = "strategy_pivot@1.0.0+rules@1.0.0"


def pivot_dict(
    *,
    pivot_id: str,
    pivot_type: str,
    source_scenarios: List[Dict[str, Any]],
    priority: int,
    scope_type: str,
    scope_key: str,
    strategy_directives: List[Dict[str, Any]],
    reason_code: str,
    created_at: str,
    pivot_engine_version: str,
    evaluation_run_id: str,
    input_digest: str,
    rule_id: str,
    rule_version: str,
    suppressed_by: Optional[List[str]] = None,
    merged_from: Optional[List[str]] = None,
    trace: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "pivot_id": pivot_id,
        "version": PIVOT_OBJECT_VERSION,
        "pivot_type": pivot_type,
        "source_scenarios": list(source_scenarios),
        "priority": int(priority),
        "scope_type": scope_type,
        "scope_key": scope_key,
        "strategy_directives": list(strategy_directives),
        "reason_code": reason_code,
        "created_at": created_at,
        "pivot_engine_version": pivot_engine_version,
        "evaluation_run_id": evaluation_run_id,
        "input_digest": input_digest,
        "rule_id": rule_id,
        "rule_version": rule_version,
    }
    if suppressed_by:
        out["suppressed_by"] = list(suppressed_by)
    if merged_from:
        out["merged_from"] = list(merged_from)
    if trace:
        out["trace"] = list(trace)
    return out
