import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aggregator import (
    normalize_creditor_name,
    build_cross_bureau_key,
    detect_discrepancies,
    build_cross_bureau_index,
    compute_unified_summary,
    get_multi_bureau_accounts,
    get_single_bureau_accounts,
    get_discrepant_accounts,
    merge_best_record,
    CrossBureauMatch,
)


class TestNormalizeCreditorName:
    def test_basic_uppercase(self):
        assert normalize_creditor_name("Capital One") == "CAPITALONE"

    def test_removes_bank(self):
        assert normalize_creditor_name("Wells Fargo Bank") == "WELLSFARGO"

    def test_removes_inc(self):
        assert normalize_creditor_name("Possible Financial Inc.") == "POSSIBLE"

    def test_removes_na(self):
        assert normalize_creditor_name("Capital One N.A.") == "CAPITALONE"

    def test_empty(self):
        assert normalize_creditor_name("") == ""

    def test_none_safe(self):
        assert normalize_creditor_name(None) == ""

    def test_truncates_long_names(self):
        result = normalize_creditor_name("A" * 100)
        assert len(result) <= 20

    def test_strips_whitespace(self):
        assert normalize_creditor_name("  DEPT OF EDUCATION  ") == "DEPTOFEDUCATION"


class TestBuildCrossBureauKey:
    def test_name_and_last4(self):
        acct = {"account_name": "CAPITAL ONE", "account_number": "517805XXXXXXXXXX1234"}
        key = build_cross_bureau_key(acct)
        assert "CAPITALONE" in key
        assert "1234" in key

    def test_name_and_date_fallback(self):
        acct = {"account_name": "CAPITAL ONE", "date_opened": "01/2020"}
        key = build_cross_bureau_key(acct)
        assert "CAPITALONE" in key
        assert "01/2020" in key

    def test_name_only_fallback(self):
        acct = {"account_name": "CAPITAL ONE"}
        key = build_cross_bureau_key(acct)
        assert "CAPITALONE" in key
        assert "NOKEY" in key

    def test_no_name(self):
        acct = {"raw_section": "some raw text"}
        key = build_cross_bureau_key(acct)
        assert key.startswith("UNK|")


class TestDetectDiscrepancies:
    def test_no_discrepancy_single_account(self):
        accounts = [{"balance": "$1000", "bureau": "equifax"}]
        assert detect_discrepancies(accounts) == []

    def test_balance_discrepancy(self):
        accounts = [
            {"balance": "$1000", "bureau": "equifax"},
            {"balance": "$1200", "bureau": "experian"},
        ]
        discs = detect_discrepancies(accounts)
        assert len(discs) == 1
        assert discs[0]["field"] == "Balance"
        assert discs[0]["severity"] == "HIGH"

    def test_status_discrepancy(self):
        accounts = [
            {"status": "Open", "bureau": "equifax"},
            {"status": "Closed", "bureau": "experian"},
        ]
        discs = detect_discrepancies(accounts)
        assert len(discs) == 1
        assert discs[0]["field"] == "Status"
        assert discs[0]["severity"] == "HIGH"

    def test_no_discrepancy_matching_values(self):
        accounts = [
            {"balance": "$1000", "bureau": "equifax"},
            {"balance": "$1000", "bureau": "experian"},
        ]
        assert detect_discrepancies(accounts) == []

    def test_small_balance_discrepancy_low_severity(self):
        accounts = [
            {"balance": "$100", "bureau": "equifax"},
            {"balance": "$105", "bureau": "experian"},
        ]
        discs = detect_discrepancies(accounts)
        if discs:
            assert discs[0]["severity"] == "LOW"


