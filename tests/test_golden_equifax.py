import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import (
    classify_accounts,
    compute_negative_items,
    count_by_classification,
    classify_by_pay_status,
    classify_by_delinquency_flags,
)
from totals_detector import detect_section_totals, detect_totals_mode, compute_totals_confidence
from completeness import compute_completeness

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
GOLDEN_PATH = os.path.join(FIXTURES_DIR, "golden_equifax.json")
GOLDEN_TEXT_PATH = os.path.join(os.path.dirname(__file__), "golden", "equifax_golden.txt")


@pytest.fixture(scope="module")
def golden():
    with open(GOLDEN_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def eq_text():
    with open(GOLDEN_TEXT_PATH) as f:
        return f.read()


@pytest.fixture(scope="module")
def parsed_accounts(eq_text):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app import parse_accounts_equifax
    accounts, rejects = parse_accounts_equifax(eq_text)
    return accounts, rejects


@pytest.fixture(scope="module")
def parsed_inquiries(eq_text):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app import parse_inquiries_equifax
    inquiries, rejects = parse_inquiries_equifax(eq_text)
    return inquiries, rejects


class TestEquifaxAccountParsing:
    def test_account_count(self, parsed_accounts, golden):
        accounts, _ = parsed_accounts
        assert len(accounts) == golden["expected_account_count"]

    def test_account_names(self, parsed_accounts, golden):
        accounts, _ = parsed_accounts
        parsed_names = [a["account_name"] for a in accounts]
        for expected in golden["accounts"]:
            assert expected["account_name"] in parsed_names, (
                f"Missing account: {expected['account_name']}"
            )

    def test_account_numbers(self, parsed_accounts, golden):
        accounts, _ = parsed_accounts
        for acct in golden["accounts"]:
            matching = [a for a in accounts if a["account_name"] == acct["account_name"] and a.get("account_number") == acct["account_number"]]
            assert len(matching) >= 1, f"No match for {acct['account_name']} {acct['account_number']}"

    def test_balances(self, parsed_accounts, golden):
        accounts, _ = parsed_accounts
        for expected_acct in golden["accounts"]:
            matching = [a for a in accounts if a.get("account_number") == expected_acct["account_number"]]
            if matching:
                parsed_balance = matching[0].get("balance", "").replace(",", "").replace("$", "")
                assert parsed_balance == expected_acct["balance"], (
                    f"{expected_acct['account_name']}: balance {parsed_balance} != {expected_acct['balance']}"
                )

    def test_statuses(self, parsed_accounts, golden):
        accounts, _ = parsed_accounts
        for expected_acct in golden["accounts"]:
            matching = [a for a in accounts if a.get("account_number") == expected_acct["account_number"]]
            if matching:
                assert matching[0].get("status") == expected_acct["status"]

    def test_delinquency_flags_present(self, parsed_accounts, golden):
        accounts, _ = parsed_accounts
        for expected_acct in golden["accounts"]:
            matching = [a for a in accounts if a.get("account_number") == expected_acct["account_number"]]
            if matching:
                has_flags = bool(matching[0].get("delinquency_flags"))
                assert has_flags == expected_acct["delinquency_flags_present"], (
                    f"{expected_acct['account_name']}: flags_present={has_flags}, expected={expected_acct['delinquency_flags_present']}"
                )

    def test_loan_types(self, parsed_accounts, golden):
        accounts, _ = parsed_accounts
        for expected_acct in golden["accounts"]:
            matching = [a for a in accounts if a.get("account_number") == expected_acct["account_number"]]
            if matching and expected_acct.get("loan_type"):
                assert matching[0].get("loan_type") == expected_acct["loan_type"]


class TestEquifaxInquiryParsing:
    def test_hard_inquiry_count(self, parsed_inquiries, golden):
        inquiries, _ = parsed_inquiries
        hard = [i for i in inquiries if i.get("type") == "Hard Inquiry"]
        assert len(hard) == golden["expected_hard_inquiry_count"]

    def test_hard_inquiry_creditors(self, parsed_inquiries, golden):
        inquiries, _ = parsed_inquiries
        hard = [i for i in inquiries if i.get("type") == "Hard Inquiry"]
        hard_creditors = [i["creditor"] for i in hard]
        for expected_inq in golden["hard_inquiries"]:
            found = any(expected_inq["creditor"] in c for c in hard_creditors)
            assert found, f"Missing hard inquiry: {expected_inq['creditor']}"

    def test_soft_inquiries_present(self, parsed_inquiries):
        inquiries, _ = parsed_inquiries
        soft = [i for i in inquiries if i.get("type") == "Soft Inquiry"]
        assert len(soft) > 0


class TestEquifaxClassification:
    def test_classification_per_account(self, parsed_accounts, eq_text, golden):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), eq_text, bureau="equifax")
        for expected_acct in golden["accounts"]:
            matching = [a for a in classified if a.get("account_number") == expected_acct["account_number"]]
            assert len(matching) >= 1, f"No match for {expected_acct['account_name']}"
            assert matching[0]["classification"] == expected_acct["expected_classification"], (
                f"{expected_acct['account_name']}: got {matching[0]['classification']}, "
                f"expected {expected_acct['expected_classification']}"
            )

    def test_classification_source(self, parsed_accounts, eq_text, golden):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), eq_text, bureau="equifax")
        for expected_acct in golden["accounts"]:
            matching = [a for a in classified if a.get("account_number") == expected_acct["account_number"]]
            if matching:
                assert matching[0]["classification_source"] == expected_acct["expected_source"], (
                    f"{expected_acct['account_name']}: got {matching[0]['classification_source']}, "
                    f"expected {expected_acct['expected_source']}"
                )

    def test_classification_rule(self, parsed_accounts, eq_text, golden):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), eq_text, bureau="equifax")
        for expected_acct in golden["accounts"]:
            matching = [a for a in classified if a.get("account_number") == expected_acct["account_number"]]
            if matching:
                assert matching[0]["classification_rule"] == expected_acct["expected_rule"], (
                    f"{expected_acct['account_name']}: got {matching[0]['classification_rule']}, "
                    f"expected {expected_acct['expected_rule']}"
                )

    def test_classification_counts(self, parsed_accounts, eq_text, golden):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), eq_text, bureau="equifax")
        counts = count_by_classification(classified)
        expected = golden["expected_classification_counts"]
        assert counts["ADVERSE"] == expected["ADVERSE"]
        assert counts["GOOD_STANDING"] == expected["GOOD_STANDING"]
        assert counts["UNKNOWN"] == expected["UNKNOWN"]

    def test_negative_items(self, parsed_accounts, eq_text, golden):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), eq_text, bureau="equifax")
        negatives = compute_negative_items(classified)
        assert len(negatives) == golden["expected_negative_items_count"]

    def test_provenance_present(self, parsed_accounts, eq_text):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), eq_text, bureau="equifax")
        for acct in classified:
            prov = acct.get("classification_provenance")
            assert prov is not None
            assert "flag_result" in prov
            assert "delinquency_flags" in prov


