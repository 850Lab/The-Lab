#!/usr/bin/env python3
"""
Workflow launch validation runner (Phase 3C).

Usage (from repo root):

  python scripts/workflow_launch_validate.py

Optional DB-backed smoke (PostgreSQL configured like the main app):

  set WORKFLOW_LAUNCH_VALIDATE_DB=1
  python scripts/workflow_launch_validate.py

Exit code 1 if any check with failure_kind=code returns FAIL.
Config-related FAIL (e.g. DB unreachable) exits 2.
"""

from __future__ import annotations

import os
import sys

# Repo root on path for `services.*` imports
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    from services.workflow.launch_readiness_checks import (
        run_checks,
        summary_lines,
    )

    outcomes = run_checks()
    for line in summary_lines(outcomes):
        print(line)

    code_fail = any(o.status == "FAIL" and o.failure_kind == "code" for o in outcomes)
    cfg_fail = any(o.status == "FAIL" and o.failure_kind == "config" for o in outcomes)
    if code_fail:
        return 1
    if cfg_fail:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
