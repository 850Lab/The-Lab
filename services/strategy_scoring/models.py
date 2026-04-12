"""
Strategy Scoring + Objective Optimization — schemas (Capability 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PathDimensionScores:
    """Explicit 0–100 scores; higher is better for every dimension."""

    timing_score: float
    readiness_score: float
    evidence_strength_score: float
    blocker_clearance_score: float
    effort_efficiency_score: float
    risk_acceptability_score: float
    prior_action_favor_score: float
    signal_richness_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timingScore": round(self.timing_score, 4),
            "readinessScore": round(self.readiness_score, 4),
            "evidenceStrengthScore": round(self.evidence_strength_score, 4),
            "blockerClearanceScore": round(self.blocker_clearance_score, 4),
            "effortEfficiencyScore": round(self.effort_efficiency_score, 4),
            "riskAcceptabilityScore": round(self.risk_acceptability_score, 4),
            "priorActionFavorScore": round(self.prior_action_favor_score, 4),
            "signalRichnessScore": round(self.signal_richness_score, 4),
        }


@dataclass
class ScoredStrategyPath:
    path_id: str
    ranking_bucket: str  # active_scorable | blocked | suppressed
    rank_within_bucket: int
    global_rank: int
    dimension_scores: PathDimensionScores
    dimension_weights_used: Dict[str, float]
    weighted_contributions: Dict[str, float]
    total_score: float
    explanation: str
    positive_factors: List[str] = field(default_factory=list)
    negative_factors: List[str] = field(default_factory=list)
    tradeoffs: List[str] = field(default_factory=list)
    role: str = "fallback"  # primary | fallback | blocked | suppressed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pathId": self.path_id,
            "rankingBucket": self.ranking_bucket,
            "rankWithinBucket": self.rank_within_bucket,
            "globalRank": self.global_rank,
            "dimensionScores": self.dimension_scores.to_dict(),
            "dimensionWeightsUsed": {k: round(v, 6) for k, v in self.dimension_weights_used.items()},
            "weightedContributions": {k: round(v, 6) for k, v in self.weighted_contributions.items()},
            "totalScore": round(self.total_score, 4),
            "explanation": self.explanation,
            "positiveFactors": list(self.positive_factors),
            "negativeFactors": list(self.negative_factors),
            "tradeoffs": list(self.tradeoffs),
            "role": self.role,
        }


@dataclass
class StrategyScoringBundle:
    schema_version: str
    scoring_version: str
    objective_id: str
    objective_description: str
    case_intelligence_schema: str
    pattern_evaluation_schema: str
    path_bundle_schema: str
    path_generation_version: str
    scored_paths: List[ScoredStrategyPath]
    ranked_active_scorable_path_ids: List[str]
    ranked_blocked_path_ids: List[str]
    ranked_suppressed_path_ids: List[str]
    recommended_primary_path_id: Optional[str]
    fallback_path_ids_ordered: List[str]
    scoring_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "scoringVersion": self.scoring_version,
            "objectiveId": self.objective_id,
            "objectiveDescription": self.objective_description,
            "caseIntelligenceSchema": self.case_intelligence_schema,
            "patternEvaluationSchema": self.pattern_evaluation_schema,
            "pathBundleSchema": self.path_bundle_schema,
            "pathGenerationVersion": self.path_generation_version,
            "scoredPaths": [p.to_dict() for p in self.scored_paths],
            "rankedActiveScorablePathIds": list(self.ranked_active_scorable_path_ids),
            "rankedBlockedPathIds": list(self.ranked_blocked_path_ids),
            "rankedSuppressedPathIds": list(self.ranked_suppressed_path_ids),
            "recommendedPrimaryPathId": self.recommended_primary_path_id,
            "fallbackPathIdsOrdered": list(self.fallback_path_ids_ordered),
            "scoringNotes": list(self.scoring_notes),
        }
