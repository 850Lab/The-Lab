"""
850 Lab Equifax Handler

Philosophy:
    - If we don't fully support it yet, we say so clearly
    - Partial truth is worse than no truth
    - No guessing, no parsing with incomplete patterns

This handler runs after Bureau ID Gate passes with EQUIFAX.
It does NOT attempt to parse Equifax sections yet.
"""

import re
import sys
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from lab_truth.truth_validator import (
        create_truth_field,
        create_not_found_field,
        create_section_marker,
        create_empty_marked_array,
        validate_truth_sheet,
        MismatchAlert
    )
    from lab_truth.bureau_detector import gate_check, Bureau
else:
    from ..truth_validator import (
        create_truth_field,
        create_not_found_field,
        create_section_marker,
        create_empty_marked_array,
        validate_truth_sheet,
        MismatchAlert
    )
    from ..bureau_detector import gate_check, Bureau


@dataclass
class HandlerResult:
    """Result of handling an Equifax report."""
    success: bool
    truth_sheet: Optional[Dict]
    errors: List[str]
    red_light: bool
    red_light_reason: Optional[str]
    support_status: str


def _create_not_supported_field() -> Dict:
    """Create a field marked as not supported yet using valid NOT_FOUND format."""
    return create_not_found_field()


def _create_not_supported_array(section_name: str = None) -> Dict:
    """Create an array section marked as not supported yet."""
    return create_empty_marked_array(False, None, section_name)


class EquifaxHandler:
    """
    Handles Equifax reports without attempting to parse them.
    
    Equifax scanning is not yet active. This handler:
    - Confirms the report is from Equifax
    - Returns a structured Truth Sheet with all sections marked NOT_SUPPORTED_YET
    - Triggers a non-crashing Red Light to inform the user
    
    Why we don't parse yet:
    - Equifax has different layouts than TransUnion and Experian
    - We need verified Equifax patterns before we can extract truthfully
    - Guessing would violate the "no guessing" rule
    """
    
    SUPPORT_STATUS = "NOT_SUPPORTED_YET"
    
    def __init__(self, raw_text: str, page_texts: List[Dict] = None):
        """
        Initialize the handler with raw report text.
        
        Args:
            raw_text: Full extracted text from the report
            page_texts: Optional list of {page_number, text} for receipt tracking
        """
        self.raw_text = raw_text
        self.page_texts = page_texts or []
    
    def _extract_snippet(self, match_start: int, match_end: int, context: int = 30) -> str:
        """Extract a snippet around a match for the receipt."""
        start = max(0, match_start - context)
        end = min(len(self.raw_text), match_end + context)
        snippet = self.raw_text[start:end].strip()
        snippet = re.sub(r'\s+', ' ', snippet)
        if start > 0:
            snippet = "..." + snippet
        if end < len(self.raw_text):
            snippet = snippet + "..."
        return snippet[:150]
    
    def _build_not_supported_identity(self) -> Dict:
        """Build consumer identity section marked as not supported."""
        return {
            "full_name": _create_not_supported_field(),
            "ssn_last_four": _create_not_supported_field(),
            "date_of_birth": _create_not_supported_field(),
            "current_address": _create_not_supported_field(),
            "previous_addresses": _create_not_supported_array("Previous Addresses"),
            "phone_numbers": _create_not_supported_array("Phone Numbers"),
            "aka_names": _create_not_supported_array("AKA Names"),
        }
    
    def _build_not_supported_scores(self) -> Dict:
        """Build credit scores section marked as not supported."""
        return {
            "score": _create_not_supported_field(),
            "score_model": _create_not_supported_field(),
            "score_range": _create_not_supported_field(),
            "score_factors": _create_not_supported_array("Score Factors"),
        }
    
    def _build_not_supported_inquiries(self) -> Dict:
        """Build inquiries section marked as not supported."""
        return {
            "_marker": create_section_marker(False, 0, None, "Inquiries"),
            "hard_inquiries": [],
            "soft_inquiries": []
        }
    
    def _build_not_supported_alerts(self) -> Dict:
        """Build alerts section marked as not supported."""
        return {
            "fraud_alerts": _create_not_supported_array("Fraud Alerts"),
            "active_duty_alerts": _create_not_supported_array("Active Duty Alerts"),
            "freeze_status": _create_not_supported_field(),
        }
    
    def handle(self, bureau_gate_result: Dict = None) -> HandlerResult:
        """
        Handle the Equifax report.
        
        This does NOT parse the report. It returns a structured Truth Sheet
        with all sections marked as NOT_SUPPORTED_YET.
        
        Args:
            bureau_gate_result: Result from gate_check(). If not provided,
                                will run the gate check internally.
        
        Returns:
            HandlerResult with Truth Sheet and support status info.
        """
        if bureau_gate_result is None:
            bureau_gate_result = gate_check(self.raw_text)
        
        if not bureau_gate_result["passed"]:
            return HandlerResult(
                success=False,
                truth_sheet=None,
                errors=[bureau_gate_result["error"]["reason"]],
                red_light=True,
                red_light_reason=bureau_gate_result["error"]["reason"],
                support_status="GATE_FAILED"
            )
        
        if bureau_gate_result["bureau"] != "EQUIFAX":
            return HandlerResult(
                success=False,
                truth_sheet=None,
                errors=[f"Wrong handler: This is a {bureau_gate_result['bureau']} report, not Equifax."],
                red_light=True,
                red_light_reason=f"This handler is for Equifax only. This report is from {bureau_gate_result['bureau']}.",
                support_status="WRONG_BUREAU"
            )
        
        report_date_match = re.search(
            r"(?:Report\s+Date|Date\s+(?:of\s+)?Report|As\s+of)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            self.raw_text, re.IGNORECASE
        )
        
        truth_sheet = {
            "meta": {
                "bureau": bureau_gate_result["truth_field"],
                "report_date": create_truth_field(
                    report_date_match.group(1), "HIGH", "1", "Header",
                    self._extract_snippet(report_date_match.start(), report_date_match.end())
                ) if report_date_match else _create_not_supported_field(),
                "file_id": _create_not_supported_field(),
                "report_type": _create_not_supported_field(),
                "scanned_at": datetime.now().isoformat(),
            },
            "consumer_identity": self._build_not_supported_identity(),
            "employment": _create_not_supported_array("Employment"),
            "credit_scores": self._build_not_supported_scores(),
            "accounts": _create_not_supported_array("Accounts"),
            "inquiries": self._build_not_supported_inquiries(),
            "public_records": _create_not_supported_array("Public Records"),
            "collections": _create_not_supported_array("Collections"),
            "consumer_statements": _create_not_supported_array("Consumer Statements"),
            "alerts": self._build_not_supported_alerts(),
        }
        
        try:
            validate_truth_sheet(truth_sheet)
        except MismatchAlert as e:
            return HandlerResult(
                success=False,
                truth_sheet=truth_sheet,
                errors=[str(e)],
                red_light=True,
                red_light_reason=f"Truth Sheet validation failed. {e.message}",
                support_status="VALIDATION_FAILED"
            )
        
        red_light_message = (
            "Equifax scanning is not yet active. "
            "We identified this as an Equifax report, but we cannot extract data from it yet. "
            "No guessing — we only scan what we can verify."
        )
        
        return HandlerResult(
            success=True,
            truth_sheet=truth_sheet,
            errors=[],
            red_light=True,
            red_light_reason=red_light_message,
            support_status=self.SUPPORT_STATUS
        )


