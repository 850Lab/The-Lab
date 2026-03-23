from dataclasses import dataclass, field
from typing import Optional
import re


@dataclass
class ProvenanceRef:
    page: int
    bbox: list

    def to_dict(self):
        return {"page": self.page, "bbox": self.bbox}


@dataclass
class CanonicalRecord:
    record_type: str
    fields: dict
    provenance: dict
    record_bbox: Optional[ProvenanceRef] = None

    def to_dict(self):
        return {
            "record_type": self.record_type,
            "fields": dict(self.fields),
            "provenance": {k: v.to_dict() for k, v in self.provenance.items()},
            "record_bbox": self.record_bbox.to_dict() if self.record_bbox else None,
        }


ACCOUNT_LABELS = {
    "creditor_name": [
        "ACCOUNT NAME", "CREDITOR NAME", "CREDITOR", "SUBSCRIBER NAME",
    ],
    "account_number_last4": [
        "ACCOUNT NUMBER", "ACCT #", "ACCOUNT #", "ACCT NUMBER",
    ],
    "status": [
        "STATUS", "ACCOUNT STATUS", "CURRENT STATUS", "PAY STATUS",
    ],
    "balance": [
        "BALANCE", "CURRENT BALANCE",
    ],
    "date_opened": [
        "DATE OPENED", "OPEN DATE",
    ],
    "date_reported": [
        "DATE REPORTED", "DATE UPDATED", "LAST REPORTED",
    ],
}

CREDITOR_START_LABELS = set(ACCOUNT_LABELS["creditor_name"])

Y_TOLERANCE = 4.0
SEARCH_NEXT_LINES_MAX = 3


def detect_tu_variant_from_text(plain_text):
    text_lower = plain_text.lower()
    if 'transunion online service center' in text_lower:
        return 'TU_OSC'
    if any(marker in text_lower for marker in [
        'annualcreditreport', 'annual credit report', 'view credit report',
        'annualcreditreport.transunion.com',
    ]):
        return 'TU_ACR'
    return 'TU_UNKNOWN'


def detect_layout_signature(layout):
    has_account_name_labels = False
    has_osc_creditor_headers = False
    has_account_information_labels = False
    has_adverse_section_header = False
    has_satisfactory_section_header = False

    osc_pattern = re.compile(r'^[A-Z][A-Z0-9\s/&\.\-]+?\s+(?:\d{5,}\*+|\*{4,}\d+)$')

    for page_data in layout.get("pages", []):
        for line in page_data.get("lines", []):
            upper = line["text"].upper().strip()
            if upper == "ACCOUNT NAME":
                has_account_name_labels = True
            if upper == "ACCOUNT INFORMATION":
                has_account_information_labels = True
            if "ACCOUNTS WITH ADVERSE INFORMATION" in upper:
                has_adverse_section_header = True
            if upper.startswith("SATISFACTORY ACCOUNTS"):
                has_satisfactory_section_header = True
            if osc_pattern.match(upper):
                has_osc_creditor_headers = True

    has_section_derived_structure = (
        has_adverse_section_header or has_satisfactory_section_header
    )

    return {
        "has_account_name_labels": has_account_name_labels,
        "has_osc_creditor_headers": has_osc_creditor_headers,
        "has_account_information_labels": has_account_information_labels,
        "has_adverse_section_header": has_adverse_section_header,
        "has_satisfactory_section_header": has_satisfactory_section_header,
        "has_section_derived_structure": has_section_derived_structure,
    }


def build_account_records(layout, variant):
    all_records = []

    for page_data in layout["pages"]:
        page_idx = page_data["page_index"]
        lines = page_data["lines"]
        if not lines:
            continue

        anchor_indices = _find_creditor_anchors(lines, variant)

        for ai, anchor_idx in enumerate(anchor_indices):
            if ai + 1 < len(anchor_indices):
                region_end_y = lines[anchor_indices[ai + 1]]["y0"] - 0.1
            else:
                region_end_y = page_data["height"] + 1.0

            anchor_line = lines[anchor_idx]
            region_lines = [
                l for l in lines
                if l["y0"] >= anchor_line["y0"] and l["y0"] < region_end_y
            ]

            if not region_lines:
                continue

            record = _extract_record_from_region(
                region_lines, page_idx, anchor_line, variant
            )

            if record is not None:
                all_records.append(record)

    all_records.sort(key=lambda r: (
        r.record_bbox.page if r.record_bbox else 0,
        r.record_bbox.bbox[1] if r.record_bbox else 0,
        r.fields.get("creditor_name", ""),
    ))

    return all_records


