import re
from io import BytesIO

_pdfplumber = None

def _get_pdfplumber():
    global _pdfplumber
    if _pdfplumber is None:
        import pdfplumber
        _pdfplumber = pdfplumber
    return _pdfplumber


def _try_expand_page(page):
    try:
        mediabox = page.page.get("/MediaBox")
        if mediabox:
            mb = [float(v) for v in mediabox]
            crop_x1 = float(page.width)
            media_x1 = mb[2] - mb[0]
            if media_x1 > crop_x1 + 5:
                return page.crop((0, 0, media_x1, float(page.height)), relative=False, strict=False)
    except Exception:
        pass
    return page


def extract_layout(pdf_bytes):
    pages = []
    with _get_pdfplumber().open(BytesIO(pdf_bytes)) as pdf:
        for page_index, page in enumerate(pdf.pages):
            expanded = _try_expand_page(page)
            width = float(expanded.width)
            height = float(expanded.height)
            words = expanded.extract_words(keep_blank_chars=False, x_tolerance=3, y_tolerance=3)
            raw_lines = _words_to_lines(words)
            lines = []
            for rl in raw_lines:
                text = re.sub(r'\s+', ' ', rl["text"]).strip()
                if not text:
                    continue
                lines.append({
                    "text": text,
                    "x0": float(rl["x0"]),
                    "y0": float(rl["y0"]),
                    "x1": float(rl["x1"]),
                    "y1": float(rl["y1"]),
                })
            lines.sort(key=lambda l: (round(l["y0"], 1), round(l["x0"], 1), l["text"]))
            pages.append({
                "page_index": page_index,
                "width": width,
                "height": height,
                "lines": lines,
            })
    return {"pages": pages}


def _words_to_lines(words):
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (round(float(w["top"]), 1), float(w["x0"])))
    lines = []
    current_line_words = [sorted_words[0]]
    current_top = round(float(sorted_words[0]["top"]), 1)

    for w in sorted_words[1:]:
        w_top = round(float(w["top"]), 1)
        if abs(w_top - current_top) <= 4.0:
            current_line_words.append(w)
        else:
            lines.append(_merge_words(current_line_words))
            current_line_words = [w]
            current_top = w_top

    if current_line_words:
        lines.append(_merge_words(current_line_words))

    return lines


def _merge_words(words):
    sorted_w = sorted(words, key=lambda w: float(w["x0"]))
    text = " ".join(w["text"] for w in sorted_w)
    x0 = min(float(w["x0"]) for w in sorted_w)
    y0 = min(float(w["top"]) for w in sorted_w)
    x1 = max(float(w["x1"]) for w in sorted_w)
    y1 = max(float(w["bottom"]) for w in sorted_w)
    return {"text": text, "x0": x0, "y0": y0, "x1": x1, "y1": y1}


def to_plain_text(layout):
    result_lines = []
    for page in layout["pages"]:
        page_idx = page["page_index"]
        result_lines.append(f"--- Page {page_idx + 1} ---")
        for line in page["lines"]:
            result_lines.append(line["text"])
    return "\n".join(result_lines)