def handle_equifax_report(raw_text: str, page_texts: List[Dict] = None) -> HandlerResult:
    """
    Convenience function to handle an Equifax report.
    
    Note: This does NOT parse the report. Equifax scanning is not yet active.
    
    Args:
        raw_text: Full extracted text from the report
        page_texts: Optional list of {page_number, text} for receipt tracking
        
    Returns:
        HandlerResult with Truth Sheet and support status info
    """
    handler = EquifaxHandler(raw_text, page_texts)
    return handler.handle()


if __name__ == "__main__":
    test_report = """
    Equifax Credit Report
    Equifax Information Services LLC
    
    Report Date: 01/25/2024
    P.O. Box 740241, Atlanta, GA 30374
    equifax.com
    
    Personal Information
    Name: ROBERT JAMES WILSON
    SSN: XXX-XX-9012
    Date of Birth: 05/15/1985
    
    Credit Accounts
    
    WELLS FARGO BANK
    Account Number: XXXX-1234
    Balance: $5,000
    Status: Open
    
    Inquiries
    
    CHASE BANK 01/15/2024
    
    Public Records
    None on file
    """
    
    result = handle_equifax_report(test_report)
    
    print("Equifax Handler Test")
    print("=" * 50)
    print(f"Success: {result.success}")
    print(f"Red Light: {result.red_light}")
    print(f"Support Status: {result.support_status}")
    
    if result.truth_sheet:
        ts = result.truth_sheet
        print(f"\nBureau: {ts['meta']['bureau']['value']}")
        print(f"Report Date: {ts['meta']['report_date']['value']}")
        print(f"Name: {ts['consumer_identity']['full_name']['value']}")
        print(f"Score: {ts['credit_scores']['score']['value']}")
        print(f"Accounts: {ts['accounts']['_marker'].get('support_status', 'N/A')}")
    
    print(f"\nRed Light Message:")
    print(f"  {result.red_light_reason}")
