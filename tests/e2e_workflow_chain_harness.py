"""
Seeded harness for retail workflow HTTP E2E: Postgres + real parse pipeline + workflow jobs.

Requires ``DATABASE_URL`` and the same PDF tooling as production (Poppler/Tesseract as applicable).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

import auth
import database as db
from services.workflow.engine import WorkflowEngine
from services.workflow.workflow_job_service import (
    JOB_TYPE_REPORT_UPLOAD_PARSE,
    STATUS_COMPLETED,
    STATUS_PENDING,
    claim_job_by_id,
    get_job,
    public_job_view,
)
from services.workflow.workflow_job_worker import _dispatch


REPO_ROOT = Path(__file__).resolve().parent.parent

# Same triple as public demo fixtures — one merged upload (multi-part) for multi-bureau coverage.
DEFAULT_FIXTURE_RELPATHS: Tuple[str, ...] = (
    "samples/transunion_acr_fixture_sample.pdf",
    "samples/experian_fixture_sample.pdf",
    "samples/equifax_fixture_sample.pdf",
)


@dataclass
class E2eRetailChainContext:
    user_id: int
    session_token: str
    workflow_id: str
    email: str


def postgres_e2e_available() -> bool:
    return bool((os.environ.get("DATABASE_URL") or "").strip())


def load_triple_pdf_fixtures(
    rels: Tuple[str, ...] = DEFAULT_FIXTURE_RELPATHS,
) -> List[Tuple[str, bytes]]:
    out: List[Tuple[str, bytes]] = []
    for rel in rels:
        p = REPO_ROOT / rel
        if not p.is_file():
            raise FileNotFoundError(f"E2E fixture missing: {rel}")
        out.append((p.name, p.read_bytes()))
    return out


def bootstrap_retail_consumer_chain() -> E2eRetailChainContext:
    """
    Create a fresh consumer user, session token, and new dispute_linear workflow (Postgres-backed).
    """
    if not postgres_e2e_available():
        raise RuntimeError("DATABASE_URL is required for retail chain E2E")

    db.init_database()
    auth.init_auth_tables()

    suffix = uuid.uuid4().hex[:12]
    email = f"e2e_chain_{suffix}@internal.invalid"
    user = auth.create_user(email, "E2E_Test_Password_A1!", display_name="E2E Chain", role="consumer")
    if user.get("error"):
        raise RuntimeError(str(user.get("error")))
    uid = int(user["id"])
    auth.add_entitlements(uid, letters=12, source="e2e_chain_harness")

    token = auth.create_session(uid)

    eng = WorkflowEngine()
    init_out = eng.init_workflow(user_id=uid, metadata={"e2e_chain": True})
    ws = init_out.get("workflowState") or {}
    wid = (ws.get("workflowId") or "").strip()
    if not wid:
        raise RuntimeError("init_workflow did not return workflowId")

    return E2eRetailChainContext(user_id=uid, session_token=token, workflow_id=wid, email=email)


def run_report_upload_parse_job(job_id: str) -> Dict[str, Any]:
    """
    Return the public job view after parse.

    If the HTTP layer already ran ``WORKFLOW_E2E_SYNCHRONOUS_PARSE`` dispatch, the row is
    ``completed`` and we return it. Otherwise claim + ``_dispatch`` once (real worker path).
    """
    pre = get_job(job_id)
    if not pre:
        raise RuntimeError(f"No workflow_jobs row for id={job_id!r}")
    st = str(pre.get("status") or "")
    if st == STATUS_COMPLETED:
        return public_job_view(pre)
    if st == STATUS_FAILED:
        raise RuntimeError(
            f"Parse job {job_id!r} failed before harness could run: "
            f"error={pre.get('error')!r} result={pre.get('result')!r}"
        )
    if st != STATUS_PENDING:
        raise RuntimeError(
            f"Job {job_id!r} unexpected status={pre.get('status')!r} (keys={list(pre.keys())})"
        )
    job = claim_job_by_id(job_id)
    if not job:
        raise RuntimeError(
            f"claim_job_by_id failed after get_job showed pending for {job_id!r} "
            f"(possible DB_BACKEND/workflow store mismatch or concurrent claim)"
        )
    if str(job.get("job_type") or "") != JOB_TYPE_REPORT_UPLOAD_PARSE:
        raise RuntimeError(f"Unexpected job_type on {job_id}: {job.get('job_type')}")
    _dispatch(job)
    row = get_job(job_id)
    if not row:
        raise RuntimeError("Job row missing after dispatch")
    return public_job_view(row)


def cleanup_e2e_user_reports(user_id: int) -> None:
    try:
        db.delete_user_reports(user_id)
    except Exception:
        pass
