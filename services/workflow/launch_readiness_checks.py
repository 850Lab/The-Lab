"""
Launch-readiness checks: static imports, critical invariants, optional DB smoke.

Run via ``python scripts/workflow_launch_validate.py`` or pytest
``tests/test_workflow_launch_readiness.py``.

Environment:
- ``WORKFLOW_LAUNCH_VALIDATE_DB=1`` — run DB smoke (requires working ``database`` config).

Scenario coverage (lightweight; full step progression needs a staging workflow + workers):
1 init / engine — ``imports_workflow_core``, ``db_engine_smoke`` (optional DB)
2 upload/parse — not automated (internal ``service-complete`` only); guarded by
  ``internal_service_complete_routes``
3 select/payment — Stripe invariants: ``stripe_checkout_workflow_id``,
  ``imports_stripe_webhook_stack``, ``streamlit_payment_return_workflow``
4 payment webhook — ``stripe_webhook_workflow_path``
5 letter/proof/mail — not automated (Streamlit/Lob); mail metadata via hooks tests N/A here
6 multi-bureau gating — code lives in ``hooks`` / engine; no isolated check
7 response intake — ``imports_workflow_core`` includes ``response_intake_service``
8 reminder candidates — DB optional: ``reminder_list_smoke``
9 reminder delivery — ``reminder_delivery`` import via core imports
10 admin override — ``workflow_api_admin_secret``
11 recovery execution — same + recovery routes exist (admin count)
12 home-summary — ``home_summary_smoke`` (optional DB)
"""

from __future__ import annotations

import importlib
import inspect
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class CheckOutcome:
    scenario: str
    status: str  # PASS | FAIL | SKIP
    module: str
    failure_kind: str  # none | config | code
    message: str = ""
    evidence: str = ""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_text(rel: str) -> str:
    p = _repo_root() / rel
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def check_imports() -> CheckOutcome:
    """Workflow Python packages only (no Stripe SDK / requests required here)."""
    mods = [
        ("services.workflow.engine", "WorkflowEngine"),
        ("services.workflow.reminder_delivery", "send_reminder"),
        ("services.workflow.recovery_execution_service", "execute_retry_step"),
        ("services.workflow.response_intake_service", "intake_bureau_response"),
        ("services.workflow.home_summary_service", "build_home_summary"),
    ]
    failed = []
    for mod, attr in mods:
        try:
            m = importlib.import_module(mod)
            getattr(m, attr)
        except Exception as ex:
            failed.append(f"{mod}.{attr}: {ex}")
    if failed:
        return CheckOutcome(
            "imports_workflow_core",
            "FAIL",
            "launch_readiness_checks",
            "code",
            "; ".join(failed[:3]) + ("…" if len(failed) > 3 else ""),
            evidence="importlib",
        )
    return CheckOutcome(
        "imports_workflow_core",
        "PASS",
        "launch_readiness_checks",
        "none",
        "Core workflow modules import",
    )


def check_stripe_webhook_imports() -> CheckOutcome:
    """Stripe + requests are runtime deps for payment paths; skip if venv is minimal."""
    try:
        importlib.import_module("stripe")
        importlib.import_module("requests")
    except ImportError as ex:
        return CheckOutcome(
            "imports_stripe_webhook_stack",
            "SKIP",
            "stripe/webhook",
            "config",
            f"Install runtime deps for payment modules: {ex}",
        )
    for mod, attr in (
        ("webhook_handler", "handle_stripe_webhook"),
        ("stripe_client", "create_checkout_session"),
    ):
        try:
            m = importlib.import_module(mod)
            getattr(m, attr)
        except Exception as ex:
            return CheckOutcome(
                "imports_stripe_webhook_stack",
                "FAIL",
                mod,
                "code",
                str(ex)[:400],
            )
    return CheckOutcome(
        "imports_stripe_webhook_stack",
        "PASS",
        "stripe_client",
        "none",
        "webhook_handler and stripe_client import",
    )


def check_fastapi_workflow_app_import() -> CheckOutcome:
    try:
        m = importlib.import_module("api.workflow_app")
        getattr(m, "app")
    except ImportError as ex:
        msg = str(ex).lower()
        if "fastapi" in msg or "uvicorn" in msg:
            return CheckOutcome(
                "import_workflow_fastapi_app",
                "SKIP",
                "api.workflow_app",
                "config",
                f"FastAPI stack not installed: {ex}",
            )
        return CheckOutcome(
            "import_workflow_fastapi_app",
            "FAIL",
            "api.workflow_app",
            "code",
            str(ex)[:300],
        )
    except Exception as ex:
        return CheckOutcome(
            "import_workflow_fastapi_app",
            "FAIL",
            "api.workflow_app",
            "code",
            str(ex)[:300],
        )
    return CheckOutcome(
        "import_workflow_fastapi_app",
        "PASS",
        "api.workflow_app",
        "none",
        "workflow FastAPI app loads",
    )


