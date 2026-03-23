from pathlib import Path
import re

def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()

def test_experian_golden_file_exists():
    path = Path("tests/golden/experian_golden.txt")
    assert path.exists(), "Experian golden file is missing"

def test_experian_golden_not_empty():
    text = Path("tests/golden/experian_golden.txt").read_text(encoding="utf-8")
    assert len(text) > 50_000, "Golden file looks truncated"

def test_experian_contains_core_anchors():
    text = Path("tests/golden/experian_golden.txt").read_text(encoding="utf-8")
    norm = normalized(text)

    anchors = [
        "prepared for",
        "at a glance",
        "personal information",
        "accounts",
        "hard inquiries"
    ]

    for anchor in anchors:
        assert anchor in norm, f"Missing anchor: {anchor}"
