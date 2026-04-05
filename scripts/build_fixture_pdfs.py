"""
Build uploadable PDFs from tests/fixtures/*.txt and ``tests/golden/experian_golden.txt`` for local / QA.

The workflow API only accepts .pdf; pdfplumber extracts text the same way as bureau
downloads when each logical page is one PDF page (no duplicate --- Page N --- in body:
extract_text_from_pdf prepends that per page).

Run from repo root:
  python scripts/build_fixture_pdfs.py
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as pdf_canvas

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "samples"

# (path relative to repo, output_pdf_name)
FIXTURE_MAP = (
    ("tests/fixtures/plain_text_equifax.txt", "equifax_fixture_sample.pdf"),
    ("tests/fixtures/plain_text_tu_osc.txt", "transunion_osc_fixture_sample.pdf"),
    ("tests/fixtures/plain_text_tu_acr.txt", "transunion_acr_fixture_sample.pdf"),
    ("tests/golden/experian_golden.txt", "experian_fixture_sample.pdf"),
)


def _ascii_safe_line(s: str) -> str:
    """Courier + pdfgen drawString are WinAnsi-oriented; drop/replace non-Latin-1 glyphs."""
    return s.encode("ascii", errors="replace").decode("ascii")


def _split_fixture_pages(raw: str) -> list[str]:
    chunks = re.split(r"^--- Page \d+ ---\s*\n?", raw.strip(), flags=re.MULTILINE)
    return [c.strip() for c in chunks if c.strip()]


def _write_pdf(path: Path, page_bodies: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = pdf_canvas.Canvas(str(path), pagesize=letter)
    w, h = letter
    margin_x, margin_y = 40, 40
    line_h = 10
    max_width = int((w - 2 * margin_x) / 4.8)  # ~ Courier 7.5pt char width estimate

    for body in page_bodies:
        y = h - margin_y
        c.setFont("Courier", 7.5)
        for para in body.split("\n"):
            para = para.rstrip() or " "
            for line in textwrap.wrap(para, width=max(20, max_width), replace_whitespace=False) or [""]:
                if y < margin_y:
                    c.showPage()
                    c.setFont("Courier", 7.5)
                    y = h - margin_y
                c.drawString(margin_x, y, _ascii_safe_line(line[:500]))
                y -= line_h
        c.showPage()

    c.save()


def main() -> None:
    for rel, out_name in FIXTURE_MAP:
        src = REPO.joinpath(*rel.split("/"))
        if not src.is_file():
            raise SystemExit(f"Missing fixture: {src}")
        pages = _split_fixture_pages(src.read_text(encoding="utf-8"))
        if not pages:
            raise SystemExit(f"No pages parsed from {src}")
        dest = OUT / out_name
        _write_pdf(dest, pages)
        print(f"Wrote {dest} ({len(pages)} pages)")


if __name__ == "__main__":
    main()
