import re
from typing import Optional


ADVERSE_TOKENS = {
    "collection", "charge off", "charged off", "repossession",
    "foreclosure", "past due", "days past due", "days late",
    "120 days", "90 days", "60 days", "30 days",
    "voluntarily surrendered", "bankruptcy",
    "account 120 days past due date",
    "account 90 days past due date",
    "account 60 days past due date",
    "account 30 days past due date",
    "collection account",
}

GOOD_TOKENS = {
    "current", "paid as agreed", "paying as agreed",
    "paid, closed", "current account", "paid",
    "current; paid or paying as agreed",
    "pays as agreed",
    "never late", "open/never late",
    "paid, closed/never late",
}

SECTION_HEADER_ADVERSE = "accounts with adverse information"
SECTION_HEADER_SATISFACTORY = "satisfactory accounts"

INQUIRY_SECTION_MARKERS = [
    "regular inquiries",
    "inquiries that may affect",
    "requests viewed only by you",
    "account review inquiries",
]


def detect_section_boundaries(full_text):
    text_lower = full_text.lower()

    adverse_start = None
    satisfactory_start = None
    inquiries_start = None

    idx = text_lower.find(SECTION_HEADER_ADVERSE)
    if idx >= 0:
        adverse_start = idx

    idx = text_lower.find(SECTION_HEADER_SATISFACTORY)
    if idx >= 0:
        satisfactory_start = idx

    for marker in INQUIRY_SECTION_MARKERS:
        idx = text_lower.find(marker)
        if idx >= 0:
            if satisfactory_start is not None and idx > satisfactory_start:
                inquiries_start = idx
                break
            elif adverse_start is not None and idx > adverse_start:
                inquiries_start = idx
                break

    return {
        "adverse_start": adverse_start,
        "satisfactory_start": satisfactory_start,
        "inquiries_start": inquiries_start,
    }


def classify_by_pay_status(pay_status):
    if not pay_status or not isinstance(pay_status, str):
        return "UNKNOWN"

    raw = pay_status.strip()
    cleaned = raw.strip("><").strip()
    cleaned_lower = cleaned.lower()

    if raw.startswith(">") and raw.endswith("<"):
        return "ADVERSE"

    if ">" in raw and "<" in raw:
        return "ADVERSE"

    for token in ADVERSE_TOKENS:
        if token in cleaned_lower:
            return "ADVERSE"

    for token in GOOD_TOKENS:
        if token in cleaned_lower:
            return "GOOD_STANDING"

    return "UNKNOWN"


def classify_by_section_position(account, section_boundaries):
    adverse_start = section_boundaries.get("adverse_start")
    satisfactory_start = section_boundaries.get("satisfactory_start")
    inquiries_start = section_boundaries.get("inquiries_start")

    text_position = account.get("_text_position")
    if text_position is None:
        return None

    if adverse_start is not None and satisfactory_start is not None:
        if adverse_start < text_position < satisfactory_start:
            return "ADVERSE"
        if satisfactory_start < text_position:
            if inquiries_start is not None:
                if text_position < inquiries_start:
                    return "GOOD_STANDING"
            else:
                return "GOOD_STANDING"

    if adverse_start is not None and satisfactory_start is None:
        if text_position > adverse_start:
            return "ADVERSE"

    if satisfactory_start is not None and adverse_start is None:
        if text_position > satisfactory_start:
            return "GOOD_STANDING"

    return None


def _locate_account_in_text(account, full_text):
    creditor = account.get("account_name", "")
    if not creditor:
        return None

    acct_num = account.get("account_number", "")
    if acct_num:
        search_str = f"{creditor} {acct_num}"
        idx = full_text.find(search_str)
        if idx >= 0:
            return idx

    idx = full_text.find(creditor)
    if idx >= 0:
        return idx

    return None


DELINQUENCY_ADVERSE_FLAGS = {"30", "60", "90", "120", "150", "180", "V", "F", "C", "CO", "B", "R"}


