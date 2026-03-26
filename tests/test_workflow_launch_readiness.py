"""
Pytest entrypoint for launch-readiness checks (no DB unless env set).

  pytest tests/test_workflow_launch_readiness.py -v
"""

from __future__ import annotations

import pytest

from services.workflow.launch_readiness_checks import run_checks


def test_launch_readiness_no_code_failures():
    outcomes = run_checks()
    code_fails = [o for o in outcomes if o.status == "FAIL" and o.failure_kind == "code"]
    if code_fails:
        msg = "\n".join(f"  {o.scenario}: {o.message}" for o in code_fails)
        pytest.fail(f"Launch readiness code failures:\n{msg}")


def test_launch_readiness_report_printable():
    from services.workflow.launch_readiness_checks import summary_lines

    lines = summary_lines(run_checks())
    assert any("PASS" in ln or "FAIL" in ln or "SKIP" in ln for ln in lines)
