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
    classify_by_section_position,
)


def _build_text(adverse_accounts=None, satisfactory_accounts=None, include_inquiries=True):
    parts = ["Personal Credit Report\n\n"]

    if adverse_accounts is not None:
        parts.append("Accounts with Adverse Information\n")
        parts.append("Adverse info header text.\n")
        for name, num in adverse_accounts:
            parts.append(f"Account Name\n{name} {num}\nAccount Information\n")
            parts.append(f"Pay Status >Collection<\n\n")

    if satisfactory_accounts is not None:
        parts.append("Satisfactory Accounts\n")
        parts.append("Good accounts header text.\n")
        for name, num in satisfactory_accounts:
            parts.append(f"Account Name\n{name} {num}\nAccount Information\n")
            parts.append(f"Pay Status Current; Paid or paying as agreed\n\n")

    if include_inquiries:
        parts.append("Regular Inquiries\nInquiry data here.\n")

    return "".join(parts)


def _make_accounts(pairs):
    return [
        {"account_name": name, "account_number": num, "status": ""}
        for name, num in pairs
    ]


class TestSectionBoundaryEdgeCases:
    def test_adverse_only_no_satisfactory(self):
        text = _build_text(
            adverse_accounts=[("BADBANK", "1234****")],
            satisfactory_accounts=None,
        )
        boundaries = detect_section_boundaries(text)
        assert boundaries["adverse_start"] is not None
        assert boundaries["satisfactory_start"] is None

    def test_satisfactory_only_no_adverse(self):
        text = _build_text(
            adverse_accounts=None,
            satisfactory_accounts=[("GOODBANK", "5678****")],
        )
        boundaries = detect_section_boundaries(text)
        assert boundaries["adverse_start"] is None
        assert boundaries["satisfactory_start"] is not None

    def test_no_section_headers_at_all(self):
        text = "Personal Credit Report\nAccount Name\nSOME BANK 1234****\nPay Status Current\n"
        boundaries = detect_section_boundaries(text)
        assert boundaries["adverse_start"] is None
        assert boundaries["satisfactory_start"] is None

    def test_multiple_inquiry_markers(self):
        text = _build_text(
            adverse_accounts=[("BANK A", "111****")],
            satisfactory_accounts=[("BANK B", "222****")],
        )
        text += "\nRequests Viewed Only By You\nSoft inquiry data.\n"
        boundaries = detect_section_boundaries(text)
        assert boundaries["inquiries_start"] is not None


class TestClassificationWithoutSectionHeaders:
    def test_token_classification_when_no_headers(self):
        text = "Account Name\nBANK ONE 999****\nPay Status Collection\n"
        accounts = [{"account_name": "BANK ONE", "account_number": "999****", "status": "Collection"}]
        classified = classify_accounts(accounts, text)
        assert classified[0]["classification"] == "ADVERSE"
        assert classified[0]["classification_source"] == "PAY_STATUS_TOKEN"
        assert classified[0]["classification_rule"] == "CLS-04"

    def test_good_token_when_no_headers(self):
        text = "Account Name\nGOODBANK 888****\nPay Status Paying as agreed\n"
        accounts = [{"account_name": "GOODBANK", "account_number": "888****", "status": "Paying as agreed"}]
        classified = classify_accounts(accounts, text)
        assert classified[0]["classification"] == "GOOD_STANDING"
        assert classified[0]["classification_source"] == "PAY_STATUS_TOKEN"
        assert classified[0]["classification_rule"] == "CLS-05"

    def test_unknown_when_no_headers_and_no_token(self):
        text = "Account Name\nMYSTERY BANK 777****\nPay Status Some weird status\n"
        accounts = [{"account_name": "MYSTERY BANK", "account_number": "777****", "status": "Some weird status"}]
        classified = classify_accounts(accounts, text)
        assert classified[0]["classification"] == "UNKNOWN"
        assert classified[0]["classification_source"] == "UNCLASSIFIED"
        assert classified[0]["classification_rule"] == "CLS-07"


