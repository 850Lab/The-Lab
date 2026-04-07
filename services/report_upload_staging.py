"""
Shared report upload limits, validation, and PDF merge/normalize logic.

HTTP handlers **stage** uploads to temp files (durable write + fsync + size + SHA-256),
then enqueue a job. Split/merge runs in ``workflow_job_worker`` after integrity checks.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from typing import List, Tuple

from starlette.datastructures import UploadFile

from services.report_pdf_merge import merge_pdf_parts
from services.report_pdf_split import split_pdf_by_max_serialized_bytes

# Per-chunk ceiling: manual multi-part uploads, and auto-split page ranges.
MAX_REPORT_UPLOAD_MB = 25
MAX_REPORT_PARTS = 12

try:
    MAX_SINGLE_REPORT_UPLOAD_MB = int(
        (os.environ.get("MAX_SINGLE_REPORT_UPLOAD_MB") or "200").strip()
    )
except ValueError:
    MAX_SINGLE_REPORT_UPLOAD_MB = 200
MAX_SINGLE_REPORT_UPLOAD_MB = max(
    MAX_REPORT_UPLOAD_MB, min(MAX_SINGLE_REPORT_UPLOAD_MB, 500)
)

try:
    MAX_MERGED_REPORT_MB = int((os.environ.get("MAX_MERGED_REPORT_MB") or "250").strip())
except ValueError:
    MAX_MERGED_REPORT_MB = 250
MAX_MERGED_REPORT_MB = max(
    MAX_SINGLE_REPORT_UPLOAD_MB,
    min(MAX_MERGED_REPORT_MB, 500),
)

# Stream multipart parts to disk in chunks (reduces peak memory vs one giant ``read()``).
_STREAM_CHUNK_BYTES = 1024 * 1024


class ReportUploadStagingError(Exception):
    """Normalize/merge failed; safe to surface to clients or fail_job."""

    def __init__(self, code: str, message_safe: str, *, http_status: int = 400) -> None:
        self.code = code
        self.message_safe = message_safe
        self.http_status = http_status
        super().__init__(message_safe)


async def stream_upload_part_to_temp_file(
    uf: UploadFile,
    *,
    max_bytes: int,
    too_large_message: str,
    prefix: str = "wf_report_part_",
) -> tuple[str, int, str]:
    """
    Stream one ``UploadFile`` to a temp path: incremental SHA-256, ``fsync``, then verify
    on-disk size matches bytes written. Raises ``ReportUploadStagingError`` for oversize /
    empty / write mismatch (caller maps to HTTP).
    """
    fd, temp_path = tempfile.mkstemp(suffix=".pdf", prefix=prefix)
    total = 0
    h = hashlib.sha256()
    try:
        await uf.seek(0)
        with os.fdopen(fd, "wb") as out:
            while True:
                block = await uf.read(_STREAM_CHUNK_BYTES)
                if not block:
                    break
                total += len(block)
                if total > max_bytes:
                    raise ReportUploadStagingError(
                        "FILE_TOO_LARGE",
                        too_large_message,
                        http_status=413,
                    )
                h.update(block)
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
    except ReportUploadStagingError:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise

    if total == 0:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise ReportUploadStagingError("EMPTY_FILE", "Empty file.")

    disk = os.path.getsize(temp_path)
    if disk != total:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise ReportUploadStagingError(
            "STAGING_WRITE_FAILED",
            "Could not persist uploaded file (size mismatch).",
            http_status=500,
        )
    return temp_path, total, h.hexdigest()


def normalize_one_large_pdf_to_pipeline_bytes(fname: str, raw: bytes) -> tuple[str, bytes]:
    """
    If ``raw`` is under the chunk ceiling, return as-is. Otherwise split by page ranges
    under the chunk ceiling, merge into one PDF, and return that (same bureau, one report).
    """
    chunk_max = MAX_REPORT_UPLOAD_MB * 1024 * 1024
    max_single = MAX_SINGLE_REPORT_UPLOAD_MB * 1024 * 1024
    max_merged = MAX_MERGED_REPORT_MB * 1024 * 1024

    if len(raw) > max_single:
        raise ReportUploadStagingError(
            "FILE_TOO_LARGE",
            f"Maximum upload size is {MAX_SINGLE_REPORT_UPLOAD_MB} MB.",
            http_status=413,
        )
    if len(raw) <= chunk_max:
        if len(raw) > max_merged:
            raise ReportUploadStagingError(
                "MERGED_TOO_LARGE",
                f"PDF exceeds {MAX_MERGED_REPORT_MB} MB.",
                http_status=413,
            )
        return fname, raw

    stem = fname.rsplit(".", 1)[0] if fname.lower().endswith(".pdf") else fname
    try:
        chunks = split_pdf_by_max_serialized_bytes(
            raw,
            stem=stem,
            chunk_max_bytes=chunk_max,
        )
    except ValueError as e:
        raise ReportUploadStagingError(
            "PDF_SPLIT_FAILED",
            (str(e) or "Could not split PDF into processable chunks.")[:280],
        ) from e

    try:
        merged_name, merged = merge_pdf_parts(chunks)
    except ValueError as e:
        raise ReportUploadStagingError(
            "PDF_MERGE_FAILED",
            (str(e) or "Could not merge PDF after splitting.")[:240],
        ) from e

    if len(merged) > max_merged:
        raise ReportUploadStagingError(
            "MERGED_TOO_LARGE",
            f"Merged PDF exceeds {MAX_MERGED_REPORT_MB} MB after processing.",
            http_status=413,
        )
    return merged_name, merged


def merge_and_normalize_report_parts(parts: List[tuple[str, bytes]]) -> tuple[str, bytes]:
    """
    Same behavior as the former ``_load_and_maybe_merge_report_pdfs`` merge phase:
    one part → normalize/split; multiple parts → merge in order then size-check.
    """
    if len(parts) == 1:
        return normalize_one_large_pdf_to_pipeline_bytes(parts[0][0], parts[0][1])

    try:
        merged_name, merged = merge_pdf_parts(parts)
    except ValueError as e:
        raise ReportUploadStagingError(
            "PDF_MERGE_FAILED",
            (str(e) or "Could not merge PDF parts.")[:240],
        ) from e

    max_merged = MAX_MERGED_REPORT_MB * 1024 * 1024
    if len(merged) > max_merged:
        raise ReportUploadStagingError(
            "MERGED_TOO_LARGE",
            f"Merged PDF exceeds {MAX_MERGED_REPORT_MB} MB. Use fewer or smaller parts.",
            http_status=413,
        )
    return merged_name, merged
