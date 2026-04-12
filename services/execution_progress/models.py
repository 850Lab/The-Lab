"""
Execution outcome intake and block progression — runtime state (Capability 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OutcomeSource(str, Enum):
    user_reported = "user_reported"
    transcript_derived = "transcript_derived"


@dataclass
class OutcomeSubmission:
    """
    Submit an outcome for a block and/or patch external flags (e.g. mail receipt).

    Either provide (block_id + outcome_key) for a completion, or only external_flags
    to update gates without completing a block.
    """

    block_id: Optional[str] = None
    outcome_key: Optional[str] = None
    source: OutcomeSource = OutcomeSource.user_reported
    notes: str = ""
    matched_signal_target_ids: List[str] = field(default_factory=list)
    external_flags: Dict[str, Any] = field(default_factory=dict)

    def has_completion(self) -> bool:
        return self.block_id is not None and self.outcome_key is not None

    def has_flags_only(self) -> bool:
        return not self.has_completion() and bool(self.external_flags)


@dataclass
class OutcomeRecord:
    block_id: str
    outcome_key: str
    source: str
    notes: str
    matched_signal_target_ids: List[str]
    guidance_schema_version: str
    playbook_id: str
    playbook_version: str
    recorded_at: str = ""
    external_flags_snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blockId": self.block_id,
            "outcomeKey": self.outcome_key,
            "source": self.source,
            "notes": self.notes,
            "matchedSignalTargetIds": list(self.matched_signal_target_ids),
            "guidanceSchemaVersion": self.guidance_schema_version,
            "playbookId": self.playbook_id,
            "playbookVersion": self.playbook_version,
            "recordedAt": self.recorded_at,
            "externalFlagsSnapshot": dict(self.external_flags_snapshot),
        }


@dataclass
class ExecutionProgressState:
    run_id: str
    workflow_id: Optional[str]
    guidance_schema_version: str
    playbook_id: str
    playbook_version: str
    primary_path_id: Optional[str]
    completed_block_ids: List[str]
    completed_outcomes: Dict[str, str]
    activated_block_ids: List[str]
    external_flags: Dict[str, Any]
    outcome_history: List[OutcomeRecord]
    execution_notes: List[str]
    blocked_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runId": self.run_id,
            "workflowId": self.workflow_id,
            "guidanceSchemaVersion": self.guidance_schema_version,
            "playbookId": self.playbook_id,
            "playbookVersion": self.playbook_version,
            "primaryPathId": self.primary_path_id,
            "completedBlockIds": list(self.completed_block_ids),
            "completedOutcomes": dict(self.completed_outcomes),
            "activatedBlockIds": sorted(self.activated_block_ids),
            "externalFlags": dict(self.external_flags),
            "outcomeHistory": [r.to_dict() for r in self.outcome_history],
            "executionNotes": list(self.execution_notes),
            "blockedReason": self.blocked_reason,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ExecutionProgressState":
        hist = []
        for r in d.get("outcomeHistory") or []:
            if not isinstance(r, dict):
                continue
            hist.append(
                OutcomeRecord(
                    block_id=r["blockId"],
                    outcome_key=r["outcomeKey"],
                    source=r.get("source", "user_reported"),
                    notes=r.get("notes", ""),
                    matched_signal_target_ids=list(r.get("matchedSignalTargetIds") or []),
                    guidance_schema_version=r.get("guidanceSchemaVersion", ""),
                    playbook_id=r.get("playbookId", ""),
                    playbook_version=r.get("playbookVersion", ""),
                    recorded_at=r.get("recordedAt") or "",
                    external_flags_snapshot=dict(r.get("externalFlagsSnapshot") or {}),
                )
            )
        return ExecutionProgressState(
            run_id=d["runId"],
            workflow_id=d.get("workflowId"),
            guidance_schema_version=d["guidanceSchemaVersion"],
            playbook_id=d["playbookId"],
            playbook_version=d["playbookVersion"],
            primary_path_id=d.get("primaryPathId"),
            completed_block_ids=list(d.get("completedBlockIds") or []),
            completed_outcomes=dict(d.get("completedOutcomes") or {}),
            activated_block_ids=list(d.get("activatedBlockIds") or []),
            external_flags=dict(d.get("externalFlags") or {}),
            outcome_history=hist,
            execution_notes=list(d.get("executionNotes") or []),
            blocked_reason=d.get("blockedReason"),
        )


@dataclass
class ProgressionResult:
    accepted: bool
    validation_errors: List[str]
    state: ExecutionProgressState
    active_block_ids: List[str]
    waiting_block_ids: List[str]
    blocked_block_ids: List[str]
    newly_activated_block_ids: List[str]
    transition_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "validationErrors": list(self.validation_errors),
            "state": self.state.to_dict(),
            "activeBlockIds": list(self.active_block_ids),
            "waitingBlockIds": list(self.waiting_block_ids),
            "blockedBlockIds": list(self.blocked_block_ids),
            "newlyActivatedBlockIds": list(self.newly_activated_block_ids),
            "transitionNotes": list(self.transition_notes),
        }


PROGRESS_SCHEMA_VERSION = "execution_progress.v1"


def mail_receipt_flag(block_id: str) -> str:
    """Standard external_flags key for mail receipt confirmation."""
    return f"mail_receipt_confirmed_{block_id}"
