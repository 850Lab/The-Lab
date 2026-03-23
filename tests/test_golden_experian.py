import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import (
    classify_accounts,
    compute_negative_items,
    count_by_classification,
    classify_by_bureau_label,
)
from totals_detector import detect_section_totals, detect_totals_mode, compute_totals_confidence
from completeness import compute_completeness

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
GOLDEN_PATH = os.path.join(FIXTURES_DIR, "golden_experian.json")
GOLDEN_TEXT_PATH = os.path.join(os.path.dirname(__file__), "golden", "experian_golden.txt")


@pytest.fixture(scope="module")
def golden():
    with open(GOLDEN_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def ex_text():
    with open(GOLDEN_TEXT_PATH) as f:
        return f.read()


@pytest.fixture(scope="module")
def parsed_accounts(ex_text):
    from app import parse_accounts_experian
    accounts, rejects = parse_accounts_experian(ex_text)
    return accounts, rejects


@pytest.fixture(scope="module")
def parsed_inquiries(ex_text):
    from app import parse_inquiries_experian
    inquiries, rejects = parse_inquiries_experian(ex_text)
    return inquiries, rejects


class TestExperianAccountParsing:
    def test_account_count(self, parsed_accounts, golden):
        accounts, _ = parsed_accounts
        assert len(accounts) == golden["expected_account_count"]

    def test_all_accounts_have_names(self, parsed_accounts):
        accounts, _ = parsed_accounts
        for a in accounts:
            assert a.get("account_name"), f"Account missing name: {a}"

    def test_all_accounts_have_numbers(self, parsed_accounts):
        accounts, _ = parsed_accounts
        for a in accounts:
            assert a.get("account_number"), f"Account missing number: {a.get('account_name')}"

    def test_all_accounts_have_rule(self, parsed_accounts):
        accounts, _ = parsed_accounts
        for a in accounts:
            assert a["rule"] == "EX_ACCT"

    def test_known_accounts_present(self, parsed_accounts, golden):
        accounts, _ = parsed_accounts
        parsed_names = [a["account_name"] for a in accounts]
        for expected in golden["accounts"]:
            found = any(expected["account_name"] in name for name in parsed_names)
            assert found, f"Missing account: {expected['account_name']}"

    def test_potentially_negative_label(self, parsed_accounts, golden):
        accounts, _ = parsed_accounts
        for expected in golden["accounts"]:
            if "account_number" in expected:
                matching = [a for a in accounts if a.get("account_number") == expected["account_number"]]
            else:
                matching = [a for a in accounts if expected["account_name"] in a["account_name"]
                           and a.get("account_number", "").startswith(expected.get("account_number_prefix", "ZZZ"))]
            if matching:
                assert matching[0].get("potentially_negative", False) == expected["potentially_negative"], (
                    f"{expected['account_name']}: neg={matching[0].get('potentially_negative')}, "
                    f"expected={expected['potentially_negative']}"
                )

    def test_delinquency_flags_present(self, parsed_accounts, golden):
        accounts, _ = parsed_accounts
        for expected in golden["accounts"]:
            if not expected.get("has_delinquency_flags"):
                continue
            if "account_number" in expected:
                matching = [a for a in accounts if a.get("account_number") == expected["account_number"]]
            else:
                matching = [a for a in accounts if expected["account_name"] in a["account_name"]
                           and a.get("account_number", "").startswith(expected.get("account_number_prefix", "ZZZ"))]
            if matching:
                has_flags = bool(matching[0].get("delinquency_flags"))
                assert has_flags, f"{expected['account_name']}: expected delinquency flags but found none"

    def test_good_accounts_have_status(self, parsed_accounts, golden):
        accounts, _ = parsed_accounts
        for expected in golden["accounts"]:
            if expected.get("status") and "account_number" in expected:
                matching = [a for a in accounts if a.get("account_number") == expected["account_number"]]
                if matching:
                    assert matching[0].get("status") == expected["status"], (
                        f"{expected['account_name']}: status={matching[0].get('status')}, expected={expected['status']}"
                    )

    def test_no_rejects(self, parsed_accounts):
        _, rejects = parsed_accounts
        assert rejects["missing_required_fields"] == 0


class TestExperianInquiryParsing:
    def test_hard_inquiry_count(self, parsed_inquiries, golden):
        inquiries, _ = parsed_inquiries
        hard = [i for i in inquiries if i.get("type") == "Hard Inquiry"]
        assert len(hard) == golden["expected_hard_inquiry_count"]

    def test_hard_inquiry_creditors(self, parsed_inquiries, golden):
        inquiries, _ = parsed_inquiries
        hard = [i for i in inquiries if i.get("type") == "Hard Inquiry"]
        for expected_inq in golden["hard_inquiries"]:
            found = any(expected_inq["creditor"] in h["creditor"] for h in hard)
            assert found, f"Missing hard inquiry: {expected_inq['creditor']}"

    def test_hard_inquiry_dates(self, parsed_inquiries, golden):
        inquiries, _ = parsed_inquiries
        hard = [i for i in inquiries if i.get("type") == "Hard Inquiry"]
        hard_dates = [h["date"] for h in hard]
        for expected_inq in golden["hard_inquiries"]:
            assert expected_inq["date"] in hard_dates, f"Missing date: {expected_inq['date']}"

    def test_soft_inquiries_present(self, parsed_inquiries):
        inquiries, _ = parsed_inquiries
        soft = [i for i in inquiries if i.get("type") == "Soft Inquiry"]
        assert len(soft) > 0


class TestExperianClassification:
    def test_classification_counts(self, parsed_accounts, ex_text, golden):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), ex_text, bureau="experian")
        counts = count_by_classification(classified)
        expected = golden["expected_classification_counts"]
        assert counts["ADVERSE"] == expected["ADVERSE"]
        assert counts["GOOD_STANDING"] == expected["GOOD_STANDING"]
        assert counts["UNKNOWN"] == expected["UNKNOWN"]

    def test_negative_items_count(self, parsed_accounts, ex_text, golden):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), ex_text, bureau="experian")
        negatives = compute_negative_items(classified)
        assert len(negatives) == golden["expected_negative_items_count"]

    def test_known_accounts_classification(self, parsed_accounts, ex_text, golden):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), ex_text, bureau="experian")
        for expected in golden["accounts"]:
            if "account_number" in expected:
                matching = [a for a in classified if a.get("account_number") == expected["account_number"]]
                if matching:
                    first_match = matching[0]
                    assert first_match["classification"] == expected["expected_classification"], (
                        f"{expected['account_name']}: got {first_match['classification']}, "
                        f"expected {expected['expected_classification']}"
                    )
                    assert first_match["classification_source"] == expected["expected_source"], (
                        f"{expected['account_name']}: got {first_match['classification_source']}, "
                        f"expected {expected['expected_source']}"
                    )
                    assert first_match["classification_rule"] == expected["expected_rule"], (
                        f"{expected['account_name']}: got {first_match['classification_rule']}, "
                        f"expected {expected['expected_rule']}"
                    )

    def test_bureau_label_is_highest_precedence(self, parsed_accounts, ex_text):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), ex_text, bureau="experian")
        for acct in classified:
            if acct.get("potentially_negative"):
                assert acct["classification"] == "ADVERSE"
                assert acct["classification_source"] == "BUREAU_LABEL"
                assert acct["classification_rule"] == "CLS-09"

    def test_provenance_present(self, parsed_accounts, ex_text):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), ex_text, bureau="experian")
        for acct in classified:
            prov = acct.get("classification_provenance")
            assert prov is not None
            assert "label_result" in prov
            assert "potentially_negative" in prov


