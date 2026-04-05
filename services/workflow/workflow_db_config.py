"""
Select Postgres vs SQLite for workflow persistence.

Production standard: **one data path** — workflow tables live in the same Postgres as
everything else (``database.get_db`` / ``DATABASE_URL``). Use ``assert_postgres_only_in_production()``
at startup and on every ``get_workflow_db`` entry so production-like deploys cannot use
``DB_BACKEND=sqlite`` or omit ``DATABASE_URL``.

SQLite is **opt-in only** for local dev/tests (``DB_BACKEND=sqlite`` + ``WORKFLOW_SQLITE_PATH``).
"""

from __future__ import annotations

import os


def is_production_like() -> bool:
    return (
        os.environ.get("REPLIT_DEPLOYMENT") == "1"
        or (os.environ.get("ENVIRONMENT") or "").strip().lower() == "production"
    )


def assert_postgres_only_in_production() -> None:
    """
    Fail fast in production-like environments so there is no split-brain between
    Postgres (auth, org, reports) and file SQLite (workflow). Safe to call on every
    ``get_workflow_db`` entry (env reads only).
    """
    if not is_production_like():
        return
    backend = (os.environ.get("DB_BACKEND") or "auto").strip().lower()
    if backend == "sqlite":
        raise RuntimeError(
            "DB_BACKEND=sqlite is not allowed when REPLIT_DEPLOYMENT=1 or ENVIRONMENT=production. "
            "Unset DB_BACKEND (or use auto) so workflow uses the same Postgres as DATABASE_URL."
        )
    if not (os.environ.get("DATABASE_URL") or "").strip():
        raise RuntimeError(
            "DATABASE_URL is required when REPLIT_DEPLOYMENT=1 or ENVIRONMENT=production. "
            "SQLite workflow fallback is disabled in production; configure Postgres."
        )


def workflow_sqlite_path() -> str:
    raw = (os.environ.get("WORKFLOW_SQLITE_PATH") or "").strip()
    if raw:
        return raw
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "lab_truth", "dev_workflow.sqlite")


def should_use_workflow_sqlite() -> bool:
    """
    True → workflow modules use file SQLite (separate from ``DATABASE_URL``).

    Rules:
    - Never SQLite in production-like deployments.
    - DB_BACKEND=sqlite → True (explicit opt-in; dev/tests only).
    - DB_BACKEND=postgres or auto (default) → False: workflow uses Postgres via
      ``database.get_db`` (same pool as org tables, reports, auth).

    There is no silent "empty DATABASE_URL → workflow SQLite" path: without
    ``DATABASE_URL``, the app cannot use Postgres and will fail on first ``get_db``;
    use ``DB_BACKEND=sqlite`` only when intentionally running workflow/Mission Control
    against a local file without a real database.
    """
    if is_production_like():
        return False
    backend = (os.environ.get("DB_BACKEND") or "auto").strip().lower()
    if backend == "sqlite":
        return True
    return False
