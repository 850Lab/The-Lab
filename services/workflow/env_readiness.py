"""
Workflow environment readiness: which linear phases are fully supported given env/config.

Used for startup logging and HTTP diagnostics (no secret values are logged or returned).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Tuple

from services.workflow.workflow_db_config import is_production_like, should_use_workflow_sqlite

Status = Literal["ok", "degraded", "blocked"]


def _worker_enabled() -> bool:
    raw = (os.environ.get("WORKFLOW_JOB_WORKER_ENABLED") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _customer_app_origin_configured() -> bool:
    return bool(
        (os.environ.get("WORKFLOW_CUSTOMER_APP_ORIGIN") or os.environ.get("PUBLIC_APP_ORIGIN") or "").strip()
    )


def _database_env_status() -> Tuple[Status, List[str]]:
    issues: List[str] = []
    if is_production_like():
        if not (os.environ.get("DATABASE_URL") or "").strip():
            return "blocked", ["DATABASE_URL is required in production-like environments."]
        backend = (os.environ.get("DB_BACKEND") or "auto").strip().lower()
        if backend == "sqlite":
            return "blocked", ["DB_BACKEND=sqlite is not allowed when ENVIRONMENT=production or REPLIT_DEPLOYMENT=1."]
        return "ok", []
    # Dev / test
    if should_use_workflow_sqlite():
        path = (os.environ.get("WORKFLOW_SQLITE_PATH") or "").strip()
        if not path:
            return "ok", []  # default path from workflow_db_config
        return "ok", []
    if not (os.environ.get("DATABASE_URL") or "").strip():
        return "degraded", ["DATABASE_URL is unset; Postgres-backed features need a connection string."]
    return "ok", []


def _resend_status() -> Tuple[Status, List[str]]:
    key = (os.environ.get("RESEND_API_KEY") or "").strip()
    from_email = (os.environ.get("RESEND_FROM_EMAIL") or "").strip()
    issues: List[str] = []
    if not key:
        issues.append("RESEND_API_KEY is not set (signup / verification emails will fail).")
    if not from_email:
        issues.append("RESEND_FROM_EMAIL is not set.")
    if issues:
        return "degraded", issues
    return "ok", []


def _stripe_status() -> Tuple[Status, List[str]]:
    from stripe_client import get_stripe_credentials

    if get_stripe_credentials():
        return "ok", []
    return "degraded", ["Stripe is not configured (set STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY, or Replit connector)."]


def _lob_status() -> Tuple[Status, List[str]]:
    from lob_client import customer_mail_send_blocked_reason, is_configured

    if not is_configured():
        return "degraded", ["LOB_API_KEY is not set (certified mail cannot be sent)."]
    reason = customer_mail_send_blocked_reason(is_admin=False)
    if reason:
        return "degraded", [reason]
    return "ok", []


def _stripe_webhook_status() -> Tuple[Status, List[str]]:
    """Optional: warn in production if webhook secret missing (payment reconciliation may rely on webhooks)."""
    if not is_production_like():
        return "ok", []
    if (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip():
        return "ok", []
    return "degraded", ["STRIPE_WEBHOOK_SECRET is unset (configure Stripe webhooks for reliable payment events)."]


def compute_workflow_env_readiness(*, database_initialized_ok: bool = True) -> Dict[str, Any]:
    """
    Return integration status and per-linear-phase readiness.

    ``database_initialized_ok`` should be True after ``database.init_database()`` succeeds
    (startup path); when False, upload/parse phases reflect that the DB layer did not start.
    """
    db_status, db_issues = _database_env_status()
    if not database_initialized_ok and db_status != "blocked":
        db_status = "blocked"
        db_issues = ["Database initialization failed (see startup logs)."]

    resend_status, resend_issues = _resend_status()
    stripe_status, stripe_issues = _stripe_status()
    origin_ok = _customer_app_origin_configured()
    payment_support = stripe_status == "ok" and origin_ok
    payment_issues: List[str] = list(stripe_issues)
    if not origin_ok:
        payment_issues.append(
            "WORKFLOW_CUSTOMER_APP_ORIGIN or PUBLIC_APP_ORIGIN is unset (Stripe Checkout return URLs will fail)."
        )

    lob_status, lob_issues = _lob_status()
    webhook_status, webhook_issues = _stripe_webhook_status()

    worker_ok = _worker_enabled()

    def phase(pid: str, ok: bool, degraded_reasons: List[str], blocked_reasons: List[str]) -> Dict[str, Any]:
        if blocked_reasons:
            st: Status = "blocked"
            issues = blocked_reasons
        elif degraded_reasons:
            st = "degraded"
            issues = degraded_reasons
        elif ok:
            st = "ok"
            issues = []
        else:
            st = "degraded"
            issues = ["Not fully configured."]
        return {"id": pid, "status": st, "issues": issues}

    blocked_db = db_status == "blocked"
    degraded_db = db_status == "degraded"

    phases = [
        phase(
            "upload",
            ok=not blocked_db and database_initialized_ok,
            degraded_reasons=(db_issues if degraded_db else []),
            blocked_reasons=(db_issues if blocked_db else []),
        ),
        phase(
            "parse_analyze",
            ok=not blocked_db and database_initialized_ok and worker_ok,
            degraded_reasons=(
                ([] if worker_ok else ["WORKFLOW_JOB_WORKER_ENABLED=0: background parse jobs will not run."])
                + (db_issues if degraded_db else [])
            ),
            blocked_reasons=(db_issues if blocked_db else []),
        ),
        phase(
            "review_claims",
            ok=not blocked_db and database_initialized_ok,
            degraded_reasons=(db_issues if degraded_db else []),
            blocked_reasons=(db_issues if blocked_db else []),
        ),
        phase(
            "select_disputes",
            ok=not blocked_db and database_initialized_ok,
            degraded_reasons=(db_issues if degraded_db else []),
            blocked_reasons=(db_issues if blocked_db else []),
        ),
        phase(
            "payment",
            ok=not blocked_db and database_initialized_ok and payment_support,
            degraded_reasons=(
                ([] if payment_support else payment_issues)
                + ([] if webhook_status == "ok" else webhook_issues)
                + (db_issues if degraded_db else [])
            ),
            blocked_reasons=(db_issues if blocked_db else []),
        ),
        phase(
            "letter_generation",
            ok=not blocked_db and database_initialized_ok and stripe_status == "ok",
            degraded_reasons=(stripe_issues if stripe_status != "ok" else []) + (db_issues if degraded_db else []),
            blocked_reasons=(db_issues if blocked_db else []),
        ),
        phase(
            "proof_attachment",
            ok=not blocked_db and database_initialized_ok,
            degraded_reasons=(db_issues if degraded_db else []),
            blocked_reasons=(db_issues if blocked_db else []),
        ),
        phase(
            "mail",
            ok=not blocked_db and database_initialized_ok and lob_status == "ok",
            degraded_reasons=(lob_issues if lob_status != "ok" else []) + (db_issues if degraded_db else []),
            blocked_reasons=(db_issues if blocked_db else []),
        ),
        phase(
            "track",
            ok=not blocked_db and database_initialized_ok,
            degraded_reasons=(db_issues if degraded_db else []),
            blocked_reasons=(db_issues if blocked_db else []),
        ),
    ]

    integrations: Dict[str, Any] = {
        "database": {"status": db_status, "issues": db_issues},
        "jobWorker": {
            "status": "ok" if worker_ok else "degraded",
            "issues": [] if worker_ok else ["Worker disabled (parse/letter jobs need a worker process)."],
        },
        "resend": {"status": resend_status, "issues": resend_issues},
        "stripe": {"status": stripe_status, "issues": stripe_issues},
        "stripeWebhook": {"status": webhook_status, "issues": webhook_issues},
        "customerAppOrigin": {
            "status": "ok" if origin_ok else "degraded",
            "issues": [] if origin_ok else ["Set WORKFLOW_CUSTOMER_APP_ORIGIN or PUBLIC_APP_ORIGIN."],
        },
        "lob": {"status": lob_status, "issues": lob_issues},
    }

    all_ok = all(p["status"] == "ok" for p in phases)
    counts: Dict[str, int] = {"ok": 0, "degraded": 0, "blocked": 0}
    for p in phases:
        counts[p["status"]] += 1

    return {
        "integrations": integrations,
        "linearPhases": phases,
        "summary": {
            "allPhasesOperational": all_ok,
            "phaseCounts": counts,
        },
    }


def log_workflow_env_readiness_at_startup(logger: Any, *, database_initialized_ok: bool = True) -> None:
    """Emit INFO for healthy path; WARNING when any phase is not ok."""
    payload = compute_workflow_env_readiness(database_initialized_ok=database_initialized_ok)
    summary = payload["summary"]
    phases = payload["linearPhases"]
    if summary["allPhasesOperational"]:
        logger.info(
            "Workflow env readiness: all %s linear phases operational.",
            len(phases),
        )
        return
    bad = [f"{p['id']}={p['status']}" for p in phases if p["status"] != "ok"]
    logger.warning(
        "Workflow env readiness: not all phases operational (%s). "
        "GET /internal/admin/workflow-env-readiness (admin) or GET /health/workflow-readiness (summary).",
        "; ".join(bad),
    )
    for p in phases:
        if p["status"] == "ok":
            continue
        for issue in p.get("issues") or []:
            logger.warning("  [%s] %s", p["id"], issue)


def public_workflow_readiness_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal JSON safe for unauthenticated load balancers (no issue strings)."""
    s = payload.get("summary") or {}
    pc = s.get("phaseCounts") or {}
    return {
        "service": "workflow-api",
        "allPhasesOperational": bool(s.get("allPhasesOperational")),
        "phaseCounts": {
            "ok": int(pc.get("ok") or 0),
            "degraded": int(pc.get("degraded") or 0),
            "blocked": int(pc.get("blocked") or 0),
        },
    }
