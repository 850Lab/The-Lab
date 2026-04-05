"""
Launch-readiness checks: static imports, critical invariants, optional DB smoke.

Run via ``python scripts/workflow_launch_validate.py`` or pytest
``tests/test_workflow_launch_readiness.py``.

Environment:
- ``WORKFLOW_LAUNCH_VALIDATE_DB=1`` — run DB smoke (requires working ``database`` config).

Scenario coverage (lightweight; full step progression needs a staging workflow + workers):
1 init / engine — ``imports_workflow_core``, ``db_engine_smoke`` (optional DB);
  ``workflow_deps_import_isolated`` (import guard);
  ``workflow_job_worker_import_isolated``; ``workflow_job_service_import_isolated`` (import guards);
  ``fetch_latest_active_workflow_id_call_sites`` (grep guard)
2 upload/parse — not automated (internal ``service-complete`` only); guarded by
  ``internal_service_complete_routes``
3 select/payment — Stripe invariants: ``stripe_checkout_workflow_id``,
  ``imports_stripe_webhook_stack``, ``streamlit_payment_return_workflow``
4 payment webhook — ``stripe_webhook_workflow_path``
5 letter/proof/mail — not automated (Streamlit/Lob); mail metadata via hooks tests N/A here
6 multi-bureau gating — code lives in ``hooks`` / engine; no isolated check;
  ``integrity_hints_service_import_isolated`` (import guard);
  ``workflow_flow_gates_import_isolated`` (import guard);
  ``merge_into_workflow_metadata_call_sites``; ``patch_session_metadata_call_sites``
  (grep guards)
7 response intake — ``imports_workflow_core`` includes ``response_intake_service``;
  ``response_intake_service_import_isolated``; ``response_flow_events_import_isolated``
  (import guards); ``emit_response_flow_event_call_sites``;
  ``update_response_classification_call_sites`` (grep guards)
8 reminder candidates — DB optional: ``reminder_list_smoke``
9 reminder delivery — ``reminder_delivery`` import via core imports;
  ``queue_reminder_call_sites``; ``mark_reminder_outcome_call_sites``;
  ``reminder_delivery_send_call_sites`` (grep guards)
10 admin override — ``workflow_api_admin_secret``; ``admin_reopen_failed_step_callers``;
  ``admin_override_entry_call_sites``; ``insert_admin_audit_call_sites``;
  ``merge_session_admin_override_metadata_call_sites``;
  ``fetch_response_by_id_call_sites`` (grep guards);
  ``admin_override_service_import_isolated``; ``mission_control_service_import_isolated``
  (import guards)
11 recovery execution — same + recovery routes exist (admin count);
  ``recovery_execution_service_import_isolated`` (import guard);
  ``recovery_resume_mail_call_sites``; ``recovery_retry_step_call_sites`` (grep guards)
12 home-summary — ``home_summary_smoke`` (optional DB)
13 e2e harness — ``e2e_operational_harness_import_isolated`` (import guard; verify script only)
14 workflow event log read — ``list_workflow_events_call_sites``;
  ``record_system_event_call_sites``; ``record_event_tx_call_sites`` (grep guards)
15 async workflow jobs (HTTP) — ``workflow_job_route_helpers_call_sites`` (grep guard)
16 async workflow jobs (worker) — ``claim_job_call_sites``;
  ``job_worker_start_stop_call_sites`` (grep guards)
17 public demo — ``public_demo_fixture_pdfs_present`` (``samples/*.pdf`` in repo);
  ``public_demo_enabled_consistency`` when ``PUBLIC_DEMO_ENABLED=1`` (+ optional DB user)
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


_WORKFLOW_DEPS_PKG_IMPORT = re.compile(
    r"from\s+api\s+import\b[^\n]*\bworkflow_deps\b"
)
_WORKFLOW_DEPS_DIRECT_IMPORT = re.compile(r"from\s+api\.workflow_deps\s+import\b")
_WORKFLOW_DEPS_MODULE_IMPORT = re.compile(r"import\s+api\.workflow_deps\b")


def check_workflow_deps_import_isolated() -> CheckOutcome:
    """
    Shared FastAPI dependencies for the workflow API must not be wired from other modules.
    """
    root = _repo_root()
    allowed_rel = "api/workflow_app.py"
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel == allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            _WORKFLOW_DEPS_PKG_IMPORT.search(text)
            or _WORKFLOW_DEPS_DIRECT_IMPORT.search(text)
            or _WORKFLOW_DEPS_MODULE_IMPORT.search(text)
        ):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "workflow_deps_import_isolated",
            "FAIL",
            "api.workflow_deps",
            "code",
            "api.workflow_deps must only be imported from api/workflow_app.py; "
            "also imported in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "workflow_deps_import_isolated",
        "PASS",
        "api.workflow_deps",
        "none",
        "api.workflow_deps import confined to workflow FastAPI app",
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


_QUEUE_REMINDER_CALL = re.compile(r"\bqueue_reminder\s*\(")


def check_queue_reminder_call_sites() -> CheckOutcome:
    """
    Reminder queueing for delivery is invoked from workflow API routes, the reminder service
    implementation, and the ops harness only.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/e2e_operational_harness.py",
        "services/workflow/reminder_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _QUEUE_REMINDER_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "queue_reminder_call_sites",
            "FAIL",
            "reminder_service",
            "code",
            "queue_reminder call sites must only appear in api/workflow_app.py, "
            "services/workflow/e2e_operational_harness.py, and "
            "services/workflow/reminder_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "queue_reminder_call_sites",
        "PASS",
        "reminder_service",
        "none",
        "queue_reminder confined to workflow API + reminder service + ops harness",
    )


