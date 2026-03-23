"""Dedupe keys and deduped counts for summary/truth-layer display (Streamlit-free)."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List

from .report_metrics import is_hard_inquiry


def smart_account_dedupe_key(account: Dict[str, Any]) -> str:
    """Build dedupe key for accounts using creditor name + account number + date opened + high credit"""
    name = (account.get("account_name", "") or "").upper().strip()
    name = re.sub(r"[^A-Z0-9]", "", name)[:20] if name else ""

    acct_num = (account.get("account_number", "") or "").strip()
    date_opened = (account.get("date_opened", "") or account.get("opened_date", "") or "").strip()
    high_credit = (
        (account.get("high_credit", "") or account.get("credit_limit", "") or "")
        .replace(",", "")
        .replace("$", "")
        .strip()
    )
    balance = (account.get("balance", "") or "").replace(",", "").replace("$", "").strip()

    parts = [name]
    if acct_num:
        parts.append(acct_num)
    if date_opened:
        parts.append(date_opened)
    if high_credit:
        parts.append(high_credit)

    if len(parts) >= 3:
        return "|".join(parts)

    if name and balance:
        return f"{name}|{balance}"

    if name:
        return f"{name}|NODATE"

    raw = (account.get("raw_section", "") or "")[:100]
    return f"UNK|{hash(raw)}"


def smart_inquiry_dedupe_key(inquiry: Dict[str, Any]) -> str:
    """Build robust dedupe key for inquiries - extract creditor name + date"""
    raw_text = (inquiry.get("raw_text", "") or "").upper()
    date = inquiry.get("date", "") or ""

    creditor_patterns = [
        r"(CAPITAL\s*ONE)",
        r"(CHASE)",
        r"(BANK\s*OF\s*AMERICA)",
        r"(DISCOVER)",
        r"(AMERICAN\s*EXPRESS)",
        r"(CITIBANK)",
        r"(WELLS\s*FARGO)",
        r"(SYNCHRONY)",
        r"([A-Z]{4,}\s*(?:BANK|FINANCIAL|AUTO|CREDIT))",
    ]

    for pattern in creditor_patterns:
        match = re.search(pattern, raw_text)
        if match:
            creditor = re.sub(r"[^A-Z0-9]", "", match.group(1))[:12]
            return f"{creditor}|{date}" if date else creditor

    words = re.findall(r"[A-Z]{4,}", raw_text)
    skip = {"INQUIRY", "CREDIT", "CHECK", "DATE", "TYPE", "HARD", "SOFT"}
    for word in words:
        if word not in skip:
            return f"{word[:12]}|{date}" if date else word[:12]

    return f"INQ|{date}" if date else f"INQ|{hash(raw_text[:20])}"


def smart_negative_dedupe_key(item: Dict[str, Any]) -> str:
    """Build robust dedupe key for negative items - aggressive by type + creditor"""
    item_type = (item.get("type", "") or "").upper().strip()[:10]
    context = item.get("context", "") or ""

    creditor_match = re.search(r"([A-Z][A-Za-z\s&]+)", context.upper())
    creditor = (
        re.sub(r"[^A-Z0-9]", "", creditor_match.group(1))[:12] if creditor_match else ""
    )

    if item_type and creditor:
        return f"{item_type}|{creditor}"
    if item_type:
        return item_type

    return f"NEG|{hash(context[:30])}"


def dedupe_list(items: List[Any], key_func: Callable[[Any], str]) -> List[Any]:
    """Simple deduplication using key function"""
    seen = set()
    result = []
    for item in items:
        key = key_func(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def compute_deduped_counts(parsed_data: Dict[str, Any]) -> Dict[str, int]:
    """Compute deduped counts for truth layer display.

    Uses smart dedupe functions for robust deduplication.
    """
    accounts = parsed_data.get("accounts", [])
    inquiries = parsed_data.get("inquiries", [])
    negatives = parsed_data.get("negative_items", [])

    deduped_accounts = dedupe_list(accounts, smart_account_dedupe_key)
    deduped_inquiries = dedupe_list(inquiries, smart_inquiry_dedupe_key)
    deduped_negatives = dedupe_list(negatives, smart_negative_dedupe_key)

    hard_inquiries = [i for i in deduped_inquiries if is_hard_inquiry(i)]
    soft_inquiries = [i for i in deduped_inquiries if not is_hard_inquiry(i)]

    return {
        "accounts": len(deduped_accounts),
        "hard_inquiries": len(hard_inquiries),
        "soft_inquiries": len(soft_inquiries),
        "negative_items": len(deduped_negatives),
        "raw_accounts": len(accounts),
        "raw_inquiries": len(inquiries),
        "raw_negatives": len(negatives),
    }
