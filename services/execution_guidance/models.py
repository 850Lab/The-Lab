"""
Execution guidance blocks — user participation, channels, branching (Capability 5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .signals import SignalCaptureTarget
from .triggers import TimingTrigger


@dataclass
class ParallelGroup:
    group_id: str
    block_ids: List[str]
    synchronization_note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "groupId": self.group_id,
            "blockIds": list(self.block_ids),
            "synchronizationNote": self.synchronization_note,
        }


@dataclass
class ExecutionGuidanceBlock:
    block_id: str
    path_id: str
    block_type: str
    action_name: str
    actor: str  # user | system | hybrid
    channel: str
    timing_trigger: TimingTrigger
    prerequisites: List[str]
    instructions: str
    script_objective: Optional[str]
    prohibited_actions: List[str]
    caution_notes: List[str]
    expected_outcomes: List[str]
    signal_capture_targets: List[SignalCaptureTarget]
    next_by_outcome: Dict[str, List[str]]
    readiness_state: str
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blockId": self.block_id,
            "pathId": self.path_id,
            "blockType": self.block_type,
            "actionName": self.action_name,
            "actor": self.actor,
            "channel": self.channel,
            "timingTrigger": self.timing_trigger.to_dict(),
            "prerequisites": list(self.prerequisites),
            "instructions": self.instructions,
            "scriptObjective": self.script_objective,
            "prohibitedActions": list(self.prohibited_actions),
            "cautionNotes": list(self.caution_notes),
            "expectedOutcomes": list(self.expected_outcomes),
            "signalCaptureTargets": [t.to_dict() for t in self.signal_capture_targets],
            "nextByOutcome": {k: list(v) for k, v in self.next_by_outcome.items()},
            "readinessState": self.readiness_state,
            "explanation": self.explanation,
        }


@dataclass
class ExecutionGuidanceBundle:
    schema_version: str
    playbook_id: str
    playbook_version: str
    primary_path_id: Optional[str]
    objective_id: str
    blocks: List[ExecutionGuidanceBlock]
    parallel_groups: List[ParallelGroup]
    entry_block_ids: List[str]
    terminal_block_ids: List[str]
    case_intelligence_schema: str
    pattern_library_version: str
    path_generation_version: str
    scoring_version: str
    generation_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "playbookId": self.playbook_id,
            "playbookVersion": self.playbook_version,
            "primaryPathId": self.primary_path_id,
            "objectiveId": self.objective_id,
            "blocks": [b.to_dict() for b in self.blocks],
            "parallelGroups": [g.to_dict() for g in self.parallel_groups],
            "entryBlockIds": list(self.entry_block_ids),
            "terminalBlockIds": list(self.terminal_block_ids),
            "caseIntelligenceSchema": self.case_intelligence_schema,
            "patternLibraryVersion": self.pattern_library_version,
            "pathGenerationVersion": self.path_generation_version,
            "scoringVersion": self.scoring_version,
            "generationNotes": list(self.generation_notes),
        }