_MARK_REMINDER_OUTCOME_CALL = re.compile(
    r"\b(?:mark_reminder_sent_stub|mark_reminder_failed|mark_reminder_skipped_internal)\s*\("
)


def check_mark_reminder_outcome_call_sites() -> CheckOutcome:
    """
    Reminder sent/failed/skipped state transitions are invoked from internal workflow routes,
    the reminder service implementation, and admin override delegation only.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/reminder_service.py",
        "services/workflow/admin_override_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _MARK_REMINDER_OUTCOME_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "mark_reminder_outcome_call_sites",
            "FAIL",
            "reminder_service",
            "code",
            "mark_reminder_sent_stub / mark_reminder_failed / "
            "mark_reminder_skipped_internal call sites must only appear in "
            "api/workflow_app.py, services/workflow/reminder_service.py, and "
            "services/workflow/admin_override_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "mark_reminder_outcome_call_sites",
        "PASS",
        "reminder_service",
        "none",
        "reminder outcome mutators confined to API + reminder service + admin overrides",
    )


_REMINDER_DELIVERY_SEND_CALL = re.compile(r"reminder_delivery\.send_reminder\s*\(")


def check_reminder_delivery_send_call_sites() -> CheckOutcome:
    """
    Low-level reminder send is invoked from ``reminder_service`` only (single choke point).
    """
    root = _repo_root()
    allowed_rel = {"services/workflow/reminder_service.py"}
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _REMINDER_DELIVERY_SEND_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "reminder_delivery_send_call_sites",
            "FAIL",
            "reminder_delivery",
            "code",
            "reminder_delivery.send_reminder call sites must only appear in "
            "services/workflow/reminder_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "reminder_delivery_send_call_sites",
        "PASS",
        "reminder_delivery",
        "none",
        "reminder_delivery.send_reminder confined to reminder_service",
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


def check_trusted_hook_flow_gates() -> CheckOutcome:
    """Trusted server paths (hooks + payment sync) must call flow gate helpers (control layer)."""
    hooks_src = _read_text("services/workflow/hooks.py")
    pay_src = _read_text("services/workflow_payment_service.py")
    gates_src = _read_text("services/workflow/workflow_flow_gates.py")
    missing: List[str] = []
    if "assert_internal_service_complete_allowed" not in hooks_src:
        missing.append("hooks.py must call assert_internal_service_complete_allowed")
    if "assert_internal_service_fail_allowed" not in hooks_src:
        missing.append("hooks.py must call assert_internal_service_fail_allowed")
    if "assert_customer_payment_capture_allowed" not in pay_src:
        missing.append("workflow_payment_service must use assert_customer_payment_capture_allowed")
    if "assert_customer_payment_continue_credits_allowed" not in pay_src:
        missing.append("workflow_payment_service must use assert_customer_payment_continue_credits_allowed")
    if "def assert_internal_service_complete_allowed" not in gates_src:
        missing.append("workflow_flow_gates must define assert_internal_service_complete_allowed")
    if "def assert_internal_service_fail_allowed" not in gates_src:
        missing.append("workflow_flow_gates must define assert_internal_service_fail_allowed")
    if missing:
        return CheckOutcome(
            "trusted_hook_flow_gates",
            "FAIL",
            "services.workflow.hooks",
            "code",
            "; ".join(missing),
        )
    return CheckOutcome(
        "trusted_hook_flow_gates",
        "PASS",
        "services.workflow.hooks",
        "none",
        "Trusted mutation hooks wired to flow gate helpers",
    )


_WORKFLOW_FLOW_GATES_PKG_IMPORT = re.compile(
    r"from\s+services\.workflow\s+import\b[^\n]*\bworkflow_flow_gates\b"
)
_WORKFLOW_FLOW_GATES_DIRECT_IMPORT = re.compile(
    r"from\s+services\.workflow\.workflow_flow_gates\s+import\b"
)
_WORKFLOW_FLOW_GATES_MODULE_IMPORT = re.compile(
    r"import\s+services\.workflow\.workflow_flow_gates\b"
)


def check_workflow_flow_gates_import_isolated() -> CheckOutcome:
    """
    Flow-gate assertions are imported only by trusted workflow surfaces (API, hooks, payment
    sync, async job worker).
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/hooks.py",
        "services/workflow/workflow_job_worker.py",
        "services/workflow_payment_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            _WORKFLOW_FLOW_GATES_PKG_IMPORT.search(text)
            or _WORKFLOW_FLOW_GATES_DIRECT_IMPORT.search(text)
            or _WORKFLOW_FLOW_GATES_MODULE_IMPORT.search(text)
        ):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "workflow_flow_gates_import_isolated",
            "FAIL",
            "workflow_flow_gates",
            "code",
            "workflow_flow_gates must only be imported from api/workflow_app.py, "
            "services/workflow/hooks.py, services/workflow/workflow_job_worker.py, or "
            "services/workflow_payment_service.py; also imported in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "workflow_flow_gates_import_isolated",
        "PASS",
        "workflow_flow_gates",
        "none",
        "workflow_flow_gates import confined to trusted workflow surfaces",
    )


_MERGE_INTO_WORKFLOW_METADATA_CALL = re.compile(r"\bmerge_into_workflow_metadata\s*\(")


def check_merge_into_workflow_metadata_call_sites() -> CheckOutcome:
    """
    Workflow session metadata merges are performed from trusted hooks, dispute strategy,
    and the repository implementation only.
    """
    root = _repo_root()
    allowed_rel = {
        "services/workflow/hooks.py",
        "services/workflow/repository.py",
        "services/customer_dispute_strategy.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _MERGE_INTO_WORKFLOW_METADATA_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "merge_into_workflow_metadata_call_sites",
            "FAIL",
            "services.workflow.repository",
            "code",
            "merge_into_workflow_metadata call sites must only appear in "
            "services/workflow/hooks.py, services/workflow/repository.py, "
            "and services/customer_dispute_strategy.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "merge_into_workflow_metadata_call_sites",
        "PASS",
        "services.workflow.repository",
        "none",
        "merge_into_workflow_metadata confined to hooks + repo + dispute strategy",
    )


