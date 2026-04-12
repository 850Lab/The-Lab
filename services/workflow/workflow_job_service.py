"""
Workflow background jobs: queue, claim, complete/fail/retry.

All job row writes go through this module. Emits ``job.*`` events via
``workflow_event_service`` (standalone transactions for worker path; same txn on create).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from services.workflow.workflow_db import get_workflow_db
from services.workflow.workflow_db_config import should_use_workflow_sqlite
from services.workflow.workflow_event_service import record_event_tx

_log = logging.getLogger(__name__)

JOB_TYPE_LETTER_GENERATION = "letter_generation"
JOB_TYPE_REPORT_UPLOAD_PARSE = "report_upload_parse"

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def _dump_json(d: Any) -> str:
    return json.dumps(d if isinstance(d, dict) else {})


def _load_json(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    return val


def _as_map(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    return {k: row[k] for k in row.keys()}


def _emit_job_event(
    conn: Any,
    cur: Any,
    workflow_id: str,
    event_type: str,
    job_id: str,
    job_type: str,
    *,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> None:
    meta: Dict[str, Any] = {"jobId": job_id, "jobType": job_type}
    if extra_meta:
        meta.update(extra_meta)
    record_event_tx(
        conn,
        cur,
        workflow_id,
        event_type,
        actor="system",
        source="workflow_job_worker",
        metadata=meta,
    )


def create_job(
    workflow_id: str,
    job_type: str,
    payload: Dict[str, Any],
    *,
    max_attempts: int = 3,
    run_at: Optional[datetime] = None,
    dedupe_pending: bool = True,
) -> str:
    """
    Insert a pending job and emit ``job.created``. Returns job id.

    If ``dedupe_pending`` and a pending job of the same type exists for this workflow,
    returns that job id (no duplicate row).
    """
    wf = (workflow_id or "").strip()
    jt = (job_type or "").strip()[:64]
    if not wf or not jt:
        raise ValueError("workflow_id and job_type required")
    max_a = max(1, min(10, int(max_attempts)))

    with get_workflow_db(dict_cursor=True) as (conn, cur):
        if dedupe_pending:
            cur.execute(
                """
                SELECT id FROM workflow_jobs
                WHERE workflow_id = %s AND job_type = %s AND status = %s
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (wf, jt, STATUS_PENDING),
            )
            ex = cur.fetchone()
            if ex:
                jid = str(_as_map(ex)["id"])
                conn.commit()
                return jid

        jid = str(uuid.uuid4())
        run_param: Any = None
        if isinstance(run_at, datetime):
            run_param = run_at.isoformat() if should_use_workflow_sqlite() else run_at
        cur.execute(
            """
            INSERT INTO workflow_jobs (
                id, workflow_id, job_type, status, attempt_count, max_attempts,
                payload, result, error, run_at
            )
            VALUES (%s, %s, %s, %s, 0, %s, %s::jsonb, NULL, NULL, %s)
            """,
            (
                jid,
                wf,
                jt,
                STATUS_PENDING,
                max_a,
                _dump_json(payload),
                run_param,
            ),
        )
        _emit_job_event(conn, cur, wf, "job.created", jid, jt)
        conn.commit()
    return jid


def claim_job() -> Optional[Dict[str, Any]]:
    """
    Atomically claim the next eligible pending job (``pending``, ``attempt_count < max_attempts``,
    ``run_at`` elapsed). Sets ``running`` and increments ``attempt_count``. Emits ``job.started``
    in the same transaction.
    """
    if should_use_workflow_sqlite():
        return _claim_job_sqlite()
    return _claim_job_postgres()


def claim_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Atomically claim one pending job by id (same row shape as ``claim_job``).

    Use when a caller already knows the job id (e.g. HTTP returned ``jobId``) and must not
    risk dequeuing an unrelated pending row.
    """
    jid = (job_id or "").strip()
    if not jid:
        return None
    if should_use_workflow_sqlite():
        return _claim_job_by_id_sqlite(jid)
    return _claim_job_by_id_postgres(jid)


def _claim_job_postgres() -> Optional[Dict[str, Any]]:
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            WITH c AS (
                SELECT id FROM workflow_jobs
                WHERE status = %s
                  AND attempt_count < max_attempts
                  AND (run_at IS NULL OR run_at <= CURRENT_TIMESTAMP)
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE workflow_jobs j
            SET status = %s,
                attempt_count = j.attempt_count + 1,
                updated_at = CURRENT_TIMESTAMP
            FROM c
            WHERE j.id = c.id
            RETURNING j.id, j.workflow_id, j.job_type, j.status, j.attempt_count, j.max_attempts,
                      j.payload, j.result, j.error, j.created_at, j.updated_at, j.run_at
            """,
            (STATUS_PENDING, STATUS_RUNNING),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return None
        d = dict(row)
        jid = str(d["id"])
        wf = str(d["workflow_id"])
        jt = str(d["job_type"])
        d["payload"] = _load_json(d.get("payload"))
        d["result"] = _load_json(d.get("result"))
        _emit_job_event(conn, cur, wf, "job.started", jid, jt, extra_meta={"attempt": d["attempt_count"]})
        conn.commit()
        return d


