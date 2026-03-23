"""
850 Lab TransUnion Inquiry Extraction Tests

Phase 1.1 regression harness for inquiry boundary enforcement.

Tests:
- No inquiry.name equals city/state, "SUITE", "PHONE", "LOCATION"
- Every inquiry has requested_on date
- Every inquiry has inquiry_type (HARD/SOFT) and subsection_label
- Count sanity: not more than reasonable upper bound
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import re
from typing import Dict, List, Tuple


def get_value(field) -> any:
    """Extract value from a truth field or return as-is."""
    if isinstance(field, dict) and "value" in field:
        return field["value"]
    return field


FORBIDDEN_INQUIRY_NAMES = [
    "LOCATION",
    "PHONE",
    "SUITE",
    "APT",
    "UNIT",
    "REQUESTED ON",
    "INQUIRY TYPE",
    "PERMISSIBLE PURPOSE",
    "P.O. BOX",
    "PO BOX",
]

CITY_STATE_PATTERN = re.compile(
    r'^[A-Z][A-Z\s]+,\s*[A-Z]{2}(?:\s+\d{5}(?:-\d{4})?)?$',
    re.IGNORECASE
)

PHONE_PATTERN = re.compile(r'^\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$')


def validate_inquiry(inquiry: Dict, index: int, inquiry_type_expected: str) -> List[str]:
    """Validate a single inquiry record. Returns list of errors."""
    errors = []
    prefix = f"Inquiry #{index}"
    
    creditor_name = get_value(inquiry.get("creditor_name"))
    if not creditor_name:
        errors.append(f"{prefix}: Missing creditor_name")
    else:
        creditor_upper = creditor_name.upper().strip()
        
        for forbidden in FORBIDDEN_INQUIRY_NAMES:
            if creditor_upper == forbidden or creditor_upper.startswith(forbidden + " "):
                errors.append(f"{prefix}: Forbidden name '{creditor_name}' (starts with {forbidden})")
        
        if CITY_STATE_PATTERN.match(creditor_name.strip()):
            errors.append(f"{prefix}: Name looks like city/state: '{creditor_name}'")
        
        if PHONE_PATTERN.match(creditor_name.strip()):
            errors.append(f"{prefix}: Name looks like phone number: '{creditor_name}'")
    
    inquiry_date = get_value(inquiry.get("inquiry_date"))
    if not inquiry_date:
        errors.append(f"{prefix}: Missing inquiry_date (requested_on)")
    
    inquiry_type = get_value(inquiry.get("inquiry_type"))
    if not inquiry_type:
        errors.append(f"{prefix}: Missing inquiry_type")
    elif inquiry_type.upper() not in ("HARD", "SOFT"):
        errors.append(f"{prefix}: Invalid inquiry_type: '{inquiry_type}' (expected HARD or SOFT)")
    elif inquiry_type.upper() != inquiry_type_expected.upper():
        errors.append(f"{prefix}: inquiry_type mismatch: got '{inquiry_type}', expected '{inquiry_type_expected}'")
    
    subsection_label = get_value(inquiry.get("subsection_label"))
    if not subsection_label:
        errors.append(f"{prefix}: Missing subsection_label receipt")
    
    return errors


def validate_inquiries_section(inquiries_section: Dict, max_expected: int = 50) -> Tuple[bool, List[str]]:
    """
    Validate the entire inquiries section.
    
    Returns (passed, errors)
    """
    all_errors = []
    
    hard_inquiries = inquiries_section.get("hard_inquiries", [])
    soft_inquiries = inquiries_section.get("soft_inquiries", [])
    
    total_count = len(hard_inquiries) + len(soft_inquiries)
    
    if total_count > max_expected:
        all_errors.append(f"Count sanity failed: {total_count} inquiries exceeds max expected {max_expected}")
    
    for i, inq in enumerate(hard_inquiries):
        errors = validate_inquiry(inq, i, "HARD")
        all_errors.extend(errors)
    
    for i, inq in enumerate(soft_inquiries):
        errors = validate_inquiry(inq, i, "SOFT")
        all_errors.extend(errors)
    
    passed = len(all_errors) == 0
    return passed, all_errors


def create_test_inquiry_section() -> Dict:
    """Create a mock inquiries section for testing."""
    from lab_truth.truth_validator import create_truth_field, create_section_marker
    
    return {
        "_marker": create_section_marker(True, 3, 5, "Inquiries"),
        "hard_inquiries": [
            {
                "creditor_name": create_truth_field("CHASE BANK", "HIGH", 5, "Inquiries - REGULAR INQUIRIES", "CHASE BANK"),
                "inquiry_date": create_truth_field("01/15/2024", "HIGH", 5, "Inquiries - REGULAR INQUIRIES", "Requested On: 01/15/2024"),
                "inquiry_type": create_truth_field("HARD", "HIGH", 5, "Inquiries - REGULAR INQUIRIES", "Subsection: REGULAR INQUIRIES"),
                "subsection_label": create_truth_field("REGULAR INQUIRIES", "HIGH", 5, "Inquiries - REGULAR INQUIRIES", "Section header"),
            },
            {
                "creditor_name": create_truth_field("CAPITAL ONE", "HIGH", 5, "Inquiries - REGULAR INQUIRIES", "CAPITAL ONE"),
                "inquiry_date": create_truth_field("12/01/2023", "HIGH", 5, "Inquiries - REGULAR INQUIRIES", "Requested On: 12/01/2023"),
                "inquiry_type": create_truth_field("HARD", "HIGH", 5, "Inquiries - REGULAR INQUIRIES", "Subsection: REGULAR INQUIRIES"),
                "subsection_label": create_truth_field("REGULAR INQUIRIES", "HIGH", 5, "Inquiries - REGULAR INQUIRIES", "Section header"),
            },
        ],
        "soft_inquiries": [
            {
                "creditor_name": create_truth_field("CREDIT KARMA", "HIGH", 6, "Inquiries - REQUESTS VIEWED ONLY BY YOU", "CREDIT KARMA"),
                "inquiry_date": create_truth_field("11/20/2023", "HIGH", 6, "Inquiries - REQUESTS VIEWED ONLY BY YOU", "Requested On: 11/20/2023"),
                "inquiry_type": create_truth_field("SOFT", "HIGH", 6, "Inquiries - REQUESTS VIEWED ONLY BY YOU", "Subsection: REQUESTS VIEWED ONLY BY YOU"),
                "subsection_label": create_truth_field("REQUESTS VIEWED ONLY BY YOU", "HIGH", 6, "Inquiries - REQUESTS VIEWED ONLY BY YOU", "Section header"),
            },
        ],
    }


def create_bad_inquiry_section() -> Dict:
    """Create a mock inquiries section with known violations for negative testing."""
    from lab_truth.truth_validator import create_truth_field, create_section_marker
    
    return {
        "_marker": create_section_marker(True, 3, 5, "Inquiries"),
        "hard_inquiries": [
            {
                "creditor_name": create_truth_field("NEW YORK, NY", "HIGH", 5, "Inquiries", "NEW YORK, NY"),
                "inquiry_date": create_truth_field("01/15/2024", "HIGH", 5, "Inquiries", "01/15/2024"),
                "inquiry_type": create_truth_field("HARD", "HIGH", 5, "Inquiries", "HARD"),
                "subsection_label": create_truth_field("REGULAR INQUIRIES", "HIGH", 5, "Inquiries", "Section header"),
            },
            {
                "creditor_name": create_truth_field("SUITE 100", "HIGH", 5, "Inquiries", "SUITE 100"),
                "inquiry_date": create_truth_field("12/01/2023", "HIGH", 5, "Inquiries", "12/01/2023"),
                "inquiry_type": create_truth_field("HARD", "HIGH", 5, "Inquiries", "HARD"),
                "subsection_label": create_truth_field("REGULAR INQUIRIES", "HIGH", 5, "Inquiries", "Section header"),
            },
            {
                "creditor_name": create_truth_field("CHASE BANK", "HIGH", 5, "Inquiries", "CHASE BANK"),
                "inquiry_type": create_truth_field("HARD", "HIGH", 5, "Inquiries", "HARD"),
            },
        ],
        "soft_inquiries": [],
    }


def run_tests():
    """Run all inquiry validation tests."""
    print("=" * 70)
    print("850 Lab TransUnion Inquiry Extraction - Regression Tests")
    print("=" * 70)
    
    all_passed = True
    
    print("\nTest 1: Valid inquiry section should pass...")
    good_section = create_test_inquiry_section()
    passed, errors = validate_inquiries_section(good_section)
    if passed:
        print("  ✓ PASSED: Valid inquiries accepted")
    else:
        print("  ✗ FAILED: Valid inquiries rejected")
        for e in errors:
            print(f"    - {e}")
        all_passed = False
    
    print("\nTest 2: Bad inquiry section should fail...")
    bad_section = create_bad_inquiry_section()
    passed, errors = validate_inquiries_section(bad_section)
    if not passed:
        print("  ✓ PASSED: Bad inquiries correctly rejected")
        print(f"    Detected {len(errors)} errors (expected)")
    else:
        print("  ✗ FAILED: Bad inquiries incorrectly accepted")
        all_passed = False
    
    print("\nTest 3: Forbidden name detection...")
    test_cases = [
        ("NEW YORK, NY", True, "city/state"),
        ("LOCATION 123 MAIN ST", True, "LOCATION prefix"),
        ("PHONE", True, "PHONE prefix"),
        ("SUITE 100", True, "SUITE prefix"),
        ("CHASE BANK", False, "valid creditor"),
        ("CAPITAL ONE AUTO FINANCE", False, "valid creditor"),
        ("ABC LENDING CORP", False, "valid creditor"),
        ("(555) 123-4567", True, "phone number"),
    ]
    
    all_name_tests_passed = True
    for name, should_be_forbidden, reason in test_cases:
        name_upper = name.upper().strip()
        
        has_forbidden_prefix = any(name_upper.startswith(f) or name_upper == f for f in FORBIDDEN_INQUIRY_NAMES)
        is_city_state = bool(CITY_STATE_PATTERN.match(name.strip()))
        is_phone = bool(PHONE_PATTERN.match(name.strip()))
        
        is_forbidden = has_forbidden_prefix or is_city_state or is_phone
        
        if is_forbidden == should_be_forbidden:
            print(f"  ✓ '{name}' -> {'forbidden' if is_forbidden else 'allowed'} ({reason})")
        else:
            print(f"  ✗ '{name}' -> expected {'forbidden' if should_be_forbidden else 'allowed'}, got opposite (prefix={has_forbidden_prefix}, city={is_city_state}, phone={is_phone})")
            all_name_tests_passed = False
    
    if not all_name_tests_passed:
        all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("ALL TESTS PASSED")
        return 0
    else:
        print("SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = run_tests()
    exit(exit_code)
