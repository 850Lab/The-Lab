"""Report-level metrics lifted from app_real for reuse by services and UI."""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple


def count_hard_inquiries(parsed_data: Dict[str, Any]) -> int:
    return sum(
        1
        for inq in parsed_data.get("inquiries", [])
        if "hard" in inq.get("type", "").lower() or inq.get("type", "") == "Inquiry"
    )


def compute_report_totals(raw_text: str, _bureau: str = "") -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "accounts_total": None,
        "inquiries_total": None,
        "negatives_total": None,
        "public_records_total": None,
        "confidence": "LOW",
        "receipts": {"accounts": [], "inquiries": [], "negatives": [], "public_records": []},
    }

    text_lower = raw_text.lower()

    acct_total = None
    acct_receipts = []
    tu_acct_match = re.search(
        r"(?:total\s+(?:number\s+of\s+)?accounts|number\s+of\s+accounts|accounts?\s*:\s*)[\s:]*(\d+)",
        text_lower,
    )
    if tu_acct_match:
        acct_total = int(tu_acct_match.group(1))
        acct_receipts.append(tu_acct_match.group(0).strip()[:120])

    inq_total = None
    inq_receipts = []
    inq_match = re.search(
        r"(?:total\s+(?:number\s+of\s+)?inquiries|number\s+of\s+inquiries|inquiries?\s*:\s*)[\s:]*(\d+)",
        text_lower,
    )
    if inq_match:
        inq_total = int(inq_match.group(1))
        inq_receipts.append(inq_match.group(0).strip()[:120])

    neg_total = None
    neg_receipts = []
    neg_match = re.search(
        r"(?:total\s+(?:number\s+of\s+)?negative\s+items?|negative\s+items?\s*:\s*|adverse\s+items?\s*:\s*)[\s:]*(\d+)",
        text_lower,
    )
    if neg_match:
        neg_total = int(neg_match.group(1))
        neg_receipts.append(neg_match.group(0).strip()[:120])

    pr_total = None
    pr_receipts = []
    pr_match = re.search(
        r"(?:total\s+(?:number\s+of\s+)?public\s+records?|public\s+records?\s*:\s*)[\s:]*(\d+)",
        text_lower,
    )
    if pr_match:
        pr_total = int(pr_match.group(1))
        pr_receipts.append(pr_match.group(0).strip()[:120])

    result["accounts_total"] = acct_total
    result["inquiries_total"] = inq_total
    result["negatives_total"] = neg_total
    result["public_records_total"] = pr_total
    result["receipts"]["accounts"] = acct_receipts
    result["receipts"]["inquiries"] = inq_receipts
    result["receipts"]["negatives"] = neg_receipts
    result["receipts"]["public_records"] = pr_receipts

    all_sections = [acct_total, inq_total, neg_total, pr_total]
    non_none = [v for v in all_sections if v is not None]
    if len(non_none) == 4:
        result["confidence"] = "HIGH"
    elif len(non_none) >= 2:
        result["confidence"] = "MEDIUM"
    else:
        result["confidence"] = "LOW"

    return result


def compute_exactness(
    report_totals: Dict[str, Any], parsed_data: Dict[str, Any]
) -> Tuple[Dict[str, int], str]:
    parsed_totals = {
        "accounts_total": len(parsed_data.get("accounts", [])),
        "inquiries_total": len(parsed_data.get("inquiries", [])),
        "negatives_total": len(parsed_data.get("negative_items", [])),
        "public_records_total": len(parsed_data.get("public_records", [])),
    }

    if report_totals.get("confidence") != "HIGH":
        return parsed_totals, "NOT_EXACT"

    section_keys = ["accounts_total", "inquiries_total", "negatives_total", "public_records_total"]
    for key in section_keys:
        report_val = report_totals.get(key)
        if report_val is None:
            return parsed_totals, "NOT_EXACT"
        if parsed_totals[key] != report_val:
            return parsed_totals, "NOT_EXACT"

    return parsed_totals, "EXACT"


def is_hard_inquiry(inquiry: Dict[str, Any]) -> bool:
    raw_text = (inquiry.get("raw_text", "") or "").lower()
    inq_type = (inquiry.get("type", "") or "").lower()

    soft_indicators = [
        "soft",
        "promotional",
        "preapproved",
        "pre-approved",
        "promo",
        "account review",
        "consumer disclosure",
        "account monitoring",
        "insurance",
        "employment",
        "marketing",
        "periodic review",
        "existing account",
        "ar ",
        "prom",
        "am ",
    ]

    if any(s in raw_text for s in soft_indicators):
        return False
    if any(s in inq_type for s in soft_indicators):
        return False

    if "regular inquir" in raw_text or "credit inquir" in raw_text:
        return True

    return True
