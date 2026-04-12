"""
Phase 14 — Guidance refinement & delivery intelligence (deterministic view only).
"""

from __future__ import annotations

from .builder import build_guidance_view, load_refinement_rules
from .context_adapter import build_refinement_context
from .digest import compute_refinement_input_digest
from .schema import (
    GUIDANCE_VIEW_VERSION,
    REFINEMENT_VERSION_DEFAULT,
    VIS_DEFERRED,
    VIS_HIDDEN,
    VIS_SUPPRESSED,
    VIS_VISIBLE,
)

__all__ = [
    "GUIDANCE_VIEW_VERSION",
    "REFINEMENT_VERSION_DEFAULT",
    "VIS_DEFERRED",
    "VIS_HIDDEN",
    "VIS_SUPPRESSED",
    "VIS_VISIBLE",
    "build_guidance_view",
    "build_refinement_context",
    "compute_refinement_input_digest",
    "load_refinement_rules",
]
