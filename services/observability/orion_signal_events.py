"""
ORION V2.4 — fixed client signal names for Proof script evaluation (observational only).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

ORION_PROOF_SCRIPT_RENDERED = "orion_proof_script_rendered"
ORION_PROOF_SCRIPT_VISIBLE = "orion_proof_script_visible"
ORION_PROOF_SCRIPT_INTERACTED = "orion_proof_script_interacted"
ORION_PROOF_STEP_COMPLETED = "orion_proof_step_completed"

ORION_SIGNAL_EVENTS = frozenset(
    {
        ORION_PROOF_SCRIPT_RENDERED,
        ORION_PROOF_SCRIPT_VISIBLE,
        ORION_PROOF_SCRIPT_INTERACTED,
        ORION_PROOF_STEP_COMPLETED,
    }
)


def map_orion_signal_category_status(event_name: str) -> Tuple[str, str]:
    """(event_category, status) for observability_events."""
    en = (event_name or "").strip()
    if en == ORION_PROOF_STEP_COMPLETED:
        return ("completion", "success")
    if en == ORION_PROOF_SCRIPT_VISIBLE:
        return ("navigation", "info")
    return ("input", "info")


def try_record_orion_signal(
    *,
    user_id: int,
    workflow_id: str,
    event_name: str,
    metadata: Optional[Dict[str, Any]] = None,
    client_timestamp: Optional[str] = None,
) -> None:
    """
    Append one row to ``observability_events`` (never raises).
    Unknown ``event_name`` values are ignored.
    """
    from services.workflow.observability_events import (
        emit_observability_event,
        sanitize_observability_metadata,
    )

    en = (event_name or "").strip()
    if en not in ORION_SIGNAL_EVENTS:
        return
    cat, st = map_orion_signal_category_status(en)
    meta = sanitize_observability_metadata(metadata or {})
    if client_timestamp:
        ts = str(client_timestamp).strip()[:64]
        if ts:
            meta["clientTimestamp"] = ts
    emit_observability_event(
        user_id=int(user_id),
        workflow_id=str(workflow_id).strip(),
        step_id="proof_attachment",
        event_name=en[:120],
        event_category=cat,
        status=st,
        metadata=meta,
        source="frontend",
    )