_PATCH_SESSION_METADATA_CALL = re.compile(r"\bpatch_session_metadata\s*\(")


def check_patch_session_metadata_call_sites() -> CheckOutcome:
    """
    Transactional session metadata patches stay inside workflow engine, instance service,
    mail gating, intake, admin overrides, and reminder repository helpers.
    """
    root = _repo_root()
    allowed_rel = {
        "services/workflow/workflow_instance_service.py",
        "services/workflow/engine.py",
        "services/workflow/mail_gating.py",
        "services/workflow/response_intake_service.py",
        "services/workflow/admin_override_service.py",
        "services/workflow/reminder_repository.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _PATCH_SESSION_METADATA_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "patch_session_metadata_call_sites",
            "FAIL",
            "workflow_instance_service",
            "code",
            "patch_session_metadata call sites must only appear in services/workflow/"
            "workflow_instance_service.py, engine.py, mail_gating.py, "
            "response_intake_service.py, admin_override_service.py, "
            "and reminder_repository.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "patch_session_metadata_call_sites",
        "PASS",
        "workflow_instance_service",
        "none",
        "patch_session_metadata confined to core workflow mutation modules",
    )


_REOPEN_FAILED_STEP_CALL = re.compile(r"\breopen_failed_step\s*\(")


def check_admin_reopen_failed_step_callers() -> CheckOutcome:
    """
    ``services.workflow.admin_override_service.reopen_failed_step`` must not be imported or
    invoked outside ``api/workflow_app.py`` (besides its definition file). Operator reopen
    must stay behind the gated admin route. Engine ``service_reopen_failed_step`` is a
    different symbol and may still be used from recovery tooling.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/admin_override_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _REOPEN_FAILED_STEP_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "admin_reopen_failed_step_callers",
            "FAIL",
            "admin_override_service",
            "code",
            "reopen_failed_step call sites must only appear in api/workflow_app.py and "
            "services/workflow/admin_override_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "admin_reopen_failed_step_callers",
        "PASS",
        "admin_override_service",
        "none",
        "reopen_failed_step references confined to workflow API + definition",
    )


_ADMIN_OVERRIDE_ENTRY_CALL = re.compile(
    r"\b(?:trigger_recovery_action_record|apply_payment_waived|mark_reminder_skipped|"
    r"clear_stalled_flag|override_response_classification|override_escalation_recommendation)"
    r"\s*\("
)


def check_admin_override_entry_call_sites() -> CheckOutcome:
    """
    Public admin override entrypoints (except ``reopen_failed_step``, guarded separately)
    must only be invoked from gated workflow API routes and the service module.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/admin_override_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _ADMIN_OVERRIDE_ENTRY_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "admin_override_entry_call_sites",
            "FAIL",
            "admin_override_service",
            "code",
            "admin override entry call sites (classification / escalation / reminder skip / "
            "stalled clear / payment waived / recovery record) must only appear in "
            "api/workflow_app.py and services/workflow/admin_override_service.py; "
            "also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "admin_override_entry_call_sites",
        "PASS",
        "admin_override_service",
        "none",
        "admin override entry calls confined to workflow API + definition",
    )


_INSERT_ADMIN_AUDIT_CALL = re.compile(r"\binsert_admin_audit\s*\(")


def check_insert_admin_audit_call_sites() -> CheckOutcome:
    """
    Admin audit rows are written from operator overrides and recovery execution only
    (plus the reminder repository implementation).
    """
    root = _repo_root()
    allowed_rel = {
        "services/workflow/reminder_repository.py",
        "services/workflow/admin_override_service.py",
        "services/workflow/recovery_execution_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _INSERT_ADMIN_AUDIT_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "insert_admin_audit_call_sites",
            "FAIL",
            "reminder_repository",
            "code",
            "insert_admin_audit call sites must only appear in "
            "services/workflow/reminder_repository.py, admin_override_service.py, "
            "and recovery_execution_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "insert_admin_audit_call_sites",
        "PASS",
        "reminder_repository",
        "none",
        "insert_admin_audit confined to audit repo + overrides + recovery execution",
    )


_MERGE_SESSION_ADMIN_OVERRIDE_META_CALL = re.compile(
    r"\bmerge_session_admin_override_metadata\s*\("
)


def check_merge_session_admin_override_metadata_call_sites() -> CheckOutcome:
    """
    Session admin-override metadata merges are performed by the override service only
    (plus the reminder repository implementation).
    """
    root = _repo_root()
    allowed_rel = {
        "services/workflow/reminder_repository.py",
        "services/workflow/admin_override_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _MERGE_SESSION_ADMIN_OVERRIDE_META_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "merge_session_admin_override_metadata_call_sites",
            "FAIL",
            "reminder_repository",
            "code",
            "merge_session_admin_override_metadata call sites must only appear in "
            "services/workflow/reminder_repository.py and "
            "services/workflow/admin_override_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "merge_session_admin_override_metadata_call_sites",
        "PASS",
        "reminder_repository",
        "none",
        "merge_session_admin_override_metadata confined to repo + admin overrides",
    )


_FETCH_RESPONSE_BY_ID_CALL = re.compile(r"\bfetch_response_by_id\s*\(")


