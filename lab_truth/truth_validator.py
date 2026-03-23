"""
850 Lab Truth Sheet Validator

No guessing. No filler. Every value has receipts.
This validator throws Mismatch Alerts when rules are broken.
"""

import json
from pathlib import Path
from typing import Any
from datetime import datetime


VALID_CONFIDENCE_LEVELS = {"LOW", "MED", "HIGH", "NOT_FOUND"}

REQUIRED_SECTIONS = [
    "meta", "consumer_identity", "employment", "credit_scores",
    "accounts", "inquiries", "public_records", "collections",
    "consumer_statements", "alerts"
]


class MismatchAlert(Exception):
    """
    Thrown when a Truth Sheet breaks the rules.
    This is our Red Light - something's wrong and we need to fix it.
    """
    def __init__(self, message: str, field_path: str = None, details: dict = None):
        self.message = message
        self.field_path = field_path
        self.details = details or {}
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        msg = f"🚨 MISMATCH ALERT: {self.message}"
        if self.field_path:
            msg += f"\n   📍 Location: {self.field_path}"
        if self.details:
            for key, value in self.details.items():
                msg += f"\n   • {key}: {value}"
        return msg


class TruthValidator:
    """
    Validates Truth Sheets against the strict template.
    Throws MismatchAlert on any rule violation.
    """
    
    def __init__(self, template_path: str = None):
        if template_path is None:
            template_path = Path(__file__).parent / "truth_template.json"
        
        with open(template_path, 'r') as f:
            self.template = json.load(f)
        
        self.errors = []
    
    def validate(self, truth_sheet: dict) -> bool:
        """
        Validate a Truth Sheet. Returns True if valid.
        Raises MismatchAlert with all collected errors.
        """
        self.errors = []
        
        self._validate_required_sections(truth_sheet)
        self._validate_meta(truth_sheet.get("meta", {}))
        self._validate_consumer_identity(truth_sheet.get("consumer_identity", {}))
        self._validate_employment(truth_sheet.get("employment", {}))
        self._validate_credit_scores(truth_sheet.get("credit_scores", {}))
        self._validate_accounts(truth_sheet.get("accounts", {}))
        self._validate_inquiries(truth_sheet.get("inquiries", {}))
        self._validate_public_records(truth_sheet.get("public_records", {}))
        self._validate_collections(truth_sheet.get("collections", {}))
        self._validate_consumer_statements(truth_sheet.get("consumer_statements", {}))
        self._validate_alerts(truth_sheet.get("alerts", {}))
        self._check_for_phantom_fields(truth_sheet)
        
        if self.errors:
            raise MismatchAlert(
                f"Found {len(self.errors)} rule violations",
                details={"violations": self.errors}
            )
        
        return True
    
    def validate_and_collect_errors(self, truth_sheet: dict) -> list:
        """
        Validate and return list of all errors instead of raising.
        Useful for debugging and batch validation.
        """
        try:
            self.validate(truth_sheet)
            return []
        except MismatchAlert:
            return self.errors
    
    def _validate_required_sections(self, truth_sheet: dict):
        """Check that all required top-level sections exist."""
        for section in REQUIRED_SECTIONS:
            if section not in truth_sheet:
                self._add_error(
                    "Missing Field",
                    section,
                    f"Required section '{section}' is missing from Truth Sheet"
                )
    
    def _validate_section_marker(self, marker: dict, path: str, expected_count: int):
        """Validate a section marker."""
        if not isinstance(marker, dict):
            self._add_error("Invalid Format", path, "Section marker must be an object")
            return
        
        allowed_keys = {"section_found", "item_count", "receipt"}
        extra_keys = set(marker.keys()) - allowed_keys
        if extra_keys:
            self._add_error("Phantom Field", path,
                           f"Extra fields not allowed in section marker: {extra_keys}")
        
        if "section_found" not in marker:
            self._add_error("Missing Field", f"{path}.section_found", "section_found is required")
        elif not isinstance(marker["section_found"], bool):
            self._add_error("Invalid Format", f"{path}.section_found", "section_found must be true or false")
        
        if "item_count" not in marker:
            self._add_error("Missing Field", f"{path}.item_count", "item_count is required")
        elif not isinstance(marker["item_count"], int):
            self._add_error("Invalid Format", f"{path}.item_count", "item_count must be a number")
        elif marker["item_count"] != expected_count:
            self._add_error("Bad Section Marker", f"{path}.item_count",
                           f"item_count is {marker['item_count']} but array has {expected_count} items")
        
        if marker.get("section_found") and marker.get("receipt") is None:
            self._add_error("Value Without Receipt", path,
                           "section_found is true but no receipt showing where section was found")
        
        receipt = marker.get("receipt")
        if receipt is not None and isinstance(receipt, dict):
            self._validate_section_marker_receipt(receipt, f"{path}.receipt")
    
    def _validate_section_marker_receipt(self, receipt: dict, path: str):
        """Validate a section marker's receipt structure."""
        allowed_keys = {"page", "section"}
        extra_keys = set(receipt.keys()) - allowed_keys
        if extra_keys:
            self._add_error("Phantom Field", path,
                           f"Extra fields not allowed in section marker receipt: {extra_keys}")
        
        if not any([receipt.get("page"), receipt.get("section")]):
            self._add_error("Empty Receipt", path,
                           "Section marker receipt must have at least page or section")
    
    def _validate_marked_array(self, data: dict, path: str, item_validator=None):
        """Validate an array section with a _marker."""
        if not isinstance(data, dict):
            self._add_error("Invalid Format", path, "Expected object with _marker and items")
            return
        
        allowed_keys = {"_marker", "items"}
        extra_keys = set(data.keys()) - allowed_keys
        if extra_keys:
            self._add_error("Phantom Field", path,
                           f"Extra fields not allowed in marked array: {extra_keys}")
        
        if "_marker" not in data:
            self._add_error("Missing Field", f"{path}._marker", "Section marker is required")
        
        if "items" not in data:
            self._add_error("Missing Field", f"{path}.items", "items array is required")
            return
        
        items = data.get("items", [])
        if not isinstance(items, list):
            self._add_error("Invalid Format", f"{path}.items", "items must be an array")
            return
        
        if "_marker" in data:
            self._validate_section_marker(data["_marker"], f"{path}._marker", len(items))
        
        if item_validator:
            for i, item in enumerate(items):
                item_validator(item, f"{path}.items[{i}]")
    
    def _validate_meta(self, meta: dict):
        """Validate the meta section."""
        required_fields = ["bureau", "report_date", "file_id", "report_type", "scanned_at"]
        
        for field in required_fields:
            if field not in meta:
                self._add_error("Missing Field", f"meta.{field}", 
                               f"Required field '{field}' missing from meta")
            elif field == "scanned_at":
                try:
                    datetime.fromisoformat(meta["scanned_at"].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    self._add_error("Invalid Format", "meta.scanned_at",
                                   "scanned_at must be a valid ISO datetime string")
            else:
                self._validate_truth_field(meta[field], f"meta.{field}")
    
    def _validate_consumer_identity(self, identity: dict):
        """Validate consumer identity section."""
        simple_fields = ["full_name", "ssn_last_four", "date_of_birth", "current_address"]
        array_fields = ["previous_addresses", "phone_numbers", "aka_names"]
        
        for field in simple_fields:
            if field not in identity:
                self._add_error("Missing Field", f"consumer_identity.{field}",
                               f"Required field '{field}' missing")
            else:
                self._validate_truth_field(identity[field], f"consumer_identity.{field}")
        
        for field in array_fields:
            if field not in identity:
                self._add_error("Missing Field", f"consumer_identity.{field}",
                               f"Required field '{field}' missing")
            else:
                self._validate_marked_array(
                    identity[field],
                    f"consumer_identity.{field}",
                    lambda item, path: self._validate_truth_field(item, path)
                )
    
    def _validate_employment(self, employment: dict):
        """Validate employment section."""
        def validate_employer(item, path):
            required = ["employer_name", "position", "date_reported", "date_hired"]
            for field in required:
                if field not in item:
                    self._add_error("Missing Field", f"{path}.{field}", f"'{field}' is required")
                else:
                    self._validate_truth_field(item[field], f"{path}.{field}")
        
        self._validate_marked_array(employment, "employment", validate_employer)
    
    def _validate_credit_scores(self, scores: dict):
        """Validate credit scores section."""
        simple_fields = ["score", "score_model", "score_range"]
        
        for field in simple_fields:
            if field not in scores:
                self._add_error("Missing Field", f"credit_scores.{field}",
                               f"Required field '{field}' missing")
            else:
                self._validate_truth_field(scores[field], f"credit_scores.{field}")
        
        if "score_factors" not in scores:
            self._add_error("Missing Field", "credit_scores.score_factors", "score_factors is required")
        else:
            self._validate_marked_array(
                scores["score_factors"],
                "credit_scores.score_factors",
                lambda item, path: self._validate_truth_field(item, path)
            )
    
    def _validate_accounts(self, accounts: dict):
        """Validate accounts section."""
        required_account_fields = [
            "creditor_name", "account_number", "account_type", "account_status",
            "responsibility", "date_opened", "date_closed", "date_last_active",
            "date_first_delinquency", "credit_limit", "high_balance", "current_balance",
            "payment_status", "past_due_amount", "monthly_payment", "terms",
            "last_payment_date", "last_reported_date", "dispute_status"
        ]
        
        def validate_payment_entry(item, path):
            for field in ["month", "status"]:
                if field not in item:
                    self._add_error("Missing Field", f"{path}.{field}", f"'{field}' is required")
                else:
                    self._validate_truth_field(item[field], f"{path}.{field}")
        
        def validate_account(item, path):
            for field in required_account_fields:
                if field not in item:
                    self._add_error("Missing Field", f"{path}.{field}", f"'{field}' is required")
                else:
                    self._validate_truth_field(item[field], f"{path}.{field}")
            
            if "payment_history" not in item:
                self._add_error("Missing Field", f"{path}.payment_history", "payment_history is required")
            else:
                self._validate_marked_array(item["payment_history"], f"{path}.payment_history", validate_payment_entry)
            
            if "remarks" not in item:
                self._add_error("Missing Field", f"{path}.remarks", "remarks is required")
            else:
                self._validate_marked_array(
                    item["remarks"],
                    f"{path}.remarks",
                    lambda r, p: self._validate_truth_field(r, p)
                )
        
        self._validate_marked_array(accounts, "accounts", validate_account)
    
    def _validate_inquiries(self, inquiries: dict):
        """Validate inquiries section."""
        if not isinstance(inquiries, dict):
            self._add_error("Invalid Format", "inquiries", "inquiries must be an object")
            return
        
        if "_marker" not in inquiries:
            self._add_error("Missing Field", "inquiries._marker", "Section marker is required")
        else:
            total_count = len(inquiries.get("hard_inquiries", [])) + len(inquiries.get("soft_inquiries", []))
            self._validate_section_marker(inquiries["_marker"], "inquiries._marker", total_count)
        
        def validate_inquiry(item, path):
            for field in ["inquiry_date", "creditor_name", "inquiry_type"]:
                if field not in item:
                    self._add_error("Missing Field", f"{path}.{field}", f"'{field}' is required")
                else:
                    self._validate_truth_field(item[field], f"{path}.{field}")
        
        for inquiry_type in ["hard_inquiries", "soft_inquiries"]:
            if inquiry_type not in inquiries:
                self._add_error("Missing Field", f"inquiries.{inquiry_type}", f"{inquiry_type} is required")
            elif not isinstance(inquiries[inquiry_type], list):
                self._add_error("Invalid Format", f"inquiries.{inquiry_type}", f"{inquiry_type} must be an array")
            else:
                for i, inq in enumerate(inquiries[inquiry_type]):
                    validate_inquiry(inq, f"inquiries.{inquiry_type}[{i}]")
    
    def _validate_public_records(self, records: dict):
        """Validate public records section."""
        required_fields = ["record_type", "court_name", "case_number", "filed_date", 
                          "resolved_date", "status", "amount", "responsibility"]
        
        def validate_record(item, path):
            for field in required_fields:
                if field not in item:
                    self._add_error("Missing Field", f"{path}.{field}", f"'{field}' is required")
                else:
                    self._validate_truth_field(item[field], f"{path}.{field}")
        
        self._validate_marked_array(records, "public_records", validate_record)
    
    def _validate_collections(self, collections: dict):
        """Validate collections section."""
        required_fields = [
            "collection_agency", "original_creditor", "account_number",
            "date_opened", "date_first_delinquency", "balance", "original_amount",
            "status", "dispute_status", "last_reported_date"
        ]
        
        def validate_collection(item, path):
            for field in required_fields:
                if field not in item:
                    self._add_error("Missing Field", f"{path}.{field}", f"'{field}' is required")
                else:
                    self._validate_truth_field(item[field], f"{path}.{field}")
        
        self._validate_marked_array(collections, "collections", validate_collection)
    
    def _validate_consumer_statements(self, statements: dict):
        """Validate consumer statements section."""
        def validate_statement(item, path):
            for field in ["statement_text", "date_added"]:
                if field not in item:
                    self._add_error("Missing Field", f"{path}.{field}", f"'{field}' is required")
                else:
                    self._validate_truth_field(item[field], f"{path}.{field}")
        
        self._validate_marked_array(statements, "consumer_statements", validate_statement)
    
    def _validate_alerts(self, alerts: dict):
        """Validate alerts section."""
        if not isinstance(alerts, dict):
            self._add_error("Invalid Format", "alerts", "alerts must be an object")
            return
        
        if "freeze_status" not in alerts:
            self._add_error("Missing Field", "alerts.freeze_status", "freeze_status is required")
        else:
            self._validate_truth_field(alerts["freeze_status"], "alerts.freeze_status")
        
        def validate_fraud_alert(item, path):
            for field in ["alert_type", "date_placed", "expiration_date"]:
                if field not in item:
                    self._add_error("Missing Field", f"{path}.{field}", f"'{field}' is required")
                else:
                    self._validate_truth_field(item[field], f"{path}.{field}")
        
        def validate_duty_alert(item, path):
            for field in ["date_placed", "expiration_date"]:
                if field not in item:
                    self._add_error("Missing Field", f"{path}.{field}", f"'{field}' is required")
                else:
                    self._validate_truth_field(item[field], f"{path}.{field}")
        
        if "fraud_alerts" not in alerts:
            self._add_error("Missing Field", "alerts.fraud_alerts", "fraud_alerts is required")
        else:
            self._validate_marked_array(alerts["fraud_alerts"], "alerts.fraud_alerts", validate_fraud_alert)
        
        if "active_duty_alerts" not in alerts:
            self._add_error("Missing Field", "alerts.active_duty_alerts", "active_duty_alerts is required")
        else:
            self._validate_marked_array(alerts["active_duty_alerts"], "alerts.active_duty_alerts", validate_duty_alert)
    
    def _validate_truth_field(self, field: Any, path: str):
        """
        Validate a single truth field against the Three Laws.
        This is where the Red Light Rule lives.
        """
        if not isinstance(field, dict):
            self._add_error("Invalid Format", path, 
                           f"Expected truth field object, got {type(field).__name__}")
            return
        
        if "value" not in field:
            self._add_error("Missing Field", f"{path}.value", 
                           "Every truth field must have a 'value'")
        
        if "how_sure_we_are" not in field:
            self._add_error("Missing Field", f"{path}.how_sure_we_are",
                           "Every truth field must have 'how_sure_we_are'")
        else:
            confidence = field["how_sure_we_are"]
            if confidence not in VALID_CONFIDENCE_LEVELS:
                self._add_error("Bad Confidence", f"{path}.how_sure_we_are",
                               f"'{confidence}' is not valid. Must be: {', '.join(VALID_CONFIDENCE_LEVELS)}")
        
        if "receipt" not in field:
            self._add_error("Missing Field", f"{path}.receipt",
                           "Every truth field must have 'receipt' (null if NOT_FOUND)")
        
        value = field.get("value")
        confidence = field.get("how_sure_we_are")
        receipt = field.get("receipt")
        
        if value == "NOT_FOUND":
            if confidence != "NOT_FOUND":
                self._add_error("Confidence Mismatch", path,
                               f"Value is NOT_FOUND but how_sure_we_are is '{confidence}' (should be NOT_FOUND)")
            if receipt is not None:
                self._add_error("Receipt Without Value", path,
                               "Cannot have a receipt when value is NOT_FOUND")
        
        elif value is not None and value != "NOT_FOUND":
            if confidence == "NOT_FOUND":
                self._add_error("Confidence Mismatch", path,
                               f"Value is '{value}' but how_sure_we_are is NOT_FOUND")
            if receipt is None:
                self._add_error("Value Without Receipt", path,
                               "Found values must have receipts (Red Light Rule)")
            elif isinstance(receipt, dict):
                self._validate_receipt(receipt, f"{path}.receipt")
        
        allowed_keys = {"value", "how_sure_we_are", "receipt"}
        extra_keys = set(field.keys()) - allowed_keys
        if extra_keys:
            self._add_error("Phantom Field", path,
                           f"Extra fields not allowed in truth field: {extra_keys}")
    
    def _validate_receipt(self, receipt: dict, path: str):
        """Validate a receipt has the required info."""
        if not any([receipt.get("page"), receipt.get("section"), receipt.get("snippet")]):
            self._add_error("Empty Receipt", path,
                           "Receipt must have at least one of: page, section, snippet")
        
        allowed_keys = {"page", "section", "snippet"}
        extra_keys = set(receipt.keys()) - allowed_keys
        if extra_keys:
            self._add_error("Phantom Field", path,
                           f"Extra fields not allowed in receipt: {extra_keys}")
    
    def _check_for_phantom_fields(self, truth_sheet: dict):
        """Check for fields that aren't in the template (phantom fields)."""
        allowed_top_level = set(REQUIRED_SECTIONS)
        
        for key in truth_sheet.keys():
            if key not in allowed_top_level:
                self._add_error("Phantom Field", key,
                               f"Field '{key}' is not in the Truth Template")
    
    def _add_error(self, error_type: str, path: str, message: str):
        """Add an error to the collection."""
        self.errors.append({
            "type": error_type,
            "path": path,
            "message": message
        })


def create_not_found_field() -> dict:
    """Helper to create a proper NOT_FOUND truth field."""
    return {
        "value": "NOT_FOUND",
        "how_sure_we_are": "NOT_FOUND",
        "receipt": None
    }


def create_truth_field(value: Any, confidence: str, page: str = None, 
                       section: str = None, snippet: str = None) -> dict:
    """
    Helper to create a truth field with proper receipts.
    """
    if confidence not in {"LOW", "MED", "HIGH"}:
        raise ValueError(f"Invalid confidence: {confidence}. Use LOW, MED, or HIGH.")
    
    return {
        "value": value,
        "how_sure_we_are": confidence,
        "receipt": {
            "page": page,
            "section": section,
            "snippet": snippet
        }
    }


def create_section_marker(section_found: bool, item_count: int, 
                          page: str = None, section: str = None) -> dict:
    """Helper to create a section marker."""
    return {
        "section_found": section_found,
        "item_count": item_count,
        "receipt": {"page": page, "section": section} if section_found else None
    }


def create_empty_marked_array(section_found: bool = False, 
                              page: str = None, section: str = None) -> dict:
    """Helper to create an empty marked array section."""
    return {
        "_marker": create_section_marker(section_found, 0, page, section),
        "items": []
    }


def validate_truth_sheet(truth_sheet: dict, template_path: str = None) -> bool:
    """
    Main validation function. Raises MismatchAlert if invalid.
    """
    validator = TruthValidator(template_path)
    return validator.validate(truth_sheet)


if __name__ == "__main__":
    example_sheet = {
        "meta": {
            "bureau": create_truth_field("Equifax", "HIGH", "1", "Header", "Bureau: Equifax"),
            "report_date": create_truth_field("2024-01-15", "HIGH", "1", "Header", "Report Date: 01/15/2024"),
            "file_id": create_truth_field("EFX-123456789", "HIGH", "1", "Header", "File #: EFX-123456789"),
            "report_type": create_truth_field("Consumer Disclosure", "HIGH", "1", "Header", "Consumer Disclosure Report"),
            "scanned_at": datetime.now().isoformat()
        },
        "consumer_identity": {
            "full_name": create_truth_field("JOHN DOE", "HIGH", "1", "Personal Information", "Name: JOHN DOE"),
            "ssn_last_four": create_truth_field("1234", "HIGH", "1", "Personal Information", "SSN: XXX-XX-1234"),
            "date_of_birth": create_truth_field("1985-03-15", "HIGH", "1", "Personal Information", "DOB: 03/15/1985"),
            "current_address": create_truth_field("123 MAIN ST, ANYTOWN, ST 12345", "HIGH", "1", "Address", "Current: 123 MAIN ST"),
            "previous_addresses": create_empty_marked_array(True, "1", "Previous Addresses"),
            "phone_numbers": create_empty_marked_array(False),
            "aka_names": create_empty_marked_array(False)
        },
        "employment": create_empty_marked_array(False),
        "credit_scores": {
            "score": create_truth_field(720, "HIGH", "1", "Credit Score", "FICO Score: 720"),
            "score_model": create_truth_field("FICO Score 8", "HIGH", "1", "Credit Score", "Model: FICO Score 8"),
            "score_range": create_truth_field("300-850", "HIGH", "1", "Credit Score", "Range: 300-850"),
            "score_factors": create_empty_marked_array(True, "1", "Score Factors")
        },
        "accounts": create_empty_marked_array(True, "2", "Accounts"),
        "inquiries": {
            "_marker": create_section_marker(True, 0, "4", "Inquiries"),
            "hard_inquiries": [],
            "soft_inquiries": []
        },
        "public_records": create_empty_marked_array(True, "5", "Public Records"),
        "collections": create_empty_marked_array(True, "5", "Collections"),
        "consumer_statements": create_empty_marked_array(False),
        "alerts": {
            "fraud_alerts": create_empty_marked_array(False),
            "active_duty_alerts": create_empty_marked_array(False),
            "freeze_status": create_not_found_field()
        }
    }
    
    try:
        validate_truth_sheet(example_sheet)
        print("✅ Truth Sheet is valid!")
    except MismatchAlert as e:
        print(e)
