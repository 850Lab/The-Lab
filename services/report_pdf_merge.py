"""
Merge multiple PDF byte blobs into one PDF for the upload → parse pipeline.

Used for user-provided parts and for server-side page splits of a large bureau PDF.
"""

from __future__ import annotations

import re
from typing import List, Tuple

import fitz  # PyMuPDF


def _safe_stem_from_filename(name: str) -> str:
    base = (name or "report").replace("\\", "/").split("/")[-1]
    stem = base.rsplit(".", 1)[0].strip() or "report"
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", stem).strip("._") or "report"
    return stem[:80]


def merge_pdf_parts(parts: List[Tuple[str, bytes]]) -> Tuple[str, bytes]:
    """
    Concatenate PDFs in order. Each part must be a valid PDF with at least one page.

    Returns (merged_filename, merged_pdf_bytes).
    """
    if not parts:
        raise ValueError("No PDF parts to merge.")
    merged = fitz.open()
    try:
        for filename, data in parts:
            if not data:
                raise ValueError(f"Empty PDF part: {filename!r}")
            with fitz.open(stream=data, filetype="pdf") as src:
                if src.page_count < 1:
                    raise ValueError(f"No pages in PDF part: {filename!r}")
                merged.insert_pdf(src)
        pdf_bytes = merged.tobytes(deflate=True, garbage=3, clean=True)
    finally:
        merged.close()
    stem = _safe_stem_from_filename(parts[0][0])
    return f"{stem}_merged.pdf", pdf_bytes