def check_fetch_response_by_id_call_sites() -> CheckOutcome:
    """
    Single-response lookups by id are used for admin classification overrides only
    (plus the response repository implementation).
    """
    root = _repo_root()
    allowed_rel = {
        "services/workflow/response_repository.py",
        "services/workflow/admin_override_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _FETCH_RESPONSE_BY_ID_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "fetch_response_by_id_call_sites",
            "FAIL",
            "response_repository",
            "code",
            "fetch_response_by_id call sites must only appear in "
            "services/workflow/response_repository.py and "
            "services/workflow/admin_override_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "fetch_response_by_id_call_sites",
        "PASS",
        "response_repository",
        "none",
        "fetch_response_by_id confined to repo + admin overrides",
    )


_LIST_WORKFLOW_EVENTS_CALL = re.compile(r"\blist_workflow_events\s*\(")


def check_list_workflow_events_call_sites() -> CheckOutcome:
    """
    Event timeline reads should stay on the customer workflow API route, not arbitrary callers.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/workflow_event_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _LIST_WORKFLOW_EVENTS_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "list_workflow_events_call_sites",
            "FAIL",
            "workflow_event_service",
            "code",
            "list_workflow_events call sites must only appear in api/workflow_app.py and "
            "services/workflow/workflow_event_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "list_workflow_events_call_sites",
        "PASS",
        "workflow_event_service",
        "none",
        "list_workflow_events confined to workflow API + definition",
    )


_RECORD_SYSTEM_EVENT_CALL = re.compile(r"\brecord_system_event\s*\(")


def check_record_system_event_call_sites() -> CheckOutcome:
    """
    System workflow events are written from the letter pipeline and demo harness only
    (plus the event service definition).
    """
    root = _repo_root()
    allowed_rel = {
        "services/workflow/workflow_event_service.py",
        "services/public_demo_service.py",
        "services/customer_letter_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _RECORD_SYSTEM_EVENT_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "record_system_event_call_sites",
            "FAIL",
            "workflow_event_service",
            "code",
            "record_system_event call sites must only appear in "
            "services/workflow/workflow_event_service.py, services/public_demo_service.py, "
            "and services/customer_letter_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "record_system_event_call_sites",
        "PASS",
        "workflow_event_service",
        "none",
        "record_system_event confined to event service + demo + letter pipeline",
    )


_RECORD_EVENT_TX_CALL = re.compile(r"\brecord_event_tx\s*\(")


def check_record_event_tx_call_sites() -> CheckOutcome:
    """
    Transactional workflow event writes stay inside workflow persistence and job plumbing.
    """
    root = _repo_root()
    allowed_rel = {
        "services/workflow/workflow_event_service.py",
        "services/workflow/workflow_instance_service.py",
        "services/workflow/workflow_job_service.py",
        "services/workflow/repository.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _RECORD_EVENT_TX_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "record_event_tx_call_sites",
            "FAIL",
            "workflow_event_service",
            "code",
            "record_event_tx call sites must only appear in services/workflow/"
            "workflow_event_service.py, workflow_instance_service.py, "
            "workflow_job_service.py, and repository.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "record_event_tx_call_sites",
        "PASS",
        "workflow_event_service",
        "none",
        "record_event_tx confined to core workflow persistence modules",
    )


_FETCH_LATEST_ACTIVE_WID_CALL = re.compile(r"\bfetch_latest_active_workflow_id\s*\(")


def check_fetch_latest_active_workflow_id_call_sites() -> CheckOutcome:
    """
    Default active workflow selection for API auth context must not sprawl outside the
    workflow API and repository helpers.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/repository.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _FETCH_LATEST_ACTIVE_WID_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "fetch_latest_active_workflow_id_call_sites",
            "FAIL",
            "services.workflow.repository",
            "code",
            "fetch_latest_active_workflow_id call sites must only appear in api/workflow_app.py "
            "and services/workflow/repository.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "fetch_latest_active_workflow_id_call_sites",
        "PASS",
        "services.workflow.repository",
        "none",
        "fetch_latest_active_workflow_id confined to workflow API + repository",
    )


_WORKFLOW_JOB_ROUTE_HELPERS_CALL = re.compile(
    r"\b(?:create_job|wf_list_jobs|wf_get_job|wf_public_job_view)\s*\("
)


def check_workflow_job_route_helpers_call_sites() -> CheckOutcome:
    """
    Letter-generation job create/list/get helpers are wired for workflow API routes only
    (plus definitions in ``workflow_job_service``).
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/workflow_job_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _WORKFLOW_JOB_ROUTE_HELPERS_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "workflow_job_route_helpers_call_sites",
            "FAIL",
            "workflow_job_service",
            "code",
            "workflow job route helpers (create_job / wf_list_jobs / wf_get_job / "
            "wf_public_job_view) must only appear in api/workflow_app.py and "
            "services/workflow/workflow_job_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "workflow_job_route_helpers_call_sites",
        "PASS",
        "workflow_job_service",
        "none",
        "workflow job route helpers confined to workflow API + job service",
    )


_CLAIM_JOB_CALL = re.compile(r"\bclaim_job\s*\(")


def check_claim_job_call_sites() -> CheckOutcome:
    """
    Job claiming is for the in-process worker loop and the service implementation only.
    """
    root = _repo_root()
    allowed_rel = {
        "services/workflow/workflow_job_worker.py",
        "services/workflow/workflow_job_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _CLAIM_JOB_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "claim_job_call_sites",
            "FAIL",
            "workflow_job_service",
            "code",
            "claim_job call sites must only appear in services/workflow/workflow_job_worker.py "
            "and services/workflow/workflow_job_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "claim_job_call_sites",
        "PASS",
        "workflow_job_service",
        "none",
        "claim_job confined to job worker + job service",
    )


_JOB_WORKER_START_STOP_CALL = re.compile(
    r"\b(?:start_job_worker|stop_job_worker)\s*\("
)


def check_job_worker_start_stop_call_sites() -> CheckOutcome:
    """
    In-process job worker lifecycle hooks are invoked from the workflow API lifespan and
    defined in ``workflow_job_worker`` only.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/workflow_job_worker.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _JOB_WORKER_START_STOP_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "job_worker_start_stop_call_sites",
            "FAIL",
            "workflow_job_worker",
            "code",
            "start_job_worker / stop_job_worker call sites must only appear in "
            "api/workflow_app.py and services/workflow/workflow_job_worker.py; "
            "also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "job_worker_start_stop_call_sites",
        "PASS",
        "workflow_job_worker",
        "none",
        "job worker start/stop confined to workflow API + worker module",
    )


