#!/usr/bin/env python3
"""
Phase 3D — operational E2E harness (DB + trusted engine/hooks only).

Does not call Stripe or Lob APIs. Simulates progression the same way workers/hooks do.

Usage (repo root):

  set WORKFLOW_E2E_USER_ID=123
  python scripts/workflow_e2e_verify.py

Optional failure-injection suite:

  set WORKFLOW_E2E_FAILURES=1

Exit codes: 0 all critical steps pass, 1 failure, 2 configuration error (missing user/env).
"""

from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    if not (os.environ.get("WORKFLOW_E2E_USER_ID") or "").strip():
        print("ERROR: Set WORKFLOW_E2E_USER_ID to an existing users.id", file=sys.stderr)
        return 2
    try:
        from services.workflow.e2e_operational_harness import run_all
    except ImportError as ex:
        print(f"ERROR: import failed: {ex}", file=sys.stderr)
        return 2

    try:
        report = run_all()
    except RuntimeError as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return 2
    except Exception as ex:
        print(f"ERROR: {type(ex).__name__}: {ex}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, default=str))

    def bad(step_list: list) -> list:
        return [s for s in step_list if not s.get("ok") and s.get("kind") == "fail"]

    hp = bad(report.get("happyPathSteps") or [])
    fs = bad(report.get("failureSteps") or [])
    exs = bad(report.get("extraSteps") or [])
    if hp or fs or exs:
        print("\n--- FAILURES (kind=fail) ---", file=sys.stderr)
        for block in (hp, fs, exs):
            for s in block:
                print(s.get("name"), s.get("detail", "")[:500], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
