import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from translator import build_account_records, detect_tu_variant_from_text
from layout_extract import to_plain_text

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_layout(name):
    with open(os.path.join(FIXTURES_DIR, name), "r") as f:
        return json.load(f)


def _load_text(name):
    with open(os.path.join(FIXTURES_DIR, name), "r") as f:
        return f.read()


class TestVariantDetection:
    def test_acr_detection(self):
        text = _load_text("plain_text_tu_acr.txt")
        assert detect_tu_variant_from_text(text) == "TU_ACR"

    def test_osc_detection(self):
        text = _load_text("plain_text_tu_osc.txt")
        assert detect_tu_variant_from_text(text) == "TU_OSC"


class TestACRDeterminism:
    def test_same_results_across_runs(self):
        layout = _load_layout("layout_tu_acr.json")
        run1 = build_account_records(layout, "TU_ACR")
        run2 = build_account_records(layout, "TU_ACR")
        assert len(run1) == len(run2)
        for r1, r2 in zip(run1, run2):
            assert r1.fields == r2.fields
            assert r1.record_type == r2.record_type

    def test_acr_extracts_accounts(self):
        layout = _load_layout("layout_tu_acr.json")
        records = build_account_records(layout, "TU_ACR")
        assert len(records) >= 2
        names = [r.fields.get("creditor_name") for r in records]
        assert "CHASE BANK" in names
        assert "WELLS FARGO" in names

    def test_acr_no_inferred_fields(self):
        layout = _load_layout("layout_tu_acr.json")
        records = build_account_records(layout, "TU_ACR")
        for rec in records:
            for field_name, val in rec.fields.items():
                if val is not None:
                    assert field_name in rec.provenance, (
                        f"Field '{field_name}' has value but no provenance"
                    )

    def test_acr_fields_deterministic(self):
        layout = _load_layout("layout_tu_acr.json")
        records = build_account_records(layout, "TU_ACR")
        for rec in records:
            assert rec.record_type == "account"
            assert rec.fields.get("creditor_name") is not None


class TestOSCDeterminism:
    def test_same_results_across_runs(self):
        layout = _load_layout("layout_tu_osc.json")
        run1 = build_account_records(layout, "TU_OSC")
        run2 = build_account_records(layout, "TU_OSC")
        assert len(run1) == len(run2)
        for r1, r2 in zip(run1, run2):
            assert r1.fields == r2.fields

    def test_osc_extracts_accounts(self):
        layout = _load_layout("layout_tu_osc.json")
        records = build_account_records(layout, "TU_OSC")
        assert len(records) >= 2
        names = [r.fields.get("creditor_name") for r in records]
        assert "CHASE BANK" in names
        assert "WELLS FARGO" in names

    def test_osc_no_inferred_fields(self):
        layout = _load_layout("layout_tu_osc.json")
        records = build_account_records(layout, "TU_OSC")
        for rec in records:
            for field_name, val in rec.fields.items():
                if val is not None:
                    assert field_name in rec.provenance


class TestToPlainText:
    def test_deterministic(self):
        layout = _load_layout("layout_tu_acr.json")
        t1 = to_plain_text(layout)
        t2 = to_plain_text(layout)
        assert t1 == t2

    def test_contains_content(self):
        layout = _load_layout("layout_tu_acr.json")
        text = to_plain_text(layout)
        assert "CHASE BANK" in text
        assert "annualcreditreport" in text
