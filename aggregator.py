"""
Multi-bureau aggregation module for 850 Lab.

Provides cross-bureau deduplication, unified summary computation,
and discrepancy detection across Equifax, Experian, and TransUnion reports.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple


@dataclass
class CrossBureauMatch:
    creditor_key: str
    bureaus: List[str]
    accounts: List[Dict[str, Any]]
    discrepancies: List[Dict[str, str]] = field(default_factory=list)
    match_confidence: str = "HIGH"

    @property
    def bureau_count(self) -> int:
        return len(self.bureaus)

    @property
    def is_multi_bureau(self) -> bool:
        return self.bureau_count > 1


@dataclass
class AggregatedSummary:
    total_accounts_raw: int
    total_accounts_unique: int
    total_adverse: int
    total_good_standing: int
    total_unknown: int
    total_hard_inquiries: int
    total_soft_inquiries: int
    total_negative_items: int
    total_public_records: int
    bureaus_found: List[str]
    cross_bureau_matches: List[CrossBureauMatch]
    per_bureau: Dict[str, Dict[str, int]]
    discrepancy_count: int = 0
    personal_info: Dict[str, Any] = field(default_factory=dict)


def _is_hard_inquiry(inquiry: Dict[str, Any]) -> bool:
    raw_text = (inquiry.get('raw_text', '') or '').lower()
    inq_type = (inquiry.get('type', '') or '').lower()
    soft_indicators = [
        'soft', 'promotional', 'preapproved', 'pre-approved', 'promo',
        'account review', 'consumer disclosure', 'account monitoring',
        'insurance', 'employment', 'marketing', 'periodic review',
        'existing account', 'ar ', 'prom', 'am '
    ]
    if any(s in raw_text for s in soft_indicators):
        return False
    if any(s in inq_type for s in soft_indicators):
        return False
    if 'regular inquir' in raw_text or 'credit inquir' in raw_text:
        return True
    return True


def normalize_creditor_name(name: str) -> str:
    if not name:
        return ""
    upper = name.upper().strip()
    upper = re.sub(r'\s+', ' ', upper)
    removals = [
        r'\bN\.?A\.?\b',
        r'\bINC\.?\b',
        r'\bLLC\b',
        r'\bCORP\.?\b',
        r'\bCO\.?\b',
        r'\bLTD\.?\b',
        r'\bBANK\b',
        r'\bFINANCIAL\b',
        r'\bSERVICES?\b',
        r'\bGROUP\b',
        r'\bINTERNATIONAL\b',
        r'\bNATIONAL\b',
        r'\bAMERIC(?:A|AN)?\b',
    ]
    for pattern in removals:
        upper = re.sub(pattern, '', upper)
    upper = re.sub(r'[^A-Z0-9]', '', upper)
    return upper[:20] if upper else ""


def build_cross_bureau_key(account: Dict[str, Any]) -> str:
    name = normalize_creditor_name(account.get('account_name', ''))
    acct_num = (account.get('account_number', '') or '').strip()
    num_digits = re.sub(r'[^0-9]', '', acct_num)
    last4 = num_digits[-4:] if len(num_digits) >= 4 else ''
    date_opened = (account.get('date_opened', '') or '').strip()
    if name and last4:
        return f"{name}|{last4}"
    if name and date_opened:
        return f"{name}|{date_opened}"
    if name:
        return f"{name}|NOKEY"
    return f"UNK|{hash(str(account.get('raw_section', ''))[:80])}"


def detect_discrepancies(accounts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    if len(accounts) < 2:
        return []
    discrepancies = []
    fields_to_check = [
        ('balance', 'Balance'),
        ('status', 'Status'),
        ('high_credit', 'High Credit'),
        ('credit_limit', 'Credit Limit'),
        ('payment_status', 'Payment Status'),
    ]
    for field_key, field_label in fields_to_check:
        values = {}
        for acct in accounts:
            val = (acct.get(field_key, '') or '').strip()
            if val:
                bureau = acct.get('bureau', 'unknown')
                values[bureau] = val
        if len(values) > 1:
            unique_vals = set(values.values())
            if len(unique_vals) > 1:
                discrepancies.append({
                    'field': field_label,
                    'field_key': field_key,
                    'values': values,
                    'severity': _discrepancy_severity(field_key, values),
                })
    return discrepancies


def _discrepancy_severity(field_key: str, values: Dict[str, str]) -> str:
    if field_key == 'balance':
        nums = []
        for v in values.values():
            cleaned = re.sub(r'[^0-9.]', '', v)
            try:
                nums.append(float(cleaned))
            except (ValueError, TypeError):
                pass
        if len(nums) >= 2:
            diff = abs(max(nums) - min(nums))
            if diff > 100:
                return "HIGH"
            elif diff > 10:
                return "MEDIUM"
            return "LOW"
    if field_key in ('status', 'payment_status'):
        return "HIGH"
    return "MEDIUM"


def build_cross_bureau_index(
    reports: Dict[str, Dict[str, Any]]
) -> Tuple[List[CrossBureauMatch], Dict[str, List[Dict[str, Any]]]]:
    key_groups: Dict[str, List[Dict[str, Any]]] = {}
    for snapshot_key, report in reports.items():
        bureau = report.get('bureau', 'unknown')
        parsed = report.get('parsed_data', {})
        for acct in parsed.get('accounts', []):
            acct_copy = dict(acct)
            acct_copy['bureau'] = bureau
            acct_copy['snapshot_key'] = snapshot_key
            cb_key = build_cross_bureau_key(acct_copy)
            if cb_key not in key_groups:
                key_groups[cb_key] = []
            key_groups[cb_key].append(acct_copy)

    matches = []
    for cb_key, accts in key_groups.items():
        bureaus = list(set(a.get('bureau', 'unknown') for a in accts))
        discrepancies = detect_discrepancies(accts) if len(bureaus) > 1 else []
        confidence = "HIGH"
        if cb_key.endswith("|NOKEY"):
            confidence = "LOW"
        elif len(bureaus) == 1 and len(accts) > 1:
            confidence = "MEDIUM"
        match = CrossBureauMatch(
            creditor_key=cb_key,
            bureaus=sorted(bureaus),
            accounts=accts,
            discrepancies=discrepancies,
            match_confidence=confidence,
        )
        matches.append(match)
    return matches, key_groups


def compute_unified_summary(
    reports: Dict[str, Dict[str, Any]]
) -> AggregatedSummary:
    if not reports:
        return AggregatedSummary(
            total_accounts_raw=0, total_accounts_unique=0,
            total_adverse=0, total_good_standing=0, total_unknown=0,
            total_hard_inquiries=0, total_soft_inquiries=0,
            total_negative_items=0, total_public_records=0,
            bureaus_found=[], cross_bureau_matches=[],
            per_bureau={}, personal_info={},
        )

    cross_matches, key_groups = build_cross_bureau_index(reports)

    bureaus_found = []
    per_bureau: Dict[str, Dict[str, int]] = {}
    total_raw = 0
    total_adverse = 0
    total_good = 0
    total_unknown = 0
    total_hard = 0
    total_soft = 0
    total_neg = 0
    total_pr = 0
    merged_personal: Dict[str, Any] = {}

    for snapshot_key, report in reports.items():
        bureau = report.get('bureau', 'unknown')
        if bureau not in bureaus_found:
            bureaus_found.append(bureau)
        parsed = report.get('parsed_data', {})
        accounts = parsed.get('accounts', [])
        inquiries = parsed.get('inquiries', [])
        neg_items = parsed.get('negative_items', [])
        pub_records = parsed.get('public_records', [])
        cls_counts = parsed.get('classification_counts', {})

        b_adverse = cls_counts.get('ADVERSE', 0)
        b_good = cls_counts.get('GOOD_STANDING', 0)
        b_unknown = cls_counts.get('UNKNOWN', 0)

        b_hard = len([i for i in inquiries if _is_hard_inquiry(i)])
        b_soft = len([i for i in inquiries if not _is_hard_inquiry(i)])

        per_bureau[bureau] = {
            'accounts': len(accounts),
            'adverse': b_adverse,
            'good_standing': b_good,
            'unknown': b_unknown,
            'hard_inquiries': b_hard,
            'soft_inquiries': b_soft,
            'negative_items': len(neg_items),
            'public_records': len(pub_records),
        }

        total_raw += len(accounts)
        total_adverse += b_adverse
        total_good += b_good
        total_unknown += b_unknown
        total_hard += b_hard
        total_soft += b_soft
        total_neg += len(neg_items)
        total_pr += len(pub_records)

        pi = parsed.get('personal_info', {})
        for k, v in pi.items():
            if v and not merged_personal.get(k):
                merged_personal[k] = v

    total_unique = len(cross_matches)
    total_discrepancies = sum(len(m.discrepancies) for m in cross_matches)

    return AggregatedSummary(
        total_accounts_raw=total_raw,
        total_accounts_unique=total_unique,
        total_adverse=total_adverse,
        total_good_standing=total_good,
        total_unknown=total_unknown,
        total_hard_inquiries=total_hard,
        total_soft_inquiries=total_soft,
        total_negative_items=total_neg,
        total_public_records=total_pr,
        bureaus_found=sorted(bureaus_found),
        cross_bureau_matches=cross_matches,
        per_bureau=per_bureau,
        discrepancy_count=total_discrepancies,
        personal_info=merged_personal,
    )


def get_multi_bureau_accounts(
    cross_matches: List[CrossBureauMatch],
) -> List[CrossBureauMatch]:
    return [m for m in cross_matches if m.is_multi_bureau]


def get_single_bureau_accounts(
    cross_matches: List[CrossBureauMatch],
) -> List[CrossBureauMatch]:
    return [m for m in cross_matches if not m.is_multi_bureau]


def get_discrepant_accounts(
    cross_matches: List[CrossBureauMatch],
) -> List[CrossBureauMatch]:
    return [m for m in cross_matches if m.discrepancies]


def merge_best_record(match: CrossBureauMatch) -> Dict[str, Any]:
    if not match.accounts:
        return {}
    best = dict(match.accounts[0])
    best['reporting_bureaus'] = match.bureaus
    best['bureau_count'] = match.bureau_count
    best['discrepancies'] = match.discrepancies
    for acct in match.accounts[1:]:
        for key in ('balance', 'high_credit', 'credit_limit', 'date_opened',
                     'date_closed', 'status', 'payment_status', 'loan_type',
                     'account_type'):
            if not best.get(key) and acct.get(key):
                best[key] = acct[key]
    return best