_ADMIN_OVERRIDE_PKG_IMPORT = re.compile(
    r"from\s+services\.workflow\s+import\b[^\n]*\badmin_override_service\b"
)
_ADMIN_OVERRIDE_DIRECT_IMPORT = re.compile(
    r"from\s+services\.workflow\.admin_override_service\s+import\b"
)
_ADMIN_OVERRIDE_MODULE_IMPORT = re.compile(
    r"import\s+services\.workflow\.admin_override_service\b"
)


def check_admin_override_service_import_isolated() -> CheckOutcome:
    """
    ``admin_override_service`` must only be imported from ``api/workflow_app.py`` so operator
    overrides stay behind gated admin routes.
    """
    root = _repo_root()
    allowed_rel = "api/workflow_app.py"
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel == allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            _ADMIN_OVERRIDE_PKG_IMPORT.search(text)
            or _ADMIN_OVERRIDE_DIRECT_IMPORT.search(text)
            or _ADMIN_OVERRIDE_MODULE_IMPORT.search(text)
        ):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "admin_override_service_import_isolated",
            "FAIL",
            "admin_override_service",
            "code",
            "admin_override_service must only be imported from api/workflow_app.py; "
            "also imported in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "admin_override_service_import_isolated",
        "PASS",
        "admin_override_service",
        "none",
        "admin_override_service import confined to workflow API",
    )


_MISSION_CONTROL_PKG_IMPORT = re.compile(
    r"from\s+services\.workflow\s+import\b[^\n]*\bmission_control_service\b"
)
_MISSION_CONTROL_DIRECT_IMPORT = re.compile(
    r"from\s+services\.workflow\.mission_control_service\s+import\b"
)
_MISSION_CONTROL_MODULE_IMPORT = re.compile(
    r"import\s+services\.workflow\.mission_control_service\b"
)


def check_mission_control_service_import_isolated() -> CheckOutcome:
    """
    Mission Control aggregates are operator-facing; keep imports on the gated workflow API only.
    """
    root = _repo_root()
    allowed_rel = "api/workflow_app.py"
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel == allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            _MISSION_CONTROL_PKG_IMPORT.search(text)
            or _MISSION_CONTROL_DIRECT_IMPORT.search(text)
            or _MISSION_CONTROL_MODULE_IMPORT.search(text)
        ):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "mission_control_service_import_isolated",
            "FAIL",
            "mission_control_service",
            "code",
            "mission_control_service must only be imported from api/workflow_app.py; "
            "also imported in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "mission_control_service_import_isolated",
        "PASS",
        "mission_control_service",
        "none",
        "mission_control_service import confined to workflow API",
    )


_INTEGRITY_HINTS_PKG_IMPORT = re.compile(
    r"from\s+services\.workflow\s+import\b[^\n]*\bintegrity_hints_service\b"
)
_INTEGRITY_HINTS_DIRECT_IMPORT = re.compile(
    r"from\s+services\.workflow\.integrity_hints_service\s+import\b"
)
_INTEGRITY_HINTS_MODULE_IMPORT = re.compile(
    r"import\s+services\.workflow\.integrity_hints_service\b"
)


def check_integrity_hints_service_import_isolated() -> CheckOutcome:
    """
    Integrity hints aggregate workflow/mail state for the API; keep imports on the gated app only.
    """
    root = _repo_root()
    allowed_rel = "api/workflow_app.py"
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel == allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            _INTEGRITY_HINTS_PKG_IMPORT.search(text)
            or _INTEGRITY_HINTS_DIRECT_IMPORT.search(text)
            or _INTEGRITY_HINTS_MODULE_IMPORT.search(text)
        ):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "integrity_hints_service_import_isolated",
            "FAIL",
            "integrity_hints_service",
            "code",
            "integrity_hints_service must only be imported from api/workflow_app.py; "
            "also imported in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "integrity_hints_service_import_isolated",
        "PASS",
        "integrity_hints_service",
        "none",
        "integrity_hints_service import confined to workflow API",
    )


_RESPONSE_INTAKE_PKG_IMPORT = re.compile(
    r"from\s+services\.workflow\s+import\b[^\n]*\bresponse_intake_service\b"
)
_RESPONSE_INTAKE_DIRECT_IMPORT = re.compile(
    r"from\s+services\.workflow\.response_intake_service\s+import\b"
)
_RESPONSE_INTAKE_MODULE_IMPORT = re.compile(
    r"import\s+services\.workflow\.response_intake_service\b"
)


