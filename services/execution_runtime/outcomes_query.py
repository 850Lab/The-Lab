"""
Flatten persisted execution outcomes for operator / pattern-discovery queries.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.execution_progress.models import ExecutionProgressState, OutcomeRecord

from .repository import list_execution_runs_for_admin

OUTCOME_FLAT_CAP = 5000


def _ts_iso(v: Any) -> str:
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _outcome_to_dto(row: Dict[str, Any], rec: OutcomeRecord) -> Dict[str, Any]:
    return {
        "runId": str(row.get("run_id", "")),
        "workflowId": str(row.get("workflow_id", "")),
        "userId": int(row.get("user_id", 0)),
        "runCreatedAt": _ts_iso(row.get("created_at")),
        "runUpdatedAt": _ts_iso(row.get("updated_at")),
        "blockId": rec.block_id,
        "outcomeKey": rec.outcome_key,
        "source": rec.source,
        "notes": rec.notes,
        "matchedSignalTargetIds": list(rec.matched_signal_target_ids),
        "guidanceSchemaVersion": rec.guidance_schema_version,
        "playbookId": rec.playbook_id,
        "playbookVersion": rec.playbook_version,
        "recordedAt": rec.recorded_at,
        "externalFlagsSnapshot": dict(rec.external_flags_snapshot),
    }


def _passes_history_filters(
    rec: OutcomeRecord,
    *,
    block_id: Optional[str],
    outcome_key: Optional[str],
    has_notes: Optional[bool],
    source: Optional[str],
) -> bool:
    if block_id is not None and str(block_id).strip() and rec.block_id != str(block_id).strip():
        return False
    if outcome_key is not None and str(outcome_key).strip() and rec.outcome_key != str(outcome_key).strip():
        return False
    if has_notes is not None:
        nonempty = bool(rec.notes and str(rec.notes).strip())
        if has_notes and not nonempty:
            return False
        if not has_notes and nonempty:
            return False
    if source is not None and str(source).strip():
        if str(rec.source or "").strip() != str(source).strip():
            return False
    return True


def list_execution_outcomes(
    *,
    workflow_id: Optional[str] = None,
    run_id: Optional[str] = None,
    block_id: Optional[str] = None,
    outcome_key: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    has_notes: Optional[bool] = None,
    source: Optional[str] = None,
    limit: int = 100,
    max_flat_rows: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Load matching runs (newest first), parse progress JSON, emit flat outcome rows.
    Filters apply per history row before append (including ``source``).
    ``max_flat_rows`` defaults to the module flat cap.
    """
    cap = int(max_flat_rows) if max_flat_rows is not None else OUTCOME_FLAT_CAP
    cap = max(1, min(cap, OUTCOME_FLAT_CAP))
    runs = list_execution_runs_for_admin(
        workflow_id=workflow_id,
        run_id=run_id,
        since=since,
        until=until,
        limit=limit,
    )
    flat: List[Dict[str, Any]] = []
    for row in runs:
        psj = row.get("progress_state_json")
        if not isinstance(psj, dict):
            continue
        try:
            state = ExecutionProgressState.from_dict(psj)
        except Exception:
            continue
        for rec in state.outcome_history:
            if not _passes_history_filters(
                rec,
                block_id=block_id,
                outcome_key=outcome_key,
                has_notes=has_notes,
                source=source,
            ):
                continue
            flat.append(_outcome_to_dto(row, rec))
            if len(flat) >= cap:
                return flat
    return flat
