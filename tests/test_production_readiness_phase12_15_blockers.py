"""
Phases 12–15 — explicit automation blockers.

Phases 12–15 are asserted as implemented under ``services.*`` with real entry points.
"""

from __future__ import annotations


def test_phase12_scenario_recognition_implemented():
    import services.scenario_recognition as sr

    assert hasattr(sr, "detect_scenarios")
    assert hasattr(sr, "compute_input_digest")


def test_phase13_strategy_pivot_implemented():
    import services.strategy_pivot as sp

    assert hasattr(sp, "build_strategy_pivots")
    assert hasattr(sp, "compute_pivot_input_digest")


def test_phase14_guidance_refinement_implemented():
    import services.guidance_refinement as gr

    assert hasattr(gr, "build_guidance_view")
    assert hasattr(gr, "compute_refinement_input_digest")


def test_phase15_ai_augmentation_implemented():
    import services.ai_augmentation as aa

    assert hasattr(aa, "run_ai_augmentation")
    assert hasattr(aa, "validate_ai_output")
    assert hasattr(aa, "build_ai_augmentation_request")
