"""
claims.py | 850 Lab Parser Machine
Claim Extraction and State Management Engine

ARCHITECTURE:
- Engine 1: Extraction Engine (neutral claim output only)
- Engine 2: Confidence Engine (reliability assessment)
- Engine 3: Consumer Authority Engine (explicit confirmation gates)
- Engine 4: Legal Harm & Strategy Engine (legally_actionable only)

STATE MACHINE (one-way transitions):
  extracted → low_confidence → awaiting_consumer_review
  awaiting_consumer_review → consumer_confirmed_true | consumer_marked_inaccurate | consumer_marked_unverifiable
  consumer_marked_inaccurate | consumer_marked_unverifiable → legally_actionable

TERMINOLOGY ENFORCEMENT:
- Claims are NOT facts, truths, violations, errors, or inaccuracies
- Claims are extracted observations requiring consumer review
"""

import hashlib
import re
from enum import Enum
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set, Tuple, Optional
from dataclasses import dataclass, field


# ============================================================================
# CANONICALIZATION LAYER
# Account-Bound Validation & Canonical Identity Functions
# ============================================================================

INVALID_PLACEHOLDER_VALUES = {
    '', 'not provided', 'n/a', 'unknown', 'none', 'null', 
    'not available', 'not reported', 'no data', '-', '--'
}

UNQUALIFIED_KEYWORDS = {
    'bankruptcy', 'foreclosure', 'repossession', 'judgment', 
    'collection', 'charge off', 'charge-off', 'charged off'
}


def normalize_creditor_name(name: str) -> str:
    """
    Normalize creditor/account name for canonical matching.
    Removes common suffixes, punctuation, and standardizes spacing.
    """
    if not name:
        return ''
    
    normalized = name.lower().strip()
    
    suffixes_to_remove = [
        'llc', 'inc', 'corp', 'corporation', 'company', 'co', 
        'ltd', 'lp', 'na', 'n.a.', 'bank', 'financial', 'services',
        'credit', 'card', 'cards', 'lending'
    ]
    
    for suffix in suffixes_to_remove:
        pattern = r'\b' + re.escape(suffix) + r'\.?\s*$'
        normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
    
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def normalize_account_identifier(account: str) -> str:
    """
    Normalize account number/mask for canonical matching.
    Extracts last 4 digits if present, otherwise returns cleaned value.
    """
    if not account:
        return ''
    
    cleaned = re.sub(r'[^\dXx*]', '', str(account))
    
    digits = re.sub(r'[^\d]', '', cleaned)
    if len(digits) >= 4:
        return digits[-4:]
    
    return cleaned[-4:] if len(cleaned) >= 4 else cleaned


def generate_canonical_account_key(
    creditor: str,
    account: str,
    bureau: str
) -> str:
    """
    Generate a canonical account key for deduplication and merging.
    
    Format: {normalized_creditor}|{account_mask}|{bureau_lower}
    
    This key uniquely identifies an account within a bureau.
    """
    norm_creditor = normalize_creditor_name(creditor)
    norm_account = normalize_account_identifier(account)
    norm_bureau = bureau.lower().strip()
    
    if not norm_creditor and not norm_account:
        return ''
    
    return f"{norm_creditor}|{norm_account}|{norm_bureau}"


def is_valid_value(value: Any) -> bool:
    """Check if a value is valid (not a placeholder)"""
    if value is None:
        return False
    str_val = str(value).lower().strip()
    return str_val not in INVALID_PLACEHOLDER_VALUES


# ============================================================================
# CLAIM CONFIDENCE + EVIDENCE SUFFICIENCY LAYER
# Deterministic scoring for claim quality assessment
# ============================================================================

DATE_FIELDS = [
    'date_opened', 'date_reported', 'date_of_first_delinquency', 'inquiry_date',
    'status_date', 'last_payment_date', 'date_closed', 'date', 'opened_date',
    'reported_date', 'closed_date', 'first_delinquency_date'
]

AMOUNT_FIELDS = [
    'balance', 'past_due', 'monthly_payment', 'high_credit', 'credit_limit',
    'amount', 'original_amount', 'charge_off_amount', 'payment_amount',
    'current_balance', 'original_balance'
]

STATUS_FIELDS = [
    'status', 'payment_status', 'account_status', 'remark', 'remarks',
    'comment', 'compliance_status', 'account_condition'
]


def _has_date_fields(item: Dict[str, Any]) -> bool:
    """Check if item has any valid date fields"""
    for field in DATE_FIELDS:
        if is_valid_value(item.get(field)):
            return True
    return False


def _has_amount_fields(item: Dict[str, Any]) -> bool:
    """Check if item has any valid amount fields"""
    for field in AMOUNT_FIELDS:
        val = item.get(field)
        if is_valid_value(val):
            str_val = str(val).lower().strip()
            if str_val not in ['$0', '0', '0.00', '$0.00']:
                return True
    return False


def _has_status_fields(item: Dict[str, Any]) -> bool:
    """Check if item has any valid status fields"""
    for field in STATUS_FIELDS:
        if is_valid_value(item.get(field)):
            return True
    return False