def check_response_intake_service_import_isolated() -> CheckOutcome:
    """
    Bureau response intake mutates workflow state; only the gated workflow API and the internal
    operational harness may import this module.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/e2e_operational_harness.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            _RESPONSE_INTAKE_PKG_IMPORT.search(text)
            or _RESPONSE_INTAKE_DIRECT_IMPORT.search(text)
            or _RESPONSE_INTAKE_MODULE_IMPORT.search(text)
        ):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "response_intake_service_import_isolated",
            "FAIL",
            "response_intake_service",
            "code",
            "response_intake_service must only be imported from api/workflow_app.py "
            "or services/workflow/e2e_operational_harness.py; also imported in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "response_intake_service_import_isolated",
        "PASS",
        "response_intake_service",
        "none",
        "response_intake_service import confined to API + ops harness",
    )


_RESPONSE_FLOW_PKG_IMPORT = re.compile(
    r"from\s+services\.workflow\s+import\b[^\n]*\bresponse_flow_events\b"
)
_RESPONSE_FLOW_DIRECT_IMPORT = re.compile(
    r"from\s+services\.workflow\.response_flow_events\s+import\b"
)
_RESPONSE_FLOW_MODULE_IMPORT = re.compile(
    r"import\s+services\.workflow\.response_flow_events\b"
)


def check_response_flow_events_import_isolated() -> CheckOutcome:
    """
    Response-flow step events are emitted from the API and the intake pipeline only.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/response_intake_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            _RESPONSE_FLOW_PKG_IMPORT.search(text)
            or _RESPONSE_FLOW_DIRECT_IMPORT.search(text)
            or _RESPONSE_FLOW_MODULE_IMPORT.search(text)
        ):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "response_flow_events_import_isolated",
            "FAIL",
            "response_flow_events",
            "code",
            "response_flow_events must only be imported from api/workflow_app.py or "
            "services/workflow/response_intake_service.py; also imported in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "response_flow_events_import_isolated",
        "PASS",
        "response_flow_events",
        "none",
        "response_flow_events import confined to API + intake service",
    )


_EMIT_RESPONSE_FLOW_EVENT_CALL = re.compile(r"\bemit_response_flow_event\s*\(")


def check_emit_response_flow_event_call_sites() -> CheckOutcome:
    """
    Response-flow audit emissions belong to the workflow API, intake pipeline, and emitter module.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/response_intake_service.py",
        "services/workflow/response_flow_events.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _EMIT_RESPONSE_FLOW_EVENT_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "emit_response_flow_event_call_sites",
            "FAIL",
            "response_flow_events",
            "code",
            "emit_response_flow_event call sites must only appear in api/workflow_app.py, "
            "services/workflow/response_intake_service.py, and "
            "services/workflow/response_flow_events.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "emit_response_flow_event_call_sites",
        "PASS",
        "response_flow_events",
        "none",
        "emit_response_flow_event confined to API + intake + emitter",
    )


_UPDATE_RESPONSE_CLASSIFICATION_CALL = re.compile(
    r"\bupdate_response_classification\s*\("
)


def check_update_response_classification_call_sites() -> CheckOutcome:
    """
    Bureau response classification rows are updated from intake and admin override paths only
    (plus the response repository implementation).
    """
    root = _repo_root()
    allowed_rel = {
        "services/workflow/response_repository.py",
        "services/workflow/admin_override_service.py",
        "services/workflow/response_intake_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _UPDATE_RESPONSE_CLASSIFICATION_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "update_response_classification_call_sites",
            "FAIL",
            "response_repository",
            "code",
            "update_response_classification call sites must only appear in "
            "services/workflow/response_repository.py, admin_override_service.py, "
            "and response_intake_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "update_response_classification_call_sites",
        "PASS",
        "response_repository",
        "none",
        "update_response_classification confined to repo + overrides + intake",
    )


_RECOVERY_EXEC_PKG_IMPORT = re.compile(
    r"from\s+services\.workflow\s+import\b[^\n]*\brecovery_execution_service\b"
)
_RECOVERY_EXEC_DIRECT_IMPORT = re.compile(
    r"from\s+services\.workflow\.recovery_execution_service\s+import\b"
)
_RECOVERY_EXEC_MODULE_IMPORT = re.compile(
    r"import\s+services\.workflow\.recovery_execution_service\b"
)


def check_recovery_execution_service_import_isolated() -> CheckOutcome:
    """
    Recovery execution mutates workflow state; only the gated workflow API and the internal
    operational harness may import this module.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/e2e_operational_harness.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            _RECOVERY_EXEC_PKG_IMPORT.search(text)
            or _RECOVERY_EXEC_DIRECT_IMPORT.search(text)
            or _RECOVERY_EXEC_MODULE_IMPORT.search(text)
        ):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "recovery_execution_service_import_isolated",
            "FAIL",
            "recovery_execution_service",
            "code",
            "recovery_execution_service must only be imported from api/workflow_app.py "
            "or services/workflow/e2e_operational_harness.py; also imported in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "recovery_execution_service_import_isolated",
        "PASS",
        "recovery_execution_service",
        "none",
        "recovery_execution_service import confined to API + ops harness",
    )


_RECOVERY_RESUME_MAIL_CALL = re.compile(
    r"\b(?:execute_resume_current_step|execute_re_run_mail_attempt)\s*\("
)


def check_recovery_resume_mail_call_sites() -> CheckOutcome:
    """
    Resume-current and mail re-run recovery actions are admin-route only plus the
    execution service implementation.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/recovery_execution_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _RECOVERY_RESUME_MAIL_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "recovery_resume_mail_call_sites",
            "FAIL",
            "recovery_execution_service",
            "code",
            "execute_resume_current_step / execute_re_run_mail_attempt call sites must "
            "only appear in api/workflow_app.py and "
            "services/workflow/recovery_execution_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "recovery_resume_mail_call_sites",
        "PASS",
        "recovery_execution_service",
        "none",
        "recovery resume + mail retry confined to workflow API + execution service",
    )


_RECOVERY_RETRY_STEP_CALL = re.compile(r"\bexecute_retry_step\s*\(")


def check_recovery_retry_step_call_sites() -> CheckOutcome:
    """
    Retry-step recovery is invoked from admin routes, the ops harness, and the service def.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/e2e_operational_harness.py",
        "services/workflow/recovery_execution_service.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _RECOVERY_RETRY_STEP_CALL.search(text):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "recovery_retry_step_call_sites",
            "FAIL",
            "recovery_execution_service",
            "code",
            "execute_retry_step call sites must only appear in api/workflow_app.py, "
            "services/workflow/e2e_operational_harness.py, and "
            "services/workflow/recovery_execution_service.py; also found in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "recovery_retry_step_call_sites",
        "PASS",
        "recovery_execution_service",
        "none",
        "execute_retry_step confined to API + ops harness + execution service",
    )


