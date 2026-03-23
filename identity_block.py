"""
identity_block.py | 850 Lab Parser Machine
Identity block contract for gating UI rendering with required context.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class DisputeIdentityBlock:
    """Required context before showing any claim for consumer approval"""
    bureau: str
    item_category: str
    furnisher_name: Optional[str] = None
    account_reference: Optional[str] = None
    key_fact_summary: List[str] = field(default_factory=list)
    evidence_present: Dict[str, bool] = field(default_factory=dict)
    is_complete: bool = False
    block_reason: Optional[str] = None


INVALID_VALUES = {'unknown', 'not provided', 'n/a', 'none', '', 'null'}


def _clean_value(value: Any) -> Optional[str]:
    """Return value if valid, None otherwise"""
    if value is None:
        return None
    val_str = str(value).strip()
    if val_str.lower() in INVALID_VALUES:
        return None
    return val_str if val_str else None


def build_dispute_identity_block(review_claim, bureau: str) -> DisputeIdentityBlock:
    """
    Build identity block from ReviewClaim - single source of truth for UI gating.
    
    Args:
        review_claim: ReviewClaim object with entities and evidence_summary
        bureau: Bureau name string
    
    Returns:
        DisputeIdentityBlock with is_complete flag and block_reason if incomplete
    """
    entities = getattr(review_claim, 'entities', {}) or {}
    evidence = getattr(review_claim, 'evidence_summary', None)
    review_type = getattr(review_claim, 'review_type', None)
    
    item_category = str(review_type.value) if review_type else 'unknown'
    
    furnisher_name = (
        _clean_value(entities.get('creditor')) or
        _clean_value(entities.get('_extracted_creditor')) or
        _clean_value(entities.get('account_name')) or
        _clean_value(entities.get('furnisher')) or
        _clean_value(entities.get('inquirer')) or
        None
    )
    
    account_reference = (
        _clean_value(entities.get('account_mask')) or
        _clean_value(entities.get('last4')) or
        _clean_value(entities.get('account')) or
        _clean_value(entities.get('account_reference')) or
        None
    )
    
    key_facts = []
    if entities.get('balance'):
        bal = _clean_value(entities.get('balance'))
        if bal:
            key_facts.append(f"Balance: ${bal}")
    if entities.get('inquiry_date'):
        date = _clean_value(entities.get('inquiry_date'))
        if date:
            key_facts.append(f"Inquiry date: {date}")
    if entities.get('status'):
        status = _clean_value(entities.get('status'))
        if status:
            key_facts.append(f"Status: {status}")
    if entities.get('opened_date'):
        opened = _clean_value(entities.get('opened_date'))
        if opened:
            key_facts.append(f"Opened: {opened}")
    
    if evidence and hasattr(evidence, 'system_observations'):
        for obs in (evidence.system_observations or [])[:2]:
            if obs and len(key_facts) < 3:
                key_facts.append(obs)
    
    evidence_present = {
        'has_furnisher': furnisher_name is not None,
        'has_account_ref': account_reference is not None,
        'has_key_facts': len(key_facts) > 0,
    }
    
    is_complete = True

    block_reason = None
    missing = []
    if not furnisher_name:
        missing.append("creditor/furnisher name")
    if not key_facts:
        missing.append("identifying details")
    if missing:
        block_reason = f"Partial data: {', '.join(missing)}"
    
    return DisputeIdentityBlock(
        bureau=bureau,
        item_category=item_category,
        furnisher_name=furnisher_name,
        account_reference=account_reference,
        key_fact_summary=key_facts,
        evidence_present=evidence_present,
        is_complete=is_complete,
        block_reason=block_reason
    )
