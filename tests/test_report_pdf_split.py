"""Page-based PDF splitting under a serialized-size ceiling."""

from __future__ import annotations

from io import BytesIO

import fitz
import pytest
from reportlab.pdfgen import canvas

from services.report_pdf_merge import merge_pdf_parts
from services.report_pdf_split import split_pdf_by_max_serialized_bytes


def _n_page_pdf(n: int) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    for i in range(n):
        c.drawString(72, 720, f"Page {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def test_split_produces_chunks_under_ceiling():
    raw = _n_page_pdf(5)
    chunks = split_pdf_by_max_serialized_bytes(
        raw,
        stem="eq",
        chunk_max_bytes=1200,
    )
    assert len(chunks) >= 2
    for _name, blob in chunks:
        assert len(blob) <= 8000
    merged_name, merged = merge_pdf_parts(chunks)
    assert merged_name.endswith("_merged.pdf")
    doc = fitz.open(stream=merged, filetype="pdf")
    try:
        assert doc.page_count == 5
    finally:
        doc.close()


def test_split_single_huge_page_errors():
    raw = _n_page_pdf(1)
    with pytest.raises(ValueError, match="single PDF page"):
        split_pdf_by_max_serialized_bytes(
            raw,
            stem="x",
            chunk_max_bytes=500,
        )
