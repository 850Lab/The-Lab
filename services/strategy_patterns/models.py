"""
Strategy Pattern Library — schemas (Capability 2).

Patterns are versioned, code-defined units matched against CanonicalCaseIntelligenceV1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple


class RequirementOperator(str, Enum):
    """Explicit requirement kinds for pattern applicability."""

    MIN_INT = "min_int"  # field >= value
    MAX_INT = "max_int"
    HAS_ANY_CONTRADICTION_TYPE = "has_any_contradiction_type"
    HAS_ANY_STRATEGY_SIGNAL = "has_any_strategy_signal"  # substring match on signal name
    DOCUMENTATION_IN = "documentation_in"
    DOCUMENTATION_NOT_IN = "documentation_not_in"
    CASE_TYPE_SUMMARY_ONE_OF = "case_type_summary_one_of"
    CASE_TYPE_SUMMARY_CONTAINS_ANY = "case_type_summary_contains_any"
    MIN_BUREAU_COVERAGE_COUNT = "min_bureau_coverage_count"  # distinct bureaus in identity
    READINESS_BLOCKER_ABSENT = "readiness_blocker_absent"  # arg is blocker id string


@dataclass(frozen=True)
class RequirementSpec:
    """Single applicability clause; all active pattern requirements must pass."""

    req_id: str
    op: RequirementOperator
    field: str  # logical target: case_summary.key | derived
    value: Any  # int, str, or list depending on op
    description: str  # human-readable for explanations


class ExclusionOperator(str, Enum):
    DOCUMENTATION_IN = "documentation_in"
    NO_CANDIDATE_DISPUTES = "no_candidate_disputes"
    HAS_READINESS_BLOCKER = "has_readiness_blocker"
    MIN_PRIOR_LETTERS = "min_prior_letters"  # exclude first-time path if letters exist


@dataclass(frozen=True)
class ExclusionSpec:
    """If any exclusion fires, pattern does not match (even if requirements pass)."""

    ex_id: str
    op: ExclusionOperator
    value: Any
    description: str


@dataclass(frozen=True)
class StrategyPatternDefinition:
    """
    Reusable strategy unit. ``applies_logic`` ``any`` means at least one ``applies_when`` row
    must pass; ``all`` means every row must pass.
    """

    pattern_id: str
    pattern_name: str
    pattern_family: str
    version: str
    description: str
    applies_when: Tuple[RequirementSpec, ...]
    excludes_when: Tuple[ExclusionSpec, ...] = ()
    applies_logic: str = "all"  # all | any
    required_signals: Tuple[str, ...] = ()
    optional_signals: Tuple[str, ...] = ()
    required_documentation_states: Optional[Tuple[str, ...]] = None
    action_sequence_template: Tuple[str, ...] = ()
    fallback_pattern_ids: Tuple[str, ...] = ()
    timing_class: str = "standard"
    aggressiveness_class: str = "standard"
    confidence_class: str = "medium"
    notes: str = ""
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patternId": self.pattern_id,
            "patternName": self.pattern_name,
            "patternFamily": self.pattern_family,
            "version": self.version,
            "description": self.description,
            "appliesLogic": self.applies_logic,
            "appliesWhen": [
                {
                    "reqId": r.req_id,
                    "op": r.op.value,
                    "field": r.field,
                    "value": r.value,
                    "description": r.description,
                }
                for r in self.applies_when
            ],
            "excludesWhen": [
                {
                    "exId": e.ex_id,
                    "op": e.op.value,
                    "value": e.value,
                    "description": e.description,
                }
                for e in self.excludes_when
            ],
            "requiredSignals": list(self.required_signals),
            "optionalSignals": list(self.optional_signals),
            "requiredDocumentationStates": (
                list(self.required_documentation_states)
                if self.required_documentation_states
                else None
            ),
            "actionSequenceTemplate": list(self.action_sequence_template),
            "fallbackPatternIds": list(self.fallback_pattern_ids),
            "timingClass": self.timing_class,
            "aggressivenessClass": self.aggressiveness_class,
            "confidenceClass": self.confidence_class,
            "notes": self.notes,
            "active": self.active,
        }


@dataclass
class PatternEvaluationResult:
    pattern_id: str
    pattern_version: str
    matched: bool
    applicability_score: float  # fraction of applies_when satisfied (0-1)
    match_confidence: str  # gated: high | medium | low
    matched_requirements: List[str]
    missing_requirements: List[str]
    exclusion_hits: List[str]
    matched_signals_used: List[str]
    missing_optional_signals: List[str]
    explanation: str
    caution_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patternId": self.pattern_id,
            "patternVersion": self.pattern_version,
            "matched": self.matched,
            "applicabilityScore": self.applicability_score,
            "matchConfidence": self.match_confidence,
            "matchedRequirements": list(self.matched_requirements),
            "missingRequirements": list(self.missing_requirements),
            "exclusionHits": list(self.exclusion_hits),
            "matchedSignalsUsed": list(self.matched_signals_used),
            "missingOptionalSignals": list(self.missing_optional_signals),
            "explanation": self.explanation,
            "cautionFlags": list(self.caution_flags),
        }


@dataclass
class StrategyPatternEvaluationBundle:
    """Full evaluation run over the pattern library."""

    schema_version: str
    case_intelligence_schema: str
    library_version: str
    evaluations: List[PatternEvaluationResult]
    matched_pattern_ids: List[str]
    unmatched_pattern_ids: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "caseIntelligenceSchema": self.case_intelligence_schema,
            "libraryVersion": self.library_version,
            "evaluations": [e.to_dict() for e in self.evaluations],
            "matchedPatternIds": list(self.matched_pattern_ids),
            "unmatchedPatternIds": list(self.unmatched_pattern_ids),
        }