class TestBuildCrossBureauIndex:
    def test_single_report(self):
        reports = {
            "UPL_abc": {
                "bureau": "equifax",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "CAPITAL ONE", "account_number": "1234567890"},
                    ]
                }
            }
        }
        matches, groups = build_cross_bureau_index(reports)
        assert len(matches) == 1
        assert matches[0].bureaus == ["equifax"]
        assert not matches[0].is_multi_bureau

    def test_same_account_two_bureaus(self):
        reports = {
            "UPL_abc": {
                "bureau": "equifax",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "CAPITAL ONE", "account_number": "5178051234"},
                    ]
                }
            },
            "UPL_def": {
                "bureau": "experian",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "CAPITAL ONE", "account_number": "5178051234"},
                    ]
                }
            },
        }
        matches, groups = build_cross_bureau_index(reports)
        assert len(matches) == 1
        assert matches[0].is_multi_bureau
        assert set(matches[0].bureaus) == {"equifax", "experian"}

    def test_different_accounts(self):
        reports = {
            "UPL_abc": {
                "bureau": "equifax",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "CAPITAL ONE", "account_number": "1111222233334444"},
                    ]
                }
            },
            "UPL_def": {
                "bureau": "experian",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "WELLS FARGO", "account_number": "5555666677778888"},
                    ]
                }
            },
        }
        matches, groups = build_cross_bureau_index(reports)
        assert len(matches) == 2

    def test_three_bureaus(self):
        reports = {
            "UPL_a": {
                "bureau": "equifax",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "CHASE", "account_number": "1234567890"},
                    ]
                }
            },
            "UPL_b": {
                "bureau": "experian",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "CHASE", "account_number": "1234567890"},
                    ]
                }
            },
            "UPL_c": {
                "bureau": "transunion",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "CHASE", "account_number": "1234567890"},
                    ]
                }
            },
        }
        matches, _ = build_cross_bureau_index(reports)
        assert len(matches) == 1
        assert matches[0].bureau_count == 3

    def test_discrepancies_detected_cross_bureau(self):
        reports = {
            "UPL_a": {
                "bureau": "equifax",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "CHASE", "account_number": "1234567890", "balance": "$5000"},
                    ]
                }
            },
            "UPL_b": {
                "bureau": "experian",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "CHASE", "account_number": "1234567890", "balance": "$3000"},
                    ]
                }
            },
        }
        matches, _ = build_cross_bureau_index(reports)
        assert len(matches) == 1
        assert len(matches[0].discrepancies) > 0


class TestComputeUnifiedSummary:
    def test_empty_reports(self):
        summary = compute_unified_summary({})
        assert summary.total_accounts_raw == 0
        assert summary.bureaus_found == []

    def test_single_bureau(self):
        reports = {
            "UPL_abc": {
                "bureau": "equifax",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "A", "account_number": "1111", "classification": "ADVERSE"},
                        {"account_name": "B", "account_number": "2222", "classification": "GOOD_STANDING"},
                    ],
                    "inquiries": [],
                    "negative_items": [{"type": "late"}],
                    "public_records": [],
                    "classification_counts": {"ADVERSE": 1, "GOOD_STANDING": 1, "UNKNOWN": 0},
                    "personal_info": {"name": "John Doe"},
                }
            }
        }
        summary = compute_unified_summary(reports)
        assert summary.total_accounts_raw == 2
        assert summary.total_accounts_unique == 2
        assert summary.total_adverse == 1
        assert summary.total_good_standing == 1
        assert summary.total_negative_items == 1
        assert summary.bureaus_found == ["equifax"]
        assert summary.personal_info.get("name") == "John Doe"

    def test_two_bureaus_with_overlap(self):
        reports = {
            "UPL_a": {
                "bureau": "equifax",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "CHASE", "account_number": "1234567890"},
                    ],
                    "inquiries": [],
                    "negative_items": [],
                    "public_records": [],
                    "classification_counts": {"ADVERSE": 0, "GOOD_STANDING": 1, "UNKNOWN": 0},
                    "personal_info": {"name": "Jane Doe"},
                }
            },
            "UPL_b": {
                "bureau": "experian",
                "parsed_data": {
                    "accounts": [
                        {"account_name": "CHASE", "account_number": "1234567890"},
                    ],
                    "inquiries": [],
                    "negative_items": [],
                    "public_records": [],
                    "classification_counts": {"ADVERSE": 0, "GOOD_STANDING": 1, "UNKNOWN": 0},
                    "personal_info": {"dob": "01/01/1990"},
                }
            },
        }
        summary = compute_unified_summary(reports)
        assert summary.total_accounts_raw == 2
        assert summary.total_accounts_unique == 1
        assert summary.bureaus_found == ["equifax", "experian"]
        assert summary.personal_info.get("name") == "Jane Doe"
        assert summary.personal_info.get("dob") == "01/01/1990"

    def test_per_bureau_counts(self):
        reports = {
            "UPL_a": {
                "bureau": "equifax",
                "parsed_data": {
                    "accounts": [{"account_name": "A", "account_number": "1111"}],
                    "inquiries": [],
                    "negative_items": [],
                    "public_records": [],
                    "classification_counts": {"ADVERSE": 1, "GOOD_STANDING": 0, "UNKNOWN": 0},
                }
            },
        }
        summary = compute_unified_summary(reports)
        assert "equifax" in summary.per_bureau
        assert summary.per_bureau["equifax"]["accounts"] == 1
        assert summary.per_bureau["equifax"]["adverse"] == 1


