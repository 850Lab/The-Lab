"""
Canonical writers for ``workflow_sessions`` / ``workflow_steps`` lifecycle fields.

All step status and overall_status changes should go through this module so transitions
stay allowlisted. Metadata-only patches use ``patch_session_metadata`` helpers (no
overall_status validation).

Illegal lifecycle transitions raise ``WorkflowTransitionRejected`` (programmer/operator
contract violation — callers must validate before invoking).
"""

from __future__ import annotations

from typing import Any, Dict, Final, FrozenSet, Tuple

from services.workflow.repository import (
    _UNSET,
    update_session_fields,
    update_step_fields,
)
from services.workflow.workflow_event_service import record_event_tx


class WorkflowTransitionRejected(ValueError):
    """Raised when a requested session or step status change is not on the allowlist."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


# --- Step.status edges (linear dispute workflow) ---
ALLOWED_STEP_STATUS_EDGES: Final[FrozenSet[Tuple[str, str]]] = frozenset(
    {
        ("not_started", "available"),
        ("available", "in_progress"),
        ("failed", "in_progress"),
        ("in_progress", "completed"),
        ("in_progress", "failed"),
        ("failed", "available"),
        # Programmatic only: begin next dispute round after linear completion.
        ("completed", "available"),
    }
)

# --- workflow_sessions.overall_status edges ---
ALLOWED_SESSION_OVERALL_EDGES: Final[FrozenSet[Tuple[str, str]]] = frozenset(
    {
        ("active", "completed"),
        ("active", "failed"),
        ("failed", "active"),
        ("completed", "active"),
    }
)


def _ensure_step_edge(from_status: str, to_status: str) -> None:
    pair = (from_status, to_status)
    if pair in ALLOWED_STEP_STATUS_EDGES:
        return
    if from_status == to_status:
        return
    raise WorkflowTransitionRejected(
        "ILLEGAL_STEP_TRANSITION",
        f"Disallowed step status change: {from_status!r} -> {to_status!r}",
    )


def _ensure_session_overall_edge(from_status: str, to_status: str) -> None:
    if from_status == to_status:
        return
    pair = (from_status, to_status)
    if pair in ALLOWED_SESSION_OVERALL_EDGES:
        return
    raise WorkflowTransitionRejected(
        "ILLEGAL_SESSION_TRANSITION",
        f"Disallowed overall_status change: {from_status!r} -> {to_status!r}",
    )


def mutate_step(
    conn,
    cur,
    workflow_id: str,
    step_id: str,
    *,
    prior_step_status: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Forward to ``update_step_fields`` after validating a step ``status`` change, if any.

    When ``status`` is passed and not None, ``prior_step_status`` must reflect the row
    state before this update (same transaction / known head).
    """
    new_status = kwargs.get("status", _UNSET)
    if new_status is not _UNSET and new_status is not None:
        if prior_step_status is None:
            raise WorkflowTransitionRejected(
                "MISSING_PRIOR_STEP_STATUS",
                "prior_step_status is required when setting step status",
            )
        _ensure_step_edge(prior_step_status, str(new_status))
    update_step_fields(conn, cur, workflow_id, step_id, **kwargs)
    if new_status is not _UNSET and new_status is not None and prior_step_status is not None:
        if str(prior_step_status) != str(new_status):
            record_event_tx(
                conn,
                cur,
                workflow_id,
                "step.status",
                step_id=step_id,
                previous_state={"status": str(prior_step_status)},
                new_state={"status": str(new_status)},
                actor="system",
                source="engine",
                metadata={},
            )


def mutate_session(
    conn,
    cur,
    workflow_id: str,
    *,
    prior_overall_status: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Forward to ``update_session_fields`` after validating ``overall_status`` change, if any.
    """
    nu = kwargs.get("overall_status", _UNSET)
    if nu is not _UNSET and prior_overall_status is not None:
        if str(nu) != str(prior_overall_status):
            _ensure_session_overall_edge(str(prior_overall_status), str(nu))

    prior_cs_for_event: Any = None
    cs_kw = kwargs.get("current_step", _UNSET)
    if cs_kw is not _UNSET:
        cur.execute(
            "SELECT current_step FROM workflow_sessions WHERE workflow_id = %s",
            (workflow_id,),
        )
        rw = cur.fetchone()
        if rw:
            if isinstance(rw, tuple):
                prior_cs_for_event = rw[0]
            elif isinstance(rw, dict):
                prior_cs_for_event = rw.get("current_step")
            else:
                prior_cs_for_event = rw["current_step"]

    update_session_fields(conn, cur, workflow_id, **kwargs)

    if nu is not _UNSET and prior_overall_status is not None:
        if str(nu) != str(prior_overall_status):
            record_event_tx(
                conn,
                cur,
                workflow_id,
                "session.overall_status",
                previous_state={"overallStatus": str(prior_overall_status)},
                new_state={"overallStatus": str(nu)},
                actor="system",
                source="engine",
                metadata={},
            )

    if cs_kw is not _UNSET:
        if str(prior_cs_for_event or "") != str(cs_kw or ""):
            record_event_tx(
                conn,
                cur,
                workflow_id,
                "session.current_step",
                previous_state={"currentStep": prior_cs_for_event},
                new_state={"currentStep": cs_kw},
                actor="system",
                source="engine",
                metadata={},
            )


def touch_session_updated_at(conn, cur, workflow_id: str) -> None:
    """Bump ``updated_at`` only."""
    update_session_fields(conn, cur, workflow_id)


def patch_session_metadata(
    conn,
    cur,
    workflow_id: str,
    metadata_patch: Dict[str, Any],
) -> None:
    """JSON-merge metadata keys; does not change overall_status or current_step."""
    update_session_fields(conn, cur, workflow_id, metadata_patch=metadata_patch)