class TestSectionOverridesToken:
    def test_section_adverse_overrides_good_token(self):
        adverse = [("CONFUSING BANK", "111****")]
        satisfactory = []
        text = _build_text(adverse_accounts=adverse, satisfactory_accounts=satisfactory)
        accounts = [{"account_name": "CONFUSING BANK", "account_number": "111****", "status": "Current"}]
        classified = classify_accounts(accounts, text)
        assert classified[0]["classification"] == "ADVERSE"
        assert classified[0]["classification_source"] == "SECTION_HEADER"

    def test_section_good_overrides_adverse_token(self):
        adverse = []
        satisfactory = [("MISREPORTED BANK", "222****")]
        text = _build_text(adverse_accounts=adverse, satisfactory_accounts=satisfactory)
        accounts = [{"account_name": "MISREPORTED BANK", "account_number": "222****", "status": "Collection"}]
        classified = classify_accounts(accounts, text)
        assert classified[0]["classification"] == "GOOD_STANDING"
        assert classified[0]["classification_source"] == "SECTION_HEADER"


class TestPayStatusTokenEdgeCases:
    def test_charge_off(self):
        assert classify_by_pay_status("Charge Off") == "ADVERSE"

    def test_charged_off(self):
        assert classify_by_pay_status("Charged Off") == "ADVERSE"

    def test_past_due(self):
        assert classify_by_pay_status("Past Due") == "ADVERSE"

    def test_repossession(self):
        assert classify_by_pay_status("Repossession") == "ADVERSE"

    def test_foreclosure(self):
        assert classify_by_pay_status("Foreclosure") == "ADVERSE"

    def test_voluntarily_surrendered(self):
        assert classify_by_pay_status("Voluntarily Surrendered") == "ADVERSE"

    def test_bankruptcy(self):
        assert classify_by_pay_status("Bankruptcy") == "ADVERSE"

    def test_30_days_late(self):
        assert classify_by_pay_status("Account 30 days past due date") == "ADVERSE"

    def test_60_days_late(self):
        assert classify_by_pay_status("Account 60 days past due date") == "ADVERSE"

    def test_90_days_late(self):
        assert classify_by_pay_status("Account 90 days past due date") == "ADVERSE"

    def test_120_days_late(self):
        assert classify_by_pay_status("Account 120 days past due date") == "ADVERSE"

    def test_collection_account(self):
        assert classify_by_pay_status("Collection Account") == "ADVERSE"

    def test_paid_as_agreed(self):
        assert classify_by_pay_status("Paid As Agreed") == "GOOD_STANDING"

    def test_paying_as_agreed(self):
        assert classify_by_pay_status("Paying As Agreed") == "GOOD_STANDING"

    def test_current_account(self):
        assert classify_by_pay_status("Current Account") == "GOOD_STANDING"

    def test_paid_closed(self):
        assert classify_by_pay_status("Paid, Closed") == "GOOD_STANDING"

    def test_brackets_adverse(self):
        assert classify_by_pay_status(">Account 120 Days Past Due Date<") == "ADVERSE"

    def test_inner_brackets(self):
        assert classify_by_pay_status(">Collection<") == "ADVERSE"

    def test_whitespace_only(self):
        assert classify_by_pay_status("   ") == "UNKNOWN"

    def test_numeric_only(self):
        assert classify_by_pay_status("12345") == "UNKNOWN"

    def test_case_insensitive(self):
        assert classify_by_pay_status("CURRENT") == "GOOD_STANDING"
        assert classify_by_pay_status("COLLECTION") == "ADVERSE"
        assert classify_by_pay_status("charge OFF") == "ADVERSE"