class TestEquifaxTotalsDetection:
    def test_account_totals(self, eq_text, golden):
        totals = detect_section_totals(eq_text, "equifax")
        assert totals["accounts"] == golden["expected_account_count"]

    def test_inquiry_totals(self, eq_text, golden):
        totals = detect_section_totals(eq_text, "equifax")
        assert totals["inquiries"] == golden["expected_hard_inquiry_count"]

    def test_totals_mode(self, eq_text, golden):
        totals = detect_section_totals(eq_text, "equifax")
        mode = detect_totals_mode(totals, "equifax", eq_text)
        assert mode == golden["expected_totals_mode"]

    def test_totals_confidence(self, eq_text):
        totals = detect_section_totals(eq_text, "equifax")
        conf = compute_totals_confidence(totals)
        assert conf in ("HIGH", "MED")


class TestEquifaxCompleteness:
    def test_completeness_provable(self, parsed_accounts, eq_text, golden):
        accounts, _ = parsed_accounts
        classified = classify_accounts(list(accounts), eq_text, bureau="equifax")
        negatives = compute_negative_items(classified)
        totals = detect_section_totals(eq_text, "equifax")
        mode = detect_totals_mode(totals, "equifax", eq_text)
        extracted = {
            "accounts": len(classified),
            "inquiries": totals.get("inquiries") or 0,
            "negative_items": len(negatives),
            "public_records": 0,
            "personal_info_fields": 3,
        }
        report = compute_completeness("equifax", totals, extracted, totals_mode=mode)
        assert report.mode == "SECTION_DERIVED"
        assert report.exactness in ("PROVABLE", "NOT_EXACT")


class TestEquifaxDelinquencyClassifier:
    def test_flags_adverse(self):
        account = {"delinquency_flags": [30, 60, 90]}
        assert classify_by_delinquency_flags(account) == "ADVERSE"

    def test_no_flags_none(self):
        account = {"delinquency_flags": []}
        assert classify_by_delinquency_flags(account) is None

    def test_missing_flags_none(self):
        account = {}
        assert classify_by_delinquency_flags(account) is None

    def test_single_30_adverse(self):
        account = {"delinquency_flags": [30]}
        assert classify_by_delinquency_flags(account) == "ADVERSE"

    def test_collection_flag(self):
        account = {"delinquency_flags": ["C"]}
        assert classify_by_delinquency_flags(account) == "ADVERSE"

    def test_chargeoff_flag(self):
        account = {"delinquency_flags": ["CO"]}
        assert classify_by_delinquency_flags(account) == "ADVERSE"

    def test_foreclosure_flag(self):
        account = {"delinquency_flags": ["F"]}
        assert classify_by_delinquency_flags(account) == "ADVERSE"

    def test_pays_as_agreed_token(self):
        assert classify_by_pay_status("Pays As Agreed") == "GOOD_STANDING"


class TestEquifaxPersonalInfo:
    def test_name_detected(self, eq_text, golden):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from app import parse_personal_info
        info = parse_personal_info(eq_text)
        expected_name = golden["personal_info"]["name"]
        assert info.get("name") is not None

    def test_ssn_detected(self, eq_text, golden):
        from app import parse_personal_info
        info = parse_personal_info(eq_text)
        assert info.get("ssn") == golden["personal_info"]["ssn"]

    def test_dob_detected(self, eq_text, golden):
        from app import parse_personal_info
        info = parse_personal_info(eq_text)
        assert info.get("dob") == golden["personal_info"]["dob"]
