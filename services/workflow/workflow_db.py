"""
Workflow DB access: Postgres (``database.get_db``, same as org/reports) by default;
SQLite file only when ``DB_BACKEND=sqlite`` (explicit).
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Generator, List, Optional, Sequence

from services.workflow import workflow_sqlite as wsq
from services.workflow.workflow_db_config import (
    assert_postgres_only_in_production,
    is_production_like,
    should_use_workflow_sqlite,
    workflow_sqlite_path,
)
from services.workflow.workflow_sql_adapt import adapt_sql

_log = logging.getLogger(__name__)
_split_db_warning_emitted = False


class _SqliteCursor:
    """sqlite3.Cursor wrapper: adapt SQL + expose fetch* like psycopg2."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def execute(self, operation: str, parameters: Optional[Sequence[Any]] = None) -> Any:
        if parameters is None:
            parameters = ()
        op2, p2 = adapt_sql(operation, parameters)
        return self._raw.execute(op2, p2)

    def executemany(self, operation: str, seq_of_parameters: List[Tuple[Any, ...]]) -> Any:
        return self._raw.executemany(operation, seq_of_parameters)

    def fetchone(self) -> Any:
        return self._raw.fetchone()

    def fetchall(self) -> Any:
        return self._raw.fetchall()

    @property
    def rowcount(self) -> int:
        return int(self._raw.rowcount or 0)


@contextmanager
def get_workflow_db(
    dict_cursor: bool = False,
) -> Generator[Tuple[Any, Any], None, None]:
    """
    Yields (conn, cur). Callers must commit/rollback like Postgres paths.
    SQLite uses a process-wide connection guarded by workflow_sqlite._lock.
    """
    assert_postgres_only_in_production()
    if not should_use_workflow_sqlite():
        import database as db

        with db.get_db(dict_cursor=dict_cursor) as pair:
            yield pair
        return

    if is_production_like():
        raise RuntimeError(
            "SQLite workflow persistence must not run in production-like environment "
            "(check DB_BACKEND and assert_postgres_only_in_production)."
        )

    global _split_db_warning_emitted
    if not _split_db_warning_emitted:
        _split_db_warning_emitted = True
        dsn = ( __import__("os").environ.get("DATABASE_URL") or "").strip()
        if dsn:
            _log.warning(
                "Workflow persistence uses SQLite at %s while DATABASE_URL is set: "
                "workflow/Mission Control data is NOT in Postgres. "
                "Unset DB_BACKEND or use DB_BACKEND=postgres for a single database.",
                workflow_sqlite_path(),
            )
        else:
            _log.info(
                "Workflow persistence uses SQLite at %s (DB_BACKEND=sqlite); "
                "set DATABASE_URL and omit DB_BACKEND for Postgres-only mode.",
                workflow_sqlite_path(),
            )

    wsq.ensure_schema()
    with wsq.sqlite_write_lock:
        conn = wsq.get_connection()
        raw = conn.cursor()
        cur: Any = _SqliteCursor(raw)
        try:
            yield conn, cur
        finally:
            raw.close()
