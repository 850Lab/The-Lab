"""
review_claims.py | 850 Lab Parser Machine
Semantic Compression Layer: Raw Claims → ReviewClaims

PURPOSE:
Transform noisy atomic extracted claims into human-reviewable decision units.
Each ReviewClaim maps to EXACTLY ONE question a reasonable human can answer.

SCOPE BOUNDARIES:
- This module does NOT judge legality
- This module does NOT infer intent
- This module does NOT recommend actions
- This module does NOT override human authority
- This module does NOT cite statutes

COMPRESSION RULE SET (Canonical v1):
- Rule 1: Identity First (all personal discrepancies per bureau → 1 ReviewClaim)
- Rule 2: Account Ownership (all ownership signals per account+bureau → 1 ReviewClaim)
- Rule 3: Duplicate Accounts (all representations of same account → 1 ReviewClaim)
- Rule 4: Negative Impact (pattern-based, same account same pattern → 1 ReviewClaim)
- Rule 5: Accuracy Verification (incorrect data per account → 1 ReviewClaim)
- Rule 6: Unverifiable Information (unverifiable data per account → 1 ReviewClaim)
- Rule 7: Temporal Cohesion (same account + contiguous time → compress)
"""

import hashlib
import re
from enum import Enum
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from claims import Claim, ClaimType


# TEMPORAL COHESION: Contiguous reporting period (pattern-relative)
# Claims for the same account + same pattern are grouped together
# No fixed time windows - temporal context is provided via date range in summary


class ReviewType(Enum):
    """
    The six canonical review types.
    Each ReviewClaim has exactly one review_type (immutable once set).
    """
    IDENTITY_VERIFICATION = "identity_verification"
    ACCOUNT_OWNERSHIP = "account_ownership"
    DUPLICATE_ACCOUNT = "duplicate_account"
    NEGATIVE_IMPACT = "negative_impact"
    ACCURACY_VERIFICATION = "accuracy_verification"
    UNVERIFIABLE_INFORMATION = "unverifiable_information"


class CrossBureauStatus(Enum):
    """Cross-bureau presence indicator"""
    SINGLE_BUREAU = "single_bureau"
    MULTI_BUREAU = "multi_bureau"
    UNKNOWN = "unknown"