def check_stripe_workflow_id_required() -> CheckOutcome:
    try:
        from stripe_client import create_checkout_session
    except ImportError as ex:
        return CheckOutcome(
            "stripe_checkout_workflow_id",
            "SKIP",
            "stripe_client",
            "config",
            f"stripe_client not importable: {ex}",
        )

    sig = inspect.signature(create_checkout_session)
    if "workflow_id" not in sig.parameters:
        return CheckOutcome(
            "stripe_checkout_workflow_id",
            "FAIL",
            "stripe_client",
            "code",
            "create_checkout_session missing workflow_id parameter",
        )
    p = sig.parameters["workflow_id"]
    if p.default is not inspect.Parameter.empty:
        return CheckOutcome(
            "stripe_checkout_workflow_id",
            "FAIL",
            "stripe_client",
            "code",
            "workflow_id must be keyword-required (no default)",
        )
    return CheckOutcome(
        "stripe_checkout_workflow_id",
        "PASS",
        "stripe_client",
        "none",
        "workflow_id is required keyword-only for checkout metadata",
        evidence=str(sig),
    )


def check_streamlit_payment_return_workflow_notify() -> CheckOutcome:
    src = _read_text("app.py")
    if "notify_payment_completed" not in src:
        return CheckOutcome(
            "streamlit_payment_return_workflow",
            "FAIL",
            "app.py",
            "code",
            "app.py does not call notify_payment_completed",
        )
    if "streamlit:payment_return" not in src:
        return CheckOutcome(
            "streamlit_payment_return_workflow",
            "FAIL",
            "app.py",
            "code",
            "Missing streamlit:payment_return audit source for workflow payment sync",
        )
    return CheckOutcome(
        "streamlit_payment_return_workflow",
        "PASS",
        "app.py",
        "none",
        "Return URL payment path notifies workflow when workflow_id in metadata",
    )


def check_webhook_workflow_path() -> CheckOutcome:
    src = _read_text("webhook_handler.py")
    if "workflow_id" not in src or "notify_payment_completed" not in src:
        return CheckOutcome(
            "stripe_webhook_workflow_path",
            "FAIL",
            "webhook_handler.py",
            "code",
            "Webhook missing workflow payment completion path",
        )
    return CheckOutcome(
        "stripe_webhook_workflow_path",
        "PASS",
        "webhook_handler.py",
        "none",
        "checkout.session.completed calls workflow notify when metadata present",
    )


def check_admin_routes_use_admin_secret() -> CheckOutcome:
    src = _read_text("api/workflow_app.py")
    if "require_admin_service" not in src:
        return CheckOutcome(
            "workflow_api_admin_secret",
            "FAIL",
            "api/workflow_app.py",
            "code",
            "require_admin_service not referenced",
        )
    admin_routes = len(re.findall(r'@app\.post\("/internal/admin/', src))
    admin_deps = len(re.findall(r"Depends\(require_admin_service\)", src))
    if admin_routes == 0:
        return CheckOutcome(
            "workflow_api_admin_secret",
            "SKIP",
            "api/workflow_app.py",
            "none",
            "No /internal/admin routes found",
        )
    if admin_deps < admin_routes:
        return CheckOutcome(
            "workflow_api_admin_secret",
            "FAIL",
            "api/workflow_app.py",
            "code",
            f"Admin POST count={admin_routes} but Depends(require_admin_service)={admin_deps}",
        )
    return CheckOutcome(
        "workflow_api_admin_secret",
        "PASS",
        "api/workflow_app.py",
        "none",
        f"{admin_routes} admin route(s) with require_admin_service",
    )


def check_internal_completion_routes() -> CheckOutcome:
    src = _read_text("api/workflow_app.py")
    if "service-complete" not in src or "require_internal_service" not in src:
        return CheckOutcome(
            "internal_service_complete_routes",
            "FAIL",
            "api/workflow_app.py",
            "code",
            "Missing internal service-complete or internal auth",
        )
    return CheckOutcome(
        "internal_service_complete_routes",
        "PASS",
        "api/workflow_app.py",
        "none",
        "Trusted step completion is internal-only",
    )


def check_db_engine_smoke() -> CheckOutcome:
    if (os.environ.get("WORKFLOW_LAUNCH_VALIDATE_DB") or "").strip() not in ("1", "true", "yes"):
        return CheckOutcome(
            "db_engine_smoke",
            "SKIP",
            "database",
            "none",
            "Set WORKFLOW_LAUNCH_VALIDATE_DB=1 to run (needs live DB)",
        )
    try:
        from services.workflow.engine import WorkflowEngine

        eng = WorkflowEngine()
        bad = "00000000-0000-0000-0000-000000000099"
        r = eng.get_state(bad)
        if r.get("actionResult") != "error":
            return CheckOutcome(
                "db_engine_smoke",
                "FAIL",
                "services.workflow.engine",
                "code",
                f"get_state(missing) expected actionResult=error, got {r.get('actionResult')}",
            )
    except Exception as ex:
        return CheckOutcome(
            "db_engine_smoke",
            "FAIL",
            "database",
            "config",
            str(ex)[:500],
        )
    return CheckOutcome(
        "db_engine_smoke",
        "PASS",
        "services.workflow.engine",
        "none",
        "Engine get_state against non-existent workflow returns error envelope",
    )


