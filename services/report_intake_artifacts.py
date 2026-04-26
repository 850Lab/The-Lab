"""
Durable on-disk staging for ``report_upload_parse`` jobs.

Multipart uploads are first streamed to process temp files, then **moved** under a
workflow-scoped directory before the HTTP handler returns. Background workers must not
depend on request-scoped tempfile paths that can vanish after the connection closes.
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from typing import List

_log = logging.getLogger(__name__)


def intake_artifact_root() -> str:
    raw = (os.environ.get("REPORT_INTAKE_ARTIFACT_DIR") or "").strip()
    if raw:
        return os.path.abspath(raw)
    return os.path.abspath(os.path.join(os.getcwd(), "lab_truth", "report_intake"))


def _safe_segment(value: str) -> str:
    s = (value or "").strip().replace(os.sep, "_").replace("/", "_")
    return s or "unknown"


def intake_dir_for_job(workflow_id: str, job_id: str) -> str:
    root = intake_artifact_root()
    return os.path.join(root, _safe_segment(workflow_id), _safe_segment(job_id))


def rmtree_intake_job(workflow_id: str, job_id: str) -> None:
    path = intake_dir_for_job(workflow_id, job_id)
    if os.path.isdir(path):
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            _log.debug("intake rmtree failed path=%s", path, exc_info=True)


def promote_temp_files_to_durable(workflow_id: str, job_id: str, temp_paths: List[str]) -> List[str]:
    """
    Atomically move each temp file into ``{root}/{workflow_id}/{job_id}/part_NNN.pdf``.

    Falls back to copy+unlink when ``os.replace`` crosses devices.
    """
    wf = (workflow_id or "").strip()
    jid = (job_id or "").strip()
    try:
        uuid.UUID(jid)
    except ValueError as e:
        raise ValueError("job_id must be a UUID string") from e

    dest_dir = intake_dir_for_job(wf, jid)
    os.makedirs(dest_dir, mode=0o700, exist_ok=False)

    out: List[str] = []
    try:
        for i, src in enumerate(temp_paths):
            s = (src or "").strip()
            if not s or not os.path.isfile(s):
                raise FileNotFoundError(f"staging temp missing before promote: {s!r}")
            dest = os.path.join(dest_dir, f"part_{i:03d}.pdf")
            try:
                os.replace(s, dest)
            except OSError:
                shutil.copy2(s, dest)
                try:
                    os.unlink(s)
                except OSError:
                    pass
            out.append(dest)
    except Exception:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise

    _log.info(
        "intake.upload_persisted workflow_id=%s job_id=%s parts=%s root=%s",
        _safe_segment(wf),
        jid,
        len(out),
        intake_artifact_root(),
    )
    return out