class CreditImpact(Enum):
    """Credit impact classification"""
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class Severity(Enum):
    """Severity classification"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"


class ConsumerResponseStatus(Enum):
    """Consumer review status"""
    UNREVIEWED = "unreviewed"
    ACCURATE = "accurate"
    INACCURATE = "inaccurate"
    UNSURE = "unsure"


REVIEW_TYPE_QUESTIONS = {
    ReviewType.IDENTITY_VERIFICATION: "Is this personal information correct as shown on this credit report?",
    ReviewType.ACCOUNT_OWNERSHIP: "Do you recognize this account as yours?",
    ReviewType.DUPLICATE_ACCOUNT: "Is this the same account reported multiple times?",
    ReviewType.NEGATIVE_IMPACT: "Is this negative information accurate?",
    ReviewType.ACCURACY_VERIFICATION: "Is the reported information (balance, status, dates) accurate?",
    ReviewType.UNVERIFIABLE_INFORMATION: "Can you verify this information from your records?",
}


@dataclass
class ClaimConfidenceSummary:
    """Summary of claim confidence levels within a ReviewClaim"""
    high: int = 0
    medium: int = 0
    low: int = 0
    
    def to_dict(self) -> Dict[str, int]:
        return {"high": self.high, "medium": self.medium, "low": self.low}


@dataclass
class LetterEligibility:
    """
    Letter eligibility status for a ReviewClaim.
    
    Rules:
    - high confidence → auto-eligible, default selected
    - medium confidence → not eligible until user confirms
    - low confidence → not eligible, hidden by default
    """
    letter_eligible: bool = False
    default_selected: bool = False
    requires_user_confirmation: bool = True
    hidden_by_default: bool = False
    letter_ready: bool = False
    letter_block_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "letter_eligible": self.letter_eligible,
            "default_selected": self.default_selected,
            "requires_user_confirmation": self.requires_user_confirmation,
            "hidden_by_default": self.hidden_by_default,
            "letter_ready": self.letter_ready
        }
        if self.letter_block_reason:
            result["letter_block_reason"] = self.letter_block_reason
        return result


def determine_letter_eligibility(confidence_summary: Optional[ClaimConfidenceSummary]) -> LetterEligibility:
    """
    Determine letter eligibility based on claim confidence summary.
    
    Rules:
    - If any high-confidence claims exist → letter_eligible, letter_ready
    - If only medium-confidence claims → not eligible until user confirms
    - If only low-confidence claims → not eligible, hidden by default
    - If no claims → blocked with reason
    
    Returns:
        LetterEligibility with all flags set
    """
    if not confidence_summary:
        return LetterEligibility(
            letter_eligible=False,
            default_selected=False,
            requires_user_confirmation=True,
            hidden_by_default=False,
            letter_ready=False,
            letter_block_reason="No claims available for this item."
        )
    
    high = confidence_summary.high
    medium = confidence_summary.medium
    low = confidence_summary.low
    total = high + medium + low
    
    if total == 0:
        return LetterEligibility(
            letter_eligible=False,
            default_selected=False,
            requires_user_confirmation=True,
            hidden_by_default=False,
            letter_ready=False,
            letter_block_reason="No claims available for this item."
        )
    
    if high > 0:
        return LetterEligibility(
            letter_eligible=True,
            default_selected=True,
            requires_user_confirmation=False,
            hidden_by_default=False,
            letter_ready=True,
            letter_block_reason=None
        )
    
    if medium > 0:
        return LetterEligibility(
            letter_eligible=False,
            default_selected=False,
            requires_user_confirmation=True,
            hidden_by_default=False,
            letter_ready=False,
            letter_block_reason="No high-confidence disputes detected. Review medium-confidence items to enable letter generation."
        )
    
    return LetterEligibility(
        letter_eligible=False,
        default_selected=False,
        requires_user_confirmation=True,
        hidden_by_default=True,
        letter_ready=False,
        letter_block_reason="Only low-confidence claims detected. These items are hidden by default."
    )


@dataclass
class EvidenceSummary:
    """Evidence supporting the ReviewClaim"""
    system_observations: List[str] = field(default_factory=list)
    cross_bureau_status: CrossBureauStatus = CrossBureauStatus.UNKNOWN
    claim_confidence_summary: Optional[ClaimConfidenceSummary] = None


@dataclass
class ConsumerResponse:
    """Consumer's response to the ReviewClaim"""
    status: ConsumerResponseStatus = ConsumerResponseStatus.UNREVIEWED
    allowed_responses: List[str] = field(default_factory=lambda: ["accurate", "inaccurate", "unsure"])


@dataclass
class ImpactAssessment:
    """Impact assessment for the ReviewClaim"""
    credit_impact: CreditImpact = CreditImpact.UNKNOWN
    severity: Severity = Severity.UNKNOWN


@dataclass
class Audit:
    """Audit trail for the ReviewClaim"""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    derived_from: str = "compression_layer_v1"
    immutable_summary: bool = True