def _find_creditor_anchors(lines, variant):
    anchors = []

    if variant == "TU_ACR":
        for i, line in enumerate(lines):
            upper = line["text"].upper().strip()
            if upper == "ACCOUNT NAME":
                if i + 1 < len(lines):
                    anchors.append(i + 1)
            elif _looks_like_acr_creditor_start(line, lines, i):
                anchors.append(i)
    else:
        for i, line in enumerate(lines):
            upper = line["text"].upper().strip()
            if _looks_like_osc_creditor_header(upper):
                anchors.append(i)

    return anchors


def _looks_like_acr_creditor_start(line, lines, idx):
    text = line["text"].strip()
    upper = text.upper()

    if len(text) < 2 or len(text) > 80:
        return False

    if re.match(r'^\d{1,2}/\d{1,2}/\d{2,4}$', text):
        return False
    if re.match(r'^[\d,\.\$\*\-\s]+$', text):
        return False
    if re.match(r'^\d+$', text):
        return False

    skip_labels = {
        "ACCOUNT INFORMATION", "ACCOUNT NAME", "RATINGS", "REMARKS", "CODE",
        "BALANCE", "STATUS", "PAYMENT/REMARKS KEY", "SATISFACTORY ACCOUNTS",
        "ACCOUNTS WITH ADVERSE INFORMATION", "PERSONAL INFORMATION",
        "PERSONAL CREDIT REPORT", "INQUIRIES", "REGULAR INQUIRIES",
        "REQUESTS VIEWED ONLY BY YOU", "PUBLIC RECORDS", "CONSUMER STATEMENTS",
        "CREDIT REPORT DATE", "SOCIAL SECURITY NUMBER", "DATE OF BIRTH",
        "ADDRESSES", "PHONE NUMBERS", "EMPLOYERS", "NAME",
        "CURRENT ADDRESS", "OTHER ADDRESS", "DATE REPORTED",
        "ACCOUNT TYPE", "LOAN TYPE", "DATE OPENED", "DATE UPDATED",
        "PAY STATUS", "MONTHLY PAYMENT", "HIGH BALANCE", "CREDIT LIMIT",
        "RESPONSIBILITY", "TERMS", "PAYMENT HISTORY",
    }
    if upper in skip_labels:
        return False

    has_following_account_info = False
    for j in range(idx + 1, min(idx + 6, len(lines))):
        if lines[j]["text"].upper().strip() == "ACCOUNT INFORMATION":
            has_following_account_info = True
            break

    return has_following_account_info


def _looks_like_osc_creditor_header(upper_text):
    pattern = r'^([A-Z][A-Z0-9\s/&\.\-]+?)\s+(\d{5,}\*+|\*{4,}\d+)$'
    return bool(re.match(pattern, upper_text))


