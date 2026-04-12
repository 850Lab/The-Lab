"""
Multi-Path Strategy Generator — schemas (Capability 3).

Paths are composed routes derived from case intelligence + matched strategy patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class StrategyGeneratedPath:
    path_id: str
    path_name: str
    path_family: str
    version: str
    path_objective: str
    source_pattern_ids: Tuple[str, ...]
    path_summary: str
    why_it_applies: str
    prerequisites: List[str]
    blockers: List[str]
    timing_class: str
    effort_class: str
    risk_class: str
    aggressiveness_class: str
    action_sequence_template: Tuple[str, ...]
    fallback_path_ids: Tuple[str, ...]
    caution_flags: List[str] = field(default_factory=list)
    readiness_state: str = "conditional"  # ready_now | conditional | blocked
    explanation: str = ""
    suppressed: bool = False
    suppression_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pathId": self.path_id,
            "pathName": self.path_name,
            "pathFamily": self.path_family,
            "version": self.version,
            "pathObjective": self.path_objective,
            "sourcePatternIds": list(self.source_pattern_ids),
            "pathSummary": self.path_summary,
            "whyItApplies": self.why_it_applies,
            "prerequisites": list(self.prerequisites),
            "blockers": list(self.blockers),
            "timingClass": self.timing_class,
            "effortClass": self.effort_class,
            "riskClass": self.risk_class,
            "aggressivenessClass": self.aggressiveness_class,
            "actionSequenceTemplate": list(self.action_sequence_template),
            "fallbackPathIds": list(self.fallback_path_ids),
            "cautionFlags": list(self.caution_flags),
            "readinessState": self.readiness_state,
            "explanation": self.explanation,
            "suppressed": self.suppressed,
            "suppressionReason": self.suppression_reason,
        }


@dataclass
class MultiPathStrategyBundle:
    schema_version: str
    case_intelligence_schema: str
    pattern_evaluation_schema: str
    pattern_library_version: str
    generation_version: str
    all_paths: List[StrategyGeneratedPath]
    active_candidate_path_ids: List[str]
    blocked_path_ids: List[str]
    suppressed_path_ids: List[str]
    generation_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "caseIntelligenceSchema": self.case_intelligence_schema,
            "patternEvaluationSchema": self.pattern_evaluation_schema,
            "patternLibraryVersion": self.pattern_library_version,
            "generationVersion": self.generation_version,
            "allPaths": [p.to_dict() for p in self.all_paths],
            "activeCandidatePathIds": list(self.active_candidate_path_ids),
            "blockedPathIds": list(self.blocked_path_ids),
            "suppressedPathIds": list(self.suppressed_path_ids),
            "generationNotes": list(self.generation_notes),
        }
