"""
Select Postgres vs SQLite for workflow persistence (local dev only).

Postgres remains default whenever DATABASE_URL is set and DB_BACKEND is not sqlite.
Production-like environments never use SQLite.
"""

from __future__ import annotations

import os


def is_production_like() -> bool:
    return (
        os.environ.get("REPLIT_DEPLOYMENT") == "1"
        or (os.environ.get("ENVIRONMENT") or "").strip().lower() == "production"
    )


def workflow_sqlite_path() -> str:
    raw = (os.environ.get("WORKFLOW_SQLITE_PATH") or "").strip()
    if raw:
        return raw
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "lab_truth", "dev_workflow.sqlite")


def should_use_workflow_sqlite() -> bool:
    """
    True → workflow modules use file SQLite (no DATABASE_URL pool).

    Rules:
    - Never SQLite in production-like deployments.
    - DB_BACKEND=postgres → False (Postgres required).
    - DB_BACKEND=sqlite → True (dev only; blocked if production-like).
    - DB_BACKEND=auto (default): SQLite only when DATABASE_URL is unset/empty.
    """
    if is_production_like():
        return False
    backend = (os.environ.get("DB_BACKEND") or "auto").strip().lower()
    if backend == "postgres":
        return False
    if backend == "sqlite":
        return True
    # auto
    url = (os.environ.get("DATABASE_URL") or "").strip()
    return not url
