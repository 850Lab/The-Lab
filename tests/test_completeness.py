import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from completeness import compute_completeness, SectionCompleteness, CompletenessReport
from totals_detector import detect_section_totals, compute_totals_confidence, self_verify_totals, detect_section_totals_with_sources, detect_totals_mode_with_sources


class TestTotalsConfidence:
    def test_high_confidence(self):
        totals = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": 0}
        assert compute_totals_confidence(totals) == "HIGH"

    def test_med_confidence(self):
        totals = {"accounts": 10, "inquiries": None, "negative_items": 3, "public_records": None}
        assert compute_totals_confidence(totals) == "MED"

    def test_low_confidence(self):
        totals = {"accounts": None, "inquiries": None, "negative_items": None, "public_records": None}
        assert compute_totals_confidence(totals) == "LOW"

    def test_three_non_none_is_high(self):
        totals = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": None}
        assert compute_totals_confidence(totals) == "HIGH"

    def test_one_non_none_is_med(self):
        totals = {"accounts": 10, "inquiries": None, "negative_items": None, "public_records": None}
        assert compute_totals_confidence(totals) == "MED"


class TestCompletenessExact:
    def test_exact_when_all_match_high_confidence(self):
        totals = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": 0}
        extracted = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": 0, "personal_info_fields": 3}
        report = compute_completeness("transunion", totals, extracted)
        assert report.totals_confidence == "HIGH"
        assert report.exactness == "EXACT"

    def test_not_exact_when_mismatch(self):
        totals = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": 0}
        extracted = {"accounts": 8, "inquiries": 5, "negative_items": 3, "public_records": 0, "personal_info_fields": 3}
        report = compute_completeness("transunion", totals, extracted)
        assert report.totals_confidence == "HIGH"
        assert report.exactness == "NOT_EXACT"
        acct_section = report.sections["accounts"]
        assert acct_section.delta == -2
        assert acct_section.section_pass is False

    def test_unprovable_when_low_confidence_no_sv(self):
        totals = {"accounts": None, "inquiries": None, "negative_items": None, "public_records": None}
        extracted = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": 0, "personal_info_fields": 4}
        report = compute_completeness("transunion", totals, extracted)
        assert report.totals_confidence == "LOW"
        assert report.exactness == "UNPROVABLE"

    def test_not_exact_when_med_confidence(self):
        totals = {"accounts": 10, "inquiries": None, "negative_items": None, "public_records": None}
        extracted = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": 0, "personal_info_fields": 4}
        report = compute_completeness("transunion", totals, extracted)
        assert report.totals_confidence == "MED"
        assert report.exactness == "NOT_EXACT"


class TestSelfVerification:
    def test_provable_when_self_verified_high(self):
        totals = {"accounts": None, "inquiries": None, "negative_items": None, "public_records": None}
        extracted = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": 0, "personal_info_fields": 4}
        sv = {
            "verified": True,
            "confidence": "HIGH",
            "matches": 3,
            "checked": 3,
            "matched_sections": ["accounts", "inquiries", "public_records"],
            "independent_counts": {"accounts": 10, "inquiries": 5, "public_records": 0, "negative_items": None},
            "sources": {"accounts": "section_derived", "inquiries": "section_derived", "public_records": "section_derived"},
        }
        report = compute_completeness("transunion", totals, extracted, self_verification=sv)
        assert report.totals_confidence == "HIGH"
        assert report.exactness == "PROVABLE"
        assert report.verification_method == "self_verified"
        assert "accounts" in report.matched_sections

    def test_provable_when_self_verified_med(self):
        totals = {"accounts": None, "inquiries": None, "negative_items": None, "public_records": None}
        extracted = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": 0, "personal_info_fields": 4}
        sv = {
            "verified": True,
            "confidence": "MED",
            "matches": 2,
            "checked": 3,
            "matched_sections": ["accounts", "inquiries"],
            "independent_counts": {"accounts": 10, "inquiries": 5, "public_records": 1, "negative_items": None},
            "sources": {"accounts": "section_derived", "inquiries": "section_derived", "public_records": "section_derived"},
        }
        report = compute_completeness("transunion", totals, extracted, self_verification=sv)
        assert report.totals_confidence == "MED"
        assert report.exactness == "PROVABLE"
        assert report.verification_method == "self_verified"

    def test_unprovable_when_sv_not_verified(self):
        totals = {"accounts": None, "inquiries": None, "negative_items": None, "public_records": None}
        extracted = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": 0, "personal_info_fields": 4}
        sv = {
            "verified": False,
            "confidence": "LOW",
            "matches": 0,
            "checked": 0,
            "matched_sections": [],
            "independent_counts": {"accounts": None, "inquiries": None, "public_records": None, "negative_items": None},
            "sources": {},
        }
        report = compute_completeness("transunion", totals, extracted, self_verification=sv)
        assert report.totals_confidence == "LOW"
        assert report.exactness == "UNPROVABLE"

    def test_section_derived_mode_provable(self):
        totals = {"accounts": 10, "inquiries": 5, "negative_items": None, "public_records": 0}
        extracted = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": 0, "personal_info_fields": 4}
        report = compute_completeness("transunion", totals, extracted, totals_mode="SECTION_DERIVED")
        assert report.exactness == "PROVABLE"
        assert report.verification_method == "section_derived"