def _claim_job_sqlite() -> Optional[Dict[str, Any]]:
    """Single-process worker: SELECT candidate then conditional UPDATE (no SKIP LOCKED)."""
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, workflow_id, job_type, attempt_count, max_attempts, payload, result, error,
                   created_at, updated_at, run_at
            FROM workflow_jobs
            WHERE status = %s
              AND attempt_count < max_attempts
              AND (run_at IS NULL OR run_at <= CURRENT_TIMESTAMP)
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (STATUS_PENDING,),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return None
        r = _as_map(row)
        jid = str(r["id"])
        wf = str(r["workflow_id"])
        jt = str(r["job_type"])
        n_attempt = int(r["attempt_count"]) + 1
        cur.execute(
            """
            UPDATE workflow_jobs
            SET status = %s, attempt_count = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = %s
            """,
            (STATUS_RUNNING, n_attempt, jid, STATUS_PENDING),
        )
        rc = getattr(cur, "rowcount", 1)
        if rc != 1:
            conn.rollback()
            return None
        _emit_job_event(conn, cur, wf, "job.started", jid, jt, extra_meta={"attempt": n_attempt})
        cur.execute(
            """
            SELECT id, workflow_id, job_type, status, attempt_count, max_attempts, payload, result, error,
                   created_at, updated_at, run_at
            FROM workflow_jobs WHERE id = %s
            """,
            (jid,),
        )
        out = cur.fetchone()
        conn.commit()
        if not out:
            return None
        d = _as_map(out)
        d["payload"] = _load_json(d.get("payload"))
        d["result"] = _load_json(d.get("result"))
        return d


def _claim_job_by_id_postgres(job_id: str) -> Optional[Dict[str, Any]]:
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            UPDATE workflow_jobs j
            SET status = %s,
                attempt_count = j.attempt_count + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE j.id = %s
              AND j.status = %s
              AND j.attempt_count < j.max_attempts
              AND (j.run_at IS NULL OR j.run_at <= CURRENT_TIMESTAMP)
            RETURNING j.id, j.workflow_id, j.job_type, j.status, j.attempt_count, j.max_attempts,
                      j.payload, j.result, j.error, j.created_at, j.updated_at, j.run_at
            """,
            (STATUS_RUNNING, job_id, STATUS_PENDING),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return None
        d = dict(row)
        jid = str(d["id"])
        wf = str(d["workflow_id"])
        jt = str(d["job_type"])
        d["payload"] = _load_json(d.get("payload"))
        d["result"] = _load_json(d.get("result"))
        _emit_job_event(
            conn, cur, wf, "job.started", jid, jt, extra_meta={"attempt": d["attempt_count"]}
        )
        conn.commit()
        return d


def _claim_job_by_id_sqlite(job_id: str) -> Optional[Dict[str, Any]]:
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, workflow_id, job_type, attempt_count, max_attempts, payload, result, error,
                   created_at, updated_at, run_at
            FROM workflow_jobs
            WHERE id = %s
              AND status = %s
              AND attempt_count < max_attempts
              AND (run_at IS NULL OR run_at <= CURRENT_TIMESTAMP)
            """,
            (job_id, STATUS_PENDING),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return None
        r = _as_map(row)
        jid = str(r["id"])
        wf = str(r["workflow_id"])
        jt = str(r["job_type"])
        n_attempt = int(r["attempt_count"]) + 1
        cur.execute(
            """
            UPDATE workflow_jobs
            SET status = %s, attempt_count = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = %s
            """,
            (STATUS_RUNNING, n_attempt, jid, STATUS_PENDING),
        )
        if cur.rowcount != 1:
            conn.rollback()
            return None
        _emit_job_event(conn, cur, wf, "job.started", jid, jt, extra_meta={"attempt": n_attempt})
        cur.execute(
            """
            SELECT id, workflow_id, job_type, status, attempt_count, max_attempts, payload, result, error,
                   created_at, updated_at, run_at
            FROM workflow_jobs WHERE id = %s
            """,
            (jid,),
        )
        out = cur.fetchone()
        conn.commit()
        if not out:
            return None
        d = _as_map(out)
        d["payload"] = _load_json(d.get("payload"))
        d["result"] = _load_json(d.get("result"))
        return d