def compute_claim_confidence(evidence_flags: Dict[str, bool]) -> Tuple[float, str]:
    """
    Compute claim confidence score and label from evidence flags.
    
    Scoring:
    - has_creditor: +0.25
    - has_account_mask: +0.25
    - has_dates: +0.20
    - has_amounts: +0.15
    - has_status: +0.15
    
    Labels:
    - score >= 0.80 => "high"
    - score >= 0.55 => "medium"
    - else => "low"
    """
    score = 0.0
    
    if evidence_flags.get('has_creditor', False):
        score += 0.25
    if evidence_flags.get('has_account_mask', False):
        score += 0.25
    if evidence_flags.get('has_dates', False):
        score += 0.20
    if evidence_flags.get('has_amounts', False):
        score += 0.15
    if evidence_flags.get('has_status', False):
        score += 0.15
    
    if score >= 0.80:
        label = "high"
    elif score >= 0.55:
        label = "medium"
    else:
        label = "low"
    
    return (round(score, 2), label)


def build_evidence_flags(claim_fields: Dict[str, Any], source_item: Dict[str, Any]) -> Dict[str, bool]:
    """
    Build evidence flags from claim fields and source item.
    
    Returns dict with:
    - has_creditor: bool
    - has_account_mask: bool
    - has_dates: bool
    - has_amounts: bool
    - has_status: bool
    """
    has_creditor = (
        is_valid_value(claim_fields.get('creditor')) or
        is_valid_value(claim_fields.get('creditor_name')) or
        is_valid_value(claim_fields.get('account_name')) or
        is_valid_value(source_item.get('creditor')) or
        is_valid_value(source_item.get('creditor_name')) or
        is_valid_value(source_item.get('account_name'))
    )
    
    has_account_mask = (
        is_valid_value(claim_fields.get('account_number')) or
        is_valid_value(claim_fields.get('account_mask')) or
        is_valid_value(claim_fields.get('account')) or
        is_valid_value(source_item.get('account_number')) or
        is_valid_value(source_item.get('account_mask')) or
        is_valid_value(source_item.get('account'))
    )
    
    has_dates = _has_date_fields(source_item) or _has_date_fields(claim_fields)
    has_amounts = _has_amount_fields(source_item) or _has_amount_fields(claim_fields)
    has_status = _has_status_fields(source_item) or _has_status_fields(claim_fields)
    
    return {
        'has_creditor': has_creditor,
        'has_account_mask': has_account_mask,
        'has_dates': has_dates,
        'has_amounts': has_amounts,
        'has_status': has_status,
    }


