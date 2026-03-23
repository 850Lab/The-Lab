"""
========================================================================
REGRESSION TEST — TransUnion Account Parser Variants
========================================================================
Validates that both TU_OSC and TU_ACR variants produce non-zero accounts.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re


def _load_parsers():
    from app import (
        detect_tu_variant,
        parse_accounts_transunion_osc,
        parse_accounts_tu_acr,
        parse_accounts,
        detect_bureau,
    )
    return {
        'detect_tu_variant': detect_tu_variant,
        'parse_accounts_transunion_osc': parse_accounts_transunion_osc,
        'parse_accounts_tu_acr': parse_accounts_tu_acr,
        'parse_accounts': parse_accounts,
        'detect_bureau': detect_bureau,
    }


def test_detect_tu_variant_osc():
    funcs = _load_parsers()
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'tu_osc_sample.txt')
    with open(fixture_path, 'r') as f:
        text = f.read()
    variant = funcs['detect_tu_variant'](text)
    assert variant == 'TU_OSC', f"Expected TU_OSC, got {variant}"


def test_detect_tu_variant_acr():
    funcs = _load_parsers()
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'tu_acr_sample.txt')
    with open(fixture_path, 'r') as f:
        text = f.read()
    variant = funcs['detect_tu_variant'](text)
    assert variant == 'TU_ACR', f"Expected TU_ACR, got {variant}"


def test_detect_tu_variant_unknown():
    funcs = _load_parsers()
    text = "TransUnion Credit Report\nSome generic text without specific markers"
    variant = funcs['detect_tu_variant'](text)
    assert variant == 'TU_UNKNOWN', f"Expected TU_UNKNOWN, got {variant}"


def test_osc_fixture_accounts():
    funcs = _load_parsers()
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'tu_osc_sample.txt')
    with open(fixture_path, 'r') as f:
        text = f.read()
    accounts, rejects = funcs['parse_accounts'](text, 'transunion')
    assert len(accounts) >= 1, f"OSC fixture: expected >= 1 accounts, got {len(accounts)}"
    names = [a.get('account_name', '') for a in accounts]
    print(f"  OSC accounts: {len(accounts)}: {names}")


def test_acr_fixture_accounts():
    funcs = _load_parsers()
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'tu_acr_sample.txt')
    with open(fixture_path, 'r') as f:
        text = f.read()
    accounts, rejects = funcs['parse_accounts'](text, 'transunion')
    assert len(accounts) >= 1, f"ACR fixture: expected >= 1 accounts, got {len(accounts)}"
    names = [a.get('account_name', '') for a in accounts]
    print(f"  ACR accounts: {len(accounts)}: {names}")


def test_acr_golden_full_parse():
    """Test the full golden text file for ACR format."""
    funcs = _load_parsers()
    golden_path = os.path.join(os.path.dirname(__file__), 'golden', 'transunion_golden.txt')
    if not os.path.exists(golden_path):
        print("SKIP: golden text not found")
        return
    with open(golden_path, 'r') as f:
        text = f.read()

    variant = funcs['detect_tu_variant'](text)
    assert variant == 'TU_ACR', f"Expected TU_ACR for golden, got {variant}"

    accounts, rejects = funcs['parse_accounts'](text, 'transunion')
    assert len(accounts) >= 10, f"Golden ACR: expected >= 10 accounts, got {len(accounts)}"
    print(f"  Golden ACR accounts: {len(accounts)}")

    for acct in accounts:
        assert acct.get('account_name'), f"Account missing account_name: {acct}"


def test_osc_does_not_regress():
    """Ensure OSC parser still works independently."""
    funcs = _load_parsers()
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'tu_osc_sample.txt')
    with open(fixture_path, 'r') as f:
        text = f.read()
    accounts, rejects = funcs['parse_accounts_transunion_osc'](text)
    assert len(accounts) >= 1, f"OSC parser regression: expected >= 1 accounts, got {len(accounts)}"
    for acct in accounts:
        assert acct.get('account_name'), "Account missing account_name"
        assert acct.get('balance') is not None or acct.get('status') is not None, \
            f"Account {acct.get('account_name')} missing both balance and status"


def test_routing_selects_correct_parser():
    """Verify that parse_accounts routes to correct parser based on variant."""
    funcs = _load_parsers()

    osc_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'tu_osc_sample.txt')
    acr_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'tu_acr_sample.txt')

    with open(osc_path, 'r') as f:
        osc_text = f.read()
    with open(acr_path, 'r') as f:
        acr_text = f.read()

    osc_accounts, _ = funcs['parse_accounts'](osc_text, 'transunion')
    acr_accounts, _ = funcs['parse_accounts'](acr_text, 'transunion')

    assert len(osc_accounts) >= 1, "Routing: OSC accounts must be >= 1"
    assert len(acr_accounts) >= 1, "Routing: ACR accounts must be >= 1"


if __name__ == '__main__':
    tests = [
        test_detect_tu_variant_osc,
        test_detect_tu_variant_acr,
        test_detect_tu_variant_unknown,
        test_osc_fixture_accounts,
        test_acr_fixture_accounts,
        test_acr_golden_full_parse,
        test_osc_does_not_regress,
        test_routing_selects_correct_parser,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'='*60}")
    sys.exit(0 if failed == 0 else 1)