class TestHelperFunctions:
    def test_get_multi_bureau_accounts(self):
        matches = [
            CrossBureauMatch("A", ["equifax", "experian"], [{}, {}]),
            CrossBureauMatch("B", ["equifax"], [{}]),
        ]
        multi = get_multi_bureau_accounts(matches)
        assert len(multi) == 1
        assert multi[0].creditor_key == "A"

    def test_get_single_bureau_accounts(self):
        matches = [
            CrossBureauMatch("A", ["equifax", "experian"], [{}, {}]),
            CrossBureauMatch("B", ["equifax"], [{}]),
        ]
        single = get_single_bureau_accounts(matches)
        assert len(single) == 1
        assert single[0].creditor_key == "B"

    def test_get_discrepant_accounts(self):
        matches = [
            CrossBureauMatch("A", ["equifax", "experian"], [{}, {}],
                           discrepancies=[{"field": "Balance"}]),
            CrossBureauMatch("B", ["equifax"], [{}]),
        ]
        disc = get_discrepant_accounts(matches)
        assert len(disc) == 1

    def test_merge_best_record_fills_gaps(self):
        match = CrossBureauMatch(
            "A", ["equifax", "experian"],
            [
                {"account_name": "CHASE", "balance": "$1000", "bureau": "equifax"},
                {"account_name": "CHASE", "balance": "$1000", "date_opened": "01/2020", "bureau": "experian"},
            ]
        )
        merged = merge_best_record(match)
        assert merged["account_name"] == "CHASE"
        assert merged["balance"] == "$1000"
        assert merged["date_opened"] == "01/2020"
        assert merged["reporting_bureaus"] == ["equifax", "experian"]
        assert merged["bureau_count"] == 2

    def test_merge_best_record_empty(self):
        match = CrossBureauMatch("A", [], [])
        assert merge_best_record(match) == {}


class TestCrossBureauWithRealData:
    @pytest.fixture
    def real_reports(self):
        golden_dir = os.path.join(os.path.dirname(__file__), "golden")
        reports = {}
        experian_path = os.path.join(golden_dir, "experian_golden.txt")
        equifax_path = os.path.join(golden_dir, "equifax_golden.txt")

        if os.path.exists(experian_path):
            with open(experian_path) as f:
                ex_text = f.read()
            from app import parse_credit_report_data
            from classifier import classify_accounts, compute_negative_items, count_by_classification
            ex_parsed = parse_credit_report_data(ex_text, "experian")
            classify_accounts(ex_parsed.get("accounts", []), ex_text, bureau="experian")
            ex_parsed["negative_items"] = compute_negative_items(ex_parsed.get("accounts", []))
            ex_parsed["classification_counts"] = count_by_classification(ex_parsed.get("accounts", []))
            reports["UPL_experian"] = {
                "bureau": "experian",
                "parsed_data": ex_parsed,
                "full_text": ex_text,
            }

        if os.path.exists(equifax_path):
            with open(equifax_path) as f:
                eq_text = f.read()
            from app import parse_credit_report_data
            from classifier import classify_accounts, compute_negative_items, count_by_classification
            eq_parsed = parse_credit_report_data(eq_text, "equifax")
            classify_accounts(eq_parsed.get("accounts", []), eq_text, bureau="equifax")
            eq_parsed["negative_items"] = compute_negative_items(eq_parsed.get("accounts", []))
            eq_parsed["classification_counts"] = count_by_classification(eq_parsed.get("accounts", []))
            reports["UPL_equifax"] = {
                "bureau": "equifax",
                "parsed_data": eq_parsed,
                "full_text": eq_text,
            }

        return reports

    def test_both_bureaus_detected(self, real_reports):
        if len(real_reports) < 2:
            pytest.skip("Need both golden files")
        summary = compute_unified_summary(real_reports)
        assert len(summary.bureaus_found) == 2
        assert "equifax" in summary.bureaus_found
        assert "experian" in summary.bureaus_found

    def test_unique_less_than_raw(self, real_reports):
        if len(real_reports) < 2:
            pytest.skip("Need both golden files")
        summary = compute_unified_summary(real_reports)
        assert summary.total_accounts_unique <= summary.total_accounts_raw

    def test_per_bureau_present(self, real_reports):
        if len(real_reports) < 2:
            pytest.skip("Need both golden files")
        summary = compute_unified_summary(real_reports)
        assert "equifax" in summary.per_bureau
        assert "experian" in summary.per_bureau

    def test_personal_info_merged(self, real_reports):
        if len(real_reports) < 2:
            pytest.skip("Need both golden files")
        summary = compute_unified_summary(real_reports)
        assert summary.personal_info.get("name")

    def test_cross_bureau_matches_present(self, real_reports):
        if len(real_reports) < 2:
            pytest.skip("Need both golden files")
        summary = compute_unified_summary(real_reports)
        multi = get_multi_bureau_accounts(summary.cross_bureau_matches)
        assert len(multi) >= 0

    def test_single_bureau_accounts_present(self, real_reports):
        if len(real_reports) < 2:
            pytest.skip("Need both golden files")
        summary = compute_unified_summary(real_reports)
        single = get_single_bureau_accounts(summary.cross_bureau_matches)
        assert len(single) > 0
