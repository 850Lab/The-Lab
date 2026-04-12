"""
Rehydrate ExecutionGuidanceBundle from JSON (same camelCase shape as to_dict()).
"""

from __future__ import annotations

from typing import Any, Dict, List

from services.execution_guidance.models import (
    ExecutionGuidanceBlock,
    ExecutionGuidanceBundle,
    ParallelGroup,
)
from services.execution_guidance.signals import SignalCaptureTarget
from services.execution_guidance.triggers import TimingTrigger


def _timing_trigger(d: Dict[str, Any]) -> TimingTrigger:
    return TimingTrigger(
        kind=str(d.get("kind", "immediate")),
        payload=dict(d.get("payload") or {}),
    )


def _signal_target(d: Dict[str, Any]) -> SignalCaptureTarget:
    return SignalCaptureTarget(
        target_id=str(d["targetId"]),
        description=str(d.get("description", "")),
        severity_if_matched=d.get("severityIfMatched"),
        source_hint=str(d.get("sourceHint", "user_reported")),
    )


def _block(d: Dict[str, Any]) -> ExecutionGuidanceBlock:
    nbo = d.get("nextByOutcome") or {}
    next_by_outcome: Dict[str, List[str]] = {
        str(k): list(v) if isinstance(v, (list, tuple)) else [] for k, v in nbo.items()
    }
    sigs = d.get("signalCaptureTargets") or []
    return ExecutionGuidanceBlock(
        block_id=str(d["blockId"]),
        path_id=str(d.get("pathId", "")),
        block_type=str(d.get("blockType", "")),
        action_name=str(d.get("actionName", "")),
        actor=str(d.get("actor", "user")),
        channel=str(d.get("channel", "")),
        timing_trigger=_timing_trigger(d.get("timingTrigger") or {}),
        prerequisites=list(d.get("prerequisites") or []),
        instructions=str(d.get("instructions", "")),
        script_objective=d.get("scriptObjective"),
        prohibited_actions=list(d.get("prohibitedActions") or []),
        caution_notes=list(d.get("cautionNotes") or []),
        expected_outcomes=list(d.get("expectedOutcomes") or []),
        signal_capture_targets=[_signal_target(x) for x in sigs if isinstance(x, dict)],
        next_by_outcome=next_by_outcome,
        readiness_state=str(d.get("readinessState", "")),
        explanation=str(d.get("explanation", "")),
    )


def _parallel_group(d: Dict[str, Any]) -> ParallelGroup:
    return ParallelGroup(
        group_id=str(d["groupId"]),
        block_ids=list(d.get("blockIds") or []),
        synchronization_note=str(d.get("synchronizationNote", "")),
    )


def execution_guidance_bundle_from_dict(d: Dict[str, Any]) -> ExecutionGuidanceBundle:
    blocks_raw = d.get("blocks") or []
    groups_raw = d.get("parallelGroups") or []
    return ExecutionGuidanceBundle(
        schema_version=str(d.get("schemaVersion", "")),
        playbook_id=str(d.get("playbookId", "")),
        playbook_version=str(d.get("playbookVersion", "")),
        primary_path_id=d.get("primaryPathId"),
        objective_id=str(d.get("objectiveId", "")),
        blocks=[_block(x) for x in blocks_raw if isinstance(x, dict)],
        parallel_groups=[_parallel_group(x) for x in groups_raw if isinstance(x, dict)],
        entry_block_ids=list(d.get("entryBlockIds") or []),
        terminal_block_ids=list(d.get("terminalBlockIds") or []),
        case_intelligence_schema=str(d.get("caseIntelligenceSchema", "")),
        pattern_library_version=str(d.get("patternLibraryVersion", "")),
        path_generation_version=str(d.get("pathGenerationVersion", "")),
        scoring_version=str(d.get("scoringVersion", "")),
        generation_notes=list(d.get("generationNotes") or []),
    )