_E2E_HARNESS_PKG_IMPORT = re.compile(
    r"from\s+services\.workflow\s+import\b[^\n]*\be2e_operational_harness\b"
)
_E2E_HARNESS_DIRECT_IMPORT = re.compile(
    r"from\s+services\.workflow\.e2e_operational_harness\s+import\b"
)
_E2E_HARNESS_MODULE_IMPORT = re.compile(
    r"import\s+services\.workflow\.e2e_operational_harness\b"
)


def check_e2e_operational_harness_import_isolated() -> CheckOutcome:
    """
    Synthetic end-to-end driver mutates real workflow state; keep imports on the dedicated
    verify script only (not production routes or random tooling).
    """
    root = _repo_root()
    allowed_rel = "scripts/workflow_e2e_verify.py"
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel == allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            _E2E_HARNESS_PKG_IMPORT.search(text)
            or _E2E_HARNESS_DIRECT_IMPORT.search(text)
            or _E2E_HARNESS_MODULE_IMPORT.search(text)
        ):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "e2e_operational_harness_import_isolated",
            "FAIL",
            "e2e_operational_harness",
            "code",
            "e2e_operational_harness must only be imported from scripts/workflow_e2e_verify.py; "
            "also imported in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "e2e_operational_harness_import_isolated",
        "PASS",
        "e2e_operational_harness",
        "none",
        "e2e_operational_harness import confined to workflow_e2e_verify script",
    )


_WORKFLOW_JOB_WORKER_PKG_IMPORT = re.compile(
    r"from\s+services\.workflow\s+import\b[^\n]*\bworkflow_job_worker\b"
)
_WORKFLOW_JOB_WORKER_DIRECT_IMPORT = re.compile(
    r"from\s+services\.workflow\.workflow_job_worker\s+import\b"
)
_WORKFLOW_JOB_WORKER_MODULE_IMPORT = re.compile(
    r"import\s+services\.workflow\.workflow_job_worker\b"
)


def check_workflow_job_worker_import_isolated() -> CheckOutcome:
    """
    In-process workflow job worker start/stop is tied to the FastAPI lifespan; only the
    workflow API app may import this module.
    """
    root = _repo_root()
    allowed_rel = "api/workflow_app.py"
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel == allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            _WORKFLOW_JOB_WORKER_PKG_IMPORT.search(text)
            or _WORKFLOW_JOB_WORKER_DIRECT_IMPORT.search(text)
            or _WORKFLOW_JOB_WORKER_MODULE_IMPORT.search(text)
        ):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "workflow_job_worker_import_isolated",
            "FAIL",
            "workflow_job_worker",
            "code",
            "workflow_job_worker must only be imported from api/workflow_app.py; "
            "also imported in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "workflow_job_worker_import_isolated",
        "PASS",
        "workflow_job_worker",
        "none",
        "workflow_job_worker import confined to workflow API",
    )


_WORKFLOW_JOB_SVC_PKG_IMPORT = re.compile(
    r"from\s+services\.workflow\s+import\b[^\n]*\bworkflow_job_service\b"
)
_WORKFLOW_JOB_SVC_DIRECT_IMPORT = re.compile(
    r"from\s+services\.workflow\.workflow_job_service\s+import\b"
)
_WORKFLOW_JOB_SVC_MODULE_IMPORT = re.compile(
    r"import\s+services\.workflow\.workflow_job_service\b"
)


def check_workflow_job_service_import_isolated() -> CheckOutcome:
    """
    Async job claim/run logic is used by HTTP routes and the in-process worker only.
    """
    root = _repo_root()
    allowed_rel = {
        "api/workflow_app.py",
        "services/workflow/workflow_job_worker.py",
    }
    skip_prefixes = (
        "tests/",
        "attached_assets/",
        ".venv/",
        "venv/",
    )
    offenders: List[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(skip_prefixes) or "/__pycache__/" in rel:
            continue
        if rel in allowed_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            _WORKFLOW_JOB_SVC_PKG_IMPORT.search(text)
            or _WORKFLOW_JOB_SVC_DIRECT_IMPORT.search(text)
            or _WORKFLOW_JOB_SVC_MODULE_IMPORT.search(text)
        ):
            offenders.append(rel)
    if offenders:
        return CheckOutcome(
            "workflow_job_service_import_isolated",
            "FAIL",
            "workflow_job_service",
            "code",
            "workflow_job_service must only be imported from api/workflow_app.py or "
            "services/workflow/workflow_job_worker.py; also imported in: "
            + ", ".join(offenders[:15])
            + ("…" if len(offenders) > 15 else ""),
            evidence=offenders[0],
        )
    return CheckOutcome(
        "workflow_job_service_import_isolated",
        "PASS",
        "workflow_job_service",
        "none",
        "workflow_job_service import confined to API + job worker",
    )


