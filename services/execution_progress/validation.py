"""
Outcome key validation — consistent rules for all blocks.
"""

from __future__ import annotations

from typing import Set

from services.execution_guidance.models import ExecutionGuidanceBlock


def _next_keys(block: ExecutionGuidanceBlock) -> Set[str]:
    return set(block.next_by_outcome.keys())


def complete_always_allowed(block: ExecutionGuidanceBlock) -> bool:
    """
    If next_by_outcome is empty OR only {"complete": []}, "complete" is always valid.
    """
    nbo = block.next_by_outcome
    if not nbo:
        return True
    if set(nbo.keys()) == {"complete"}:
        v = nbo.get("complete")
        if v is None or (isinstance(v, (list, tuple)) and len(v) == 0):
            return True
    return False


def is_valid_outcome_key(block: ExecutionGuidanceBlock, outcome_key: str) -> bool:
    keys = _next_keys(block)
    if outcome_key in keys:
        return True
    if outcome_key == "complete" and complete_always_allowed(block):
        return True
    return False
