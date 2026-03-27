"""
Structured workflow audit lines for customer response intake (log aggregation).

Uses ``log_workflow_event`` — no raw response text, only safe derived fields.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.workflow.audit_log import log_workflow_event

# Authoritative linear step for post-mail response handling (matches customer shell guard).
RESPONSE_FLOW_STEP_ID = "track"


def _summary_length_bucket(parsed_summary: Optional[Dict[str, Any]]) -> str:
    if not isinstance(parsed_summary, dict):
        return "none"
    s = parsed_summary.get("summary_safe")
    if not isinstance(s, str):
        return "none"
    n = len(s.strip())
    if n == 0:
        return "empty"
    if n < 32:
        return "lt_32"
    if n <= 200:
        return "m_32_200"
    return "gt_200"


def _safe_meta(meta: Optional[Dict[str, Any]], max_pairs: int = 24) -> Dict[str, Any]:
    if not meta:
        return {}
    out: Dict[str, Any] = {}
    for i, (k, v) in enumerate(meta.items()):
        if i >= max_pairs:
            break
        key = str(k)[:64]
        if v is None or isinstance(v, (bool, int, float)):
            out[key] = v
        elif isinstance(v, str):
            out[key] = v[:200]
        else:
            out[key] = str(v)[:200]
    return out


def emit_response_flow_event(
    event_name: str,
    *,
    workflow_id: str,
    user_id: int,
    step_id: str = RESPONSE_FLOW_STEP_ID,
    status: str = "ok",
    source: str = "backend",
    metadata: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    message_safe: Optional[str] = None,
) -> None:
    """Emit one JSON line via workflow audit logger (``workflow_audit``)."""
    extra: Dict[str, Any] = {
        "event_name": event_name,
        "status": status,
        **_safe_meta(metadata),
    }
    log_workflow_event(
        event_name,
        workflow_id=str(workflow_id),
        step_id=step_id,
        source=source[:64],
        user_id=int(user_id),
        error_code=error_code,
        message_safe=message_safe[:500] if message_safe else None,
        extra=extra,
    )