class TestNegativeItemsComputation:
    def test_only_adverse_become_negative(self):
        accounts = [
            {"account_name": "A", "classification": "ADVERSE", "classification_source": "SECTION_HEADER", "classification_rule": "CLS-01"},
            {"account_name": "B", "classification": "GOOD_STANDING", "classification_source": "SECTION_HEADER", "classification_rule": "CLS-02"},
            {"account_name": "C", "classification": "UNKNOWN", "classification_source": "UNCLASSIFIED", "classification_rule": "CLS-07"},
        ]
        negatives = compute_negative_items(accounts)
        assert len(negatives) == 1
        assert negatives[0]["creditor_name"] == "A"

    def test_no_adverse_no_negatives(self):
        accounts = [
            {"account_name": "B", "classification": "GOOD_STANDING", "classification_source": "SECTION_HEADER", "classification_rule": "CLS-02"},
        ]
        negatives = compute_negative_items(accounts)
        assert len(negatives) == 0

    def test_all_adverse(self):
        accounts = [
            {"account_name": "X", "classification": "ADVERSE", "classification_source": "PAY_STATUS_TOKEN", "classification_rule": "CLS-04"},
            {"account_name": "Y", "classification": "ADVERSE", "classification_source": "SECTION_HEADER", "classification_rule": "CLS-01"},
        ]
        negatives = compute_negative_items(accounts)
        assert len(negatives) == 2

    def test_empty_accounts(self):
        negatives = compute_negative_items([])
        assert len(negatives) == 0


class TestCountByClassification:
    def test_all_three_categories(self):
        accounts = [
            {"classification": "ADVERSE"},
            {"classification": "ADVERSE"},
            {"classification": "GOOD_STANDING"},
            {"classification": "UNKNOWN"},
        ]
        counts = count_by_classification(accounts)
        assert counts == {"ADVERSE": 2, "GOOD_STANDING": 1, "UNKNOWN": 1}

    def test_unknown_default(self):
        accounts = [{"classification": "SOME_OTHER"}]
        counts = count_by_classification(accounts)
        assert counts["UNKNOWN"] == 1

    def test_empty(self):
        counts = count_by_classification([])
        assert counts == {"ADVERSE": 0, "GOOD_STANDING": 0, "UNKNOWN": 0}


class TestProvenanceFields:
    def test_provenance_has_all_fields(self):
        text = _build_text(
            adverse_accounts=[("TESTBANK", "999****")],
            satisfactory_accounts=[],
        )
        accounts = [{"account_name": "TESTBANK", "account_number": "999****", "status": ">Collection<"}]
        classified = classify_accounts(accounts, text)
        prov = classified[0]["classification_provenance"]

        assert "text_position" in prov
        assert "section_result" in prov
        assert "token_result" in prov
        assert "pay_status_used" in prov
        assert "boundaries" in prov
        assert "adverse_start" in prov["boundaries"]
        assert "satisfactory_start" in prov["boundaries"]
        assert "inquiries_start" in prov["boundaries"]

    def test_text_position_removed_from_account(self):
        text = _build_text(
            adverse_accounts=[("TESTBANK", "999****")],
            satisfactory_accounts=[],
        )
        accounts = [{"account_name": "TESTBANK", "account_number": "999****", "status": ""}]
        classified = classify_accounts(accounts, text)
        assert "_text_position" not in classified[0]


class TestSectionPositionDirect:
    def test_account_before_adverse_section(self):
        boundaries = {"adverse_start": 100, "satisfactory_start": 500, "inquiries_start": 900}
        account = {"_text_position": 50}
        result = classify_by_section_position(account, boundaries)
        assert result is None

    def test_account_in_adverse_section(self):
        boundaries = {"adverse_start": 100, "satisfactory_start": 500, "inquiries_start": 900}
        account = {"_text_position": 300}
        result = classify_by_section_position(account, boundaries)
        assert result == "ADVERSE"

    def test_account_in_satisfactory_section(self):
        boundaries = {"adverse_start": 100, "satisfactory_start": 500, "inquiries_start": 900}
        account = {"_text_position": 700}
        result = classify_by_section_position(account, boundaries)
        assert result == "GOOD_STANDING"

    def test_account_after_inquiries(self):
        boundaries = {"adverse_start": 100, "satisfactory_start": 500, "inquiries_start": 900}
        account = {"_text_position": 1000}
        result = classify_by_section_position(account, boundaries)
        assert result is None

    def test_no_text_position(self):
        boundaries = {"adverse_start": 100, "satisfactory_start": 500, "inquiries_start": 900}
        account = {"_text_position": None}
        result = classify_by_section_position(account, boundaries)
        assert result is None

    def test_no_text_position_key(self):
        boundaries = {"adverse_start": 100, "satisfactory_start": 500, "inquiries_start": 900}
        account = {}
        result = classify_by_section_position(account, boundaries)
        assert result is None
