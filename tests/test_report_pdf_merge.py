"""Merge split PDF parts (used for large bureau exports under per-request size caps)."""

from __future__ import annotations

from io import BytesIO

import fitz
import pytest
from reportlab.pdfgen import canvas

from services.report_pdf_merge import merge_pdf_parts


def _one_page_pdf(text: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_merge_pdf_parts_concatenates_pages():
    p1 = _one_page_pdf("first")
    p2 = _one_page_pdf("second")
    name, merged = merge_pdf_parts([("part_a.pdf", p1), ("part_b.pdf", p2)])
    assert name == "part_a_merged.pdf"
    doc = fitz.open(stream=merged, filetype="pdf")
    try:
        assert doc.page_count == 2
    finally:
        doc.close()


def test_merge_pdf_parts_rejects_empty():
    with pytest.raises(ValueError, match="No PDF parts"):
        merge_pdf_parts([])
