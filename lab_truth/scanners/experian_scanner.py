"""
850 Lab Experian Report Scanner

Philosophy:
    - Same Truth Sheet, different layout
    - Structure changes, truth rules do not
    - If it's not clearly on the report → NOT_FOUND
    - Every value has receipts

This scanner ONLY runs after Bureau ID Gate passes with EXPERIAN.
"""

import re
import sys
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
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
class ScanResult:
    """Result of scanning an Experian report."""
    success: bool
    truth_sheet: Optional[Dict]
    errors: List[str]
    red_light: bool
    red_light_reason: Optional[str]


class ExperianScanner:
    """
    Scans Experian credit reports and outputs Truth Sheet format.
    
    This scanner is Experian-specific. It knows Experian's layout,
    headers, and patterns. Do not use this for TransUnion or Equifax.
    
    Experian Layout Notes:
    - Uses "Creditor Name" not "Subscriber Name"
    - Inquiry sections: "Requests Viewed by Others" (hard) vs "Requests Viewed Only By You" (soft)
    - Different date formats and field labels
    """
    
    SECTION_HEADERS = {
        "personal_info": [
            r"Personal\s+Information",
            r"Identifying\s+Information",
            r"Personal\s+Profile",
            r"Consumer\s+Identity",
        ],
        "employment": [
            r"Employment\s+(?:Information|History|Data)",
            r"Employer\s+(?:Information|History)",
        ],
        "credit_score": [
            r"(?:FICO|Credit|Experian)\s*Score",
            r"Score\s+(?:Summary|Information)",
            r"Your\s+Credit\s+Score",
        ],
        "accounts": [
            r"Credit\s+(?:Items|Accounts)",
            r"Account\s+(?:Information|History)",
            r"Trade\s*lines?",
            r"Accounts\s+in\s+Good\s+Standing",
            r"(?:Open|Closed)\s+Accounts",
        ],
        "hard_inquiries": [
            r"Requests\s+Viewed\s+by\s+Others",
            r"Regular\s+Inquiries",
            r"Hard\s+Inquiries",
            r"Credit\s+Inquiries",
        ],
        "soft_inquiries": [
            r"Requests\s+Viewed\s+Only\s+By\s+You",
            r"Promotional\s+Inquiries",
            r"Soft\s+Inquiries",
            r"Inquiries\s+(?:That\s+)?Do\s+Not\s+(?:Affect|Impact)",
        ],
        "public_records": [
            r"Public\s+Records?",
            r"Public\s+Information",
            r"Court\s+Records?",
        ],
        "collections": [
            r"Collection\s+(?:Accounts?|Information)",
            r"Accounts?\s+(?:in\s+)?Collection",
            r"Collection\s+Agency",
        ],
        "consumer_statements": [
            r"Consumer\s+Statement",
            r"Statement\s+(?:on\s+)?File",
            r"Personal\s+Statement",
        ],
        "alerts": [
            r"(?:Fraud|Security)\s+Alert",
            r"Active\s+Duty\s+Alert",
            r"Security\s+Freeze",
            r"Credit\s+Lock",
        ],
    }
    
    PERSONAL_INFO_PATTERNS = {
        "full_name": [
            r"(?:Name|Consumer)[:\s]+([A-Z][A-Z\s,.-]+)",
            r"^([A-Z][A-Z\s]+)\s*\n",
        ],
        "ssn_last_four": [
            r"(?:SSN|Social)[:\s#]*(?:XXX-XX-|[\d*X-]+)?(\d{4})",
            r"(?:Last\s+(?:4|Four))[:\s]+(\d{4})",
        ],
        "date_of_birth": [
            r"(?:DOB|Date\s+of\s+Birth|Year\s+of\s+Birth)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4})",
            r"(?:Birth)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
        "current_address": [
            r"(?:Current\s+)?Address[:\s]+(.+?)(?:\n|Reported|Date)",
            r"(?:Residence|Home)[:\s]+(.+?)(?:\n|$)",
        ],
    }
    
    ACCOUNT_PATTERNS = {
        "creditor_name": [
            r"(?:Creditor|Account)\s*(?:Name)?[:\s]+([A-Z0-9][A-Z0-9\s&.,/-]+)",
            r"^([A-Z][A-Z0-9\s&.,/-]+)(?:\n|Account)",
        ],
        "account_number": [
            r"(?:Account|Acct)\s*(?:Number|#|No\.?)[:\s]+([A-Z0-9*X-]+)",
        ],
        "account_type": [
            r"(?:Type\s+of\s+Account|Account\s+Type|Type)[:\s]+(\w+(?:\s+\w+)?)",
        ],
        "account_status": [
            r"(?:Status|Account\s+Status)[:\s]+(\w+(?:\s+\w+)?)",
            r"(?:Condition)[:\s]+(\w+)",
        ],
        "responsibility": [
            r"(?:Responsibility|Account\s+Ownership)[:\s]+(Individual|Joint|Authorized|Co-?signer)",
            r"(?:Terms)[:\s]+(Individual|Joint)",
        ],
        "date_opened": [
            r"(?:Open\s+Date|Date\s+Opened|Opened)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
        "date_closed": [
            r"(?:Close\s+Date|Date\s+Closed|Closed)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
        "date_last_active": [
            r"(?:Last\s+Activity|Date\s+of\s+Last\s+Activity)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
        "date_first_delinquency": [
            r"(?:First\s+Delinquency|Date\s+of\s+First\s+Delinquency|DOFD)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
        "credit_limit": [
            r"(?:Credit\s+Limit|Highest\s+Credit)[:\s]+\$?([\d,]+)",
        ],
        "high_balance": [
            r"(?:High(?:est)?\s+Balance|Original\s+Amount)[:\s]+\$?([\d,]+)",
        ],
        "current_balance": [
            r"(?:Balance(?:\s+Owed)?|Current\s+Balance)[:\s]+\$?([\d,]+)",
        ],
        "payment_status": [
            r"(?:Payment\s+Status|Pay\s+Status)[:\s]+(.+?)(?:\n|$)",
        ],
        "past_due_amount": [
            r"(?:Past\s+Due|Amount\s+Past\s+Due)[:\s]+\$?([\d,]+)",
        ],
        "monthly_payment": [
            r"(?:Monthly\s+Payment|Scheduled\s+Payment)[:\s]+\$?([\d,]+)",
            r"(?:Terms)[:\s]+\$?([\d,]+)/mo",
        ],
        "terms": [
            r"(?:Terms|Months\s+Reviewed)[:\s]+(\d+\s*(?:months?|MO)|\w+)",
        ],
        "last_payment_date": [
            r"(?:Last\s+Payment|Date\s+of\s+Last\s+Payment)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
        "last_reported_date": [
            r"(?:Date\s+Reported|Last\s+Reported|Updated)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
        "dispute_status": [
            r"(?:Dispute|Disputed|Consumer\s+Dispute)[:\s]*(Yes|No|True|False|\w+)",
        ],
    }
    
    INQUIRY_PATTERNS = {
        "inquiry_date": [
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
        "creditor_name": [
            r"([A-Z][A-Z0-9\s&.,/-]+?)(?:\s+\d{1,2}[/-]|\n|$)",
        ],
    }
    
    PUBLIC_RECORD_PATTERNS = {
        "record_type": [
            r"(Bankruptcy(?:\s+Chapter\s*\d+)?|Judgment|Tax\s+Lien|Civil\s+Judgment|Foreclosure)",
        ],
        "court_name": [
            r"(?:Court|Filed\s+(?:In|At))[:\s]+(.+?)(?:\n|$)",
        ],
        "case_number": [
            r"(?:Case|Docket|Reference)\s*(?:#|Number|No\.?)[:\s]+([A-Z0-9-]+)",
        ],
        "filed_date": [
            r"(?:Filed|Filing\s+Date)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
        "resolved_date": [
            r"(?:Discharged|Resolved|Satisfied|Released)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
        "amount": [
            r"(?:Amount|Liability|Asset)[:\s]+\$?([\d,]+)",
        ],
    }
    
    COLLECTION_PATTERNS = {
        "collection_agency": [
            r"(?:Creditor|Agency|Collection\s+Agency)[:\s]+([A-Z][A-Z0-9\s&.,/-]+)",
        ],
        "original_creditor": [
            r"(?:Original\s+Creditor)[:\s]+([A-Z][A-Z0-9\s&.,/-]+)",
        ],
        "account_number": [
            r"(?:Account|Acct)\s*(?:#|Number|No\.?)[:\s]+([A-Z0-9*X-]+)",
        ],
        "date_opened": [
            r"(?:Date\s+)?(?:Opened|Assigned)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
        "balance": [
            r"(?:Balance|Amount\s+Owed)[:\s]+\$?([\d,]+)",
        ],
        "original_amount": [
            r"(?:Original\s+(?:Balance|Amount))[:\s]+\$?([\d,]+)",
        ],
    }
    
    def __init__(self, raw_text: str, page_texts: List[Dict] = None):
        """
        Initialize the scanner with raw report text.
        
        Args:
            raw_text: Full extracted text from the report
            page_texts: Optional list of {page_number, text} for receipt tracking
        """
        self.raw_text = raw_text
        self.page_texts = page_texts or []
        self.errors = []
        
    def _find_page_for_position(self, position: int) -> str:
        """Estimate page number based on text position."""
        if not self.page_texts:
            text_before = self.raw_text[:position]
            page_markers = len(re.findall(r'\f|--- Page \d+|PAGE \d+', text_before))
            return str(page_markers + 1)
        
        current_pos = 0
        for page_info in self.page_texts:
            page_len = len(page_info.get('text', ''))
            if current_pos + page_len > position:
                return str(page_info.get('page_number', '?'))
            current_pos += page_len
        return "?"
    
    def _extract_snippet(self, text: str, match_start: int, match_end: int, context: int = 30) -> str:
        """Extract a snippet around a match for the receipt."""
        start = max(0, match_start - context)
        end = min(len(text), match_end + context)
        snippet = text[start:end].strip()
        snippet = re.sub(r'\s+', ' ', snippet)
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet[:150]
    
    def _find_section(self, section_name: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """Find a section in the report by its headers."""
        patterns = self.SECTION_HEADERS.get(section_name, [])
        for pattern in patterns:
            match = re.search(pattern, self.raw_text, re.IGNORECASE)
            if match:
                return True, match.start(), match.group(0)
        return False, None, None
    
    def _extract_section_text(self, start_pos: int, next_section_patterns: List[str] = None) -> str:
        """Extract text from a section start to the next section or end."""
        if next_section_patterns is None:
            next_section_patterns = []
            for patterns in self.SECTION_HEADERS.values():
                next_section_patterns.extend(patterns)
        
        text_from_start = self.raw_text[start_pos:]
        end_pos = len(text_from_start)
        
        for pattern in next_section_patterns:
            match = re.search(pattern, text_from_start[100:], re.IGNORECASE)
            if match and match.start() + 100 < end_pos:
                end_pos = match.start() + 100
        
        return text_from_start[:end_pos]
    
    def _try_patterns(self, text: str, patterns: List[str], 
                      section_name: str, base_position: int = 0) -> Dict:
        """Try multiple patterns and return a truth field."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip() if match.lastindex else match.group(0).strip()
                position = base_position + match.start()
                page = self._find_page_for_position(position)
                snippet = self._extract_snippet(text, match.start(), match.end())
                
                confidence = "HIGH" if len(value) > 2 else "MED"
                
                return create_truth_field(value, confidence, page, section_name, snippet)
        
        return create_not_found_field()
    
    def _scan_consumer_identity(self) -> Dict:
        """Scan the consumer identity section."""
        found, start_pos, header = self._find_section("personal_info")
        
        if not found:
            return {
                "full_name": create_not_found_field(),
                "ssn_last_four": create_not_found_field(),
                "date_of_birth": create_not_found_field(),
                "current_address": create_not_found_field(),
                "previous_addresses": create_empty_marked_array(False),
                "phone_numbers": create_empty_marked_array(False),
                "aka_names": create_empty_marked_array(False),
            }
        
        section_text = self._extract_section_text(start_pos)
        page = self._find_page_for_position(start_pos)
        
        result = {
            "full_name": self._try_patterns(
                section_text, self.PERSONAL_INFO_PATTERNS["full_name"], 
                "Personal Information", start_pos
            ),
            "ssn_last_four": self._try_patterns(
                section_text, self.PERSONAL_INFO_PATTERNS["ssn_last_four"],
                "Personal Information", start_pos
            ),
            "date_of_birth": self._try_patterns(
                section_text, self.PERSONAL_INFO_PATTERNS["date_of_birth"],
                "Personal Information", start_pos
            ),
            "current_address": self._try_patterns(
                section_text, self.PERSONAL_INFO_PATTERNS["current_address"],
                "Personal Information", start_pos
            ),
        }
        
        prev_addr_pattern = r"(?:Previous|Former|Prior)\s+Address[:\s]+(.+?)(?:\n|Reported|Date)"
        prev_addresses = []
        for match in re.finditer(prev_addr_pattern, section_text, re.IGNORECASE):
            addr = match.group(1).strip()
            snippet = self._extract_snippet(section_text, match.start(), match.end())
            prev_addresses.append(create_truth_field(addr, "MED", page, "Previous Addresses", snippet))
        
        if prev_addresses:
            result["previous_addresses"] = {
                "_marker": create_section_marker(True, len(prev_addresses), page, "Previous Addresses"),
                "items": prev_addresses
            }
        else:
            result["previous_addresses"] = create_empty_marked_array(found, page, "Personal Information")
        
        phone_pattern = r"(?:Phone|Telephone|Tel)[:\s]+(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})"
        phones = []
        for match in re.finditer(phone_pattern, section_text, re.IGNORECASE):
            phone = match.group(1).strip()
            snippet = self._extract_snippet(section_text, match.start(), match.end())
            phones.append(create_truth_field(phone, "HIGH", page, "Phone Numbers", snippet))
        
        if phones:
            result["phone_numbers"] = {
                "_marker": create_section_marker(True, len(phones), page, "Phone Numbers"),
                "items": phones
            }
        else:
            result["phone_numbers"] = create_empty_marked_array(False)
        
        aka_pattern = r"(?:AKA|Also\s+Known\s+As|Alias(?:es)?)[:\s]+([A-Z][A-Z\s,.-]+)"
        akas = []
        for match in re.finditer(aka_pattern, section_text, re.IGNORECASE):
            aka = match.group(1).strip()
            snippet = self._extract_snippet(section_text, match.start(), match.end())
            akas.append(create_truth_field(aka, "MED", page, "AKA Names", snippet))
        
        if akas:
            result["aka_names"] = {
                "_marker": create_section_marker(True, len(akas), page, "AKA Names"),
                "items": akas
            }
        else:
            result["aka_names"] = create_empty_marked_array(False)
        
        return result
    
    def _scan_employment(self) -> Dict:
        """Scan the employment section."""
        found, start_pos, header = self._find_section("employment")
        
        if not found:
            return create_empty_marked_array(False)
        
        section_text = self._extract_section_text(start_pos)
        page = self._find_page_for_position(start_pos)
        
        employer_pattern = r"(?:Employer|Company|Employed\s+(?:By|At))[:\s]+([A-Z][A-Z0-9\s&.,/-]+)"
        employers = []
        
        for match in re.finditer(employer_pattern, section_text, re.IGNORECASE):
            employer_name = match.group(1).strip()
            snippet = self._extract_snippet(section_text, match.start(), match.end())
            
            employer_section = section_text[match.start():match.start() + 500]
            
            position_match = re.search(r"(?:Position|Title|Occupation)[:\s]+(.+?)(?:\n|$)", 
                                       employer_section, re.IGNORECASE)
            date_reported_match = re.search(r"(?:Date\s+)?(?:Reported|Verified)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                                            employer_section, re.IGNORECASE)
            date_hired_match = re.search(r"(?:Hired|Start(?:ed)?|Since)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                                         employer_section, re.IGNORECASE)
            
            employers.append({
                "employer_name": create_truth_field(employer_name, "HIGH", page, "Employment", snippet),
                "position": create_truth_field(position_match.group(1).strip(), "MED", page, "Employment", 
                                               self._extract_snippet(section_text, position_match.start(), position_match.end()))
                            if position_match else create_not_found_field(),
                "date_reported": create_truth_field(date_reported_match.group(1), "HIGH", page, "Employment",
                                                    self._extract_snippet(section_text, date_reported_match.start(), date_reported_match.end()))
                                 if date_reported_match else create_not_found_field(),
                "date_hired": create_truth_field(date_hired_match.group(1), "HIGH", page, "Employment",
                                                 self._extract_snippet(section_text, date_hired_match.start(), date_hired_match.end()))
                              if date_hired_match else create_not_found_field(),
            })
        
        return {
            "_marker": create_section_marker(True, len(employers), page, "Employment"),
            "items": employers
        }
    
    def _scan_credit_scores(self) -> Dict:
        """Scan the credit score section."""
        found, start_pos, header = self._find_section("credit_score")
        
        if not found:
            return {
                "score": create_not_found_field(),
                "score_model": create_not_found_field(),
                "score_range": create_not_found_field(),
                "score_factors": create_empty_marked_array(False),
            }
        
        section_text = self._extract_section_text(start_pos)
        page = self._find_page_for_position(start_pos)
        
        score_match = re.search(r"(?:Score|FICO)[:\s]*(\d{3})", section_text, re.IGNORECASE)
        model_match = re.search(r"(FICO\s*(?:Score)?\s*\d*|VantageScore\s*\d*\.?\d*|Experian\s+Score)", 
                                section_text, re.IGNORECASE)
        range_match = re.search(r"(?:Range|Scale|Scores\s+range)[:\s]*(\d{3})\s*[-–to]+\s*(\d{3})", 
                                section_text, re.IGNORECASE)
        
        result = {
            "score": create_truth_field(int(score_match.group(1)), "HIGH", page, "Credit Score",
                                        self._extract_snippet(section_text, score_match.start(), score_match.end()))
                     if score_match else create_not_found_field(),
            "score_model": create_truth_field(model_match.group(1).strip(), "HIGH", page, "Credit Score",
                                              self._extract_snippet(section_text, model_match.start(), model_match.end()))
                           if model_match else create_not_found_field(),
            "score_range": create_truth_field(f"{range_match.group(1)}-{range_match.group(2)}", "HIGH", page, "Credit Score",
                                              self._extract_snippet(section_text, range_match.start(), range_match.end()))
                           if range_match else create_not_found_field(),
        }
        
        factor_pattern = r"(?:Factor|Reason|(?:What's\s+)?Affecting)[:\s]*\d*[.)\s]*(.+?)(?:\n|$)"
        factors = []
        for match in re.finditer(factor_pattern, section_text, re.IGNORECASE):
            factor = match.group(1).strip()
            if len(factor) > 5 and not factor.startswith("Score"):
                snippet = self._extract_snippet(section_text, match.start(), match.end())
                factors.append(create_truth_field(factor, "HIGH", page, "Score Factors", snippet))
        
        if factors:
            result["score_factors"] = {
                "_marker": create_section_marker(True, len(factors), page, "Score Factors"),
                "items": factors
            }
        else:
            result["score_factors"] = create_empty_marked_array(found, page, "Credit Score")
        
        return result
    
    def _scan_single_account(self, account_text: str, base_position: int) -> Dict:
        """Scan a single account/tradeline."""
        page = self._find_page_for_position(base_position)
        section_name = "Credit Accounts"
        
        account = {}
        
        for field_name, patterns in self.ACCOUNT_PATTERNS.items():
            account[field_name] = self._try_patterns(account_text, patterns, section_name, base_position)
        
        payment_history_pattern = r"(?:Payment\s+(?:History|Pattern)|24.?Month\s+Payment)[:\s]*(.+?)(?:\n\n|\n[A-Z])"
        ph_match = re.search(payment_history_pattern, account_text, re.IGNORECASE | re.DOTALL)
        
        payment_items = []
        if ph_match:
            ph_text = ph_match.group(1)
            month_pattern = r"(\d{1,2}[/-]\d{2,4}|\w{3}\s*\'?\d{2,4})[:\s]*([0-9COXND*-]+|OK|Current|Late|\d+)"
            for m in re.finditer(month_pattern, ph_text, re.IGNORECASE):
                month_val = m.group(1)
                status_val = m.group(2)
                snippet = self._extract_snippet(ph_text, m.start(), m.end())
                payment_items.append({
                    "month": create_truth_field(month_val, "MED", page, "Payment History", snippet),
                    "status": create_truth_field(status_val, "MED", page, "Payment History", snippet),
                })
        
        if payment_items:
            account["payment_history"] = {
                "_marker": create_section_marker(True, len(payment_items), page, "Payment History"),
                "items": payment_items
            }
        else:
            account["payment_history"] = create_empty_marked_array(False)
        
        remark_pattern = r"(?:Remark|Comment|Status\s+Details?)[:\s]+(.+?)(?:\n|$)"
        remarks = []
        for match in re.finditer(remark_pattern, account_text, re.IGNORECASE):
            remark = match.group(1).strip()
            if len(remark) > 3:
                snippet = self._extract_snippet(account_text, match.start(), match.end())
                remarks.append(create_truth_field(remark, "MED", page, "Remarks", snippet))
        
        if remarks:
            account["remarks"] = {
                "_marker": create_section_marker(True, len(remarks), page, "Remarks"),
                "items": remarks
            }
        else:
            account["remarks"] = create_empty_marked_array(False)
        
        return account
    
    def _scan_accounts(self) -> Dict:
        """Scan all accounts/tradelines."""
        found, start_pos, header = self._find_section("accounts")
        
        if not found:
            return create_empty_marked_array(False)
        
        section_text = self._extract_section_text(start_pos)
        page = self._find_page_for_position(start_pos)
        
        account_splits = re.split(
            r'\n(?=(?:Creditor|Account\s+Name)[:\s])',
            section_text,
            flags=re.IGNORECASE
        )
        
        accounts = []
        current_pos = start_pos
        
        for account_text in account_splits:
            if len(account_text) < 50:
                current_pos += len(account_text)
                continue
            
            creditor_match = re.search(r"(?:Creditor|Account)[:\s]+([A-Z])", account_text, re.IGNORECASE)
            if creditor_match:
                account = self._scan_single_account(account_text, current_pos)
                accounts.append(account)
            
            current_pos += len(account_text)
        
        return {
            "_marker": create_section_marker(True, len(accounts), page, "Credit Accounts"),
            "items": accounts
        }
    
    def _scan_inquiries(self) -> Dict:
        """
        Scan the inquiries section.
        
        Experian Note: Experian has distinct sections:
        - "Requests Viewed by Others" = HARD inquiries
        - "Requests Viewed Only By You" = SOFT inquiries
        """
        hard_found, hard_start, hard_header = self._find_section("hard_inquiries")
        soft_found, soft_start, soft_header = self._find_section("soft_inquiries")
        
        hard_inquiries = []
        soft_inquiries = []
        page = "?"
        
        if hard_found:
            hard_section = self._extract_section_text(hard_start)
            page = self._find_page_for_position(hard_start)
            
            inquiry_pattern = r"([A-Z][A-Z0-9\s&.,/-]+?)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
            for match in re.finditer(inquiry_pattern, hard_section, re.IGNORECASE):
                creditor = match.group(1).strip()
                date = match.group(2)
                snippet = self._extract_snippet(hard_section, match.start(), match.end())
                
                hard_inquiries.append({
                    "inquiry_date": create_truth_field(date, "HIGH", page, "Hard Inquiries", snippet),
                    "creditor_name": create_truth_field(creditor, "HIGH", page, "Hard Inquiries", snippet),
                    "inquiry_type": create_truth_field("Hard", "HIGH", page, "Hard Inquiries", snippet),
                })
        
        if soft_found:
            soft_section = self._extract_section_text(soft_start)
            soft_page = self._find_page_for_position(soft_start)
            
            inquiry_pattern = r"([A-Z][A-Z0-9\s&.,/-]+?)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
            for match in re.finditer(inquiry_pattern, soft_section, re.IGNORECASE):
                creditor = match.group(1).strip()
                date = match.group(2)
                snippet = self._extract_snippet(soft_section, match.start(), match.end())
                
                soft_inquiries.append({
                    "inquiry_date": create_truth_field(date, "HIGH", soft_page, "Soft Inquiries", snippet),
                    "creditor_name": create_truth_field(creditor, "HIGH", soft_page, "Soft Inquiries", snippet),
                    "inquiry_type": create_truth_field("Soft", "HIGH", soft_page, "Soft Inquiries", snippet),
                })
        
        section_found = hard_found or soft_found
        total = len(hard_inquiries) + len(soft_inquiries)
        
        return {
            "_marker": create_section_marker(section_found, total, page, "Inquiries"),
            "hard_inquiries": hard_inquiries,
            "soft_inquiries": soft_inquiries
        }
    
    def _scan_public_records(self) -> Dict:
        """Scan the public records section."""
        found, start_pos, header = self._find_section("public_records")
        
        if not found:
            return create_empty_marked_array(False)
        
        section_text = self._extract_section_text(start_pos)
        page = self._find_page_for_position(start_pos)
        
        record_types = ["Bankruptcy Chapter 7", "Bankruptcy Chapter 13", "Bankruptcy", 
                       "Judgment", "Tax Lien", "Civil Judgment", "Foreclosure"]
        records = []
        
        for record_type in record_types:
            pattern = rf"({re.escape(record_type)}.*?)(?=(?:Bankruptcy|Judgment|Tax Lien|Foreclosure|\Z))"
            for match in re.finditer(pattern, section_text, re.IGNORECASE | re.DOTALL):
                record_text = match.group(1)
                snippet = self._extract_snippet(section_text, match.start(), match.end())
                
                record = {
                    "record_type": create_truth_field(record_type, "HIGH", page, "Public Records", snippet),
                    "court_name": self._try_patterns(record_text, self.PUBLIC_RECORD_PATTERNS["court_name"], 
                                                     "Public Records", start_pos + match.start()),
                    "case_number": self._try_patterns(record_text, self.PUBLIC_RECORD_PATTERNS["case_number"],
                                                      "Public Records", start_pos + match.start()),
                    "filed_date": self._try_patterns(record_text, self.PUBLIC_RECORD_PATTERNS["filed_date"],
                                                     "Public Records", start_pos + match.start()),
                    "resolved_date": self._try_patterns(record_text, self.PUBLIC_RECORD_PATTERNS["resolved_date"],
                                                        "Public Records", start_pos + match.start()),
                    "status": self._try_patterns(record_text, [r"(?:Status)[:\s]+(\w+(?:\s+\w+)?)"],
                                                 "Public Records", start_pos + match.start()),
                    "amount": self._try_patterns(record_text, self.PUBLIC_RECORD_PATTERNS["amount"],
                                                 "Public Records", start_pos + match.start()),
                    "responsibility": self._try_patterns(record_text, [r"(?:Responsibility|Type)[:\s]+(\w+)"],
                                                         "Public Records", start_pos + match.start()),
                }
                records.append(record)
        
        return {
            "_marker": create_section_marker(found, len(records), page, "Public Records"),
            "items": records
        }
    
    def _scan_collections(self) -> Dict:
        """Scan the collections section."""
        found, start_pos, header = self._find_section("collections")
        
        if not found:
            return create_empty_marked_array(False)
        
        section_text = self._extract_section_text(start_pos)
        page = self._find_page_for_position(start_pos)
        
        collection_splits = re.split(
            r'\n(?=(?:Creditor|Agency|Collection)[:\s])',
            section_text,
            flags=re.IGNORECASE
        )
        
        collections = []
        current_pos = start_pos
        
        for coll_text in collection_splits:
            if len(coll_text) < 30:
                current_pos += len(coll_text)
                continue
            
            has_collection_marker = re.search(r"(?:collection|agency)", coll_text, re.IGNORECASE)
            if has_collection_marker:
                collection = {
                    "collection_agency": self._try_patterns(coll_text, self.COLLECTION_PATTERNS["collection_agency"],
                                                            "Collections", current_pos),
                    "original_creditor": self._try_patterns(coll_text, self.COLLECTION_PATTERNS["original_creditor"],
                                                            "Collections", current_pos),
                    "account_number": self._try_patterns(coll_text, self.COLLECTION_PATTERNS["account_number"],
                                                         "Collections", current_pos),
                    "date_opened": self._try_patterns(coll_text, self.COLLECTION_PATTERNS["date_opened"],
                                                      "Collections", current_pos),
                    "date_first_delinquency": self._try_patterns(coll_text, 
                                                                  [r"(?:First\s+)?Delinquency[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"],
                                                                  "Collections", current_pos),
                    "balance": self._try_patterns(coll_text, self.COLLECTION_PATTERNS["balance"],
                                                  "Collections", current_pos),
                    "original_amount": self._try_patterns(coll_text, self.COLLECTION_PATTERNS["original_amount"],
                                                          "Collections", current_pos),
                    "status": self._try_patterns(coll_text, [r"(?:Status)[:\s]+(\w+(?:\s+\w+)?)"],
                                                 "Collections", current_pos),
                    "dispute_status": self._try_patterns(coll_text, [r"(?:Dispute|Disputed)[:\s]+(\w+)"],
                                                         "Collections", current_pos),
                    "last_reported_date": self._try_patterns(coll_text, 
                                                             [r"(?:Reported|Updated)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"],
                                                             "Collections", current_pos),
                }
                collections.append(collection)
            
            current_pos += len(coll_text)
        
        return {
            "_marker": create_section_marker(found, len(collections), page, "Collections"),
            "items": collections
        }
    
    def _scan_consumer_statements(self) -> Dict:
        """Scan the consumer statements section."""
        found, start_pos, header = self._find_section("consumer_statements")
        
        if not found:
            return create_empty_marked_array(False)
        
        section_text = self._extract_section_text(start_pos)
        page = self._find_page_for_position(start_pos)
        
        statement_pattern = r"(?:Statement|Consumer\s+Statement)[:\s]*(.+?)(?:\n\n|Added|Date|$)"
        statements = []
        
        for match in re.finditer(statement_pattern, section_text, re.IGNORECASE | re.DOTALL):
            statement_text = match.group(1).strip()
            if len(statement_text) > 10:
                snippet = self._extract_snippet(section_text, match.start(), match.end())
                
                date_match = re.search(r"(?:Added|Date)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", 
                                       section_text[match.end():match.end()+100], re.IGNORECASE)
                
                statements.append({
                    "statement_text": create_truth_field(statement_text, "HIGH", page, "Consumer Statements", snippet),
                    "date_added": create_truth_field(date_match.group(1), "HIGH", page, "Consumer Statements",
                                                     self._extract_snippet(section_text, match.end(), match.end()+100))
                                  if date_match else create_not_found_field(),
                })
        
        return {
            "_marker": create_section_marker(found, len(statements), page, "Consumer Statements"),
            "items": statements
        }
    
    def _scan_alerts(self) -> Dict:
        """Scan the alerts section (fraud alerts, freezes, etc.)."""
        found, start_pos, header = self._find_section("alerts")
        
        if not found:
            return {
                "fraud_alerts": create_empty_marked_array(False),
                "active_duty_alerts": create_empty_marked_array(False),
                "freeze_status": create_not_found_field(),
            }
        
        section_text = self._extract_section_text(start_pos)
        page = self._find_page_for_position(start_pos)
        
        fraud_alerts = []
        fraud_pattern = r"(?:Fraud\s+Alert|Security\s+Alert)[:\s]*(.+?)(?:\n|Expires|$)"
        for match in re.finditer(fraud_pattern, section_text, re.IGNORECASE):
            alert_text = match.group(1).strip()
            snippet = self._extract_snippet(section_text, match.start(), match.end())
            
            date_placed = re.search(r"(?:Placed|Added|Set)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", 
                                    section_text[match.start():match.start()+200], re.IGNORECASE)
            expires = re.search(r"(?:Expires?|Expiration)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                               section_text[match.start():match.start()+200], re.IGNORECASE)
            
            fraud_alerts.append({
                "alert_type": create_truth_field("Fraud Alert", "HIGH", page, "Alerts", snippet),
                "date_placed": create_truth_field(date_placed.group(1), "HIGH", page, "Alerts", snippet)
                               if date_placed else create_not_found_field(),
                "expiration_date": create_truth_field(expires.group(1), "HIGH", page, "Alerts", snippet)
                                   if expires else create_not_found_field(),
            })
        
        active_duty_alerts = []
        duty_pattern = r"(?:Active\s+Duty\s+Alert|Military\s+Alert)[:\s]*(.+?)(?:\n|Expires|$)"
        for match in re.finditer(duty_pattern, section_text, re.IGNORECASE):
            snippet = self._extract_snippet(section_text, match.start(), match.end())
            
            date_placed = re.search(r"(?:Placed|Added)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                                    section_text[match.start():match.start()+200], re.IGNORECASE)
            expires = re.search(r"(?:Expires?|Expiration)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                               section_text[match.start():match.start()+200], re.IGNORECASE)
            
            active_duty_alerts.append({
                "date_placed": create_truth_field(date_placed.group(1), "HIGH", page, "Alerts", snippet)
                               if date_placed else create_not_found_field(),
                "expiration_date": create_truth_field(expires.group(1), "HIGH", page, "Alerts", snippet)
                                   if expires else create_not_found_field(),
            })
        
        freeze_match = re.search(r"(?:Security\s+)?Freeze[:\s]*(Active|Inactive|Yes|No|Locked|Unlocked|\w+)", 
                                 section_text, re.IGNORECASE)
        if freeze_match:
            snippet = self._extract_snippet(section_text, freeze_match.start(), freeze_match.end())
            freeze_status = create_truth_field(freeze_match.group(1), "HIGH", page, "Alerts", snippet)
        else:
            freeze_status = create_not_found_field()
        
        return {
            "fraud_alerts": {
                "_marker": create_section_marker(found, len(fraud_alerts), page, "Fraud Alerts"),
                "items": fraud_alerts
            },
            "active_duty_alerts": {
                "_marker": create_section_marker(found, len(active_duty_alerts), page, "Active Duty Alerts"),
                "items": active_duty_alerts
            },
            "freeze_status": freeze_status,
        }
    
    def scan(self, bureau_gate_result: Dict = None) -> ScanResult:
        """
        Scan the Experian report and produce a Truth Sheet.
        
        Args:
            bureau_gate_result: Result from gate_check(). If not provided, 
                                will run the gate check internally.
        
        Returns:
            ScanResult with success status and Truth Sheet or error info.
        """
        if bureau_gate_result is None:
            bureau_gate_result = gate_check(self.raw_text)
        
        if not bureau_gate_result["passed"]:
            return ScanResult(
                success=False,
                truth_sheet=None,
                errors=[bureau_gate_result["error"]["reason"]],
                red_light=True,
                red_light_reason=bureau_gate_result["error"]["reason"]
            )
        
        if bureau_gate_result["bureau"] != "EXPERIAN":
            return ScanResult(
                success=False,
                truth_sheet=None,
                errors=[f"Wrong scanner: This is a {bureau_gate_result['bureau']} report, not Experian."],
                red_light=True,
                red_light_reason=f"Red Light Rule: This scanner is for Experian only. This report is from {bureau_gate_result['bureau']}."
            )
        
        report_date_match = re.search(
            r"(?:Report\s+Date|Date\s+(?:of\s+)?Report|As\s+of)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            self.raw_text, re.IGNORECASE
        )
        file_id_match = re.search(
            r"(?:Report\s*(?:#|Number)|File\s*(?:#|Number|ID))[:\s]+([A-Z0-9-]+)",
            self.raw_text, re.IGNORECASE
        )
        report_type_match = re.search(
            r"(Consumer\s+(?:Credit\s+)?Report|Credit\s+Report|Experian\s+Report|Personal\s+Credit\s+Report)",
            self.raw_text, re.IGNORECASE
        )
        
        truth_sheet = {
            "meta": {
                "bureau": bureau_gate_result["truth_field"],
                "report_date": create_truth_field(
                    report_date_match.group(1), "HIGH", "1", "Header",
                    self._extract_snippet(self.raw_text, report_date_match.start(), report_date_match.end())
                ) if report_date_match else create_not_found_field(),
                "file_id": create_truth_field(
                    file_id_match.group(1), "HIGH", "1", "Header",
                    self._extract_snippet(self.raw_text, file_id_match.start(), file_id_match.end())
                ) if file_id_match else create_not_found_field(),
                "report_type": create_truth_field(
                    report_type_match.group(1), "HIGH", "1", "Header",
                    self._extract_snippet(self.raw_text, report_type_match.start(), report_type_match.end())
                ) if report_type_match else create_not_found_field(),
                "scanned_at": datetime.now().isoformat(),
            },
            "consumer_identity": self._scan_consumer_identity(),
            "employment": self._scan_employment(),
            "credit_scores": self._scan_credit_scores(),
            "accounts": self._scan_accounts(),
            "inquiries": self._scan_inquiries(),
            "public_records": self._scan_public_records(),
            "collections": self._scan_collections(),
            "consumer_statements": self._scan_consumer_statements(),
            "alerts": self._scan_alerts(),
        }
        
        try:
            validate_truth_sheet(truth_sheet)
        except MismatchAlert as e:
            return ScanResult(
                success=False,
                truth_sheet=truth_sheet,
                errors=[str(e)],
                red_light=True,
                red_light_reason=f"Red Light Rule: Truth Sheet validation failed. {e.message}"
            )
        
        return ScanResult(
            success=True,
            truth_sheet=truth_sheet,
            errors=[],
            red_light=False,
            red_light_reason=None
        )


def scan_experian_report(raw_text: str, page_texts: List[Dict] = None) -> ScanResult:
    """
    Convenience function to scan an Experian report.
    
    Args:
        raw_text: Full extracted text from the report
        page_texts: Optional list of {page_number, text} for receipt tracking
        
    Returns:
        ScanResult with Truth Sheet or error info
    """
    scanner = ExperianScanner(raw_text, page_texts)
    return scanner.scan()


if __name__ == "__main__":
    test_report = """
    Experian Credit Report
    Personal Credit Report
    
    Report Number: EXP-2024-789012
    Report Date: 01/20/2024
    Experian Information Solutions
    P.O. Box 4500, Allen, TX
    experian.com
    
    Personal Information
    Name: JANE MARIE SMITH
    SSN: XXX-XX-5678
    Year of Birth: 1990
    Current Address: 789 OAK AVENUE, NEWCITY, ST 67890
    Previous Address: 321 ELM STREET, OLDCITY, ST 12345 Reported 06/2019
    Phone: (555) 987-6543
    
    Employment Information
    Employer: XYZ INDUSTRIES
    Position: ANALYST
    Date Reported: 01/2024
    
    Your Credit Score
    FICO Score: 685
    Scores range from 300 to 850
    What's Affecting Your Score:
    Factor 1: Too many accounts with balances
    Factor 2: Length of time accounts have been established
    
    Credit Accounts
    
    Creditor Name: BANK OF AMERICA
    Account Number: XXXX-XXXX-5678
    Type of Account: Revolving
    Status: Open
    Responsibility: Individual
    Open Date: 03/15/2019
    Credit Limit: $8,000
    Balance Owed: $3,200
    Payment Status: Current
    Date Reported: 01/15/2024
    
    Requests Viewed by Others
    
    CAPITAL ONE 01/10/2024
    DISCOVER BANK 12/20/2023
    
    Requests Viewed Only By You
    
    EXPERIAN 01/01/2024
    CREDIT KARMA 12/15/2023
    
    Public Records
    No public records on file
    
    Collection Accounts
    No collection accounts
    
    Consumer Statement
    No consumer statements
    
    Security Alert
    No security alerts on file
    """
    
    result = scan_experian_report(test_report)
    
    print("Experian Scanner Test")
    print("=" * 50)
    print(f"Success: {result.success}")
    print(f"Red Light: {result.red_light}")
    
    if result.success:
        ts = result.truth_sheet
        print(f"\nBureau: {ts['meta']['bureau']['value']}")
        print(f"Report Date: {ts['meta']['report_date']['value']}")
        print(f"Name: {ts['consumer_identity']['full_name']['value']}")
        print(f"Score: {ts['credit_scores']['score']['value']}")
        print(f"Accounts Found: {ts['accounts']['_marker']['item_count']}")
        print(f"Hard Inquiries: {len(ts['inquiries']['hard_inquiries'])}")
        print(f"Soft Inquiries: {len(ts['inquiries']['soft_inquiries'])}")
    else:
        print(f"\nErrors: {result.errors}")
        print(f"Red Light Reason: {result.red_light_reason}")
