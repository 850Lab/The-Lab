"""
Multi-Path Strategy Generator (Capability 3).
"""

from __future__ import annotations

from .generator import (
    GENERATION_VERSION,
    generate_strategy_paths,
    generate_strategy_paths_for_workflow,
)
from .models import MultiPathStrategyBundle, StrategyGeneratedPath

__all__ = [
    "GENERATION_VERSION",
    "MultiPathStrategyBundle",
    "StrategyGeneratedPath",
    "generate_strategy_paths",
    "generate_strategy_paths_for_workflow",
]
