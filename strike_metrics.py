"""
strike_metrics.py | 850 Lab Parser Machine
Lightweight metrics calculation layer for the 72-hour War Room plan.
Computes key credit profile metrics from parsed report data.
Deterministic, explainable, gracefully degrades on missing data.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
import re


CREDIT_THRESHOLDS = {
    "thin_file_max_accounts": 5,
    "high_utilization_pct": 50,
    "critical_utilization_pct": 70,
    "inquiry_heavy_min": 6,
}


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    s = str(val).replace(',', '').replace('$', '').strip()
    s = re.sub(r'[^\d.\-]', '', s)
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _safe_str(val) -> str:
    if val is None:
        return ''
    return str(val).strip().lower()


def _parse_date(val) -> Optional[datetime]:
    if not val:
        return None
    s = str(val).strip()
    for fmt in ('%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d', '%m-%d-%Y', '%b %d, %Y',
                '%B %d, %Y', '%m/%Y', '%m-%Y', '%Y%m%d'):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, AttributeError):
            continue
    return None


def _get_account_type(account: Dict[str, Any]) -> str:
    raw = _safe_str(
        account.get('account_type', '')
        or account.get('type', '')
        or account.get('loan_type', '')
    )
    if not raw:
        name = _safe_str(account.get('account_name', ''))
        if any(k in name for k in ('visa', 'mastercard', 'amex', 'discover', 'credit card', 'card')):
            return 'revolving'
        if any(k in name for k in ('mortgage', 'auto', 'student', 'loan', 'installment')):
            return 'installment'
        return 'unknown'

    if any(k in raw for k in ('revolv', 'credit card', 'charge', 'line of credit', 'heloc')):
        return 'revolving'
    if any(k in raw for k in ('install', 'mortgage', 'auto', 'student', 'loan', 'fixed')):
        return 'installment'
    return 'unknown'


def _get_balance(account: Dict[str, Any]) -> Optional[float]:
    return _safe_float(
        account.get('balance')
        or account.get('current_balance')
        or account.get('amount')
    )


def _get_limit(account: Dict[str, Any]) -> Optional[float]:
    return _safe_float(
        account.get('credit_limit')
        or account.get('limit')
        or account.get('high_credit')
    )


def _get_open_date(account: Dict[str, Any]) -> Optional[datetime]:
    return _parse_date(
        account.get('date_opened')
        or account.get('open_date')
        or account.get('opened_date')
    )


NEGATIVE_PATTERNS = re.compile(
    r'charge.?off|collection|repossession|foreclosure|'
    r'bankrupt|judgment|tax.?lien|written.?off|'
    r'seriously.?past.?due|account.?closed.?by.?credit|'
    r'involuntary|profit.?and.?loss',
    re.IGNORECASE,
)

COLLECTION_PATTERNS = re.compile(r'collection', re.IGNORECASE)
CHARGEOFF_PATTERNS = re.compile(r'charge.?off|written.?off', re.IGNORECASE)
PAID_COLLECTION_PATTERNS = re.compile(
    r'paid.?collection|collection.?paid|paid.?in.?full.*collection|'
    r'closed.*collection|settled',
    re.IGNORECASE,
)
LATE_PATTERNS = re.compile(
    r'late|past.?due|days?\s*late|30\s*day|60\s*day|90\s*day|120\s*day|delinq',
    re.IGNORECASE,
)


def _is_negative(account: Dict[str, Any]) -> bool:
    status = _safe_str(account.get('status', '') or account.get('payment_status', '') or account.get('account_status', ''))
    classification = _safe_str(account.get('classification', ''))
    raw_section = _safe_str(account.get('raw_section', ''))

    if classification == 'adverse':
        return True
    if NEGATIVE_PATTERNS.search(status):
        return True
    if NEGATIVE_PATTERNS.search(raw_section[:200]):
        return True
    return False


def _is_collection(account: Dict[str, Any]) -> bool:
    combined = ' '.join([
        _safe_str(account.get('status', '')),
        _safe_str(account.get('account_type', '')),
        _safe_str(account.get('account_name', '')),
        _safe_str(account.get('raw_section', ''))[:200],
    ])
    return bool(COLLECTION_PATTERNS.search(combined))


def _is_paid_collection(account: Dict[str, Any]) -> bool:
    combined = ' '.join([
        _safe_str(account.get('status', '')),
        _safe_str(account.get('raw_section', ''))[:300],
    ])
    return bool(PAID_COLLECTION_PATTERNS.search(combined))


def _is_chargeoff(account: Dict[str, Any]) -> bool:
    combined = ' '.join([
        _safe_str(account.get('status', '')),
        _safe_str(account.get('raw_section', ''))[:200],
    ])
    return bool(CHARGEOFF_PATTERNS.search(combined))


def _has_late_indicators(account: Dict[str, Any]) -> bool:
    payment_history = _safe_str(account.get('payment_history', '') or account.get('payment_pattern', ''))
    status = _safe_str(account.get('status', ''))
    if LATE_PATTERNS.search(status) or LATE_PATTERNS.search(payment_history):
        return True
    return False


@dataclass
class StrikeMetrics:
    total_accounts: int = 0
    revolving_accounts_count: int = 0
    installment_accounts_count: int = 0
    total_revolving_balance: Optional[float] = None
    total_revolving_limit: Optional[float] = None
    overall_utilization_pct: Optional[float] = None
    max_single_card_utilization_pct: Optional[float] = None
    negative_accounts_count: int = 0
    collections_count: int = 0
    paid_collections_count: int = 0
    charge_off_count: int = 0
    late_payment_indicators_count: Optional[int] = None
    inquiries_12mo_count: Optional[int] = None
    inquiries_total_count: int = 0
    oldest_account_age_months: Optional[int] = None
    newest_account_age_months: Optional[int] = None
    thin_file_flag: bool = False
    high_utilization_flag: bool = False
    critical_utilization_flag: bool = False
    inquiry_heavy_flag: bool = False
    primary_lever: str = "OPTIMIZATION"
    data_quality: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_strike_metrics(parsed_report: Dict[str, Any]) -> StrikeMetrics:
    accounts = parsed_report.get('accounts', []) or parsed_report.get('tradelines', []) or []
    inquiries = parsed_report.get('inquiries', []) or []

    metrics = StrikeMetrics()
    notes: List[str] = []

    metrics.total_accounts = len(accounts)

    revolving_balances: List[float] = []
    revolving_limits: List[float] = []
    card_utilizations: List[float] = []
    open_dates: List[datetime] = []
    has_any_balance = False
    has_any_limit = False
    has_any_date = False
    late_count = 0

    for acct in accounts:
        acct_type = _get_account_type(acct)
        if acct_type == 'revolving':
            metrics.revolving_accounts_count += 1
        elif acct_type == 'installment':
            metrics.installment_accounts_count += 1

        balance = _get_balance(acct)
        limit_val = _get_limit(acct)

        if balance is not None:
            has_any_balance = True
        if limit_val is not None:
            has_any_limit = True

        if acct_type == 'revolving':
            if balance is not None and balance >= 0:
                revolving_balances.append(balance)
            if limit_val is not None and limit_val > 0:
                revolving_limits.append(limit_val)
            if balance is not None and limit_val is not None and limit_val > 0:
                util = (balance / limit_val) * 100
                card_utilizations.append(util)

        open_date = _get_open_date(acct)
        if open_date:
            has_any_date = True
            open_dates.append(open_date)

        if _is_negative(acct):
            metrics.negative_accounts_count += 1
        if _is_collection(acct):
            metrics.collections_count += 1
        if _is_paid_collection(acct):
            metrics.paid_collections_count += 1
        if _is_chargeoff(acct):
            metrics.charge_off_count += 1
        if _has_late_indicators(acct):
            late_count += 1

    if late_count > 0:
        metrics.late_payment_indicators_count = late_count

    if revolving_balances:
        metrics.total_revolving_balance = sum(revolving_balances)
    if revolving_limits:
        metrics.total_revolving_limit = sum(revolving_limits)

    if metrics.total_revolving_balance is not None and metrics.total_revolving_limit and metrics.total_revolving_limit > 0:
        metrics.overall_utilization_pct = round(
            (metrics.total_revolving_balance / metrics.total_revolving_limit) * 100, 1
        )

    if card_utilizations:
        metrics.max_single_card_utilization_pct = round(max(card_utilizations), 1)

    now = datetime.now()
    has_inquiry_dates = False
    inq_12mo = 0

    for inq in inquiries:
        inq_date = _parse_date(inq.get('date', '') or inq.get('inquiry_date', ''))
        if inq_date:
            has_inquiry_dates = True
            if (now - inq_date).days <= 365:
                inq_12mo += 1

    metrics.inquiries_total_count = len(inquiries)
    if has_inquiry_dates:
        metrics.inquiries_12mo_count = inq_12mo

    if open_dates:
        ages = [(now - d).days for d in open_dates if d < now]
        if ages:
            metrics.oldest_account_age_months = max(ages) // 30
            metrics.newest_account_age_months = min(ages) // 30

    metrics.thin_file_flag = metrics.total_accounts < CREDIT_THRESHOLDS["thin_file_max_accounts"]

    if metrics.overall_utilization_pct is not None:
        metrics.high_utilization_flag = metrics.overall_utilization_pct >= CREDIT_THRESHOLDS["high_utilization_pct"]
        metrics.critical_utilization_flag = metrics.overall_utilization_pct >= CREDIT_THRESHOLDS["critical_utilization_pct"]

    inq_count_for_flag = metrics.inquiries_12mo_count if metrics.inquiries_12mo_count is not None else metrics.inquiries_total_count
    metrics.inquiry_heavy_flag = inq_count_for_flag >= CREDIT_THRESHOLDS["inquiry_heavy_min"]

    if metrics.critical_utilization_flag:
        metrics.primary_lever = "UTILIZATION"
    elif metrics.negative_accounts_count >= 1:
        metrics.primary_lever = "DELETION"
    elif metrics.inquiry_heavy_flag:
        metrics.primary_lever = "STABILITY"
    else:
        metrics.primary_lever = "OPTIMIZATION"

    if not has_any_balance:
        notes.append("No balance data found; utilization metrics unavailable.")
    if not has_any_limit:
        notes.append("No credit limit data found; utilization metrics unavailable.")
    if not has_any_date:
        notes.append("No account open dates found; age metrics unavailable.")
    if not has_inquiry_dates:
        notes.append("No inquiry dates found; using total inquiry count as proxy.")

    metrics.data_quality = {
        'has_limits': has_any_limit,
        'has_balances': has_any_balance,
        'has_dates': has_any_date,
        'has_inquiry_dates': has_inquiry_dates,
        'notes': notes,
    }

    return metrics