@dataclass
class ReviewClaim:
    """
    A human-reviewable decision unit.
    
    Each ReviewClaim:
    - Corresponds to EXACTLY ONE question
    - Has exactly ONE review type
    - References ONE account + ONE bureau (where applicable)
    - Is IMMUTABLE once created (no merging, no mutation)
    """
    review_claim_id: str
    review_type: ReviewType
    summary: str
    question: str
    entities: Dict[str, Optional[str]]
    supporting_claim_ids: List[str]
    evidence_summary: EvidenceSummary
    consumer_response: ConsumerResponse
    impact_assessment: ImpactAssessment
    audit: Audit
    letter_eligibility: Optional[LetterEligibility] = None
    
    def __post_init__(self):
        """Compute letter eligibility from confidence summary if not set"""
        if self.letter_eligibility is None:
            confidence_summary = self.evidence_summary.claim_confidence_summary
            self.letter_eligibility = determine_letter_eligibility(confidence_summary)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary conforming to canonical schema"""
        result = {
            "review_claim_id": self.review_claim_id,
            "review_type": self.review_type.value,
            "summary": self.summary,
            "question": self.question,
            "entities": self.entities,
            "supporting_claim_ids": self.supporting_claim_ids,
            "evidence_summary": {
                "system_observations": self.evidence_summary.system_observations,
                "cross_bureau_status": self.evidence_summary.cross_bureau_status.value
            },
            "consumer_response": {
                "status": self.consumer_response.status.value,
                "allowed_responses": self.consumer_response.allowed_responses
            },
            "impact_assessment": {
                "credit_impact": self.impact_assessment.credit_impact.value,
                "severity": self.impact_assessment.severity.value
            },
            "audit": {
                "created_at": self.audit.created_at,
                "derived_from": self.audit.derived_from,
                "immutable_summary": self.audit.immutable_summary
            }
        }
        
        if self.evidence_summary.claim_confidence_summary:
            result["evidence_summary"]["claim_confidence_summary"] = self.evidence_summary.claim_confidence_summary.to_dict()
        
        if self.letter_eligibility:
            result["letter_eligibility"] = self.letter_eligibility.to_dict()
        
        return result
    
    def passes_litmus_test(self) -> bool:
        """
        LITMUS TEST: Can a reasonable human answer this with
        accurate / inaccurate / unsure WITHOUT asking a follow-up question?
        
        Returns True if ReviewClaim is valid, False if it should be split.
        """
        if not self.question or not self.summary:
            return False
        if not self.review_type:
            return False
        if len(self.supporting_claim_ids) == 0:
            return False
        return True


def _generate_review_claim_id(review_type: ReviewType, account: Optional[str], bureau: str) -> str:
    """Generate deterministic ReviewClaim ID"""
    key = f"{review_type.value}|{account or 'none'}|{bureau}"
    return f"rc_{hashlib.md5(key.encode()).hexdigest()[:8]}"


def _extract_account_key(claim: Claim) -> Optional[str]:
    """
    Extract account identifier from claim.
    
    Prefers canonical_account_key if available (from canonicalization layer).
    Falls back to creditor|account_number format.
    """
    fields = claim.fields
    
    canonical_key = fields.get('canonical_account_key', '')
    if canonical_key:
        return canonical_key
    
    creditor = fields.get('creditor', '') or fields.get('account_name', '') or ''
    account_num = fields.get('account_number', '') or fields.get('last4', '') or fields.get('account', '') or ''
    if creditor or account_num:
        return f"{creditor}|{account_num}".strip('|')
    return None


def _compute_claim_confidence_summary(claims: List[Claim]) -> ClaimConfidenceSummary:
    """
    Compute confidence summary from claims.
    
    Counts claims by confidence level (high/medium/low) and sorts claims
    with high confidence first, then by confidence_score descending.
    """
    summary = ClaimConfidenceSummary()
    
    for claim in claims:
        confidence_label = claim.fields.get('claim_confidence', 'low')
        if confidence_label == 'high':
            summary.high += 1
        elif confidence_label == 'medium':
            summary.medium += 1
        else:
            summary.low += 1
    
    return summary


def _sort_claims_by_confidence(claims: List[Claim]) -> List[Claim]:
    """
    Sort claims by confidence: high first, then by confidence_score descending.
    """
    def sort_key(claim: Claim) -> tuple:
        confidence_label = claim.fields.get('claim_confidence', 'low')
        confidence_score = claim.fields.get('confidence_score', 0.0)
        priority = {'high': 0, 'medium': 1, 'low': 2}.get(confidence_label, 2)
        return (priority, -confidence_score)
    
    return sorted(claims, key=sort_key)


def _determine_credit_impact(claims: List[Claim]) -> CreditImpact:
    """Determine credit impact from grouped claims"""
    for claim in claims:
        if claim.has_negative_impact:
            return CreditImpact.NEGATIVE
        if claim.claim_type in [ClaimType.LATE_PAYMENT_REPORTED]:
            return CreditImpact.NEGATIVE
        status = claim.fields.get('status', '').lower()
        if any(neg in status for neg in ['late', 'delinquent', 'charge', 'collection', 'closed']):
            return CreditImpact.NEGATIVE
    return CreditImpact.NEUTRAL


def _determine_severity(claims: List[Claim]) -> Severity:
    """Determine severity based on claim patterns"""
    if len(claims) >= 5:
        return Severity.HIGH
    if len(claims) >= 3:
        return Severity.MODERATE
    if len(claims) >= 1:
        return Severity.LOW
    return Severity.UNKNOWN


def _build_observations(claims: List[Claim]) -> List[str]:
    """Build system observations from claims"""
    observations = []
    for claim in claims[:5]:
        if claim.claim_type == ClaimType.PERSONAL_INFO_PRESENT:
            info_type = claim.fields.get('info_type', 'personal info')
            value = claim.fields.get('value', '')
            observations.append(f"{info_type}: {value}" if value else f"{info_type} reported")
        elif claim.claim_type == ClaimType.ACCOUNT_PRESENT:
            creditor = claim.fields.get('creditor', 'Unknown')
            observations.append(f"Account with {creditor} reported")
        elif claim.claim_type == ClaimType.BALANCE_REPORTED:
            balance = claim.fields.get('balance', 'unknown')
            observations.append(f"Balance of {balance} reported")
        elif claim.claim_type == ClaimType.STATUS_REPORTED:
            status = claim.fields.get('status', 'unknown')
            observations.append(f"Status: {status}")
        elif claim.claim_type == ClaimType.LATE_PAYMENT_REPORTED:
            date = claim.fields.get('date', '')
            observations.append(f"Late payment reported{' on ' + date if date else ''}")
        elif claim.claim_type == ClaimType.DUPLICATE_DETECTED:
            observations.append("Possible duplicate entry detected")
        elif claim.claim_type == ClaimType.INQUIRY_PRESENT:
            inquirer = claim.fields.get('creditor') or claim.fields.get('inquirer') or claim.entity or 'Unknown'
            observations.append(f"Inquiry from {inquirer}")
        else:
            observations.append(claim.entity or "Data point extracted")
    return observations


def _extract_claim_date(claim: Claim) -> Optional[datetime]:
    """
    RULE 7 SUPPORT: Extract date from claim for temporal grouping.
    Attempts to parse date from various fields.
    """
    date_fields = ['date', 'opened_date', 'reported_date', 'status_date', 'payment_date']
    
    for field_name in date_fields:
        date_str = claim.fields.get(field_name, '')
        if date_str:
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%Y/%m/%d', '%B %Y', '%b %Y']:
                try:
                    return datetime.strptime(date_str, fmt)
                except (ValueError, TypeError):
                    continue
            match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', date_str)
            if match:
                try:
                    month, day, year = match.groups()
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    return datetime(int(year), int(month), int(day))
                except (ValueError, TypeError):
                    pass
    return None


def _get_date_range_label(claims: List[Claim]) -> str:
    """
    RULE 7: Temporal Cohesion (Pattern-Relative)
    Returns a date range label for the claims' reporting period.
    No fixed windows - all claims for same pattern grouped together.
    """
    dates = []
    for claim in claims:
        claim_date = _extract_claim_date(claim)
        if claim_date:
            dates.append(claim_date)
    
    if not dates:
        return ""
    
    min_date = min(dates)
    max_date = max(dates)
    
    if min_date.year == max_date.year and min_date.month == max_date.month:
        return f" ({min_date.strftime('%B %Y')})"
    elif min_date.year == max_date.year:
        return f" ({min_date.strftime('%b')}-{max_date.strftime('%b %Y')})"
    else:
        return f" ({min_date.strftime('%b %Y')}-{max_date.strftime('%b %Y')})"


def compress_identity_claims(claims: List[Claim], bureau: str) -> Optional[ReviewClaim]:
    """
    RULE 1: Identity First
    All personal identity discrepancies per bureau → ONE identity_verification ReviewClaim
    """
    identity_claims = [c for c in claims if c.claim_type in [
        ClaimType.PERSONAL_INFO_PRESENT,
        ClaimType.ADDRESS_LISTED
    ] and c.source.lower() == bureau.lower()]
    
    if not identity_claims:
        return None
    
    review_claim_id = _generate_review_claim_id(ReviewType.IDENTITY_VERIFICATION, None, bureau)
    
    return ReviewClaim(
        review_claim_id=review_claim_id,
        review_type=ReviewType.IDENTITY_VERIFICATION,
        summary=f"Personal information reported by {bureau.title()}",
        question=REVIEW_TYPE_QUESTIONS[ReviewType.IDENTITY_VERIFICATION],
        entities={"account_name": None, "bureau": bureau.title()},
        supporting_claim_ids=[c.claim_id for c in identity_claims],
        evidence_summary=EvidenceSummary(
            system_observations=_build_observations(identity_claims),
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=CreditImpact.NEUTRAL,
            severity=Severity.UNKNOWN
        ),
        audit=Audit()
    )


def compress_ownership_claims(claims: List[Claim], account_key: str, bureau: str) -> Optional[ReviewClaim]:
    """
    RULE 2: Account Ownership
    All signals questioning ownership per account per bureau → ONE account_ownership ReviewClaim
    """
    ownership_claims = [c for c in claims 
        if _extract_account_key(c) == account_key 
        and c.source.lower() == bureau.lower()
        and c.claim_type == ClaimType.ACCOUNT_PRESENT]
    
    if not ownership_claims:
        return None
    
    ownership_claims = _sort_claims_by_confidence(ownership_claims)
    
    first_claim = ownership_claims[0]
    creditor = (
        first_claim.fields.get('creditor') or
        first_claim.fields.get('inquirer') or
        first_claim.fields.get('account_name') or
        first_claim.entity or
        'Unknown'
    )
    last4 = first_claim.fields.get('last4', '')
    
    review_claim_id = _generate_review_claim_id(ReviewType.ACCOUNT_OWNERSHIP, account_key, bureau)
    
    account_display = f"{creditor}"
    if last4:
        account_display += f" (****{last4})"
    
    return ReviewClaim(
        review_claim_id=review_claim_id,
        review_type=ReviewType.ACCOUNT_OWNERSHIP,
        summary=f"Account {account_display} reported by {bureau.title()}",
        question=REVIEW_TYPE_QUESTIONS[ReviewType.ACCOUNT_OWNERSHIP],
        entities={"account_name": account_display, "bureau": bureau.title()},
        supporting_claim_ids=[c.claim_id for c in ownership_claims],
        evidence_summary=EvidenceSummary(
            system_observations=_build_observations(ownership_claims),
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=_compute_claim_confidence_summary(ownership_claims)
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=_determine_credit_impact(ownership_claims),
            severity=_determine_severity(ownership_claims)
        ),
        audit=Audit()
    )


def compress_duplicate_claims(claims: List[Claim], account_key: str, bureau: str) -> Optional[ReviewClaim]:
    """
    RULE 3: Duplicate Accounts
    All representations of the same account → ONE duplicate_account ReviewClaim
    """
    duplicate_claims = [c for c in claims 
        if _extract_account_key(c) == account_key 
        and c.source.lower() == bureau.lower()
        and c.claim_type == ClaimType.DUPLICATE_DETECTED]
    
    if not duplicate_claims:
        return None
    
    duplicate_claims = _sort_claims_by_confidence(duplicate_claims)
    
    creditor = (
        duplicate_claims[0].fields.get('creditor') or
        duplicate_claims[0].fields.get('account_name') or
        duplicate_claims[0].entity or
        'Unknown'
    )
    
    review_claim_id = _generate_review_claim_id(ReviewType.DUPLICATE_ACCOUNT, account_key, bureau)
    
    return ReviewClaim(
        review_claim_id=review_claim_id,
        review_type=ReviewType.DUPLICATE_ACCOUNT,
        summary=f"Possible duplicate: {creditor} on {bureau.title()}",
        question=REVIEW_TYPE_QUESTIONS[ReviewType.DUPLICATE_ACCOUNT],
        entities={"account_name": creditor, "bureau": bureau.title()},
        supporting_claim_ids=[c.claim_id for c in duplicate_claims],
        evidence_summary=EvidenceSummary(
            system_observations=_build_observations(duplicate_claims),
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=_compute_claim_confidence_summary(duplicate_claims)
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=CreditImpact.NEGATIVE,
            severity=Severity.MODERATE
        ),
        audit=Audit()
    )


def compress_negative_impact_claims(claims: List[Claim], account_key: str, bureau: str) -> List[ReviewClaim]:
    """
    RULE 4: Negative Impact (Pattern-Based) + RULE 7: Temporal Cohesion
    All late payments for same account → ONE negative_impact ReviewClaim with date range
    All other negative marks for same account → ONE negative_impact ReviewClaim with date range
    Different patterns (late payments vs status changes) → separate ReviewClaims
    No fixed time windows - date range shown in summary for context
    """
    negative_claims = [c for c in claims 
        if _extract_account_key(c) == account_key 
        and c.source.lower() == bureau.lower()
        and (c.claim_type == ClaimType.LATE_PAYMENT_REPORTED or c.has_negative_impact)]
    
    if not negative_claims:
        return []
    
    late_payments = [c for c in negative_claims if c.claim_type == ClaimType.LATE_PAYMENT_REPORTED]
    other_negative = [c for c in negative_claims if c.claim_type != ClaimType.LATE_PAYMENT_REPORTED]
    
    results = []
    creditor = (
        negative_claims[0].fields.get('creditor') or
        negative_claims[0].fields.get('account_name') or
        negative_claims[0].entity or
        'Unknown'
    )
    
    if late_payments:
        date_range = _get_date_range_label(late_payments)
        review_claim_id = _generate_review_claim_id(
            ReviewType.NEGATIVE_IMPACT, 
            f"{account_key}_late", 
            bureau
        )
        sorted_late = _sort_claims_by_confidence(late_payments)
        results.append(ReviewClaim(
            review_claim_id=review_claim_id,
            review_type=ReviewType.NEGATIVE_IMPACT,
            summary=f"Late payment history on {creditor}{date_range} ({bureau.title()})",
            question=REVIEW_TYPE_QUESTIONS[ReviewType.NEGATIVE_IMPACT],
            entities={"account_name": creditor, "bureau": bureau.title()},
            supporting_claim_ids=[c.claim_id for c in sorted_late],
            evidence_summary=EvidenceSummary(
                system_observations=_build_observations(sorted_late),
                cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
                claim_confidence_summary=_compute_claim_confidence_summary(sorted_late)
            ),
            consumer_response=ConsumerResponse(),
            impact_assessment=ImpactAssessment(
                credit_impact=CreditImpact.NEGATIVE,
                severity=Severity.HIGH if len(sorted_late) >= 3 else Severity.MODERATE
            ),
            audit=Audit()
        ))
    
    if other_negative:
        date_range = _get_date_range_label(other_negative)
        review_claim_id = _generate_review_claim_id(
            ReviewType.NEGATIVE_IMPACT, 
            f"{account_key}_status", 
            bureau
        )
        sorted_other = _sort_claims_by_confidence(other_negative)
        results.append(ReviewClaim(
            review_claim_id=review_claim_id,
            review_type=ReviewType.NEGATIVE_IMPACT,
            summary=f"Negative status on {creditor}{date_range} ({bureau.title()})",
            question=REVIEW_TYPE_QUESTIONS[ReviewType.NEGATIVE_IMPACT],
            entities={"account_name": creditor, "bureau": bureau.title()},
            supporting_claim_ids=[c.claim_id for c in sorted_other],
            evidence_summary=EvidenceSummary(
                system_observations=_build_observations(sorted_other),
                cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
                claim_confidence_summary=_compute_claim_confidence_summary(sorted_other)
            ),
            consumer_response=ConsumerResponse(),
            impact_assessment=ImpactAssessment(
                credit_impact=CreditImpact.NEGATIVE,
                severity=Severity.HIGH
            ),
            audit=Audit()
        ))
    
    return results


def compress_accuracy_claims(claims: List[Claim], account_key: str, bureau: str) -> Optional[ReviewClaim]:
    """
    RULE 5: Accuracy Verification + RULE 7: Temporal Cohesion
    All accuracy claims for same account → ONE accuracy_verification ReviewClaim
    No fixed time windows - date range shown in summary for context
    """
    accuracy_claims = [c for c in claims 
        if _extract_account_key(c) == account_key 
        and c.source.lower() == bureau.lower()
        and c.claim_type in [ClaimType.BALANCE_REPORTED, ClaimType.STATUS_REPORTED, ClaimType.DATE_REPORTED]
        and not c.has_negative_impact]
    
    if not accuracy_claims:
        return None
    
    accuracy_claims = _sort_claims_by_confidence(accuracy_claims)
    
    creditor = (
        accuracy_claims[0].fields.get('creditor') or
        accuracy_claims[0].fields.get('account_name') or
        accuracy_claims[0].entity or
        'Unknown'
    )
    date_range = _get_date_range_label(accuracy_claims)
    
    review_claim_id = _generate_review_claim_id(
        ReviewType.ACCURACY_VERIFICATION, 
        account_key, 
        bureau
    )
    
    return ReviewClaim(
        review_claim_id=review_claim_id,
        review_type=ReviewType.ACCURACY_VERIFICATION,
        summary=f"Account details for {creditor}{date_range} ({bureau.title()})",
        question=REVIEW_TYPE_QUESTIONS[ReviewType.ACCURACY_VERIFICATION],
        entities={"account_name": creditor, "bureau": bureau.title()},
        supporting_claim_ids=[c.claim_id for c in accuracy_claims],
        evidence_summary=EvidenceSummary(
            system_observations=_build_observations(accuracy_claims),
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=_compute_claim_confidence_summary(accuracy_claims)
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=_determine_credit_impact(accuracy_claims),
            severity=Severity.LOW
        ),
        audit=Audit()
    )


def _requires_external_evidence(claim: Claim) -> bool:
    """
    RULE 6 GUARDRAIL: Determine if a claim requires external evidence to verify.
    
    Unverifiable_information applies ONLY when:
    - Data cannot be verified by system (parsing failed/incomplete)
    - Data cannot be verified by consumer from memory alone
    - External documentation (statements, contracts) is required
    
    Low confidence extraction alone does NOT qualify.
    """
    fields = claim.fields
    
    missing_account_identity = (
        not fields.get('creditor') and 
        not fields.get('last4') and
        not fields.get('account_number')
    )
    
    has_unverifiable_marker = fields.get('requires_external_evidence', False)
    
    has_incomplete_record = (
        fields.get('record_incomplete', False) or
        fields.get('data_truncated', False)
    )
    
    return missing_account_identity or has_unverifiable_marker or has_incomplete_record


def compress_unverifiable_claims(claims: List[Claim], account_key: str, bureau: str) -> Optional[ReviewClaim]:
    """
    RULE 6: Unverifiable Information (Guardrailed)
    
    ONLY creates ReviewClaim when data truly requires external evidence.
    Low-confidence extraction alone does NOT automatically trigger this.
    
    Unverifiable applies when:
    - Missing critical identifying information that consumer cannot provide from memory
    - Data explicitly marked as requiring external documentation
    - Record is incomplete or truncated beyond consumer recall
    
    Low-confidence claims should be surfaced via accuracy_verification first,
    allowing consumer to confirm/deny before escalating to unverifiable status.
    """
    unverifiable_claims = [c for c in claims 
        if _extract_account_key(c) == account_key 
        and c.source.lower() == bureau.lower()
        and _requires_external_evidence(c)]
    
    if not unverifiable_claims:
        return None
    
    unverifiable_claims = _sort_claims_by_confidence(unverifiable_claims)
    
    creditor = (
        unverifiable_claims[0].fields.get('creditor') or
        unverifiable_claims[0].fields.get('account_name') or
        unverifiable_claims[0].entity or
        'Unknown'
    )
    
    review_claim_id = _generate_review_claim_id(ReviewType.UNVERIFIABLE_INFORMATION, account_key, bureau)
    
    observations = []
    for claim in unverifiable_claims:
        if not claim.fields.get('creditor'):
            observations.append("Account creditor name not provided by bureau")
        if claim.fields.get('record_incomplete'):
            observations.append("Account record appears incomplete")
        if claim.fields.get('data_truncated'):
            observations.append("Account data may be truncated")
        if claim.fields.get('requires_external_evidence'):
            observations.append("Account requires external documentation to verify")
    
    if not observations:
        observations = ["Account information requires external documentation to verify"]
    
    return ReviewClaim(
        review_claim_id=review_claim_id,
        review_type=ReviewType.UNVERIFIABLE_INFORMATION,
        summary=f"Account requires external documentation ({bureau.title()})",
        question=REVIEW_TYPE_QUESTIONS[ReviewType.UNVERIFIABLE_INFORMATION],
        entities={"account_name": creditor if creditor != 'Unknown' else 'Unidentified Account', "bureau": bureau.title()},
        supporting_claim_ids=[c.claim_id for c in unverifiable_claims],
        evidence_summary=EvidenceSummary(
            system_observations=list(set(observations)),
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=_compute_claim_confidence_summary(unverifiable_claims)
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=CreditImpact.UNKNOWN,
            severity=Severity.UNKNOWN
        ),
        audit=Audit()
    )


def compress_inquiry_claims(claims: List[Claim], bureau: str) -> List[ReviewClaim]:
    """
    Compress inquiry claims - each inquiry is a separate ownership question
    """
    inquiry_claims = [c for c in claims 
        if c.claim_type == ClaimType.INQUIRY_PRESENT 
        and c.source.lower() == bureau.lower()]
    
    results = []
    for claim in inquiry_claims:
        inquirer = claim.fields.get('inquirer', 'Unknown')
        review_claim_id = _generate_review_claim_id(
            ReviewType.ACCOUNT_OWNERSHIP, 
            f"inquiry_{inquirer}", 
            bureau
        )
        
        results.append(ReviewClaim(
            review_claim_id=review_claim_id,
            review_type=ReviewType.ACCOUNT_OWNERSHIP,
            summary=f"Inquiry from {inquirer} on {bureau.title()}",
            question="Did you authorize this credit inquiry?",
            entities={"account_name": inquirer, "bureau": bureau.title()},
            supporting_claim_ids=[claim.claim_id],
            evidence_summary=EvidenceSummary(
                system_observations=[f"Credit inquiry from {inquirer}"],
                cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU
            ),
            consumer_response=ConsumerResponse(),
            impact_assessment=ImpactAssessment(
                credit_impact=CreditImpact.NEGATIVE,
                severity=Severity.LOW
            ),
            audit=Audit()
        ))
    
    return results


def compress_claims(raw_claims: List[Claim]) -> List[ReviewClaim]:
    """
    MAIN COMPRESSION PIPELINE
    
    Raw extracted claims → semantic grouping → compression rules → ReviewClaims
    
    Pipeline order:
    1. Group claims by bureau
    2. Apply Rule 1 (Identity)
    3. Extract unique account keys
    4. For each account: Apply Rules 2-6
    5. Apply inquiry compression
    6. Validate all ReviewClaims pass litmus test
    """
    if not raw_claims:
        return []
    
    review_claims: List[ReviewClaim] = []
    bureaus_seen: Set[str] = set()
    account_keys_by_bureau: Dict[str, Set[str]] = {}
    
    for claim in raw_claims:
        bureau = claim.source.lower()
        bureaus_seen.add(bureau)
        
        account_key = _extract_account_key(claim)
        if account_key:
            if bureau not in account_keys_by_bureau:
                account_keys_by_bureau[bureau] = set()
            account_keys_by_bureau[bureau].add(account_key)
    
    for bureau in bureaus_seen:
        identity_rc = compress_identity_claims(raw_claims, bureau)
        if identity_rc and identity_rc.passes_litmus_test():
            review_claims.append(identity_rc)
        
        inquiry_rcs = compress_inquiry_claims(raw_claims, bureau)
        for rc in inquiry_rcs:
            if rc.passes_litmus_test():
                review_claims.append(rc)
        
        account_keys = account_keys_by_bureau.get(bureau, set())
        for account_key in account_keys:
            ownership_rc = compress_ownership_claims(raw_claims, account_key, bureau)
            if ownership_rc and ownership_rc.passes_litmus_test():
                review_claims.append(ownership_rc)
            
            duplicate_rc = compress_duplicate_claims(raw_claims, account_key, bureau)
            if duplicate_rc and duplicate_rc.passes_litmus_test():
                review_claims.append(duplicate_rc)
            
            negative_rcs = compress_negative_impact_claims(raw_claims, account_key, bureau)
            for rc in negative_rcs:
                if rc.passes_litmus_test():
                    review_claims.append(rc)
            
            accuracy_rc = compress_accuracy_claims(raw_claims, account_key, bureau)
            if accuracy_rc and accuracy_rc.passes_litmus_test():
                review_claims.append(accuracy_rc)
            
            unverifiable_rc = compress_unverifiable_claims(raw_claims, account_key, bureau)
            if unverifiable_rc and unverifiable_rc.passes_litmus_test():
                review_claims.append(unverifiable_rc)
    
    return review_claims


def get_review_claims_by_bureau(review_claims: List[ReviewClaim]) -> Dict[str, List[ReviewClaim]]:
    """Group ReviewClaims by bureau for UI display"""
    grouped: Dict[str, List[ReviewClaim]] = {}
    for rc in review_claims:
        bureau = rc.entities.get('bureau') or 'Unknown'
        if bureau not in grouped:
            grouped[bureau] = []
        grouped[bureau].append(rc)
    return grouped


def get_review_claims_by_type(review_claims: List[ReviewClaim]) -> Dict[ReviewType, List[ReviewClaim]]:
    """Group ReviewClaims by review type"""
    grouped: Dict[ReviewType, List[ReviewClaim]] = {}
    for rc in review_claims:
        if rc.review_type not in grouped:
            grouped[rc.review_type] = []
        grouped[rc.review_type].append(rc)
    return grouped