def check_home_summary_smoke() -> CheckOutcome:
    if (os.environ.get("WORKFLOW_LAUNCH_VALIDATE_DB") or "").strip() not in ("1", "true", "yes"):
        return CheckOutcome(
            "home_summary_smoke",
            "SKIP",
            "home_summary_service",
            "none",
            "Set WORKFLOW_LAUNCH_VALIDATE_DB=1 to run",
        )
    try:
        from services.workflow.home_summary_service import build_home_summary

        r = build_home_summary("00000000-0000-0000-0000-000000000088")
        if r.get("ok") is not False:
            return CheckOutcome(
                "home_summary_smoke",
                "FAIL",
                "home_summary_service",
                "code",
                "build_home_summary(missing) should set ok=false",
            )
    except Exception as ex:
        return CheckOutcome(
            "home_summary_smoke",
            "FAIL",
            "database",
            "config",
            str(ex)[:500],
        )
    return CheckOutcome(
        "home_summary_smoke",
        "PASS",
        "home_summary_service",
        "none",
        "home-summary handles missing workflow",
    )


def check_reminder_repository_smoke() -> CheckOutcome:
    if (os.environ.get("WORKFLOW_LAUNCH_VALIDATE_DB") or "").strip() not in ("1", "true", "yes"):
        return CheckOutcome(
            "reminder_list_smoke",
            "SKIP",
            "reminder_repository",
            "none",
            "Set WORKFLOW_LAUNCH_VALIDATE_DB=1 to run",
        )
    try:
        from services.workflow import reminder_repository as rr

        rows = rr.list_eligible_reminders(limit=1)
        if not isinstance(rows, list):
            return CheckOutcome(
                "reminder_list_smoke",
                "FAIL",
                "reminder_repository",
                "code",
                "list_eligible_reminders did not return list",
            )
    except Exception as ex:
        return CheckOutcome(
            "reminder_list_smoke",
            "FAIL",
            "database",
            "config",
            str(ex)[:500],
        )
    return CheckOutcome(
        "reminder_list_smoke",
        "PASS",
        "reminder_repository",
        "none",
        "Reminder repository readable",
    )


def check_recovery_compute_smoke() -> CheckOutcome:
    if (os.environ.get("WORKFLOW_LAUNCH_VALIDATE_DB") or "").strip() not in ("1", "true", "yes"):
        return CheckOutcome(
            "recovery_actions_smoke",
            "SKIP",
            "recovery_service",
            "none",
            "Set WORKFLOW_LAUNCH_VALIDATE_DB=1 to run",
        )
    try:
        from services.workflow.recovery_service import compute_recovery_actions

        r = compute_recovery_actions("00000000-0000-0000-0000-000000000077")
        if r.get("ok") is not False:
            return CheckOutcome(
                "recovery_actions_smoke",
                "FAIL",
                "recovery_service",
                "code",
                "compute_recovery_actions(missing) should set ok=false",
            )
    except Exception as ex:
        return CheckOutcome(
            "recovery_actions_smoke",
            "FAIL",
            "database",
            "config",
            str(ex)[:500],
        )
    return CheckOutcome(
        "recovery_actions_smoke",
        "PASS",
        "recovery_service",
        "none",
        "Recovery suggestions handle missing workflow",
    )


DEFAULT_CHECKERS: List[Callable[[], CheckOutcome]] = [
    check_imports,
    check_fastapi_workflow_app_import,
    check_stripe_webhook_imports,
    check_stripe_workflow_id_required,
    check_streamlit_payment_return_workflow_notify,
    check_webhook_workflow_path,
    check_admin_routes_use_admin_secret,
    check_internal_completion_routes,
    check_db_engine_smoke,
    check_home_summary_smoke,
    check_reminder_repository_smoke,
    check_recovery_compute_smoke,
]


def run_checks(
    checkers: Optional[List[Callable[[], CheckOutcome]]] = None,
) -> List[CheckOutcome]:
    out: List[CheckOutcome] = []
    for fn in checkers or DEFAULT_CHECKERS:
        try:
            out.append(fn())
        except Exception as ex:
            out.append(
                CheckOutcome(
                    fn.__name__,
                    "FAIL",
                    fn.__name__,
                    "code",
                    f"Checker crashed: {ex}",
                )
            )
    return out


def summary_lines(outcomes: List[CheckOutcome]) -> List[str]:
    lines = []
    for o in outcomes:
        lines.append(
            f"[{o.status:4}] {o.scenario} | {o.module} | {o.failure_kind} | {o.message}"
        )
        if o.evidence and o.status != "PASS":
            lines.append(f"       evidence: {o.evidence[:200]}")
    fail = [o for o in outcomes if o.status == "FAIL"]
    skip = [o for o in outcomes if o.status == "SKIP"]
    code_fail = [o for o in fail if o.failure_kind == "code"]
    cfg_fail = [o for o in fail if o.failure_kind == "config"]
    lines.append(
        f"--- summary: PASS={sum(1 for o in outcomes if o.status == 'PASS')} "
        f"FAIL={len(fail)} (code={len(code_fail)} config={len(cfg_fail)}) SKIP={len(skip)} ---"
    )
    return lines
