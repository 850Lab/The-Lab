"""
Canonical Case Intelligence Layer (Capability 1).

Produces one strategy-grade case object from existing parse / claims / review / workflow state.
"""

from .facade import build_canonical_case_intelligence_for_workflow
from .compose import build_canonical_case_intelligence
from .models import CanonicalCaseIntelligenceV1, CaseIntelligenceInputs

__all__ = [
    "build_canonical_case_intelligence",
    "build_canonical_case_intelligence_for_workflow",
    "CanonicalCaseIntelligenceV1",
    "CaseIntelligenceInputs",
]
