"""
Objective definitions and dimension weights. Extend by adding entries to OBJECTIVES.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

# Dimension keys must match PathDimensionScores field names without _score suffix for weights dict
# We use full names in weights for readability in outputs.

FASTEST_CREDIBLE_WEIGHTS: Dict[str, float] = {
    "timing_score": 0.22,
    "readiness_score": 0.20,
    "evidence_strength_score": 0.15,
    "blocker_clearance_score": 0.14,
    "effort_efficiency_score": 0.10,
    "risk_acceptability_score": 0.08,
    "prior_action_favor_score": 0.06,
    "signal_richness_score": 0.05,
}

OBJECTIVES: Dict[str, Dict[str, Any]] = {
    "fastest_credible_result": {
        "description": (
            "Prefer faster credible timing classes, strong readiness, solid evidence and signal support, "
            "fewer blockers, reasonable risk, and limited penalty from prior rounds — without ignoring blockers."
        ),
        "weights": FASTEST_CREDIBLE_WEIGHTS,
    },
}


def get_objective_config(objective_id: str) -> Tuple[str, Dict[str, float]]:
    """Return (description, weights). Raises KeyError if unknown."""
    cfg = OBJECTIVES[objective_id]
    return str(cfg["description"]), dict(cfg["weights"])


def normalize_weights(w: Dict[str, float]) -> Dict[str, float]:
    total = sum(w.values())
    if total <= 0:
        raise ValueError("objective weights must sum to a positive value")
    return {k: v / total for k, v in w.items()}