def check_public_demo_fixture_pdfs_present() -> CheckOutcome:
    """
    Every scenario in ``DEMO_SCENARIOS`` must exist on disk at repo root.

    Production API resolves ``samples/*.pdf`` from the deployed tree; missing files
    yield an empty scenario list and a broken ``/demo`` shell.
    """
    try:
        from services.public_demo_fixtures_manifest import REPO_ROOT, demo_scenarios
    except Exception as ex:
        return CheckOutcome(
            "public_demo_fixture_pdfs_present",
            "FAIL",
            "public_demo_fixtures_manifest",
            "code",
            f"Cannot import demo fixture manifest: {ex}",
        )
    missing: List[str] = []
    for meta in demo_scenarios().values():
        rel = str(meta.get("file") or "")
        if not rel:
            continue
        p = REPO_ROOT / rel
        if not p.is_file():
            missing.append(rel)
        bundle = meta.get("fixture_bundle")
        if isinstance(bundle, list):
            for br in bundle:
                brs = str(br or "").strip()
                if not brs:
                    continue
                bp = REPO_ROOT / brs
                if not bp.is_file():
                    missing.append(brs)
    if missing:
        return CheckOutcome(
            "public_demo_fixture_pdfs_present",
            "FAIL",
            "public_demo_fixtures_manifest",
            "code",
            "Missing demo fixture PDF(s): " + ", ".join(missing),
            evidence=missing[0],
        )
    return CheckOutcome(
        "public_demo_fixture_pdfs_present",
        "PASS",
        "public_demo_fixtures_manifest",
        "none",
        "All DEMO_SCENARIOS PDFs present under repo root",
    )


def check_public_demo_enabled_consistency() -> CheckOutcome:
    """
    When the public demo is configured (``public_demo_config_error()`` is None),
    fixtures must exist. With ``WORKFLOW_LAUNCH_VALIDATE_DB=1``, also verify the demo user row.

    ``PUBLIC_DEMO_ENABLED=1`` is required only on production-like deploys; local dev can omit it.
    ``PUBLIC_DEMO_USER_ID`` is optional (auto-provisioned demo user when unset).
    """
    from services import public_demo_service as pds

    explicit_enabled = (os.environ.get("PUBLIC_DEMO_ENABLED") or "").strip() == "1"
    err = pds.public_demo_config_error()
    if err:
        if explicit_enabled:
            return CheckOutcome(
                "public_demo_enabled_consistency",
                "FAIL",
                "public_demo_service",
                "config",
                err,
            )
        return CheckOutcome(
            "public_demo_enabled_consistency",
            "SKIP",
            "public_demo_service",
            "none",
            err[:120] if err else "demo not configured",
        )
    if not pds.list_demo_scenarios_public():
        return CheckOutcome(
            "public_demo_enabled_consistency",
            "FAIL",
            "public_demo_service",
            "config",
            "PUBLIC_DEMO_ENABLED but no scenarios (fixture PDFs missing or unreadable)",
            evidence="list_demo_scenarios_public() empty",
        )
    if os.environ.get("WORKFLOW_LAUNCH_VALIDATE_DB") != "1":
        return CheckOutcome(
            "public_demo_enabled_consistency",
            "PASS",
            "public_demo_service",
            "none",
            "Public demo env + fixtures OK (DB user not validated)",
        )
    uid = pds.demo_user_id()
    try:
        import database as db

        with db.get_db(dict_cursor=True) as (conn, cur):
            cur.execute("SELECT id FROM users WHERE id = %s", (uid,))
            row = cur.fetchone()
    except Exception as ex:
        return CheckOutcome(
            "public_demo_enabled_consistency",
            "FAIL",
            "public_demo_service",
            "config",
            f"DB check failed: {ex}",
        )
    if not row:
        return CheckOutcome(
            "public_demo_enabled_consistency",
            "FAIL",
            "public_demo_service",
            "config",
            f"PUBLIC_DEMO_USER_ID={uid} has no matching users row",
        )
    return CheckOutcome(
        "public_demo_enabled_consistency",
        "PASS",
        "public_demo_service",
        "none",
        f"Public demo user id {uid} exists in users",
    )


DEFAULT_CHECKERS: List[Callable[[], CheckOutcome]] = [
    check_imports,
    check_fastapi_workflow_app_import,
    check_workflow_deps_import_isolated,
    check_stripe_webhook_imports,
    check_stripe_workflow_id_required,
    check_streamlit_payment_return_workflow_notify,
    check_webhook_workflow_path,
    check_admin_routes_use_admin_secret,
    check_internal_completion_routes,
    check_trusted_hook_flow_gates,
    check_workflow_flow_gates_import_isolated,
    check_merge_into_workflow_metadata_call_sites,
    check_patch_session_metadata_call_sites,
    check_admin_reopen_failed_step_callers,
    check_admin_override_entry_call_sites,
    check_insert_admin_audit_call_sites,
    check_merge_session_admin_override_metadata_call_sites,
    check_fetch_response_by_id_call_sites,
    check_list_workflow_events_call_sites,
    check_record_system_event_call_sites,
    check_record_event_tx_call_sites,
    check_fetch_latest_active_workflow_id_call_sites,
    check_admin_override_service_import_isolated,
    check_mission_control_service_import_isolated,
    check_integrity_hints_service_import_isolated,
    check_response_intake_service_import_isolated,
    check_response_flow_events_import_isolated,
    check_emit_response_flow_event_call_sites,
    check_update_response_classification_call_sites,
    check_recovery_execution_service_import_isolated,
    check_recovery_resume_mail_call_sites,
    check_recovery_retry_step_call_sites,
    check_e2e_operational_harness_import_isolated,
    check_workflow_job_worker_import_isolated,
    check_workflow_job_service_import_isolated,
    check_workflow_job_route_helpers_call_sites,
    check_claim_job_call_sites,
    check_job_worker_start_stop_call_sites,
    check_db_engine_smoke,
    check_home_summary_smoke,
    check_reminder_repository_smoke,
    check_queue_reminder_call_sites,
    check_mark_reminder_outcome_call_sites,
    check_reminder_delivery_send_call_sites,
    check_public_demo_fixture_pdfs_present,
    check_public_demo_enabled_consistency,
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
