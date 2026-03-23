import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import (
    classify_accounts,
    compute_negative_items,
    count_by_classification,
    detect_section_boundaries,
    classify_by_pay_status,
)
from totals_detector import detect_section_totals, detect_totals_mode
from completeness import compute_completeness

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
GOLDEN_PATH = os.path.join(FIXTURES_DIR, "golden_tu_acr.json")
SAMPLE_TEXT_PATH = os.path.join(FIXTURES_DIR, "tu_acr_sample.txt")


@pytest.fixture(scope="module")
def golden():
    with open(GOLDEN_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def sample_text():
    with open(SAMPLE_TEXT_PATH) as f:
        return f.read()


@pytest.fixture(scope="module")
def sample_accounts(golden):
    return [
        {
            "account_name": acct["account_name"],
            "account_number": acct["account_number"],
            "status": acct["status"],
        }
        for acct in golden["accounts"]
    ]


class TestSectionBoundaries:
    def test_adverse_section_detected(self, sample_text, golden):
        boundaries = detect_section_boundaries(sample_text)
        assert boundaries["adverse_start"] is not None
        if golden["expected_boundaries"]["adverse_start_present"]:
            assert boundaries["adverse_start"] >= 0

    def test_satisfactory_section_detected(self, sample_text, golden):
        boundaries = detect_section_boundaries(sample_text)
        assert boundaries["satisfactory_start"] is not None
        if golden["expected_boundaries"]["satisfactory_start_present"]:
            assert boundaries["satisfactory_start"] >= 0

    def test_adverse_before_satisfactory(self, sample_text, golden):
        if not golden["expected_boundaries"]["adverse_before_satisfactory"]:
            pytest.skip("adverse_before_satisfactory not expected")
        boundaries = detect_section_boundaries(sample_text)
        assert boundaries["adverse_start"] < boundaries["satisfactory_start"]


class TestAccountClassification:
    def test_each_account_classified_correctly(self, sample_text, golden, sample_accounts):
        classified = classify_accounts(sample_accounts, sample_text)
        for i, acct in enumerate(classified):
            expected = golden["accounts"][i]
            assert acct["classification"] == expected["expected_classification"], (
                f"Account {expected['account_name']}: "
                f"got {acct['classification']}, expected {expected['expected_classification']}"
            )

    def test_each_account_source_correct(self, sample_text, golden, sample_accounts):
        classified = classify_accounts(sample_accounts, sample_text)
        for i, acct in enumerate(classified):
            expected = golden["accounts"][i]
            assert acct["classification_source"] == expected["expected_source"], (
                f"Account {expected['account_name']}: "
                f"got {acct['classification_source']}, expected {expected['expected_source']}"
            )

    def test_each_account_rule_correct(self, sample_text, golden, sample_accounts):
        classified = classify_accounts(sample_accounts, sample_text)
        for i, acct in enumerate(classified):
            expected = golden["accounts"][i]
            assert acct["classification_rule"] == expected["expected_rule"], (
                f"Account {expected['account_name']}: "
                f"got {acct['classification_rule']}, expected {expected['expected_rule']}"
            )

    def test_classification_provenance_present(self, sample_text, sample_accounts):
        classified = classify_accounts(sample_accounts, sample_text)
        for acct in classified:
            prov = acct.get("classification_provenance")
            assert prov is not None, f"Missing provenance for {acct['account_name']}"
            assert "text_position" in prov
            assert "section_result" in prov
            assert "token_result" in prov
            assert "boundaries" in prov


class TestClassificationCounts:
    def test_counts_match_golden(self, sample_text, golden, sample_accounts):
        classified = classify_accounts(sample_accounts, sample_text)
        counts = count_by_classification(classified)
        expected = golden["expected_classification_counts"]
        assert counts["ADVERSE"] == expected["ADVERSE"]
        assert counts["GOOD_STANDING"] == expected["GOOD_STANDING"]
        assert counts["UNKNOWN"] == expected["UNKNOWN"]

    def test_total_accounts_preserved(self, sample_text, golden, sample_accounts):
        classified = classify_accounts(sample_accounts, sample_text)
        counts = count_by_classification(classified)
        total = sum(counts.values())
        assert total == len(golden["accounts"])


class TestNegativeItems:
    def test_negative_items_count(self, sample_text, golden, sample_accounts):
        classified = classify_accounts(sample_accounts, sample_text)
        negatives = compute_negative_items(classified)
        assert len(negatives) == golden["expected_negative_items_count"]

    def test_negative_items_are_adverse_only(self, sample_text, sample_accounts):
        classified = classify_accounts(sample_accounts, sample_text)
        negatives = compute_negative_items(classified)
        for neg in negatives:
            assert neg["classification_source"] in ("SECTION_HEADER", "PAY_STATUS_TOKEN")
            assert neg["classification_rule"] in ("CLS-01", "CLS-04")

    def test_negative_items_have_provenance(self, sample_text, sample_accounts):
        classified = classify_accounts(sample_accounts, sample_text)
        negatives = compute_negative_items(classified)
        for neg in negatives:
            assert neg.get("provenance") is not None


class TestTotalsMode:
    def test_totals_mode_section_derived(self, sample_text, golden):
        totals = detect_section_totals(sample_text, "transunion")
        mode = detect_totals_mode(totals, "transunion", sample_text)
        assert mode == golden["expected_totals_mode"]


class TestCompletenessIntegration:
    def test_completeness_with_section_derived(self, sample_text, golden, sample_accounts):
        classified = classify_accounts(sample_accounts, sample_text)
        negatives = compute_negative_items(classified)
        totals = detect_section_totals(sample_text, "transunion")
        mode = detect_totals_mode(totals, "transunion", sample_text)

        extracted = {
            "accounts": len(classified),
            "inquiries": 0,
            "negative_items": len(negatives),
            "public_records": 0,
            "personal_info_fields": 4,
        }
        report = compute_completeness("transunion", totals, extracted, totals_mode=mode)
        assert report.mode == "SECTION_DERIVED"
        assert report.exactness in ("PROVABLE", "NOT_EXACT", "UNPROVABLE")


class TestPayStatusTokens:
    def test_bracketed_status_is_adverse(self):
        assert classify_by_pay_status(">Account 120 Days Past Due Date<") == "ADVERSE"

    def test_paid_closed_is_good(self):
        assert classify_by_pay_status("Paid, Closed; was Paid as agreed") == "GOOD_STANDING"

    def test_current_is_good(self):
        assert classify_by_pay_status("Current; Paid or paying as agreed") == "GOOD_STANDING"

    def test_empty_is_unknown(self):
        assert classify_by_pay_status("") == "UNKNOWN"

    def test_none_is_unknown(self):
        assert classify_by_pay_status(None) == "UNKNOWN"