def enrich_claim_fields_with_confidence(
    claim_fields: Dict[str, Any], 
    source_item: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Enrich claim fields with confidence scoring and letter eligibility.
    
    Adds to claim_fields:
    - confidence_score: float (0.0-1.0)
    - claim_confidence: "high" | "medium" | "low"
    - evidence_flags: dict with boolean flags
    - letter_eligible: bool (True only for high confidence)
    - default_selected: bool (True only for high confidence)
    - requires_user_confirmation: bool (True for medium/low confidence)
    - hidden_by_default: bool (True only for low confidence)
    
    Returns enriched claim_fields dict.
    """
    evidence_flags = build_evidence_flags(claim_fields, source_item)
    confidence_score, claim_confidence = compute_claim_confidence(evidence_flags)
    
    claim_fields['confidence_score'] = confidence_score
    claim_fields['claim_confidence'] = claim_confidence
    claim_fields['evidence_flags'] = evidence_flags
    
    if claim_confidence == 'high':
        claim_fields['letter_eligible'] = True
        claim_fields['default_selected'] = True
        claim_fields['requires_user_confirmation'] = False
        claim_fields['hidden_by_default'] = False
    elif claim_confidence == 'medium':
        claim_fields['letter_eligible'] = False
        claim_fields['default_selected'] = False
        claim_fields['requires_user_confirmation'] = True
        claim_fields['hidden_by_default'] = False
    else:
        claim_fields['letter_eligible'] = False
        claim_fields['default_selected'] = False
        claim_fields['requires_user_confirmation'] = True
        claim_fields['hidden_by_default'] = True
    
    return claim_fields


def is_account_bound(item: Dict[str, Any]) -> bool:
    """
    Account Binding Enforcement (Rule 1).
    
    An item is account-bound only if it contains at least ONE of:
    - Furnisher / Creditor name
    - Account name OR masked account number
    - Responsibility indicator (Individual / Joint / AU)
    - Balance, past-due amount, or payment status
    
    Keywords alone (Bankruptcy, Foreclosure, etc.) are NOT sufficient.
    """
    creditor = item.get('creditor', '') or item.get('furnisher', '') or item.get('company', '') or item.get('account_name', '')
    account = item.get('account', '') or item.get('account_number', '') or item.get('acct', '') or item.get('account_id', '')
    responsibility = item.get('responsibility', '') or item.get('account_type', '')
    balance = item.get('balance', '') or item.get('past_due', '') or item.get('amount', '')
    status = item.get('status', '')
    
    if is_valid_value(creditor) and str(creditor).lower().strip() not in UNQUALIFIED_KEYWORDS:
        return True
    
    if is_valid_value(account):
        return True
    
    if is_valid_value(responsibility):
        return True
    
    if is_valid_value(balance) and str(balance).lower().strip() not in ['$0', '0', '0.00', '$0.00']:
        return True
    
    if is_valid_value(status) and str(status).lower().strip() not in UNQUALIFIED_KEYWORDS:
        return True
    
    return False


def is_keyword_only_item(item: Dict[str, Any]) -> bool:
    """
    Keyword Misclassification Guard (Rule 3).
    
    Returns True if the item contains only unqualified keywords
    without real account binding data.
    """
    item_type = str(item.get('type', '')).lower().strip()
    context = str(item.get('context', '')).lower().strip()
    
    has_keyword_type = item_type in UNQUALIFIED_KEYWORDS
    
    if has_keyword_type and not is_account_bound(item):
        return True
    
    for keyword in UNQUALIFIED_KEYWORDS:
        if keyword in context and not is_account_bound(item):
            return True
    
    return False


# ============================================================================
# STATE MACHINE
# ============================================================================

class ClaimState(Enum):
    """
    Claim states with enforced one-way transitions.
    No state may be skipped.
    """
    EXTRACTED = "extracted"
    LOW_CONFIDENCE = "low_confidence"
    AWAITING_CONSUMER_REVIEW = "awaiting_consumer_review"
    CONSUMER_CONFIRMED_TRUE = "consumer_confirmed_true"
    CONSUMER_MARKED_INACCURATE = "consumer_marked_inaccurate"
    CONSUMER_MARKED_UNVERIFIABLE = "consumer_marked_unverifiable"
    LEGALLY_ACTIONABLE = "legally_actionable"


VALID_STATE_TRANSITIONS = {
    ClaimState.EXTRACTED: [ClaimState.LOW_CONFIDENCE, ClaimState.AWAITING_CONSUMER_REVIEW],
    ClaimState.LOW_CONFIDENCE: [ClaimState.AWAITING_CONSUMER_REVIEW],
    ClaimState.AWAITING_CONSUMER_REVIEW: [
        ClaimState.CONSUMER_CONFIRMED_TRUE,
        ClaimState.CONSUMER_MARKED_INACCURATE,
        ClaimState.CONSUMER_MARKED_UNVERIFIABLE
    ],
    ClaimState.CONSUMER_CONFIRMED_TRUE: [],
    ClaimState.CONSUMER_MARKED_INACCURATE: [ClaimState.LEGALLY_ACTIONABLE],
    ClaimState.CONSUMER_MARKED_UNVERIFIABLE: [ClaimState.LEGALLY_ACTIONABLE],
    ClaimState.LEGALLY_ACTIONABLE: [],
}


class ClaimType(Enum):
    """Types of claims that can be extracted from a credit report"""
    ACCOUNT_PRESENT = "account_present"
    BALANCE_REPORTED = "balance_reported"
    STATUS_REPORTED = "status_reported"
    LATE_PAYMENT_REPORTED = "late_payment_reported"
    INQUIRY_PRESENT = "inquiry_present"
    PERSONAL_INFO_PRESENT = "personal_info_present"
    ADDRESS_LISTED = "address_listed"
    DUPLICATE_DETECTED = "duplicate_detected"
    DATE_REPORTED = "date_reported"


CLAIM_TYPE_LABELS = {
    ClaimType.ACCOUNT_PRESENT: "Account Reported",
    ClaimType.BALANCE_REPORTED: "Balance Reported",
    ClaimType.STATUS_REPORTED: "Status Reported",
    ClaimType.LATE_PAYMENT_REPORTED: "Late Payment Reported",
    ClaimType.INQUIRY_PRESENT: "Inquiry Reported",
    ClaimType.PERSONAL_INFO_PRESENT: "Personal Info Reported",
    ClaimType.ADDRESS_LISTED: "Address Listed",
    ClaimType.DUPLICATE_DETECTED: "Possible Duplicate Detected",
    ClaimType.DATE_REPORTED: "Date Reported",
}


class IllegalStateTransitionError(Exception):
    """Raised when attempting an invalid state transition"""
    pass


class IllegalStateAccessError(Exception):
    """Raised when attempting to access legal logic on non-legally_actionable claim"""
    pass


@dataclass
class Claim:
    """
    An extracted claim from a credit report.
    
    Claims are OBSERVATIONS, not judgments.
    State transitions are explicit and enforced.
    """
    claim_id: str
    claim_type: ClaimType
    entity: str
    source: str
    confidence: float
    state: ClaimState
    fields: Dict[str, Any] = field(default_factory=dict)
    state_history: List[Tuple[str, str]] = field(default_factory=list)
    consumer_evidence: Optional[str] = field(default=None)
    has_negative_impact: bool = field(default=False)
    
    def __post_init__(self):
        if not self.state_history:
            self.state_history = [(datetime.now().isoformat(), self.state.value)]
    
    def transition_to(self, new_state: ClaimState) -> None:
        """
        Transition claim to a new state with enforcement.
        Raises IllegalStateTransitionError if transition is not allowed.
        """
        valid_next = VALID_STATE_TRANSITIONS.get(self.state, [])
        if new_state not in valid_next:
            raise IllegalStateTransitionError(
                f"Cannot transition from {self.state.value} to {new_state.value}. "
                f"Valid transitions: {[s.value for s in valid_next]}"
            )
        self.state_history.append((datetime.now().isoformat(), new_state.value))
        self.state = new_state
    
    def apply_confidence_rules(self) -> None:
        """
        Apply confidence-based state transitions.
        confidence < 0.6 → LOW_CONFIDENCE
        """
        if self.state == ClaimState.EXTRACTED:
            if self.confidence < 0.6:
                self.transition_to(ClaimState.LOW_CONFIDENCE)
    
    def promote_to_review(self) -> None:
        """Move claim to awaiting_consumer_review (after confidence check)"""
        if self.state == ClaimState.EXTRACTED:
            self.apply_confidence_rules()
        
        if self.state in [ClaimState.EXTRACTED, ClaimState.LOW_CONFIDENCE]:
            self.transition_to(ClaimState.AWAITING_CONSUMER_REVIEW)
    
    def consumer_confirms_true(self) -> None:
        """Consumer confirms this claim is accurate (permanently non-actionable)"""
        if self.state != ClaimState.AWAITING_CONSUMER_REVIEW:
            raise IllegalStateTransitionError(
                f"Can only confirm from AWAITING_CONSUMER_REVIEW, not {self.state.value}"
            )
        self.transition_to(ClaimState.CONSUMER_CONFIRMED_TRUE)
    
    def consumer_marks_inaccurate(self, evidence: Optional[str] = None) -> None:
        """Consumer marks this claim as inaccurate"""
        if self.state != ClaimState.AWAITING_CONSUMER_REVIEW:
            raise IllegalStateTransitionError(
                f"Can only mark inaccurate from AWAITING_CONSUMER_REVIEW, not {self.state.value}"
            )
        self.consumer_evidence = evidence
        self.transition_to(ClaimState.CONSUMER_MARKED_INACCURATE)
    
    def consumer_marks_unverifiable(self) -> None:
        """Consumer cannot verify this claim (requests bureau verification)"""
        if self.state != ClaimState.AWAITING_CONSUMER_REVIEW:
            raise IllegalStateTransitionError(
                f"Can only mark unverifiable from AWAITING_CONSUMER_REVIEW, not {self.state.value}"
            )
        self.transition_to(ClaimState.CONSUMER_MARKED_UNVERIFIABLE)
    
    def promote_to_legally_actionable(self) -> None:
        """
        Promote to legally_actionable for dispute letter generation.
        Only claims marked inaccurate or unverifiable may be promoted.
        Claim must have negative credit impact.
        """
        if self.state not in [ClaimState.CONSUMER_MARKED_INACCURATE, ClaimState.CONSUMER_MARKED_UNVERIFIABLE]:
            raise IllegalStateTransitionError(
                f"Cannot promote to legally_actionable from {self.state.value}"
            )
        self.transition_to(ClaimState.LEGALLY_ACTIONABLE)
    
    def require_legally_actionable(self) -> None:
        """
        ENFORCEMENT: Must be called before any legal logic.
        Raises IllegalStateAccessError if not in legally_actionable state.
        """
        if self.state != ClaimState.LEGALLY_ACTIONABLE:
            raise IllegalStateAccessError(
                f"Cannot access legal logic: claim is in {self.state.value}, not legally_actionable. "
                f"Consumer must mark claim inaccurate/unverifiable first."
            )
    
    @property
    def is_actionable(self) -> bool:
        """Check if claim is in legally_actionable state"""
        return self.state == ClaimState.LEGALLY_ACTIONABLE
    
    @property
    def is_confirmed_accurate(self) -> bool:
        """Check if consumer confirmed this claim is true (non-actionable)"""
        return self.state == ClaimState.CONSUMER_CONFIRMED_TRUE
    
    @property
    def awaiting_review(self) -> bool:
        """Check if claim is awaiting consumer review"""
        return self.state == ClaimState.AWAITING_CONSUMER_REVIEW
    
    @property
    def display_statement(self) -> str:
        """Neutral statement about what the report contains (NO judgments)"""
        entity = self.entity or "Unknown"
        
        if self.claim_type == ClaimType.ACCOUNT_PRESENT:
            return f"Account reported: {entity}"
        elif self.claim_type == ClaimType.BALANCE_REPORTED:
            balance = self.fields.get('balance', 'unknown')
            return f"Balance reported: ${balance}"
        elif self.claim_type == ClaimType.STATUS_REPORTED:
            status = self.fields.get('status', 'unknown')
            return f"Status reported: {status}"
        elif self.claim_type == ClaimType.LATE_PAYMENT_REPORTED:
            date = self.fields.get('date', 'unknown')
            return f"Late payment reported: {date}"
        elif self.claim_type == ClaimType.INQUIRY_PRESENT:
            date = self.fields.get('date', 'unknown')
            return f"Inquiry reported: {entity} on {date}"
        elif self.claim_type == ClaimType.PERSONAL_INFO_PRESENT:
            info_type = self.fields.get('info_type', 'information')
            value = self.fields.get('value', 'unknown')
            return f"{info_type} listed: {value}"
        elif self.claim_type == ClaimType.ADDRESS_LISTED:
            return f"Address listed: {entity}"
        elif self.claim_type == ClaimType.DUPLICATE_DETECTED:
            return f"Multiple entries detected for: {entity}"
        elif self.claim_type == ClaimType.DATE_REPORTED:
            date_type = self.fields.get('date_type', 'date')
            date = self.fields.get('date', 'unknown')
            return f"{date_type}: {date}"
        
        return f"Claim extracted: {entity}"
    
    @property
    def confidence_indicator(self) -> str:
        """Visual confidence indicator"""
        if self.confidence >= 0.8:
            return "🟢"
        elif self.confidence >= 0.6:
            return "🟡"
        elif self.confidence >= 0.4:
            return "🟠"
        else:
            return "🔴"
    
    @property
    def state_label(self) -> str:
        """Human-readable state label"""
        labels = {
            ClaimState.EXTRACTED: "Extracted",
            ClaimState.LOW_CONFIDENCE: "Low Confidence",
            ClaimState.AWAITING_CONSUMER_REVIEW: "Awaiting Review",
            ClaimState.CONSUMER_CONFIRMED_TRUE: "Confirmed Accurate",
            ClaimState.CONSUMER_MARKED_INACCURATE: "Marked Inaccurate",
            ClaimState.CONSUMER_MARKED_UNVERIFIABLE: "Unverifiable",
            ClaimState.LEGALLY_ACTIONABLE: "Ready for Dispute",
        }
        return labels.get(self.state, self.state.value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize claim to dictionary"""
        return {
            'claim_id': self.claim_id,
            'claim_type': self.claim_type.value,
            'entity': self.entity,
            'source': self.source,
            'confidence': self.confidence,
            'state': self.state.value,
            'fields': self.fields,
            'state_history': self.state_history,
            'consumer_evidence': self.consumer_evidence,
            'has_negative_impact': self.has_negative_impact,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Claim':
        """Deserialize claim from dictionary"""
        claim_type_str = data.get('claim_type', 'account_present')
        try:
            claim_type = ClaimType(claim_type_str)
        except ValueError:
            claim_type = ClaimType.ACCOUNT_PRESENT
        
        state_str = data.get('state', 'extracted')
        try:
            state = ClaimState(state_str)
        except ValueError:
            state = ClaimState.EXTRACTED
        
        return cls(
            claim_id=data.get('claim_id', ''),
            claim_type=claim_type,
            entity=data.get('entity', ''),
            source=data.get('source', 'unknown'),
            confidence=data.get('confidence', 0.5),
            state=state,
            fields=data.get('fields', {}),
            state_history=data.get('state_history', []),
            consumer_evidence=data.get('consumer_evidence'),
            has_negative_impact=data.get('has_negative_impact', False),
        )


def generate_claim_id(entity: str, source: str, claim_type: ClaimType) -> str:
    """Generate deterministic claim ID"""
    composite = f"{entity}|{source}|{claim_type.value}"
    hash_suffix = hashlib.md5(composite.encode()).hexdigest()[:8]
    return f"claim_{hash_suffix}"


def extract_claims(parsed_data: Dict[str, Any], source: str = 'unknown') -> List[Claim]:
    """
    ENGINE 1: EXTRACTION ENGINE
    
    Extract neutral claims from parsed credit report data.
    Outputs are OBSERVATIONS only - no judgments, no FCRA references.
    
    Allowed outputs:
    - "Account reported: CAPITAL ONE"
    - "Balance reported: $3,421"
    - "Status reported: Late"
    
    Explicitly forbidden:
    - FCRA references
    - Accuracy judgments
    - Labels like "incorrect", "duplicate", "unauthorized"
    """
    claims: List[Claim] = []
    seen_keys: Set[str] = set()
    
    claims.extend(_extract_account_claims(parsed_data, source, seen_keys))
    claims.extend(_extract_inquiry_claims(parsed_data, source, seen_keys))
    claims.extend(_extract_personal_info_claims(parsed_data, source, seen_keys))
    claims.extend(_extract_negative_item_claims(parsed_data, source, seen_keys))
    
    for claim in claims:
        claim.apply_confidence_rules()
        claim.promote_to_review()
    
    return claims


def _extract_account_claims(
    parsed_data: Dict[str, Any],
    source: str,
    seen_keys: Set[str]
) -> List[Claim]:
    """
    Extract claims for accounts (neutral observations only).
    
    Applies Account Binding Enforcement:
    - Only creates claims for accounts with valid binding data
    - Adds canonical_account_key for deduplication
    """
    claims = []
    accounts = parsed_data.get('accounts', [])
    seen_names: Dict[str, int] = {}
    seen_canonical_keys: Set[str] = set()
    
    for account in accounts:
        if not is_account_bound(account):
            continue
        
        account_name = account.get('account_name', 'Unknown Account')
        balance = account.get('balance', '')
        status = account.get('status', '')
        account_number = account.get('account_number', '')
        date_opened = account.get('date_opened', '')
        
        canonical_key = generate_canonical_account_key(account_name, account_number, source)
        
        if canonical_key and canonical_key in seen_canonical_keys:
            continue
        if canonical_key:
            seen_canonical_keys.add(canonical_key)
        
        has_account_number = bool(account_number)
        confidence = 0.8 if has_account_number else (0.6 if account_name != 'Unknown Account' else 0.4)
        
        has_negative = status.lower() in ['collection', 'charge-off', 'charged off', 'late', 'delinquent', 'past due'] if status else False
        
        claim_id = generate_claim_id(account_name, source, ClaimType.ACCOUNT_PRESENT)
        if claim_id not in seen_keys:
            seen_keys.add(claim_id)
            claim_fields = {
                'balance': balance,
                'status': status,
                'account_number': account_number,
                'account_mask': str(account_number)[-4:] if account_number else '',
                'date_opened': date_opened,
                'canonical_account_key': canonical_key,
                'creditor': account_name,
            }
            claim_fields = enrich_claim_fields_with_confidence(claim_fields, account)
            claims.append(Claim(
                claim_id=claim_id,
                claim_type=ClaimType.ACCOUNT_PRESENT,
                entity=account_name,
                source=source,
                confidence=confidence,
                state=ClaimState.EXTRACTED,
                fields=claim_fields,
                has_negative_impact=has_negative,
            ))
        
        if balance and balance != 'Unknown':
            claim_id = generate_claim_id(f"{account_name}_balance", source, ClaimType.BALANCE_REPORTED)
            if claim_id not in seen_keys:
                seen_keys.add(claim_id)
                balance_fields = {
                    'balance': balance, 
                    'account_name': account_name,
                    'canonical_account_key': canonical_key,
                    'creditor': account_name,
                }
                balance_fields = enrich_claim_fields_with_confidence(balance_fields, account)
                claims.append(Claim(
                    claim_id=claim_id,
                    claim_type=ClaimType.BALANCE_REPORTED,
                    entity=account_name,
                    source=source,
                    confidence=confidence,
                    state=ClaimState.EXTRACTED,
                    fields=balance_fields,
                    has_negative_impact=False,
                ))
        
        if status and status.lower() in ['collection', 'charge-off', 'charged off', 'late', 'delinquent', 'past due']:
            claim_id = generate_claim_id(f"{account_name}_status", source, ClaimType.STATUS_REPORTED)
            if claim_id not in seen_keys:
                seen_keys.add(claim_id)
                status_fields = {
                    'status': status, 
                    'account_name': account_name,
                    'canonical_account_key': canonical_key,
                    'creditor': account_name,
                }
                status_fields = enrich_claim_fields_with_confidence(status_fields, account)
                claims.append(Claim(
                    claim_id=claim_id,
                    claim_type=ClaimType.STATUS_REPORTED,
                    entity=account_name,
                    source=source,
                    confidence=confidence,
                    state=ClaimState.EXTRACTED,
                    fields=status_fields,
                    has_negative_impact=True,
                ))
        
        name_key = account_name.lower().strip()[:20] if account_name else ''
        if name_key and len(name_key) > 3:
            seen_names[name_key] = seen_names.get(name_key, 0) + 1
            if seen_names[name_key] > 1:
                claim_id = generate_claim_id(f"{account_name}_dup", source, ClaimType.DUPLICATE_DETECTED)
                if claim_id not in seen_keys:
                    seen_keys.add(claim_id)
                    dup_fields = {
                        'account_name': account_name,
                        'canonical_account_key': canonical_key,
                        'creditor': account_name,
                    }
                    dup_fields = enrich_claim_fields_with_confidence(dup_fields, account)
                    claims.append(Claim(
                        claim_id=claim_id,
                        claim_type=ClaimType.DUPLICATE_DETECTED,
                        entity=account_name,
                        source=source,
                        confidence=0.5,
                        state=ClaimState.EXTRACTED,
                        fields=dup_fields,
                        has_negative_impact=True,
                    ))
    
    return claims


def _extract_inquiry_claims(
    parsed_data: Dict[str, Any],
    source: str,
    seen_keys: Set[str]
) -> List[Claim]:
    """
    Extract claims for inquiries (neutral observations only).
    
    Applies Account Binding Enforcement:
    - Only creates claims for inquiries with valid creditor/inquirer
    - Adds canonical_account_key for deduplication
    """
    claims = []
    inquiries = parsed_data.get('inquiries', [])
    seen_canonical_keys: Set[str] = set()
    
    for inquiry in inquiries:
        inquiry_text = inquiry.get('raw_text', 'Unknown')
        inquiry_date = inquiry.get('date', 'Unknown')
        
        creditor = (
            inquiry.get('_extracted_creditor') or
            inquiry.get('creditor') or
            inquiry.get('inquirer') or
            (inquiry_text[:50] if inquiry_text else None)
        )
        
        if not creditor or not is_valid_value(creditor):
            continue
        if creditor.lower() in ['unknown', 'not provided', 'n/a']:
            continue
        
        canonical_key = generate_canonical_account_key(creditor, '', source)
        
        if canonical_key and canonical_key in seen_canonical_keys:
            continue
        if canonical_key:
            seen_canonical_keys.add(canonical_key)
        
        claim_id = generate_claim_id(f"{creditor}_{inquiry_date}", source, ClaimType.INQUIRY_PRESENT)
        if claim_id not in seen_keys:
            seen_keys.add(claim_id)
            inquiry_fields = {
                'date': inquiry_date, 
                'inquiry_text': inquiry_text[:100],
                'canonical_account_key': canonical_key,
                'creditor': creditor,
                'inquiry_date': inquiry_date,
            }
            inquiry_fields = enrich_claim_fields_with_confidence(inquiry_fields, inquiry)
            claims.append(Claim(
                claim_id=claim_id,
                claim_type=ClaimType.INQUIRY_PRESENT,
                entity=creditor,
                source=source,
                confidence=0.7,
                state=ClaimState.EXTRACTED,
                fields=inquiry_fields,
                has_negative_impact=True,
            ))
    
    return claims


def _extract_personal_info_claims(
    parsed_data: Dict[str, Any],
    source: str,
    seen_keys: Set[str]
) -> List[Claim]:
    """Extract claims for personal information (neutral observations only)"""
    claims = []
    personal_info = parsed_data.get('personal_info', {})
    
    fields_to_check = [
        ('name', 'Name'),
        ('address', 'Address'),
        ('ssn', 'SSN (partial)')
    ]
    
    for field_key, field_label in fields_to_check:
        value = personal_info.get(field_key)
        if value:
            claim_id = generate_claim_id(f"pi_{field_key}", source, ClaimType.PERSONAL_INFO_PRESENT)
            if claim_id not in seen_keys:
                seen_keys.add(claim_id)
                claims.append(Claim(
                    claim_id=claim_id,
                    claim_type=ClaimType.PERSONAL_INFO_PRESENT,
                    entity=value,
                    source=source,
                    confidence=0.9,
                    state=ClaimState.EXTRACTED,
                    fields={'info_type': field_label, 'value': value},
                    has_negative_impact=False,
                ))
    
    return claims


def _is_account_bound_negative_item(item: Dict[str, Any]) -> bool:
    """
    Negative Item Qualification Gate (Rule 2 + Rule 3)
    
    A negative item is only valid if it has at least ONE account binding qualifier:
    - Creditor / furnisher name
    - Account name or masked account number
    - Responsibility indicator (Individual / Joint / Authorized User)
    - Balance, past-due amount, or status explicitly tied to an account
    
    Keywords alone (Bankruptcy, Repossession, Foreclosure, etc.) are NOT sufficient.
    """
    creditor = (item.get('creditor', '') or item.get('furnisher', '') or item.get('company', '')
                or item.get('account_name', ''))
    account = (item.get('account', '') or item.get('account_number', '') or item.get('acct', '')
               or item.get('account_id', ''))
    responsibility = item.get('responsibility', '') or item.get('account_type', '')
    balance = item.get('balance', '') or item.get('past_due', '') or item.get('amount', '')
    status = item.get('status', '')
    
    has_creditor = bool(creditor and creditor.strip() and creditor.lower() not in ['not provided', 'n/a', 'unknown', ''])
    has_account = bool(account and account.strip() and account.lower() not in ['not provided', 'n/a', 'unknown', ''])
    has_responsibility = bool(responsibility and responsibility.strip() and responsibility.lower() not in ['not provided', 'n/a', 'unknown', ''])
    has_balance = bool(balance and str(balance).strip() and str(balance).lower() not in ['not provided', 'n/a', 'unknown', '', '$0', '0'])
    has_status = bool(status and status.strip() and status.lower() not in ['not provided', 'n/a', 'unknown', ''])
    
    return has_creditor or has_account or has_responsibility or has_balance or has_status


def _extract_negative_item_claims(
    parsed_data: Dict[str, Any],
    source: str,
    seen_keys: Set[str]
) -> List[Claim]:
    """
    Extract claims for negative items (neutral observations only)
    
    Applies Negative Item Qualification Gate + Canonicalization:
    - Rule 1: Keywords alone are NOT sufficient
    - Rule 2: Must have account binding qualifier
    - Rule 3: Account binding is mandatory
    - Rule 4: Informational rows are excluded from claims
    - Rule 5: Zero fabrication - never infer events not explicitly asserted
    - Rule 6: Bureau-agnostic enforcement
    - Adds canonical_account_key for deduplication
    """
    claims = []
    seen_canonical_keys: Set[str] = set()
    
    legend_re = re.compile(
        r'paid\s+on\s+time\s+30\s+30\s+days|payment\s+history\s+guide|'
        r'current\s*/\s*terms\s+met|ND\s+No\s+data\s+for\s+this\s+period|'
        r'CO\s+Charge\s+Off\s+B\s+Included\s+in\s+Bankruptcy|'
        r'process\s+initiated\s+by\s+you\s+generally|'
        r'^\s*\d+\s+Past\s+due\s+\d+\s+days|'
        r'\d+\s+days\s+past\s+due\s+as\s+of\s+\w+\s+\d{4}|'
        r'Narrative\s+Code\s+Narrative\s+Code\s+Descri',
        re.IGNORECASE | re.MULTILINE
    )
    
    for item in parsed_data.get('negative_items', []):
        if not _is_account_bound_negative_item(item):
            continue
        
        if is_keyword_only_item(item):
            continue
        
        context = item.get('context', '') or item.get('receipt_snippet', '')
        if legend_re.search(context) and not item.get('account_name') and not item.get('creditor'):
            continue
        
        date_str = item.get('date', '')
        item_type = item.get('type', 'Negative Item')
        context = item.get('context', '')[:200]
        creditor = (item.get('creditor', '') or item.get('furnisher', '') or item.get('company', '')
                    or item.get('account_name', ''))
        account = (item.get('account', '') or item.get('account_number', '') or item.get('acct', '')
                   or item.get('account_id', ''))
        
        if not creditor:
            receipt = item.get('receipt_snippet', '')
            acct_match = re.search(r'Account:\s*([A-Za-z][A-Za-z0-9\s/&\.\-,\']+?)(?:\s*\||\s*$)', receipt)
            if acct_match:
                creditor = acct_match.group(1).strip()
        
        if not creditor:
            item_ctx = (item.get('context', '') or '')[:40]
            if item_ctx and len(item_ctx) >= 15:
                for acct in parsed_data.get('accounts', []):
                    raw = acct.get('raw_section', '')
                    if raw and item_ctx in raw:
                        creditor = acct.get('account_name', '') or acct.get('creditor', '')
                        if creditor:
                            account = account or acct.get('account_number', '') or acct.get('account_id', '')
                            break
        
        canonical_key = generate_canonical_account_key(creditor, account, source)
        
        if canonical_key and canonical_key in seen_canonical_keys:
            continue
        if canonical_key:
            seen_canonical_keys.add(canonical_key)
        
        item_date = None
        for fmt in ['%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d']:
            try:
                item_date = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        
        confidence = 0.7 if item_date else 0.4
        
        claim_id = generate_claim_id(f"neg_{item_type}_{date_str}_{creditor}", source, ClaimType.LATE_PAYMENT_REPORTED)
        if claim_id not in seen_keys:
            seen_keys.add(claim_id)
            neg_fields = {
                'item_type': item_type,
                'date': date_str,
                'context': context,
                'creditor': creditor,
                'account': account,
                'account_mask': account[-4:] if account else '',
                'canonical_account_key': canonical_key,
            }
            neg_fields = enrich_claim_fields_with_confidence(neg_fields, item)
            claims.append(Claim(
                claim_id=claim_id,
                claim_type=ClaimType.LATE_PAYMENT_REPORTED,
                entity=item_type,
                source=source,
                confidence=confidence,
                state=ClaimState.EXTRACTED,
                fields=neg_fields,
                has_negative_impact=True,
            ))
    
    return claims


def group_claims_by_source(claims: List[Claim]) -> Dict[str, List[Claim]]:
    """Group claims by source (bureau)"""
    grouped: Dict[str, List[Claim]] = {}
    for claim in claims:
        source = claim.source.lower()
        if source not in grouped:
            grouped[source] = []
        grouped[source].append(claim)
    return grouped


def group_claims_by_type(claims: List[Claim]) -> Dict[ClaimType, List[Claim]]:
    """Group claims by claim type"""
    grouped: Dict[ClaimType, List[Claim]] = {}
    for claim in claims:
        if claim.claim_type not in grouped:
            grouped[claim.claim_type] = []
        grouped[claim.claim_type].append(claim)
    return grouped


def group_claims_by_state(claims: List[Claim]) -> Dict[ClaimState, List[Claim]]:
    """Group claims by state"""
    grouped: Dict[ClaimState, List[Claim]] = {}
    for claim in claims:
        if claim.state not in grouped:
            grouped[claim.state] = []
        grouped[claim.state].append(claim)
    return grouped


def filter_awaiting_review(claims: List[Claim]) -> List[Claim]:
    """Filter claims awaiting consumer review"""
    return [c for c in claims if c.state == ClaimState.AWAITING_CONSUMER_REVIEW]


def filter_legally_actionable(claims: List[Claim]) -> List[Claim]:
    """Filter legally actionable claims"""
    return [c for c in claims if c.state == ClaimState.LEGALLY_ACTIONABLE]


def filter_low_confidence(claims: List[Claim], threshold: float = 0.4) -> List[Claim]:
    """Filter claims below confidence threshold"""
    return [c for c in claims if c.confidence < threshold]


def can_generate_letter(claims: List[Claim], identity_confirmed: bool = False) -> Tuple[bool, List[str]]:
    """
    HARD GATE: Check if letter generation is allowed.
    
    Returns (can_generate, list_of_blocking_reasons)
    
    ALL conditions must be true:
    - Identity confirmed
    - Ownership reviewed (at least one claim addressed)
    - At least one claim marked inaccurate or unverifiable by consumer
    - Claim state == legally_actionable
    """
    blocking_reasons = []
    
    if not identity_confirmed:
        blocking_reasons.append("Identity not confirmed")
    
    addressed_claims = [c for c in claims if c.state not in [ClaimState.EXTRACTED, ClaimState.LOW_CONFIDENCE, ClaimState.AWAITING_CONSUMER_REVIEW]]
    if not addressed_claims:
        blocking_reasons.append("No claims have been reviewed by consumer")
    
    actionable = filter_legally_actionable(claims)
    if not actionable:
        blocking_reasons.append("No claims are marked for dispute and promoted to legally_actionable")
    
    can_generate = len(blocking_reasons) == 0
    return can_generate, blocking_reasons


def promote_consumer_disputed_claims(claims: List[Claim]) -> List[Claim]:
    """
    Promote claims marked inaccurate/unverifiable to legally_actionable.
    Returns only the promoted claims.
    """
    promoted = []
    for claim in claims:
        if claim.state in [ClaimState.CONSUMER_MARKED_INACCURATE, ClaimState.CONSUMER_MARKED_UNVERIFIABLE]:
            claim.promote_to_legally_actionable()
            promoted.append(claim)
    return promoted