def classify_by_delinquency_flags(account):
    flags = account.get("delinquency_flags", [])
    if not flags:
        return None
    flag_set = {str(f).upper() for f in flags}
    if flag_set & DELINQUENCY_ADVERSE_FLAGS:
        return "ADVERSE"
    return None


def classify_by_bureau_label(account):
    if account.get("potentially_negative"):
        return "ADVERSE"
    return None


def classify_accounts(accounts, full_text, variant=None, layout=None, bureau=None):
    boundaries = detect_section_boundaries(full_text)
    has_section_structure = (
        boundaries["adverse_start"] is not None
        or boundaries["satisfactory_start"] is not None
    )

    for account in accounts:
        text_pos = _locate_account_in_text(account, full_text)
        account["_text_position"] = text_pos

        section_cls = None
        token_cls = None
        flag_cls = None
        label_cls = None

        label_cls = classify_by_bureau_label(account)

        if has_section_structure and text_pos is not None:
            section_cls = classify_by_section_position(account, boundaries)

        pay_status = account.get("status", "") or account.get("pay_status_raw", "")
        token_cls = classify_by_pay_status(pay_status)

        flag_cls = classify_by_delinquency_flags(account)

        if label_cls is not None:
            account["classification"] = label_cls
            account["classification_source"] = "BUREAU_LABEL"
            account["classification_rule"] = "CLS-09"
        elif section_cls is not None:
            account["classification"] = section_cls
            account["classification_source"] = "SECTION_HEADER"
            if section_cls == "ADVERSE":
                account["classification_rule"] = "CLS-01"
            else:
                account["classification_rule"] = "CLS-02"
        elif flag_cls is not None and token_cls in ("GOOD_STANDING", "UNKNOWN"):
            account["classification"] = flag_cls
            account["classification_source"] = "DELINQUENCY_FLAGS"
            account["classification_rule"] = "CLS-08"
        elif token_cls != "UNKNOWN":
            account["classification"] = token_cls
            account["classification_source"] = "PAY_STATUS_TOKEN"
            if token_cls == "ADVERSE":
                account["classification_rule"] = "CLS-04"
            else:
                account["classification_rule"] = "CLS-05"
        else:
            account["classification"] = "UNKNOWN"
            account["classification_source"] = "UNCLASSIFIED"
            account["classification_rule"] = "CLS-07"

        account["classification_provenance"] = {
            "text_position": text_pos,
            "section_result": section_cls,
            "token_result": token_cls,
            "flag_result": flag_cls,
            "label_result": label_cls,
            "pay_status_used": pay_status[:100] if pay_status else None,
            "delinquency_flags": account.get("delinquency_flags", []),
            "potentially_negative": account.get("potentially_negative", False),
            "boundaries": {
                "adverse_start": boundaries.get("adverse_start"),
                "satisfactory_start": boundaries.get("satisfactory_start"),
                "inquiries_start": boundaries.get("inquiries_start"),
            },
        }

        if "_text_position" in account:
            del account["_text_position"]

    return accounts


def compute_negative_items(classified_accounts):
    negative_items = []
    for acct in classified_accounts:
        if acct.get("classification") == "ADVERSE":
            negative_items.append({
                "creditor_name": acct.get("account_name"),
                "account_number": acct.get("account_number"),
                "classification_source": acct.get("classification_source"),
                "classification_rule": acct.get("classification_rule"),
                "page": acct.get("page"),
                "pay_status": acct.get("status"),
                "balance": acct.get("balance"),
                "provenance": acct.get("provenance") or acct.get("classification_provenance"),
            })
    return negative_items


def count_by_classification(classified_accounts):
    counts = {"ADVERSE": 0, "GOOD_STANDING": 0, "UNKNOWN": 0}
    for acct in classified_accounts:
        cls = acct.get("classification", "UNKNOWN")
        if cls in counts:
            counts[cls] += 1
        else:
            counts["UNKNOWN"] += 1
    return counts
