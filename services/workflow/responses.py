"""
Uniform API envelope for workflow endpoints (backend authority contract).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def workflow_envelope(
    *,
    action_result: str,
    workflow_state: Optional[Dict[str, Any]] = None,
    step_status: Optional[List[Dict[str, Any]]] = None,
    user_message: str = "",
    next_available_actions: Optional[List[Dict[str, Any]]] = None,
    async_task_state: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "actionResult": action_result,
        "workflowState": workflow_state or {},
        "stepStatus": step_status or [],
        "userMessage": user_message,
        "nextAvailableActions": next_available_actions or [],
        "asyncTaskState": async_task_state,
        "error": error,
    }


def safe_error(code: str, message_safe: str, detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"code": code, "messageSafe": message_safe}
    if detail:
        out["detail"] = detail
    return out
