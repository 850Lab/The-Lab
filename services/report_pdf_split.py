"""
Split a large PDF into ordered sub-PDFs so each serialized chunk stays under a byte ceiling.

Used when a single bureau export exceeds the per-request chunk limit: chunks are merged
again immediately so downstream parsing still sees one logical report.
"""

from __future__ import annotations

from typing import List, Tuple

import fitz  # PyMuPDF

from services.report_pdf_merge import _safe_stem_from_filename


def _serialize_page_range(src: fitz.Document, start: int, end: int) -> bytes:
    chunk = fitz.open()
    try:
        chunk.insert_pdf(src, from_page=start, to_page=end)
        return chunk.tobytes(deflate=True, garbage=3, clean=True)
    finally:
        chunk.close()


def split_pdf_by_max_serialized_bytes(
    pdf_bytes: bytes,
    *,
    stem: str,
    chunk_max_bytes: int,
) -> List[Tuple[str, bytes]]:
    """
    Partition pages so each sub-document's serialized size is <= ``chunk_max_bytes``.

    Returns ordered (filename, pdf_bytes) chunks. Raises ``ValueError`` if a single page
    cannot fit under the ceiling.
    """
    if chunk_max_bytes < 256:
        raise ValueError("chunk_max_bytes too small.")
    if not pdf_bytes:
        raise ValueError("Empty PDF.")
    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        n = src.page_count
        if n < 1:
            raise ValueError("PDF has no pages.")
        safe_stem = _safe_stem_from_filename(stem) if stem else "report"
        out: List[Tuple[str, bytes]] = []
        start = 0
        while start < n:
            lo, hi = start, n - 1
            best_end = -1
            while lo <= hi:
                mid = (lo + hi + 1) // 2
                b = _serialize_page_range(src, start, mid)
                if len(b) <= chunk_max_bytes:
                    best_end = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            if best_end < start:
                one = _serialize_page_range(src, start, start)
                one_mb = max(0.01, round(len(one) / (1024 * 1024), 2))
                cap_mb = max(1, round(chunk_max_bytes / (1024 * 1024), 1))
                raise ValueError(
                    f"A single PDF page is about {one_mb} MB — larger than our {cap_mb} MB processing "
                    "chunk. Re-export a compressed PDF or contact support."
                )
            b = _serialize_page_range(src, start, best_end)
            out.append((f"{safe_stem}_p{start + 1}-{best_end + 1}.pdf", b))
            start = best_end + 1
        return out
    finally:
        src.close()
