from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from claims import Claim
from review_claims import ReviewClaim


@dataclass
class BureauFootprintEntry:
    bureau: str
    report_ids: List[int]
    tradeline_observations: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bureau": self.bureau,
            "reportIds": list(self.report_ids),
            "tradelineObservations": self.tradeline_observations,
        }


@dataclass
class NormalizedAccountGroup:
    """Cross-bureau grouping of tradeline observations (best-effort, conservative)."""

    group_id: str
    normalized_creditor: str
    fingerprint_key: str
    bureaus_present: List[str]
    raw_claim_ids_sample: List[str]
    linkage_confidence: str  # high | medium | low
    linkage_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "groupId": self.group_id,
            "normalizedCreditor": self.normalized_creditor,
            "fingerprintKey": self.fingerprint_key,
            "bureausPresent": list(self.bureaus_present),
            "rawClaimIdsSample": list(self.raw_claim_ids_sample),
            "linkageConfidence": self.linkage_confidence,
            "linkageNotes": list(self.linkage_notes),
        }


@dataclass
class ContradictionRecord:
    signal_type: str
    description: str
    grounded_in: str
    involved_raw_claim_ids: List[str] = field(default_factory=list)
    involved_review_claim_ids: List[str] = field(default_factory=list)
    confidence: str = "medium"  # high | medium | low

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signalType": self.signal_type,
            "description": self.description,
            "groundedIn": self.grounded_in,
            "involvedRawClaimIds": list(self.involved_raw_claim_ids),
            "involvedReviewClaimIds": list(self.involved_review_claim_ids),
            "confidence": self.confidence,
        }


@dataclass
class StrategySignalRecord:
    name: str
    tier: str  # leverage | risk | hygiene | timing
    detail: str
    confidence: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "tier": self.tier,
            "detail": self.detail,
            "confidence": self.confidence,
        }


@dataclass
class DocumentationStateSummary:
    has_government_id: bool
    has_address_proof: bool
    has_signature: bool
    sufficiency: str  # rich | partial | thin | unknown
    missing_doc_flags: List[str]
    evidence_richness: str  # high | medium | low

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hasGovernmentId": self.has_government_id,
            "hasAddressProof": self.has_address_proof,
            "hasSignature": self.has_signature,
            "sufficiency": self.sufficiency,
            "missingDocFlags": list(self.missing_doc_flags),
            "evidenceRichness": self.evidence_richness,
        }


@dataclass
class ActionHistorySummary:
    cumulative_disputed_review_claim_ids: List[str]
    claim_outcomes: Dict[str, str]
    dispute_round_number: int
    letter_count_for_scope: int
    letter_bureaus_distinct: List[str]
    unresolved_disputed_ids: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cumulativeDisputedReviewClaimIds": list(self.cumulative_disputed_review_claim_ids),
            "claimOutcomes": dict(self.claim_outcomes),
            "disputeRoundNumber": self.dispute_round_number,
            "letterCountForScope": self.letter_count_for_scope,
            "letterBureausDistinct": list(self.letter_bureaus_distinct),
            "unresolvedDisputedIds": list(self.unresolved_disputed_ids),
        }


@dataclass
class GoalConstraintState:
    stated_objective: Optional[str]
    objective_source: str  # workflow_metadata | unknown
    timing_sensitivity: str  # unknown | workflow_active_step
    readiness_blockers: List[str]
    next_dependencies: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statedObjective": self.stated_objective,
            "objectiveSource": self.objective_source,
            "timingSensitivity": self.timing_sensitivity,
            "readinessBlockers": list(self.readiness_blockers),
            "nextDependencies": list(self.next_dependencies),
        }


@dataclass
class ConfidenceSectionNote:
    section: str
    level: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {"section": self.section, "level": self.level, "rationale": self.rationale}


@dataclass
class CaseIntelligenceInputs:
    """Explicit inputs so the composer is testable without DB."""

    workflow_id: str
    user_id: int
    report_scope: List[Dict[str, Any]]
    raw_claims: List[Claim]
    review_claims: List[ReviewClaim]
    workflow_metadata: Dict[str, Any]
    selected_review_claim_ids: List[str]
    proof_flags: Dict[str, Any]
    letter_records: List[Dict[str, Any]]
    authoritative_step_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflowId": self.workflow_id,
            "userId": self.user_id,
            "reportScopeCount": len(self.report_scope),
            "rawClaimsCount": len(self.raw_claims),
            "reviewClaimsCount": len(self.review_claims),
        }


@dataclass
class CanonicalCaseIntelligenceV1:
    schema_version: str
    identity: Dict[str, Any]
    case_summary: Dict[str, Any]
    account_groups: List[NormalizedAccountGroup]
    strategy_signals: List[StrategySignalRecord]
    contradictions: List[ContradictionRecord]
    documentation: DocumentationStateSummary
    action_history: ActionHistorySummary
    goal_constraints: GoalConstraintState
    confidence_notes: List[ConfidenceSectionNote]
    explainability: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "identity": dict(self.identity),
            "caseSummary": dict(self.case_summary),
            "accountGroups": [g.to_dict() for g in self.account_groups],
            "strategySignals": [s.to_dict() for s in self.strategy_signals],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "documentation": self.documentation.to_dict(),
            "actionHistory": self.action_history.to_dict(),
            "goalConstraints": self.goal_constraints.to_dict(),
            "confidenceNotes": [n.to_dict() for n in self.confidence_notes],
            "explainability": list(self.explainability),
        }
