"""
Strategy Pattern Library (Capability 2) — match reusable patterns to canonical case intelligence.
"""

from __future__ import annotations

from .matcher import evaluate_strategy_patterns, evaluate_strategy_patterns_for_workflow
from .models import (
    PatternEvaluationResult,
    StrategyPatternDefinition,
    StrategyPatternEvaluationBundle,
)
from .registry_v1 import LIBRARY_VERSION, load_pattern_library_v1

__all__ = [
    "LIBRARY_VERSION",
    "PatternEvaluationResult",
    "StrategyPatternDefinition",
    "StrategyPatternEvaluationBundle",
    "evaluate_strategy_patterns",
    "evaluate_strategy_patterns_for_workflow",
    "load_pattern_library_v1",
]
