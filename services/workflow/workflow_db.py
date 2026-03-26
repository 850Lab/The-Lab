"""
Workflow DB access: Postgres (database.get_db) or SQLite file (local dev).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, List, Optional, Sequence

from services.workflow import workflow_sqlite as wsq
from services.workflow.workflow_db_config import should_use_workflow_sqlite
from services.workflow.workflow_sql_adapt import adapt_sql


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


@contextmanager
def get_workflow_db(
    dict_cursor: bool = False,
) -> Generator[Tuple[Any, Any], None, None]:
    """
    Yields (conn, cur). Callers must commit/rollback like Postgres paths.
    SQLite uses a process-wide connection guarded by workflow_sqlite._lock.
    """
    if not should_use_workflow_sqlite():
        import database as db

        with db.get_db(dict_cursor=dict_cursor) as pair:
            yield pair
        return

    wsq.ensure_schema()
    with wsq.sqlite_write_lock:
        conn = wsq.get_connection()
        raw = conn.cursor()
        cur: Any = _SqliteCursor(raw)
        try:
            yield conn, cur
        finally:
            raw.close()