def _extract_record_from_region(region_lines, page_idx, anchor_line, variant):
    fields = {}
    provenance = {}

    creditor_name = anchor_line["text"].strip()

    if variant != "TU_ACR":
        upper = creditor_name.upper()
        m = re.match(r'^(.+?)\s+(\d{5,}\*+|\*{4,}\d+)$', upper)
        if m:
            creditor_name = m.group(1).strip()
            acct_num_raw = m.group(2).strip()
            last_digits = re.sub(r'[^0-9]', '', acct_num_raw)
            if last_digits:
                fields["account_number_last4"] = last_digits[-4:] if len(last_digits) >= 4 else last_digits
                provenance["account_number_last4"] = ProvenanceRef(
                    page=page_idx,
                    bbox=[anchor_line["x0"], anchor_line["y0"], anchor_line["x1"], anchor_line["y1"]]
                )

    reject_names = {
        "ratings", "remarks", "code", "balance", "status",
        "payment/remarks key", "satisfactory accounts",
        "accounts with adverse information",
    }
    if creditor_name.lower() in reject_names or len(creditor_name) < 2:
        return None

    fields["creditor_name"] = creditor_name
    provenance["creditor_name"] = ProvenanceRef(
        page=page_idx,
        bbox=[anchor_line["x0"], anchor_line["y0"], anchor_line["x1"], anchor_line["y1"]]
    )

    for field_name, label_variants in ACCOUNT_LABELS.items():
        if field_name == "creditor_name":
            continue
        if field_name == "account_number_last4" and field_name in fields:
            continue

        val, val_line = _find_label_value(region_lines, label_variants)
        if val is not None and val_line is not None:
            if field_name == "account_number_last4":
                digits = re.sub(r'[^0-9]', '', val)
                if digits:
                    fields[field_name] = digits[-4:] if len(digits) >= 4 else digits
                else:
                    fields[field_name] = None
            elif field_name == "balance":
                cleaned = re.sub(r'[^\d.]', '', val)
                fields[field_name] = cleaned if cleaned else None
            else:
                fields[field_name] = val

            if fields.get(field_name) is not None:
                provenance[field_name] = ProvenanceRef(
                    page=page_idx,
                    bbox=[val_line["x0"], val_line["y0"], val_line["x1"], val_line["y1"]]
                )

    has_any_data_field = any(
        fields.get(f) is not None
        for f in ["balance", "status", "date_opened", "date_reported", "account_number_last4"]
    )
    if not has_any_data_field:
        return None

    region_x0 = min(l["x0"] for l in region_lines)
    region_y0 = min(l["y0"] for l in region_lines)
    region_x1 = max(l["x1"] for l in region_lines)
    region_y1 = max(l["y1"] for l in region_lines)

    record_bbox = ProvenanceRef(
        page=page_idx,
        bbox=[region_x0, region_y0, region_x1, region_y1]
    )

    return CanonicalRecord(
        record_type="account",
        fields=fields,
        provenance=provenance,
        record_bbox=record_bbox,
    )


def _find_label_value(lines, label_variants):
    label_set = {lv.upper() for lv in label_variants}

    for i, line in enumerate(lines):
        upper_text = line["text"].upper().strip()

        for label in label_set:
            if upper_text == label or upper_text.startswith(label + " ") or upper_text.startswith(label + ":"):
                remainder = line["text"].strip()[len(label):].strip().lstrip(":").strip()
                if remainder:
                    return remainder, line

                for j in range(i + 1, min(i + 1 + SEARCH_NEXT_LINES_MAX, len(lines))):
                    candidate = lines[j]
                    candidate_upper = candidate["text"].upper().strip()
                    is_another_label = False
                    for other_labels in ACCOUNT_LABELS.values():
                        if candidate_upper in {ol.upper() for ol in other_labels}:
                            is_another_label = True
                            break
                    if is_another_label:
                        break
                    candidate_text = candidate["text"].strip()
                    if candidate_text and len(candidate_text) > 0:
                        return candidate_text, candidate

    return None, None


def canonical_records_to_parsed_accounts(records):
    accounts = []
    for rec in records:
        f = rec.fields
        acct = {
            "account_name": f.get("creditor_name"),
            "rule": "TRANSLATOR_LAYOUT",
            "tu_parser": "translator",
        }

        if f.get("account_number_last4"):
            acct["account_number"] = f["account_number_last4"]

        if f.get("status"):
            acct["status"] = f["status"]

        if f.get("balance"):
            acct["balance"] = f["balance"]

        if f.get("date_opened"):
            acct["date_opened"] = f["date_opened"]

        if f.get("date_reported"):
            acct["date_updated"] = f["date_reported"]

        if rec.record_bbox:
            acct["page"] = rec.record_bbox.page + 1

        prov_parts = []
        if f.get("creditor_name"):
            prov_parts.append(f["creditor_name"])
        if f.get("account_number_last4"):
            prov_parts.append(f["account_number_last4"])
        acct["receipt_snippet"] = " ".join(prov_parts)[:120]

        acct["confidence"] = "HIGH" if f.get("balance") else "MEDIUM"

        acct["provenance"] = {
            k: v.to_dict() for k, v in rec.provenance.items()
        }

        accounts.append(acct)

    return accounts
