"""
Persistence for workflow_execution_runs (Postgres or SQLite via workflow DB).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

RUNTIME_SCHEMA_VERSION = "execution_runtime.v1"

_ADMIN_RUNS_LIMIT_CAP = 500


def list_execution_runs_for_admin(
    *,
    workflow_id: Optional[str] = None,
    run_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Operator listing: recent execution runs with parsed JSON columns.
    ``since`` / ``until`` filter on ``updated_at`` (ISO-friendly string comparison on SQLite).
    """
    from services.workflow.workflow_db import get_workflow_db

    lim = max(1, min(int(limit), _ADMIN_RUNS_LIMIT_CAP))
    parts = ["1=1"]
    params: list = []
    if workflow_id is not None and str(workflow_id).strip():
        parts.append("workflow_id = %s")
        params.append(str(workflow_id).strip())
    if run_id is not None and str(run_id).strip():
        parts.append("run_id = %s")
        params.append(str(run_id).strip())
    if since is not None and str(since).strip():
        parts.append("updated_at >= %s")
        params.append(str(since).strip())
    if until is not None and str(until).strip():
        parts.append("updated_at <= %s")
        params.append(str(until).strip())
    params.append(lim)
    where = " AND ".join(parts)
    sql = f"""
        SELECT run_id, workflow_id, user_id, guidance_bundle_json, progress_state_json,
               runtime_schema_version, created_at, updated_at
        FROM workflow_execution_runs
        WHERE {where}
        ORDER BY updated_at DESC
        LIMIT %s
    """
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    out = []
    for row in rows:
        d = dict(row)
        for k in ("guidance_bundle_json", "progress_state_json"):
            v = d.get(k)
            if isinstance(v, str):
                try:
                    d[k] = json.loads(v)
                except Exception:
                    d[k] = {}
            elif v is None:
                d[k] = {}
        out.append(d)
    return out


def insert_execution_run(
    run_id: str,
    workflow_id: str,
    user_id: int,
    bundle_dict: Dict[str, Any],
    state_dict: Dict[str, Any],
) -> None:
    from services.workflow.workflow_db import get_workflow_db

    bj = json.dumps(bundle_dict)
    sj = json.dumps(state_dict)
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO workflow_execution_runs (
                run_id, workflow_id, user_id,
                guidance_bundle_json, progress_state_json, runtime_schema_version
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (run_id, workflow_id, user_id, bj, sj, RUNTIME_SCHEMA_VERSION),
        )
        conn.commit()


def update_execution_progress(run_id: str, state_dict: Dict[str, Any]) -> int:
    from services.workflow.workflow_db import get_workflow_db

    sj = json.dumps(state_dict)
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            UPDATE workflow_execution_runs
            SET progress_state_json = %s, updated_at = CURRENT_TIMESTAMP
            WHERE run_id = %s
            """,
            (sj, run_id),
        )
        n = cur.rowcount
        conn.commit()
    return int(n)


def fetch_execution_run_by_id(run_id: str) -> Optional[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT run_id, workflow_id, user_id, guidance_bundle_json, progress_state_json,
                   runtime_schema_version, created_at, updated_at
            FROM workflow_execution_runs
            WHERE run_id = %s
            """,
            (run_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    for k in ("guidance_bundle_json", "progress_state_json"):
        v = d.get(k)
        if isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except Exception:
                d[k] = {}
        elif v is None:
            d[k] = {}
    return d


def fetch_latest_execution_run_for_workflow(
    workflow_id: str,
    user_id: int,
) -> Optional[Dict[str, Any]]:
    from services.workflow.workflow_db import get_workflow_db

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT run_id, workflow_id, user_id, guidance_bundle_json, progress_state_json,
                   runtime_schema_version, created_at, updated_at
            FROM workflow_execution_runs
            WHERE workflow_id = %s AND user_id = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (workflow_id, user_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    for k in ("guidance_bundle_json", "progress_state_json"):
        v = d.get(k)
        if isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except Exception:
                d[k] = {}
        elif v is None:
            d[k] = {}
    return d