def complete_job(job_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
    """Set ``completed``, store ``result``, emit ``job.completed``."""
    jid = (job_id or "").strip()
    if not jid:
        return False
    res = result if isinstance(result, dict) else {}
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            "SELECT workflow_id, job_type FROM workflow_jobs WHERE id = %s AND status = %s",
            (jid, STATUS_RUNNING),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return False
        rm = _as_map(row)
        wf = str(rm["workflow_id"])
        jt = str(rm["job_type"])
        cur.execute(
            """
            UPDATE workflow_jobs
            SET status = %s, result = %s::jsonb, error = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = %s
            """,
            (STATUS_COMPLETED, _dump_json(res), jid, STATUS_RUNNING),
        )
        if cur.rowcount != 1:
            conn.rollback()
            return False
        _emit_job_event(conn, cur, wf, "job.completed", jid, jt, extra_meta={"summaryKeys": list(res.keys())[:20]})
        conn.commit()
    return True


def fail_job(
    job_id: str,
    error_message: str,
    *,
    error_code: str = "JOB_FAILED",
) -> bool:
    """Set ``failed``, store error text + structured ``result`` (``ok``, ``errorCode``), emit ``job.failed``."""
    jid = (job_id or "").strip()
    msg = (error_message or "unknown error").strip()[:8000]
    code = (error_code or "JOB_FAILED").strip()[:128] or "JOB_FAILED"
    if not jid:
        return False
    result_body = _dump_json(
        {"ok": False, "errorCode": code, "messageSafe": msg[:2000]},
    )
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            "SELECT workflow_id, job_type, attempt_count, max_attempts FROM workflow_jobs WHERE id = %s AND status = %s",
            (jid, STATUS_RUNNING),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return False
        rm = _as_map(row)
        wf = str(rm["workflow_id"])
        jt = str(rm["job_type"])
        att = int(rm["attempt_count"])
        mx = int(rm["max_attempts"])
        cur.execute(
            """
            UPDATE workflow_jobs
            SET status = %s, error = %s, result = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = %s
            """,
            (STATUS_FAILED, msg, result_body, jid, STATUS_RUNNING),
        )
        if cur.rowcount != 1:
            conn.rollback()
            return False
        _emit_job_event(
            conn,
            cur,
            wf,
            "job.failed",
            jid,
            jt,
            extra_meta={
                "attempt": att,
                "maxAttempts": mx,
                "messageSafe": msg[:500],
                "errorCode": code,
            },
        )
        conn.commit()
    return True


def retry_job(job_id: str) -> bool:
    """Re-queue a ``failed`` job if ``attempt_count < max_attempts``."""
    jid = (job_id or "").strip()
    if not jid:
        return False
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            UPDATE workflow_jobs
            SET status = %s, error = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = %s AND attempt_count < max_attempts
            """,
            (STATUS_PENDING, jid, STATUS_FAILED),
        )
        ok = cur.rowcount == 1
        if ok:
            cur.execute(
                "SELECT workflow_id, job_type FROM workflow_jobs WHERE id = %s",
                (jid,),
            )
            r2 = cur.fetchone()
            if r2:
                r2m = _as_map(r2)
                wf = str(r2m["workflow_id"])
                jt = str(r2m["job_type"])
                record_event_tx(
                    conn,
                    cur,
                    wf,
                    "job.retry_queued",
                    actor="system",
                    source="workflow_job_service",
                    metadata={"jobId": jid, "jobType": jt},
                )
        conn.commit()
    return ok


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    jid = (job_id or "").strip()
    if not jid:
        return None
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, workflow_id, job_type, status, attempt_count, max_attempts, payload, result, error,
                   created_at, updated_at, run_at
            FROM workflow_jobs WHERE id = %s
            """,
            (jid,),
        )
        row = cur.fetchone()
    if not row:
        return None
    d = _as_map(row)
    d["payload"] = _load_json(d.get("payload"))
    d["result"] = _load_json(d.get("result"))
    return d


def list_jobs(workflow_id: str, *, limit: int = 50) -> List[Dict[str, Any]]:
    wf = (workflow_id or "").strip()
    cap = max(1, min(100, int(limit)))
    with get_workflow_db(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, workflow_id, job_type, status, attempt_count, max_attempts, payload, result, error,
                   created_at, updated_at, run_at
            FROM workflow_jobs
            WHERE workflow_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (wf, cap),
        )
        rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = _as_map(row)
        d["payload"] = _load_json(d.get("payload"))
        d["result"] = _load_json(d.get("result"))
        out.append(d)
    return out


def public_job_view(d: Dict[str, Any]) -> Dict[str, Any]:
    """Strip job row for HTTP (timestamps ISO)."""
    def ts(v: Any) -> Any:
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v

    payload = d.get("payload") if isinstance(d.get("payload"), dict) else {}
    jt = str(d.get("job_type") or "")
    if jt == JOB_TYPE_REPORT_UPLOAD_PARSE:
        payload = {k: v for k, v in payload.items() if k != "tempPdfPath"}

    res_raw = d.get("result")
    res_dict = res_raw if isinstance(res_raw, dict) else {}
    error_code = res_dict.get("errorCode") if isinstance(res_dict, dict) else None

    return {
        "jobId": str(d.get("id", "")),
        "workflowId": str(d.get("workflow_id", "")),
        "jobType": d.get("job_type"),
        "status": d.get("status"),
        "attemptCount": d.get("attempt_count"),
        "maxAttempts": d.get("max_attempts"),
        "payload": payload,
        "result": d.get("result") if isinstance(d.get("result"), dict) else None,
        "error": d.get("error"),
        "errorCode": error_code,
        "createdAt": ts(d.get("created_at")),
        "updatedAt": ts(d.get("updated_at")),
        "runAt": ts(d.get("run_at")),
    }