class TestExperianTotalsDetection:
    def test_account_totals(self, ex_text, golden):
        totals = detect_section_totals(ex_text, "experian")
        assert totals["accounts"] == golden["expected_totals"]["accounts"]

    def test_inquiry_totals(self, ex_text, golden):
        totals = detect_section_totals(ex_text, "experian")
        assert totals["inquiries"] == golden["expected_totals"]["inquiries"]

    def test_public_records_totals(self, ex_text, golden):
        totals = detect_section_totals(ex_text, "experian")
        assert totals["public_records"] == golden["expected_totals"]["public_records"]

    def test_totals_mode(self, ex_text, golden):
        totals = detect_section_totals(ex_text, "experian")
        mode = detect_totals_mode(totals, "experian", ex_text)
        assert mode == golden["expected_totals_mode"]

    def test_totals_confidence(self, ex_text):
        totals = detect_section_totals(ex_text, "experian")
        conf = compute_totals_confidence(totals)
        assert conf == "HIGH"


class TestExperianBureauLabelClassifier:
    def test_potentially_negative_returns_adverse(self):
        account = {"potentially_negative": True}
        assert classify_by_bureau_label(account) == "ADVERSE"

    def test_no_label_returns_none(self):
        account = {}
        assert classify_by_bureau_label(account) is None

    def test_false_label_returns_none(self):
        account = {"potentially_negative": False}
        assert classify_by_bureau_label(account) is None


class TestExperianPersonalInfo:
    def test_name_detected(self, ex_text, golden):
        from app import parse_personal_info
        info = parse_personal_info(ex_text)
        assert info.get("name") == golden["personal_info"]["name"]

    def test_dob_detected(self, ex_text, golden):
        from app import parse_personal_info
        info = parse_personal_info(ex_text)
        assert info.get("dob") == golden["personal_info"]["dob"]


class TestExperianCompleteness:
    def test_completeness_provable(self, parsed_accounts, ex_text, golden):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), ex_text, bureau="experian")
        negatives = compute_negative_items(classified)
        totals = detect_section_totals(ex_text, "experian")
        mode = detect_totals_mode(totals, "experian", ex_text)
        extracted = {
            "accounts": len(classified),
            "inquiries": totals.get("inquiries") or 0,
            "negative_items": len(negatives),
            "public_records": 0,
            "personal_info_fields": 2,
        }
        report = compute_completeness("experian", totals, extracted, totals_mode=mode)
        assert report.mode == "EXPLICIT"
        assert report.exactness in ("PROVABLE", "NOT_EXACT")
