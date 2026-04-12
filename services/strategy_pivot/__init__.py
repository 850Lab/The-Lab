"""
Phase 13 — Strategy Pivot Layer (deterministic, read-only).
"""

from __future__ import annotations

from .context_adapter import build_pivot_evaluation_context
from .digest import compute_pivot_input_digest
from .evaluator import build_strategy_pivots
from .rule_model import active_pivot_rules, load_compatibility_matrix, load_pivot_rules_json
from .schema import PIVOT_OBJECT_VERSION, PIVOT_ENGINE_VERSION_DEFAULT

__all__ = [
    "PIVOT_OBJECT_VERSION",
    "PIVOT_ENGINE_VERSION_DEFAULT",
    "active_pivot_rules",
    "build_pivot_evaluation_context",
    "build_strategy_pivots",
    "compute_pivot_input_digest",
    "load_compatibility_matrix",
    "load_pivot_rules_json",
]
