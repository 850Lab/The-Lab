"""
Strategy Scoring + Objective Optimization (Capability 4).
"""

from __future__ import annotations

from .models import PathDimensionScores, ScoredStrategyPath, StrategyScoringBundle
from .scorer import (
    SCORING_ENGINE_VERSION,
    SCORING_SCHEMA_VERSION,
    score_strategy_paths,
    score_strategy_paths_for_workflow,
)

__all__ = [
    "PathDimensionScores",
    "SCORING_ENGINE_VERSION",
    "SCORING_SCHEMA_VERSION",
    "ScoredStrategyPath",
    "StrategyScoringBundle",
    "score_strategy_paths",
    "score_strategy_paths_for_workflow",
]