class TestSectionCompleteness:
    def test_section_with_no_expected(self):
        totals = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": None}
        extracted = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": 2, "personal_info_fields": 4}
        report = compute_completeness("transunion", totals, extracted)
        pr = report.sections["public_records"]
        assert pr.expected_total is None
        assert pr.delta is None
        assert pr.section_pass is None

    def test_section_delta_positive(self):
        totals = {"accounts": 10, "inquiries": 5, "negative_items": 3, "public_records": 0}
        extracted = {"accounts": 12, "inquiries": 5, "negative_items": 3, "public_records": 0, "personal_info_fields": 4}
        report = compute_completeness("transunion", totals, extracted)
        acct = report.sections["accounts"]
        assert acct.delta == 2
        assert acct.section_pass is False


class TestDetectSectionTotals:
    def test_detect_totals_from_text(self):
        text = "Total Number of Accounts: 15\nTotal Inquiries: 3\nNegative Items: 2\nTotal Public Records: 0"
        result = detect_section_totals(text, "transunion")
        assert result["accounts"] == 15
        assert result["inquiries"] == 3
        assert result["negative_items"] == 2
        assert result["public_records"] == 0

    def test_no_totals_found(self):
        text = "This is a credit report with no summary totals."
        result = detect_section_totals(text, "transunion")
        assert result["accounts"] is None
        assert result["inquiries"] is None
        assert result["negative_items"] is None
        assert result["public_records"] is None

    def test_suspicious_value_ignored(self):
        text = "Total Number of Accounts: 999"
        result = detect_section_totals(text, "transunion")
        assert result["accounts"] is None or result["accounts"] <= 500


class TestDetectSectionTotalsWithSources:
    def test_explicit_source_tracking(self):
        text = "Total Number of Accounts: 15\nTotal Inquiries: 3"
        totals, sources = detect_section_totals_with_sources(text, "transunion")
        assert totals["accounts"] == 15
        assert sources.get("accounts") == "explicit"
        assert totals["inquiries"] == 3
        assert sources.get("inquiries") == "explicit"

    def test_section_derived_source_tracking(self):
        text = (
            "Accounts with adverse information\n"
            "Account Name\nCreditor A\nAccount Information\n"
            "Account Name\nCreditor B\nAccount Information\n"
            "Satisfactory Accounts\n"
            "Account Name\nCreditor C\n"
            "Regular Inquiries\n"
            "Company A\nRequested On\n01/01/2024\n"
            "Company B\nRequested On\n02/01/2024\n"
        )
        totals, sources = detect_section_totals_with_sources(text, "transunion")
        assert totals["accounts"] is not None
        if "accounts" in sources:
            assert sources["accounts"] == "section_derived"


class TestSelfVerifyTotals:
    def test_self_verify_matching_counts(self):
        text = (
            "Accounts with adverse information\n"
            "Account Name\nSatisfactory Accounts\nAccount Name\nAccount Name\n"
            "Regular Inquiries\n"
            "Requested On\n01/01/2024\nRequested On\n02/01/2024\n"
        )
        extracted = {"accounts": 3, "inquiries": 2, "public_records": 0}
        sv = self_verify_totals(text, "transunion", extracted)
        assert sv["checked"] > 0

    def test_self_verify_no_data(self):
        text = "This is a report with no recognizable sections."
        extracted = {"accounts": 10, "inquiries": 5, "public_records": 0}
        sv = self_verify_totals(text, "transunion", extracted)
        assert sv["verified"] is False or sv["matches"] == 0


class TestTotalsMode:
    def test_explicit_mode_detected(self):
        text = "Total Number of Accounts: 15"
        totals, sources = detect_section_totals_with_sources(text, "transunion")
        mode = detect_totals_mode_with_sources(totals, sources, "transunion", text)
        assert mode == "EXPLICIT"

    def test_section_derived_from_sources(self):
        text = (
            "Account Name\nCreditor A\n"
            "Regular Inquiries\n"
            "Requested On\n01/01/2024\n"
        )
        totals, sources = detect_section_totals_with_sources(text, "transunion")
        mode = detect_totals_mode_with_sources(totals, sources, "transunion", text)
        if any(v == "section_derived" for v in sources.values()):
            assert mode == "SECTION_DERIVED"

    def test_none_mode_when_empty(self):
        text = "Nothing recognizable here."
        totals, sources = detect_section_totals_with_sources(text, "transunion")
        mode = detect_totals_mode_with_sources(totals, sources, "transunion", text)
        assert mode == "NONE"
