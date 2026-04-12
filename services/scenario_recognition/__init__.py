"""
Phase 12 — Scenario Recognition Layer (deterministic, read-only).
"""

from __future__ import annotations

from .evaluator import compute_input_digest, detect_scenarios
from .rule_model import active_rules, load_rules_json
from .schema import (
    SCENARIO_OBJECT_VERSION,
    SCOPE_ACCOUNT_FINGERPRINT,
    SCOPE_WORKFLOW,
    STATUS_BLOCKED_INSUFFICIENT_EVIDENCE,
    STATUS_DETECTED,
)

__all__ = [
    "SCOPE_ACCOUNT_FINGERPRINT",
    "SCOPE_WORKFLOW",
    "STATUS_BLOCKED_INSUFFICIENT_EVIDENCE",
    "STATUS_DETECTED",
    "SCENARIO_OBJECT_VERSION",
    "active_rules",
    "compute_input_digest",
    "detect_scenarios",
    "load_rules_json",
]
