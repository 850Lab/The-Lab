import re
import json
import logging
from io import BytesIO

import diagnostics_store as diag_store

_pdf_log = logging.getLogger(__name__)
from layout_extract import extract_layout, to_plain_text
from translator import build_account_records, detect_tu_variant_from_text, canonical_records_to_parsed_accounts, detect_layout_signature
from totals_detector import detect_section_totals_with_sources, detect_totals_mode_with_sources, self_verify_totals
from completeness import compute_completeness
from normalization import normalize_parsed_data
from classifier import classify_accounts, compute_negative_items, count_by_classification

BOILERPLATE_PHRASES = [
    'statement to', 'statement of', 'report to', 'consumer report',
    'credit report', 'credit file', 'file disclosure', 'disclosure statement',
    'prepared for', 'regarding', 'subject of', 'information about',
    'response center', 'dispute center', 'service center',
]

BOILERPLATE_NAMES = [
    'response center', 'transunion', 'experian', 'equifax',
    'consumer relations', 'dispute department', 'investigation department',
    'consumer response', 'consumer assistance', 'dispute center', 'service center',
]

BOILERPLATE_ADDRESSES = [
    'id address id', 'address id', 'id address',
    'n/a', 'not available', 'not reported', 'none',
]

def sanitize_name_field(name_value):
    if not name_value or not isinstance(name_value, str):
        return None
    
    name_value = ' '.join(name_value.strip().split())
    if not name_value:
        return None
    
    name_lower = name_value.lower()
    for phrase in BOILERPLATE_PHRASES:
        if phrase in name_lower:
            return None
    
    for phrase in BOILERPLATE_NAMES:
        if phrase in name_lower:
            return None
    
    if name_value == name_value.lower():
        return None
    
    alpha_tokens = [t for t in name_value.split() if any(c.isalpha() for c in t)]
    if len(alpha_tokens) < 2:
        return None
    
    has_capital = any(c.isupper() for c in name_value)
    if not has_capital:
        return None
    
    return name_value

def sanitize_address_field(address_value):
    if not address_value or not isinstance(address_value, str):
        return None
    address_value = address_value.strip()
    if len(address_value) < 5:
        return None
    if not any(c.isdigit() for c in address_value) and not any(c.isalpha() for c in address_value):
        return None
    address_lower = address_value.lower().strip()
    for phrase in BOILERPLATE_PHRASES:
        if phrase in address_lower:
            return None
    for phrase in BOILERPLATE_ADDRESSES:
        if address_lower == phrase or address_lower.replace(' ', '') == phrase.replace(' ', ''):
            return None
    return address_value

def sanitize_dob_field(dob_value):
    if not dob_value or not isinstance(dob_value, str):
        return None
    dob_value = dob_value.strip()
    if len(dob_value) < 4:
        return None
    if not any(c.isdigit() for c in dob_value):
        return None
    return dob_value

def sanitize_ssn_field(ssn_value):
    if not ssn_value or not isinstance(ssn_value, str):
        return None
    ssn_value = ssn_value.strip()
    digits = ''.join(c for c in ssn_value if c.isdigit())
    if len(digits) < 4:
        return None
    return ssn_value

def _extract_truth_value(field):
    if isinstance(field, dict):
        val = field.get('value') or field.get('extracted_value')
        if val:
            return str(val).strip()
    if isinstance(field, str):
        return field.strip() if field.strip() else None
    return None

def sanitize_identity_info(bureau_info):
    sanitized = dict(bureau_info) if bureau_info else {}
    
    if 'name' not in sanitized or not sanitized.get('name'):
        for alt_key in ['full_name', 'consumer_name']:
            if alt_key in sanitized:
                val = _extract_truth_value(sanitized[alt_key])
                if val:
                    sanitized['name'] = val
                    break
    
    if 'address' not in sanitized or not sanitized.get('address'):
        for alt_key in ['current_address', 'mailing_address', 'residence']:
            if alt_key in sanitized:
                val = _extract_truth_value(sanitized[alt_key])
                if val:
                    sanitized['address'] = val
                    break
    
    if 'dob' not in sanitized or not sanitized.get('dob'):
        if 'date_of_birth' in sanitized:
            val = _extract_truth_value(sanitized['date_of_birth'])
            if val:
                sanitized['dob'] = val
    
    if 'ssn' not in sanitized or not sanitized.get('ssn'):
        for alt_key in ['ssn_last_four', 'ssn_last4']:
            if alt_key in sanitized:
                val = _extract_truth_value(sanitized[alt_key])
                if val:
                    sanitized['ssn'] = f"XXX-XX-{val}" if len(val) == 4 else val
                    break
    
    if 'name' in sanitized:
        sanitized['name'] = sanitize_name_field(sanitized['name'])
    if 'address' in sanitized:
        sanitized['address'] = sanitize_address_field(sanitized['address'])
    if 'dob' in sanitized:
        sanitized['dob'] = sanitize_dob_field(sanitized['dob'])
    if 'date_of_birth' in sanitized:
        sanitized['date_of_birth'] = sanitize_dob_field(sanitized['date_of_birth'])
    if 'ssn' in sanitized:
        sanitized['ssn'] = sanitize_ssn_field(sanitized['ssn'])
    
    return sanitized

BUREAU_PATTERNS = {
    'equifax': {
        'identifiers': ['equifax', 'equifax information services', 'EFX'],
        'account_pattern': r'(?:Account\s*(?:Name|Number)?[:\s]+)(.+?)(?:\n|Account Status)',
        'balance_pattern': r'(?:Balance|Current Balance)[:\s]+\$?([\d,]+\.?\d*)',
        'status_pattern': r'(?:Account Status|Status)[:\s]+(\w+)',
        'payment_pattern': r'(?:Payment Status|Pay Status)[:\s]+(.+?)(?:\n|$)',
        'opened_pattern': r'(?:Date Opened|Opened)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
        'high_credit_pattern': r'(?:High Credit|Credit Limit)[:\s]+\$?([\d,]+)',
    },
    'experian': {
        'identifiers': ['experian', 'experian information solutions'],
        'account_pattern': r'(?:Creditor Name|Account)[:\s]+(.+?)(?:\n|Status)',
        'balance_pattern': r'(?:Balance Owed|Balance)[:\s]+\$?([\d,]+\.?\d*)',
        'status_pattern': r'(?:Status|Account Status)[:\s]+(\w+)',
        'payment_pattern': r'(?:Payment Pattern|Payment History)[:\s]+(.+?)(?:\n|$)',
        'opened_pattern': r'(?:Open Date|Date Opened)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
        'high_credit_pattern': r'(?:Highest Balance|Credit Limit)[:\s]+\$?([\d,]+)',
    },
    'transunion': {
        'identifiers': ['transunion', 'trans union'],
        'account_pattern': r'(?:Subscriber Name|Creditor)[:\s]+(.+?)(?:\n|Account)',
        'balance_pattern': r'(?:Current Balance|Balance)[:\s]+\$?([\d,]+\.?\d*)',
        'status_pattern': r'(?:Pay Status|Account Status)[:\s]+(\w+)',
        'payment_pattern': r'(?:Payment Rating|Pay Pattern)[:\s]+(.+?)(?:\n|$)',
        'opened_pattern': r'(?:Date Opened|Opened)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
        'high_credit_pattern': r'(?:High Balance|Credit Limit)[:\s]+\$?([\d,]+)',
    }
}

def run_tu_diagnostics(full_text, bureau, scores, evidence, parsed_data):
    """
    ========================================================================
    TEMPORARY DIAGNOSTICS — TransUnion 0-accounts investigation
    Remove after root cause is identified.
    ========================================================================
    Returns a dict with all diagnostic data for console + UI display.
    """
    diag = {}

    diag['bureau_detection'] = {
        'bureau_detected': bureau,
        'scores': scores,
        'matched_patterns': evidence,
    }

    parser_used = 'TU' if bureau == 'transunion' else ('EX' if bureau == 'experian' else 'EQ')
    tu_variant = detect_tu_variant(full_text) if bureau == 'transunion' else 'N/A'
    acr_parser_label = 'parse_accounts_tu_acr' if tu_variant == 'TU_ACR' else ('parse_accounts_transunion_osc' if bureau == 'transunion' else 'generic')
    diag['parser_path'] = {
        'parser_called': parser_used,
        'tu_parser_used': bureau == 'transunion',
        'tu_variant': tu_variant,
        'accounts_parser': acr_parser_label,
        'WARNING': None if bureau == 'transunion' else f"TU parser was NOT used — bureau detected as '{bureau}'",
    }

    text_lower = full_text.lower()
    sanity_needles = ["ACCOUNT", "Account Type", "Balance", "Date Opened", "TransUnion"]
    needle_hits = {}
    for needle in sanity_needles:
        needle_hits[needle] = needle.lower() in text_lower
    diag['raw_text_sanity'] = {
        'raw_text_length': len(full_text),
        'needle_hits': needle_hits,
    }

    tu_section_anchors = [
        'Revolving', 'Installment', 'Open Accounts', 'Mortgage',
        'Collection', 'Account Information', 'ACCOUNT INFORMATION',
        'REGULAR INQUIRIES', 'REQUESTS VIEWED ONLY BY YOU',
    ]
    found_anchors = [a for a in tu_section_anchors if a.lower() in text_lower]
    diag['tu_section_anchors'] = {
        'found': found_anchors if found_anchors else 'NO_TU_SECTIONS_FOUND',
    }

    accounts_list = parsed_data.get('accounts', [])
    reject_counters = parsed_data.get('reject_counters', {}).get('accounts', {})
    total_rejects = sum(reject_counters.values()) if isinstance(reject_counters, dict) else 0
    reason = 'unknown'
    if not found_anchors and len(accounts_list) == 0:
        reason = 'no_sections_found'
    elif total_rejects > 0 and len(accounts_list) == 0:
        reason = 'all_candidates_rejected'
    elif len(accounts_list) == 0 and found_anchors:
        reason = 'parser_found_sections_but_no_account_headers_matched'
    elif len(accounts_list) > 0:
        reason = 'accounts_present_no_issue'
    diag['safety_gate'] = {
        'accounts_returned': len(accounts_list),
        'reject_counters': reject_counters,
        'total_rejects': total_rejects,
        'empty_reason': reason,
    }

    tu_header_pattern = r'^([A-Z][A-Z0-9\s/&\.\-,\']+?)\s+([A-Z0-9]{3,}\*{3,}|\*{4,}[A-Z0-9]+)$'
    header_matches_found = 0
    sample_headers = []
    for line in full_text.split('\n'):
        if re.match(tu_header_pattern, line.strip()):
            header_matches_found += 1
            if len(sample_headers) < 5:
                sample_headers.append(line.strip()[:80])
    diag['tu_header_regex_scan'] = {
        'pattern': tu_header_pattern,
        'matches_in_full_text': header_matches_found,
        'sample_matches': sample_headers,
    }

    print("=" * 70)
    print("[TU_DIAG] ===== TEMPORARY TransUnion Diagnostics =====")
    print(f"[TU_DIAG] 1) Bureau Detection: {json.dumps(diag['bureau_detection'], indent=2)}")
    print(f"[TU_DIAG] 2) Parser Path: {json.dumps(diag['parser_path'], indent=2)}")
    print(f"[TU_DIAG] 3) Raw Text Sanity: {json.dumps(diag['raw_text_sanity'], indent=2)}")
    print(f"[TU_DIAG] 4) TU Section Anchors: {json.dumps(diag['tu_section_anchors'], indent=2)}")
    print(f"[TU_DIAG] 5) Safety Gate: {json.dumps(diag['safety_gate'], indent=2)}")
    print(f"[TU_DIAG] 6) TU Header Regex Scan: {json.dumps(diag['tu_header_regex_scan'], indent=2)}")
    print("=" * 70)

    return diag


def detect_bureau(text, debug=False, return_details=False):
    """
    Detect bureau from report text.
    
    Uses a tiered approach:
      1. Definitive URL/structural fingerprints (highest priority)
      2. Weighted keyword scoring with position-aware bonuses
      3. 3-bureau combined report detection to avoid misclassification
    
    If return_details=True, returns (bureau, scores, evidence) tuple.
    """
    text_lower = text.lower()
    first_500 = text_lower[:500]
    first_2000 = text_lower[:2000]
    first_5000 = text_lower[:5000]

    scores = {'transunion': 0, 'experian': 0, 'equifax': 0}
    evidence = {'transunion': [], 'experian': [], 'equifax': []}

    DEFINITIVE_FINGERPRINTS = {
        'transunion': [
            'annualcreditreport.transunion.com',
            'transunion.com/dispute',
            'transunion.com/credit-help',
            'tu file number',
            'personal credit report for:',
        ],
        'experian': [
            'annualcreditreport.experian.com',
            'experian.com/dispute',
            'experian credit report',
            'at a\nglance',
            'at a glance',
        ],
        'equifax': [
            'annualcreditreport.equifax.com',
            'equifax.com/dispute',
            'equifax credit report',
            'efx file',
            'confirmation number:',
        ],
    }

    for bureau, fingerprints in DEFINITIVE_FINGERPRINTS.items():
        for fp in fingerprints:
            if fp in first_5000:
                scores[bureau] += 25
                evidence[bureau].append(f"definitive:'{fp}'")

    STRUCTURAL_PATTERNS = {
        'transunion': [
            'account name\n',
            'accounts with adverse information',
            'satisfactory accounts',
            'regular inquiries',
            'account review inquiries',
            'you have been on our files since',
        ],
        'experian': [
            'potentially negative',
            'accounts in good standing',
            'credit inquiries',
            'your statement',
        ],
        'equifax': [
            'credit accounts',
            'negative information',
            'account number:',
            'high credit:',
            'date opened:',
        ],
    }

    for bureau, patterns in STRUCTURAL_PATTERNS.items():
        for pat in patterns:
            if pat in text_lower:
                scores[bureau] += 3
                evidence[bureau].append(f"structural:'{pat}'")

    BRAND_PATTERNS = {
        'transunion': {
            'strong': ['transunion credit report', 'transunion consumer report', 'trans union llc', 'transunion consumer relations'],
            'identifiers': ['transunion', 'trans union'],
        },
        'experian': {
            'strong': ['experian credit report', 'experian consumer report', 'experian information solutions', 'experian consumer services'],
            'identifiers': ['experian'],
        },
        'equifax': {
            'strong': ['equifax credit report', 'equifax consumer report', 'equifax information services', 'equifax credit information services'],
            'identifiers': ['equifax', 'efx'],
        },
    }

    for bureau, patterns in BRAND_PATTERNS.items():
        for strong in patterns['strong']:
            if strong in first_2000:
                scores[bureau] += 10
                evidence[bureau].append(f"strong:'{strong}'")

        for ident in patterns['identifiers']:
            if ident in first_500:
                scores[bureau] += 5
                evidence[bureau].append(f"header:'{ident}'")
            elif ident in first_2000:
                scores[bureau] += 3
                evidence[bureau].append(f"early:'{ident}'")
            elif ident in text_lower:
                scores[bureau] += 1
                evidence[bureau].append(f"body:'{ident}'")

    THREE_B_MARKERS = [
        'your 3b report',
        '3-bureau',
        'three bureau',
        'transunion®\nexperian®\nequifax®',
        'transunion® experian® equifax®',
        'smartcredit.com',
    ]
    is_3b = any(m in text_lower for m in THREE_B_MARKERS)

    if is_3b:
        three_b_source = None
        if 'smartcredit.com' in text_lower:
            three_b_source = 'smartcredit'
        evidence_note = f"3b_report:source={three_b_source or 'unknown'}"

        summary_match = re.search(
            r'summary\s*\n\s*transunion.*?experian.*?equifax.*?\n(.*?)(?:account history|payment history|\n\n)',
            text_lower, re.DOTALL
        )
        if summary_match:
            summary_text = summary_match.group(1)
            for line in summary_text.split('\n'):
                if 'total accounts' in line:
                    nums = re.findall(r'(\d+)', line)
                    if len(nums) >= 3:
                        tu_count, exp_count, eq_count = int(nums[0]), int(nums[1]), int(nums[2])
                        max_count = max(tu_count, exp_count, eq_count)
                        if tu_count == max_count:
                            scores['transunion'] += 5
                            evidence['transunion'].append(f"3b_most_accounts:{tu_count}")
                        if exp_count == max_count:
                            scores['experian'] += 5
                            evidence['experian'].append(f"3b_most_accounts:{exp_count}")
                        if eq_count == max_count:
                            scores['equifax'] += 5
                            evidence['equifax'].append(f"3b_most_accounts:{eq_count}")
                    break

    if debug:
        print(f"[BUREAU_DETECT] Scores: {scores}")
        print(f"[BUREAU_DETECT] Evidence: {evidence}")
        if is_3b:
            print(f"[BUREAU_DETECT] 3-bureau combined report detected")

    if is_3b:
        if debug:
            print("[BUREAU_DETECT] Result: 3bureau (combined multi-bureau report)")
        if return_details:
            return '3bureau', dict(scores), dict(evidence)
        return '3bureau'

    max_score = max(scores.values())
    if max_score == 0:
        if debug:
            print("[BUREAU_DETECT] Result: unknown (no matches)")
        if return_details:
            return 'unknown', dict(scores), dict(evidence)
        return 'unknown'

    winners = [b for b, s in scores.items() if s == max_score]

    if len(winners) == 1:
        result = winners[0]
    else:
        definitive_winners = []
        for b in winners:
            if any(e.startswith('definitive:') for e in evidence[b]):
                definitive_winners.append(b)
        if len(definitive_winners) == 1:
            result = definitive_winners[0]
        else:
            for bureau in ['transunion', 'experian', 'equifax']:
                if bureau in winners:
                    result = bureau
                    break
            else:
                result = winners[0]

    if debug:
        print(f"[BUREAU_DETECT] Result: {result} (score={max_score}, evidence={evidence[result]})")

    if return_details:
        return result, dict(scores), dict(evidence)
    return result

def extract_text_with_ocr(pdf_bytes, max_pages=30):
    """
    Returns (full_text, page_texts, num_pages, error_meta).
    error_meta is None on success, else {"code": str, "message": str}.
    """
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
        import logging
        _logger = logging.getLogger('850lab.startup')
        images = convert_from_bytes(pdf_bytes, dpi=300, first_page=1, last_page=max_pages)
        _logger.info(f"OCR: converted {len(images)} pages (max_pages={max_pages})")
        full_text = ""
        page_texts = []
        for i, image in enumerate(images):
            page_text = pytesseract.image_to_string(image)
            if page_text.strip():
                page_texts.append({'page_number': i + 1, 'text': page_text, 'method': 'ocr'})
                full_text += f"\n--- Page {i + 1} (OCR) ---\n{page_text}\n"
        _logger.info(f"OCR complete: {len(page_texts)}/{len(images)} pages had text, {len(full_text)} chars total")
        return full_text, page_texts, len(images), None
    except Exception as e:
        import logging
        logging.getLogger('850lab.startup').info(f"OCR extraction error: {e}")
        return None, None, 0, {"code": "ocr_error", "message": str(e)}

def _expand_page_for_text(page):
    try:
        mediabox = page.page.get("/MediaBox")
        if mediabox:
            mb = [float(v) for v in mediabox]
            crop_x1 = float(page.width)
            media_x1 = mb[2] - mb[0]
            if media_x1 > crop_x1 + 5:
                return page.crop((0, 0, media_x1, float(page.height)), relative=False, strict=False)
    except Exception:
        pass
    return page

def extract_text_from_pdf(pdf_file, use_ocr=False):
    """
    Extract text from a PDF file-like object (read/seek).

    Returns (full_text, page_texts, num_pages, error_meta).
    On success, error_meta is None. On failure, full_text/page_texts may be None
    and error_meta is {"code": str, "message": str} for logging or UI.
    Codes: password_protected, invalid_pdf, read_error, ocr_error (from OCR path).
    """
    try:
        import pdfplumber
        pdf_bytes = pdf_file.read()
        pdf_file.seek(0)
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            full_text = ""
            page_texts = []
            text_found = False
            for i, page in enumerate(pdf.pages):
                expanded = _expand_page_for_text(page)
                page_text = expanded.extract_text()
                if page_text and page_text.strip():
                    text_found = True
                    page_texts.append({'page_number': i + 1, 'text': page_text, 'method': 'native'})
                    full_text += f"\n--- Page {i + 1} ---\n{page_text}\n"
            if not text_found:
                _pdf_log.info("No native PDF text; trying OCR")
                return extract_text_with_ocr(pdf_bytes)
            if use_ocr and text_found:
                ocr_text, ocr_pages, ocr_count, ocr_err = extract_text_with_ocr(pdf_bytes)
                if ocr_text and len(ocr_text.strip()) > len(full_text.strip()):
                    return ocr_text, ocr_pages, ocr_count, ocr_err
            return full_text, page_texts, len(pdf.pages), None
    except Exception as e:
        err_str = str(e).lower()
        if 'password' in err_str or 'decrypt' in err_str or 'encrypted' in err_str:
            _pdf_log.warning("PDF extraction failed: password-protected or encrypted")
            code = "password_protected"
            message = "This PDF is password-protected. Please download an unprotected version of your credit report and try again."
        elif 'not a pdf' in err_str or 'invalid' in err_str:
            _pdf_log.warning("PDF extraction failed: invalid PDF")
            code = "invalid_pdf"
            message = "This file does not appear to be a valid PDF. Please upload a PDF credit report downloaded directly from the bureau website."
        else:
            _pdf_log.warning("PDF extraction failed: %s", e)
            code = "read_error"
            message = "We had trouble reading this file. Please try downloading a fresh copy of your report and uploading again."
        _pdf_log.info("PDF extraction error for uploaded file: %s", e)
        return None, None, 0, {"code": code, "message": message, "detail": str(e)}

def is_definition_page(page_text):
    """FIX 3: Detect if a page contains rating code definitions (should be skipped)."""
    page_lower = page_text.lower()
    definition_markers = [
        'code definitions',
        'rating rating rating',
        'ok current, paying or paid as agreed',
        'account 30 days late',
        'account 60 days late', 
        'account 90 days late',
        'transferred to collection',
        'voluntarily surrendered',
        'foreclosure remarks',
        'bankruptcy withdrawn',
        'dispute account/closed',
    ]
    match_count = sum(1 for marker in definition_markers if marker in page_lower)
    return match_count >= 3

def detect_tu_variant(raw_text):
    """
    Detect which TransUnion report template was used.
    Returns: "TU_OSC" | "TU_ACR" | "TU_UNKNOWN"
    """
    text_lower = raw_text.lower()
    if 'transunion online service center' in text_lower:
        return 'TU_OSC'
    if any(marker in text_lower for marker in [
        'annualcreditreport', 'annual credit report', 'view credit report',
        'annualcreditreport.transunion.com',
    ]):
        return 'TU_ACR'
    return 'TU_UNKNOWN'


def parse_accounts_tu_acr(text, pages_text=None):
    """
    ACR-specific TransUnion account parser.
    Uses field-label pattern detection instead of relying solely on
    the OSC-style "CREDITOR DIGITS****" + "Account Information" anchor.

    Strategy:
    1. Try OSC-style header regex first (works for many ACR PDFs too).
    2. If that yields 0, fall back to splitting on "Account Name" section
       markers and extracting field-label pairs from each block.
    """
    osc_accounts, osc_rejects = parse_accounts_transunion_osc(text, pages_text)
    if len(osc_accounts) > 0:
        for a in osc_accounts:
            a['tu_parser'] = 'TU_ACR_via_OSC'
        return osc_accounts, osc_rejects

    accounts = []
    reject_counters = {
        'header_only': 0,
        'definition_page': 0,
        'disclaimer_boilerplate': 0,
        'address_fragment': 0,
        'missing_required_fields': 0,
    }

    acr_block_pattern = re.compile(
        r'(?:^|\n)(?:Account Name\n)?'
        r'([A-Z][A-Za-z0-9\s/&\.\,\-\']+?)'
        r'(?:\s+(\S*\d[\d\*]+\**\S*))?'
        r'\s*\n'
        r'Account Information\b',
        re.MULTILINE
    )

    acr_block_pattern_relaxed = re.compile(
        r'(?:^|\n)(?:Account Name\s*\n\s*)?'
        r'([A-Z][A-Za-z0-9\s/&\.\,\-\']{2,60}?)'
        r'(?:\s+(\S*\d[\d\*]+\**\S*))?'
        r'\s*\n'
        r'(?:[^\n]{0,80}\n){0,3}'
        r'Account Information\b',
        re.MULTILINE
    )

    field_patterns = {
        'balance': re.compile(r'(?:^|\n)\s*Balance\s+\$?([\d,]+\.?\d*)', re.IGNORECASE),
        'status': re.compile(r'(?:^|\n)\s*(?:Pay Status|Account Status)\s+[>]?(.+?)(?:<|\n|$)', re.IGNORECASE),
        'date_opened': re.compile(r'(?:^|\n)\s*Date Opened\s+(\d{1,2}/\d{1,2}/\d{2,4})', re.IGNORECASE),
        'account_type': re.compile(r'(?:^|\n)\s*Account Type\s+(.+?)(?:\n|$)', re.IGNORECASE),
        'loan_type': re.compile(r'(?:^|\n)\s*Loan Type\s+(.+?)(?:\n|$)', re.IGNORECASE),
        'monthly_payment': re.compile(r'(?:^|\n)\s*Monthly Payment\s+\$?([\d,]+\.?\d*)', re.IGNORECASE),
        'date_updated': re.compile(r'(?:^|\n)\s*Date Updated\s+(\d{1,2}/\d{1,2}/\d{2,4})', re.IGNORECASE),
        'high_balance': re.compile(r'(?:^|\n)\s*(?:High Balance|Credit Limit)\s+\$?([\d,]+)', re.IGNORECASE),
        'responsibility': re.compile(r'(?:^|\n)\s*Responsibility\s+(.+?)(?:\n|$)', re.IGNORECASE),
        'pay_status': re.compile(r'(?:^|\n)\s*Pay Status\s+(.+?)(?:\n|$)', re.IGNORECASE),
        'last_payment': re.compile(r'(?:^|\n)\s*Last Payment Made\s+(.+?)(?:\n|$)', re.IGNORECASE),
        'date_closed': re.compile(r'(?:^|\n)\s*Date Closed\s+(\d{1,2}/\d{1,2}/\d{2,4})', re.IGNORECASE),
        'terms': re.compile(r'(?:^|\n)\s*Terms\s+(.+?)(?:\n|$)', re.IGNORECASE),
        'remarks': re.compile(r'(?:^|\n)\s*Remarks\s+(.+?)(?:\n|$)', re.IGNORECASE),
    }

    block_starts = [(m.start(), m) for m in acr_block_pattern.finditer(text)]

    if not block_starts:
        block_starts = [(m.start(), m) for m in acr_block_pattern_relaxed.finditer(text)]

    end_markers_pattern = re.compile(
        r'(?:^|\n)(?:Regular Inquiries|Inquiries|Public Records|Consumer Statements)',
        re.IGNORECASE | re.MULTILINE
    )

    for idx, (start_pos, match) in enumerate(block_starts):
        creditor_name = match.group(1).strip()
        account_number = (match.group(2) or '').strip() or None

        if creditor_name.lower() in ['ratings', 'remarks', 'code', 'balance', 'status',
                                      'payment/remarks key', 'satisfactory accounts',
                                      'accounts with adverse information']:
            reject_counters['header_only'] += 1
            continue

        if len(creditor_name) < 2:
            reject_counters['header_only'] += 1
            continue

        if idx + 1 < len(block_starts):
            block_end = block_starts[idx + 1][0]
        else:
            end_match = end_markers_pattern.search(text, match.end())
            block_end = end_match.start() if end_match else len(text)

        block_text = text[match.start():min(block_end, match.start() + 5000)]

        context_check = block_text[:200].lower()
        if is_definition_page(context_check):
            reject_counters['definition_page'] += 1
            continue

        account = {
            'account_name': creditor_name,
            'rule': 'TU_ACR_FIELD_LABEL',
            'tu_parser': 'TU_ACR_native',
        }
        if account_number:
            account['account_number'] = account_number

        for field_name, pattern in field_patterns.items():
            field_match = pattern.search(block_text)
            if field_match:
                val = field_match.group(1).strip()
                if field_name == 'balance':
                    account['balance'] = val.replace(',', '')
                elif field_name == 'status':
                    account['status'] = val.rstrip('>')
                    account['pay_status_raw'] = field_match.group(0)[:100]
                elif field_name == 'date_opened':
                    account['date_opened'] = val
                elif field_name == 'account_type':
                    account['account_type'] = val
                else:
                    account[field_name] = val

        has_any_field = any(account.get(f) for f in ['balance', 'status', 'date_opened', 'account_type'])
        if not has_any_field:
            reject_counters['missing_required_fields'] += 1
            continue

        account['raw_section'] = block_text[:500]
        snippet_parts = [creditor_name]
        if account_number:
            snippet_parts.append(account_number)
        account['receipt_snippet'] = ' '.join(snippet_parts)[:120]
        account['confidence'] = 'HIGH' if account.get('balance') else 'MEDIUM'

        accounts.append(account)

    accounts.sort(key=lambda a: (a.get('account_name', ''), a.get('date_opened', ''), a.get('account_number', '')))

    return accounts, reject_counters


def parse_accounts_transunion_osc(text, pages_text=None):
    """
    ========================================================================
    PHASE 1 STABLE — TRANSUNION OSC (DO NOT MODIFY LOGIC)
    ========================================================================
    Original parse_accounts_transunion, renamed for variant routing.
    Frozen: 2026-02-02 | Baseline: artifacts/tu_phase1_baseline.json
    
    FIX 2: TransUnion account parsing - standalone creditor + masked account number.
    """
    accounts = []
    reject_counters = {
        'header_only': 0,
        'definition_page': 0,
        'disclaimer_boilerplate': 0,
        'address_fragment': 0,
        'missing_required_fields': 0,
    }
    
    tu_account_header_pattern = r'^([A-Z][A-Z0-9\s/&\.\-,\']+?)\s+([A-Z0-9]{3,}\*{3,}|\*{4,}[A-Z0-9]+)$'
    tu_account_info_marker = r'^Account Information$'
    
    lines = text.split('\n')
    i = 0
    current_page = 1
    
    while i < len(lines):
        line = lines[i].strip()
        
        if 'Page ' in line and ' of ' in line:
            page_match = re.search(r'Page\s+(\d+)\s+of', line)
            if page_match:
                current_page = int(page_match.group(1))
        
        if current_page <= 6:
            context = '\n'.join(lines[max(0,i-10):min(len(lines),i+10)])
            if is_definition_page(context):
                reject_counters['definition_page'] += 1
                i += 1
                continue
        
        header_match = re.match(tu_account_header_pattern, line)
        creditor_name = None
        account_number = None
        acct_info_offset = 1

        if header_match:
            creditor_name = header_match.group(1).strip()
            account_number = header_match.group(2).strip()
        elif re.match(r'^[A-Z][A-Z0-9\s/&\.\-,\']{2,}$', line) and not re.match(r'^(Account Information|Page \d|Ratings|Remarks|Code|Balance|Status|Payment History|Date)$', line, re.IGNORECASE):
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                acct_num_match = re.match(r'^([A-Z0-9]{3,}\*{3,}|\*{4,}[A-Z0-9]+)$', next_line)
                if acct_num_match:
                    creditor_name = line.strip()
                    account_number = acct_num_match.group(1)
                    acct_info_offset = 2

        if creditor_name:
            if creditor_name.lower() in ['ratings', 'remarks', 'code', 'balance', 'status',
                                          'payment/remarks key', 'satisfactory accounts',
                                          'accounts with adverse information']:
                reject_counters['header_only'] += 1
                i += 1
                continue
            
            acct_info_found_offset = None
            for scan_offset in range(acct_info_offset, min(acct_info_offset + 8, len(lines) - i)):
                candidate = lines[i + scan_offset].strip()
                if re.match(tu_account_info_marker, candidate):
                    acct_info_found_offset = scan_offset
                    break
                if candidate and not re.match(
                    r'^(https?://|Page \d+|--- Page \d+ ---|'
                    r'\d{1,2}/\d{1,2}/\d{2,4}|'
                    r'\d{1,2}/\d{1,2}/\d{2,4},?\s*\d{1,2}:\d{2}|'
                    r':?\s*$)',
                    candidate
                ):
                    break
            
            if acct_info_found_offset is not None:
                account_block_start = i
                account_block_end = i + acct_info_found_offset + 1
                
                for j in range(i + acct_info_found_offset + 1, min(i + 50, len(lines))):
                    next_line = lines[j].strip()
                    if re.match(tu_account_header_pattern, next_line):
                        break
                    if j + 1 < len(lines) and re.match(r'^([A-Z0-9]{3,}\*{3,}|\*{4,}[A-Z0-9]+)$', lines[j + 1].strip()):
                        if re.match(r'^[A-Z][A-Z0-9\s/&\.\-,\']{2,}$', next_line):
                            break
                    if next_line.lower().startswith('inquiries') or next_line.lower().startswith('regular inquiries'):
                        break
                    account_block_end = j + 1
                
                block_text = '\n'.join(lines[account_block_start:account_block_end])
                
                account = {
                    'account_name': creditor_name,
                    'account_number': account_number,
                    'page': current_page,
                    'rule': 'TU_ACCT_HEADER',
                }
                
                balance_match = re.search(r'(?:Balance|Current Balance)[:\s]+\$?([\d,]+\.?\d*)', block_text, re.IGNORECASE)
                if balance_match:
                    account['balance'] = balance_match.group(1).replace(',', '')
                
                status_match = re.search(r'Pay Status[:\s>]+(.+?)(?:<|\n|$)', block_text, re.IGNORECASE)
                if status_match:
                    account['status'] = status_match.group(1).strip()
                    account['pay_status_raw'] = status_match.group(0)[:100]
                
                opened_match = re.search(r'Date Opened[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})', block_text, re.IGNORECASE)
                if opened_match:
                    account['date_opened'] = opened_match.group(1).strip()
                
                type_match = re.search(r'(?:Account Type|Loan Type)[:\s]+(.+?)(?:\n|$)', block_text, re.IGNORECASE)
                if type_match:
                    account['account_type'] = type_match.group(1).strip()
                
                account['raw_section'] = block_text[:500]
                account['receipt_snippet'] = f"{creditor_name} {account_number}"[:120]
                account['confidence'] = 'HIGH' if account.get('balance') else 'MEDIUM'
                
                accounts.append(account)
                i = account_block_end
                continue
        
        i += 1
    
    return accounts, reject_counters

def parse_accounts_equifax(text, pages_text=None):
    accounts = []
    reject_counters = {
        'header_only': 0,
        'definition_page': 0,
        'disclaimer_boilerplate': 0,
        'address_fragment': 0,
        'missing_required_fields': 0,
    }

    credit_accounts_match = re.search(r'Credit Accounts\b', text)
    if not credit_accounts_match:
        return accounts, reject_counters

    inquiries_match = re.search(r'\nInquiries\n', text[credit_accounts_match.start():])
    if inquiries_match:
        section_text = text[credit_accounts_match.start():credit_accounts_match.start() + inquiries_match.start()]
    else:
        section_text = text[credit_accounts_match.start():]

    acct_num_positions = [m.start() for m in re.finditer(r'Account Number:', section_text)]

    if not acct_num_positions:
        return accounts, reject_counters

    blocks = []
    for idx, pos in enumerate(acct_num_positions):
        preceding = section_text[:pos]
        lines_before = preceding.split('\n')
        creditor_name = None
        creditor_line_idx = None
        for k in range(len(lines_before) - 1, max(len(lines_before) - 10, -1), -1):
            candidate = lines_before[k].strip()
            if not candidate:
                continue
            if re.match(r'^(Prepared for|Date:|Confirmation|Credit Accounts|This includes)', candidate):
                continue
            if '|' in candidate and ('Date Reported' in candidate or 'Balance' in candidate):
                continue
            if re.match(r'^\d{6,}', candidate):
                continue
            if re.match(r'^[A-Z][A-Z0-9\s/&\.\-,\']+(?:\s*-\s*Closed)?$', candidate) and len(candidate) >= 3:
                prev_non_empty = ''
                for pk in range(k - 1, max(k - 3, -1), -1):
                    prev_cand = lines_before[pk].strip()
                    if prev_cand:
                        prev_non_empty = prev_cand
                        break
                if prev_non_empty.startswith('Prepared for'):
                    continue
                creditor_name = candidate
                creditor_line_idx = k
                break

        if not creditor_name:
            reject_counters['missing_required_fields'] += 1
            continue

        block_start_offset = len('\n'.join(lines_before[:creditor_line_idx])) + 1 if creditor_line_idx > 0 else 0
        if idx + 1 < len(acct_num_positions):
            next_pos = acct_num_positions[idx + 1]
            next_preceding = section_text[:next_pos]
            next_lines = next_preceding.split('\n')
            for nk in range(len(next_lines) - 1, max(len(next_lines) - 10, -1), -1):
                nc = next_lines[nk].strip()
                if not nc:
                    continue
                if re.match(r'^[A-Z][A-Z0-9\s/&\.\-,\']+(?:\s*-\s*Closed)?$', nc) and len(nc) >= 3:
                    block_end = len('\n'.join(next_lines[:nk])) + 1 if nk > 0 else next_pos
                    break
            else:
                block_end = next_pos
        else:
            block_end = len(section_text)

        block_text = section_text[block_start_offset:block_end]
        blocks.append((creditor_name, block_text))

    for creditor_raw, block_text in blocks:
        is_closed = False
        creditor_name = creditor_raw.strip()
        closed_match = re.match(r'^(.+?)\s*-\s*Closed$', creditor_name)
        if closed_match:
            creditor_name = closed_match.group(1).strip()
            is_closed = True

        if creditor_name.upper() in ['CREDIT ACCOUNTS', 'PAYMENT HISTORY', 'NARRATIVE CODE']:
            reject_counters['header_only'] += 1
            continue

        account = {
            'account_name': creditor_name,
            'rule': 'EQ_ACCT',
        }

        if is_closed:
            account['is_closed'] = True

        acct_num_match = re.search(r'Account Number:\s*\*?(\w+)', block_text)
        if acct_num_match:
            account['account_number'] = acct_num_match.group(1)

        balance_match = re.search(r'Balance:\s*\$?([\d,]+)', block_text)
        if balance_match:
            account['balance'] = balance_match.group(1).replace(',', '')

        status_match = re.search(r'Status:[ \t]*(.+?)(?:\n|$)', block_text)
        if status_match:
            status_val = status_match.group(1).strip()
            if status_val and not status_val.startswith('Date Opened'):
                account['status'] = status_val

        date_opened_match = re.search(r'Date Opened:\s*(\d{1,2}/\d{1,2}/\d{4})', block_text)
        if date_opened_match:
            account['date_opened'] = date_opened_match.group(1)

        high_credit_match = re.search(r'High Credit:\s*\$?([\d,]+)', block_text)
        if high_credit_match:
            account['high_credit'] = high_credit_match.group(1).replace(',', '')

        credit_limit_match = re.search(r'Credit Limit:\s*\$?([\d,]+)', block_text)
        if credit_limit_match:
            account['credit_limit'] = credit_limit_match.group(1).replace(',', '')

        loan_type_match = re.search(r'Loan/Account Type:\s*(.+?)\s*\|', block_text)
        if loan_type_match:
            account['loan_type'] = loan_type_match.group(1).strip()

        owner_match = re.search(r'Owner:\s*(.+?)\s+Credit', block_text)
        if owner_match:
            account['owner'] = owner_match.group(1).strip()

        date_reported_match = re.search(r'Date Reported:\s*(\d{1,2}/\d{1,2}/\d{4})', block_text)
        if date_reported_match:
            account['date_reported'] = date_reported_match.group(1)

        payment_match = re.search(r'Scheduled Payment Amount:\s*\$?([\d,]+)', block_text)
        if payment_match:
            account['payment_amount'] = payment_match.group(1).replace(',', '')

        past_due_match = re.search(r'Amount Past Due:\s*\$?([\d,]+)', block_text)
        if past_due_match:
            account['amount_past_due'] = past_due_match.group(1).replace(',', '')

        activity_match = re.search(r'Activity Designator:\s*(.+?)\s*(?:Narrative|$)', block_text)
        if activity_match:
            val = activity_match.group(1).strip()
            if val:
                account['activity_designator'] = val

        narrative_match = re.search(r'Narrative Code\(s\):\s*(.+?)(?:\n|$)', block_text)
        if narrative_match:
            account['narrative_codes'] = narrative_match.group(1).strip()

        delinquency_flags = []
        payment_hist_match = re.search(r'Payment History\s*\n', block_text)
        if payment_hist_match:
            hist_section = block_text[payment_hist_match.end():]
            hist_lines = hist_section.split('\n')
            for hline in hist_lines:
                hline_stripped = hline.strip()
                if hline_stripped.startswith('Paid on Time'):
                    break
                if re.match(r'^\d{4}\b', hline_stripped):
                    markers = re.findall(r'\b(30|60|90|120|150|180|V|F|C|CO|B|R)\b', hline_stripped)
                    delinquency_flags.extend(markers)

        if delinquency_flags:
            account['delinquency_flags'] = delinquency_flags

        if pages_text:
            for pg_idx, pg_text in enumerate(pages_text):
                if creditor_name in pg_text:
                    account['page'] = pg_idx + 1
                    break

        if not account.get('status'):
            loan_t = account.get('loan_type', '').lower()
            if 'debt buyer' in loan_t or 'collection' in loan_t:
                account['status'] = 'Collection'
            elif account.get('delinquency_flags'):
                flag_set = set(account['delinquency_flags'])
                if 'CO' in flag_set:
                    account['status'] = 'Charge Off'
                elif 'C' in flag_set:
                    account['status'] = 'Collection'

        has_any_field = any(account.get(f) for f in ['balance', 'status', 'date_opened'])
        if not has_any_field:
            reject_counters['missing_required_fields'] += 1
            continue

        account['raw_section'] = block_text[:500]
        snippet_parts = [creditor_name]
        if account.get('account_number'):
            snippet_parts.append(account['account_number'])
        account['receipt_snippet'] = ' '.join(snippet_parts)[:120]
        account['confidence'] = 'HIGH' if account.get('balance') else 'MEDIUM'

        accounts.append(account)

    return accounts, reject_counters


def parse_accounts_experian(text, pages_text=None):
    accounts = []
    reject_counters = {
        'header_only': 0,
        'definition_page': 0,
        'disclaimer_boilerplate': 0,
        'address_fragment': 0,
        'missing_required_fields': 0,
    }

    header_pattern = r'(\S[^\n]*)\n(?:(POTENTIALLY NEGATIVE)\n)?\s*\ue9ef?\s*\nAccount Info\n'
    header_matches = list(re.finditer(header_pattern, text))
    if not header_matches:
        header_pattern_alt = r'(\S[^\n]*)\n(?:(POTENTIALLY NEGATIVE)\n)?\s*\nAccount Info\n'
        header_matches = list(re.finditer(header_pattern_alt, text))

    if not header_matches:
        return accounts, reject_counters

    for idx, m in enumerate(header_matches):
        creditor_name = m.group(1).strip()
        is_potentially_negative = bool(m.group(2))
        block_start = m.end()

        if idx + 1 < len(header_matches):
            block_end = header_matches[idx + 1].start()
        else:
            end_markers = ['Hard Inquiries', 'Public Records', 'Soft Inquiries']
            block_end = len(text)
            for marker in end_markers:
                marker_pos = text.find(marker, block_start)
                if marker_pos != -1 and marker_pos < block_end:
                    block_end = marker_pos

        block_text = text[block_start:block_end]

        skip_names = ['ACCOUNTS', 'ACCOUNT INFORMATION', 'CREDIT ACCOUNTS']
        if creditor_name.upper() in skip_names:
            reject_counters['header_only'] += 1
            continue

        account = {
            'account_name': creditor_name,
            'rule': 'EX_ACCT',
        }

        if is_potentially_negative:
            account['potentially_negative'] = True

        full_name_match = re.search(r'Account Name\s+(.+?)(?:\s+Balance\b)', block_text)
        if full_name_match:
            parsed_name = full_name_match.group(1).strip()
            next_lines = block_text[full_name_match.end():].split('\n')
            for nl in next_lines[:3]:
                nl_stripped = nl.strip()
                if not nl_stripped:
                    break
                if re.match(r'^[A-Z][A-Z/\s&\.\-]+$', nl_stripped) and not re.match(r'^(Balance|Account|Status|Date|Responsibility|On Record)', nl_stripped):
                    parsed_name += ' ' + nl_stripped
                    break
                else:
                    break
            if len(parsed_name) > len(creditor_name):
                account['account_name'] = parsed_name

        acct_num_match = re.search(r'Account Number\s+(\S+)', block_text)
        if acct_num_match:
            raw_num = acct_num_match.group(1)
            if raw_num in ('Recent', 'Balance', '-'):
                alt_num_match = re.search(r'\n([A-Z0-9]{6,}X+)\nAccount Number', block_text)
                if alt_num_match:
                    full_num = alt_num_match.group(1)
                    remainder_match = re.search(r'Account Number\s+\S+\s+\S+\s+\S+\n(X+)', block_text)
                    if remainder_match:
                        full_num += remainder_match.group(1)
                    account['account_number'] = full_num
            else:
                account['account_number'] = raw_num

        acct_type_match = re.search(r'Account Type\s+(.+?)(?:\s+Recent Payment|\s+Monthly Payment|\n)', block_text)
        if acct_type_match:
            account['loan_type'] = acct_type_match.group(1).strip()

        responsibility_match = re.search(r'Responsibility\s+(.+?)(?:\s+Monthly Payment|\s+Original Balance|\n)', block_text)
        if responsibility_match:
            account['responsibility'] = responsibility_match.group(1).strip()

        date_opened_match = re.search(r'Date Opened\s+(\d{2}/\d{2}/\d{4})', block_text)
        if date_opened_match:
            account['date_opened'] = date_opened_match.group(1)

        status_match = re.search(r'Status\s+(.+?)(?:\s+Highest Balance|\s+Terms|\n)', block_text)
        if status_match:
            raw_status = status_match.group(1).strip()
            if not raw_status.startswith('Updated'):
                account['status'] = raw_status

        balance_match = re.search(r'Account Name\s+.+?\s+Balance\s+(\$[\d,]+|-)', block_text)
        if balance_match:
            bal = balance_match.group(1)
            if bal != '-':
                account['balance'] = bal.replace('$', '').replace(',', '')
            else:
                account['balance'] = '0'

        credit_limit_match = re.search(r'Credit Limit\s+\$?([\d,]+)', block_text)
        if credit_limit_match:
            account['credit_limit'] = credit_limit_match.group(1).replace(',', '')

        highest_bal_match = re.search(r'Highest Balance\s+\$?([\d,]+)', block_text)
        if highest_bal_match:
            account['highest_balance'] = highest_bal_match.group(1).replace(',', '')

        original_bal_match = re.search(r'Original Balance\s+\$?([\d,]+)', block_text)
        if original_bal_match:
            account['original_balance'] = original_bal_match.group(1).replace(',', '')

        monthly_pmt_match = re.search(r'Monthly Payment\s+\$?([\d,]+)', block_text)
        if monthly_pmt_match:
            account['monthly_payment'] = monthly_pmt_match.group(1).replace(',', '')

        on_record_match = re.search(r'On Record Until\s+(.+?)(?:\n|$)', block_text)
        if on_record_match:
            account['on_record_until'] = on_record_match.group(1).strip()

        delinquency_flags = []
        payment_guide_match = re.search(r'Payment history guide\n(.*?)(?:\n\n|\nBalance Histories|\nContact Info|\nComment|\Z)', block_text, re.DOTALL)
        if payment_guide_match:
            guide_text = payment_guide_match.group(1)
            for day_match in re.finditer(r'(\d+)\s+days?\s+past\s+due', guide_text, re.IGNORECASE):
                flag_val = int(day_match.group(1))
                if flag_val not in delinquency_flags:
                    delinquency_flags.append(flag_val)

        if not delinquency_flags:
            payment_hist_match = re.search(r'Payment History\n', block_text)
            if payment_hist_match:
                hist_section = block_text[payment_hist_match.end():]
                hist_lines = hist_section.split('\n')
                for hline in hist_lines:
                    hline_stripped = hline.strip()
                    if hline_stripped.startswith('Balance Histor') or hline_stripped.startswith('Contact Info') or hline_stripped.startswith('Comment'):
                        break
                    if re.match(r'^\d{4}\b', hline_stripped):
                        markers = re.findall(r'\b(30|60|90|120|150|180)\b', hline_stripped)
                        for mk in markers:
                            val = int(mk)
                            if val not in delinquency_flags:
                                delinquency_flags.append(val)
                    if 'collection' in hline_stripped.lower():
                        if 'C' not in delinquency_flags:
                            delinquency_flags.append('C')

        if delinquency_flags:
            account['delinquency_flags'] = sorted(delinquency_flags, key=lambda x: (isinstance(x, str), x))

        comment_match = re.search(r'Comment\nCurrent:\n(.*?)(?:\nPrevious:|\Z)', block_text, re.DOTALL)
        if comment_match:
            comment_text = comment_match.group(1).strip()
            comment_text = re.sub(r'https?://\S+', '', comment_text).strip()
            comment_text = re.sub(r'Page \d+ of \d+', '', comment_text).strip()
            comment_text = re.sub(r'--- Page \d+ ---', '', comment_text).strip()
            if comment_text:
                account['comment'] = comment_text[:500]

        if pages_text:
            for pg_idx, pg_text in enumerate(pages_text):
                if creditor_name in pg_text:
                    account['page'] = pg_idx + 1
                    break

        has_any_field = any(account.get(f) for f in ['balance', 'status', 'date_opened', 'account_number'])
        if not has_any_field:
            reject_counters['missing_required_fields'] += 1
            continue

        account['raw_section'] = block_text[:500]
        snippet_parts = [creditor_name]
        if account.get('account_number'):
            snippet_parts.append(account['account_number'])
        account['receipt_snippet'] = ' '.join(snippet_parts)[:120]
        account['confidence'] = 'HIGH' if account.get('balance') and account['balance'] != '0' else 'MEDIUM'

        accounts.append(account)

    return accounts, reject_counters


def parse_accounts(text, bureau, pages_text=None):
    if bureau == 'equifax':
        return parse_accounts_equifax(text, pages_text)
    if bureau == 'experian':
        return parse_accounts_experian(text, pages_text)
    if bureau == 'transunion':
        variant = detect_tu_variant(text)
        print(f"[TU_VARIANT] Detected: {variant}")
        if variant == 'TU_ACR':
            return parse_accounts_tu_acr(text, pages_text)
        else:
            return parse_accounts_transunion_osc(text, pages_text)
    
    accounts = []
    reject_counters = {
        'header_only': 0,
        'disclaimer_boilerplate': 0,
        'address_fragment': 0,
        'missing_required_fields': 0,
    }
    
    disclaimer_phrases = ['information', 'masked', 'this means', 'report contains', 
                          'credit file', 'consumer statement', 'dispute', 'verify']
    address_patterns = [r'\bSUITE\b', r'\bAPT\b', r'\bUNIT\b', r'\bPO BOX\b', r'\bP\.O\.\s*BOX\b']
    
    patterns = BUREAU_PATTERNS.get(bureau, BUREAU_PATTERNS['equifax'])
    account_sections = re.split(r'\n(?=(?:Account|Creditor|Subscriber))', text, flags=re.IGNORECASE)
    for section in account_sections:
        if len(section) < 50:
            reject_counters['header_only'] += 1
            continue
        
        section_lower = section.lower()
        if section_lower.strip().startswith('information') or any(phrase in section_lower for phrase in disclaimer_phrases[:4]):
            reject_counters['disclaimer_boilerplate'] += 1
            continue
        
        if any(re.search(pat, section, re.IGNORECASE) for pat in address_patterns) and len(section) < 150:
            reject_counters['address_fragment'] += 1
            continue
        
        account = {'rule': 'GENERIC_ACCT'}
        name_match = re.search(patterns['account_pattern'], section, re.IGNORECASE)
        if name_match:
            account['account_name'] = name_match.group(1).strip()[:100]
        balance_match = re.search(patterns['balance_pattern'], section, re.IGNORECASE)
        if balance_match:
            account['balance'] = balance_match.group(1).replace(',', '')
        status_match = re.search(patterns['status_pattern'], section, re.IGNORECASE)
        if status_match:
            account['status'] = status_match.group(1).strip()
        opened_match = re.search(patterns['opened_pattern'], section, re.IGNORECASE)
        if opened_match:
            account['date_opened'] = opened_match.group(1).strip()
        high_credit_match = re.search(patterns['high_credit_pattern'], section, re.IGNORECASE)
        if high_credit_match:
            account['high_credit'] = high_credit_match.group(1).replace(',', '')
        
        has_creditor = bool(account.get('account_name'))
        has_data_field = any([
            account.get('balance'),
            account.get('status'),
            account.get('date_opened'),
            account.get('high_credit'),
            re.search(r'\b\d{4,}\b', section),
        ])
        
        if has_creditor and has_data_field:
            account['raw_section'] = section[:500]
            account['receipt_snippet'] = section[:120].replace('\n', ' ')
            account['confidence'] = 'HIGH' if has_creditor and account.get('balance') else 'MEDIUM'
            accounts.append(account)
        else:
            reject_counters['missing_required_fields'] += 1
    
    return accounts, reject_counters

def parse_inquiries_transunion(text):
    """
    ========================================================================
    PHASE 1 STABLE — TRANSUNION (DO NOT MODIFY LOGIC)
    ========================================================================
    Frozen: 2026-02-02 | Baseline: artifacts/tu_phase1_baseline.json
    
    FIX 1: TransUnion inquiry parsing - look ABOVE date for creditor name.
    """
    inquiries = []
    reject_counters = {
        'header_only': 0,
        'city_state_line': 0,
        'address_fragment': 0,
        'missing_creditor_or_date': 0,
    }
    
    city_state_pattern = r'^[A-Z][a-z]+,?\s+[A-Z]{2}(\s+\d{5})?$'
    address_patterns = [r'\bSUITE\b', r'\bAPT\b', r'\bUNIT\b', r'\bPO BOX\b', r'\bLOCATION\b', r'\bPHONE\b', r'\d{3,}\s']
    forbidden_creditor_words = ['LOCATION', 'PHONE', 'ADDRESS', 'SUITE', 'FLOOR', 'STREET', 'AVENUE', 'ROAD', 'DRIVE']
    
    lines = text.split('\n')
    text_lower = text.lower()
    
    inquiry_section_start = -1
    soft_section_start = -1
    current_section = 'unknown'
    current_page = 1
    
    hard_markers = ['regular inquiries', 'inquiries that may affect']
    soft_markers = ['account review inquiries', 'requests viewed only by you', 'promotional inquiries']
    
    for marker in hard_markers:
        idx = text_lower.find(marker)
        if idx != -1:
            inquiry_section_start = idx
            break
    
    if inquiry_section_start == -1:
        return [], reject_counters
    
    for marker in soft_markers:
        idx = text_lower.find(marker)
        if idx != -1 and idx > inquiry_section_start:
            soft_section_start = idx
            break
    
    inquiry_text = text[inquiry_section_start:] if soft_section_start == -1 else text[inquiry_section_start:soft_section_start]
    inq_lines = inquiry_text.split('\n')
    
    i = 0
    while i < len(inq_lines):
        line = inq_lines[i].strip()
        
        if 'Page ' in line and ' of ' in line:
            page_match = re.search(r'Page\s+(\d+)\s+of', line)
            if page_match:
                current_page = int(page_match.group(1))
        
        if 'regular inquiries' in line.lower():
            current_section = 'regular_inquiries'
        elif 'account review' in line.lower():
            current_section = 'account_review_inquiries'
        
        date_on_line = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', line)
        if date_on_line:
            inquiry_date = date_on_line.group(1)
            
            creditor_name = None
            for j in range(i - 1, max(i - 6, -1), -1):
                candidate = inq_lines[j].strip()
                
                if not candidate:
                    continue
                if 'Page ' in candidate and ' of ' in candidate:
                    continue
                if candidate.lower().startswith('name'):
                    continue
                if candidate.lower().startswith('location'):
                    continue
                if 'inquiries' in candidate.lower():
                    break
                
                if re.match(city_state_pattern, candidate):
                    continue
                
                if any(word in candidate.upper() for word in forbidden_creditor_words):
                    continue
                
                if re.match(r'^[A-Z][A-Za-z0-9\s/&\.\-]+', candidate) and len(candidate) >= 3:
                    if not re.match(r'^\d', candidate):
                        creditor_name = candidate
                        break
            
            if not creditor_name:
                reject_counters['missing_creditor_or_date'] += 1
                i += 1
                continue
            
            if len(creditor_name) <= 2:
                reject_counters['header_only'] += 1
                i += 1
                continue
            
            inquiry_type = 'Hard Inquiry' if current_section == 'regular_inquiries' else 'Soft Inquiry'
            
            receipt_lines = []
            for k in range(max(0, i-3), min(len(inq_lines), i+2)):
                if inq_lines[k].strip():
                    receipt_lines.append(inq_lines[k].strip())
            receipt = ' | '.join(receipt_lines)[:200]
            
            inquiry = {
                'creditor': creditor_name,
                'date': inquiry_date,
                'type': inquiry_type,
                'section_label': current_section,
                'page': current_page,
                'rule': 'TU_INQ_UPLINE',
                'receipt_snippet': receipt,
                'confidence': 'HIGH',
                'raw_text': f"{creditor_name} {inquiry_date}",
            }
            
            if not any(inq['creditor'] == creditor_name and inq['date'] == inquiry_date for inq in inquiries):
                inquiries.append(inquiry)
        
        i += 1
    
    return inquiries, reject_counters

def parse_inquiries_equifax(text):
    inquiries = []
    reject_counters = {
        'header_only': 0,
        'city_state_line': 0,
        'address_fragment': 0,
        'missing_creditor_or_date': 0,
    }

    text_lower = text.lower()
    inq_start = text_lower.find('inquiries')
    if inq_start == -1:
        return inquiries, reject_counters

    inq_text = text[inq_start:]

    lines = inq_text.split('\n')
    i = 0
    current_page = 1

    date_pattern = re.compile(r'(\d{1,2}/\d{1,2}/\d{4})')
    inquiry_line_pattern = re.compile(
        r'^(.+?)\s+(Hard|Soft)\s+(\d{1,2}/\d{1,2}/\d{4}(?:,\s*\d{1,2}/\d{1,2}/\d{4})*[,]?)\s*$'
    )

    while i < len(lines):
        line = lines[i].strip()

        if '--- Page' in line:
            page_match = re.search(r'Page\s+(\d+)', line)
            if page_match:
                current_page = int(page_match.group(1))
            i += 1
            continue

        if line.startswith('Company Information') or line.startswith('Prepared for') or line.startswith('Date:') or line.startswith('Confirmation'):
            i += 1
            continue

        if line.startswith('A request for') or line.startswith('rating/score') or line.startswith('l ') or line.startswith('you\'ve') or line.startswith('file.') or line.startswith('promotional'):
            i += 1
            continue

        if re.match(r'^\d{6,}', line):
            i += 1
            continue

        if not line:
            i += 1
            continue

        if line.startswith('Para ') or line.startswith('A Summary'):
            break

        m = inquiry_line_pattern.match(line)
        if m:
            creditor_name = m.group(1).strip()
            inq_type_raw = m.group(2).strip()
            dates_str = m.group(3).strip()

            if creditor_name in ['Company Information']:
                i += 1
                continue

            all_dates_str = dates_str.rstrip(',')
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if re.match(r'^[\d/,\s]+$', next_line) and date_pattern.search(next_line):
                    all_dates_str += ', ' + next_line.rstrip(',')
                    j += 1
                elif date_pattern.search(next_line) and not re.match(r'^[A-Z]', next_line):
                    all_dates_str += ', ' + next_line.rstrip(',')
                    j += 1
                elif next_line.startswith('Phone:') or next_line.startswith('PO ') or next_line.startswith('PO BOX') or re.match(r'^\d+\s+[A-Z]', next_line):
                    j += 1
                elif '|' in next_line or 'Date Reported' in next_line:
                    j += 1
                else:
                    break

            dates_found = date_pattern.findall(all_dates_str)
            inquiry_type = 'Hard Inquiry' if inq_type_raw == 'Hard' else 'Soft Inquiry'

            for dt in dates_found:
                inquiry = {
                    'creditor': creditor_name,
                    'date': dt,
                    'type': inquiry_type,
                    'section_label': inq_type_raw.lower(),
                    'page': current_page,
                    'rule': 'EQ_INQ',
                    'receipt_snippet': f"{creditor_name} {inq_type_raw} {dt}"[:120],
                    'confidence': 'HIGH',
                    'raw_text': f"{creditor_name} {dt}",
                }
                inquiries.append(inquiry)

            i = j
            continue
        else:
            cont_dates = date_pattern.findall(line)
            if cont_dates and not re.match(r'^[A-Z][A-Z]', line):
                i += 1
                continue

        i += 1

    return inquiries, reject_counters


def _find_experian_section_header(text, header_keyword):
    for m in re.finditer(re.escape(header_keyword), text):
        before = text[max(0, m.start()-80):m.start()]
        if re.search(r'\d+\s+$', before):
            continue
        after_nl = text.find('\n', m.end())
        if after_nl == -1:
            after_nl = len(text)
        rest_of_line = text[m.end():after_nl].strip()
        if rest_of_line and not rest_of_line.startswith('\n'):
            if re.match(r'^[A-Z]', rest_of_line) and 'inquir' not in rest_of_line.lower():
                continue
        return m.start()
    return -1


def parse_inquiries_experian(text):
    inquiries = []
    reject_counters = {
        'header_only': 0,
        'city_state_line': 0,
        'address_fragment': 0,
        'missing_creditor_or_date': 0,
    }

    hard_start = _find_experian_section_header(text, 'Hard Inquiries')
    soft_start = _find_experian_section_header(text, 'Soft Inquiries')

    if hard_start == -1:
        return inquiries, reject_counters

    hard_end = soft_start if soft_start != -1 else len(text)
    hard_section = text[hard_start:hard_end]

    inquired_matches = list(re.finditer(r'Inquired on\s+(\d{2}/\d{2}/\d{4})', hard_section))

    for idx, m in enumerate(inquired_matches):
        date = m.group(1)
        before_text = hard_section[:m.start()]
        lines_before = before_text.strip().split('\n')

        creditor = None
        for k in range(len(lines_before) - 1, max(len(lines_before) - 10, -1), -1):
            candidate = lines_before[k].strip()
            if not candidate:
                continue
            if 'Page ' in candidate and ' of ' in candidate:
                continue
            if candidate.startswith('---'):
                continue
            if candidate.startswith('http'):
                continue
            if re.match(r'^\d{3,5}\s', candidate):
                continue
            if candidate.lower().startswith('hard inquir'):
                break
            if 'Inquired on' in candidate:
                continue

            if re.match(r'^[A-Z][A-Za-z0-9\s/&\.\-,]+', candidate) and len(candidate) >= 3:
                parts = re.split(r'\s{2,}', candidate)
                creditor = parts[0].strip()
                break

        if creditor:
            purpose_match = re.search(r'(Real Estate|Auto|Credit Card|Personal Loan|Student Loan|Mortgage|Insurance|Collection)[.\s]', hard_section[m.end():m.end()+200], re.IGNORECASE)
            inquiry = {
                'creditor': creditor,
                'date': date,
                'type': 'Hard Inquiry',
            }
            if purpose_match:
                inquiry['purpose'] = purpose_match.group(1)
            inquiries.append(inquiry)
        else:
            reject_counters['missing_creditor_or_date'] += 1

    if soft_start != -1:
        soft_end_markers = ['Consumer Statements', 'End of Report', 'Your rights under']
        soft_end = len(text)
        for marker in soft_end_markers:
            idx = text.find(marker, soft_start + 20)
            if idx != -1 and idx < soft_end:
                soft_end = idx
        soft_section = text[soft_start:soft_end]
        soft_inquired = list(re.finditer(r'Inquired on\s*\n?\s*(\d{2}/\d{2}/\d{2,4})', soft_section))

        for m in soft_inquired:
            date = m.group(1)
            before_text = soft_section[:m.start()]
            lines_before = before_text.strip().split('\n')
            creditor = None
            for k in range(len(lines_before) - 1, max(len(lines_before) - 8, -1), -1):
                candidate = lines_before[k].strip()
                if not candidate:
                    continue
                if 'Page ' in candidate or candidate.startswith('---') or candidate.startswith('http'):
                    continue
                if 'Inquired on' in candidate:
                    continue
                if candidate.lower().startswith('soft inquir'):
                    break
                if re.match(r'^[A-Z][A-Za-z0-9\s/&\.\-,]+', candidate) and len(candidate) >= 3:
                    creditor = candidate.split('  ')[0].strip()
                    break
            if creditor:
                inquiries.append({
                    'creditor': creditor,
                    'date': date,
                    'type': 'Soft Inquiry',
                })

    return inquiries, reject_counters


def parse_inquiries(text, bureau):
    """Parse inquiries with bureau-specific logic."""
    if bureau == 'equifax':
        return parse_inquiries_equifax(text)
    if bureau == 'experian':
        return parse_inquiries_experian(text)
    if bureau == 'transunion':
        return parse_inquiries_transunion(text)
    
    inquiries = []
    reject_counters = {
        'header_only': 0,
        'city_state_line': 0,
        'address_fragment': 0,
        'missing_creditor_or_date': 0,
    }
    
    city_state_pattern = r'^[A-Z]{2}\s*\d{5}|^[A-Z][a-z]+,?\s+[A-Z]{2}\s*$'
    address_patterns = [r'\bSUITE\b', r'\bAPT\b', r'\bUNIT\b', r'\bPO BOX\b', r'\bLOCATION\b', r'\bPHONE\b']
    
    text_lower = text.lower()
    
    hard_section_start = -1
    hard_section_end = len(text)
    soft_section_start = -1
    section_label = 'unknown'
    
    hard_markers = ['requests viewed by others', 'regular inquiries', 'hard inquiries', 'inquiries that may impact']
    soft_markers = ['requests viewed only by you', 'promotional inquiries', 'soft inquiries', 'inquiries that do not impact']
    
    for marker in hard_markers:
        idx = text_lower.find(marker)
        if idx != -1:
            hard_section_start = idx
            section_label = marker
            break
    
    for marker in soft_markers:
        idx = text_lower.find(marker)
        if idx != -1:
            soft_section_start = idx
            if hard_section_start != -1 and soft_section_start > hard_section_start:
                hard_section_end = soft_section_start
            break
    
    if hard_section_start != -1:
        hard_section = text[hard_section_start:hard_section_end]
        date_line_pattern = r'(\d{1,2}/\d{1,2}/\d{2,4})\s+([A-Z][A-Za-z\s\.,&]+)'
        matches = re.finditer(date_line_pattern, hard_section)
        for match in matches:
            date = match.group(1)
            creditor = match.group(2).strip()[:50]
            
            if re.match(city_state_pattern, creditor):
                reject_counters['city_state_line'] += 1
                continue
            
            if any(re.search(pat, creditor, re.IGNORECASE) for pat in address_patterns):
                reject_counters['address_fragment'] += 1
                continue
            
            if len(creditor) <= 3:
                reject_counters['header_only'] += 1
                continue
            
            inquiry = {
                'raw_text': f"{date} {creditor}",
                'date': date,
                'type': 'Hard Inquiry',
                'creditor': creditor,
                'section_label': section_label,
                'rule': 'GENERIC_INQ',
                'receipt_snippet': match.group(0)[:120],
                'confidence': 'HIGH',
            }
            if inquiry not in inquiries:
                inquiries.append(inquiry)
    
    if not inquiries:
        inquiry_patterns = [
            r'(\d{1,2}/\d{1,2}/\d{2,4})\s+([A-Z][A-Za-z\s\.,&]+?)\s+(?:Inquiry|Credit)',
        ]
        for pattern in inquiry_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                date = match.group(1)
                creditor = match.group(2).strip()[:50]
                
                if not date or not creditor or len(creditor) <= 3:
                    reject_counters['missing_creditor_or_date'] += 1
                    continue
                
                if re.match(city_state_pattern, creditor):
                    reject_counters['city_state_line'] += 1
                    continue
                
                inquiry = {
                    'raw_text': match.group(0),
                    'date': date,
                    'type': 'Inquiry',
                    'creditor': creditor,
                    'section_label': 'fallback',
                    'rule': 'GENERIC_INQ_FALLBACK',
                    'receipt_snippet': match.group(0)[:120],
                    'confidence': 'MEDIUM',
                }
                if inquiry not in inquiries:
                    inquiries.append(inquiry)
    
    return inquiries, reject_counters

def extract_negatives_from_accounts(accounts):
    """
    Extract negative signals only from within account blocks (Pay Status, remarks).
    Works for all bureaus: TransUnion, Equifax, Experian.
    """
    negative_items = []
    
    never_late_re = re.compile(r'never\s*late|paid.*closed.*never\s*late|open.*never\s*late|pays?\s*as\s*agreed|current', re.IGNORECASE)
    legend_re = re.compile(r'(paid\s+on\s+time\s+30\s+30\s+days|payment\s+history\s+guide|current\s*/\s*terms\s+met)', re.IGNORECASE)
    
    negative_pay_status_patterns = [
        (r'(\d+)\s*days?\s*(?:past\s*due|late)', 'Late Payment'),
        (r'collection\s*account|collection', 'Collection'),
        (r'charge[d\s]*off', 'Charge Off'),
        (r'repossession', 'Repossession'),
        (r'foreclosure', 'Foreclosure'),
        (r'bankruptcy', 'Bankruptcy'),
        (r'written\s*off', 'Written Off'),
    ]
    
    for account in accounts:
        pay_status = account.get('status', '') or account.get('pay_status_raw', '')
        raw_section = account.get('raw_section', '')
        account_name = (account.get('account_name', '') or account.get('creditor', '')
                        or account.get('furnisher', '') or 'Unknown Account')
        page = account.get('page', 'N/A')
        
        if never_late_re.search(pay_status) and not re.search(r'charge[d\s]*off|collection|repossession|foreclosure|bankruptcy', pay_status, re.IGNORECASE):
            continue
        
        check_text = pay_status.lower()
        if not any(re.search(p, check_text, re.IGNORECASE) for p, _ in negative_pay_status_patterns):
            raw_clean = raw_section
            if legend_re.search(raw_clean):
                continue
            check_text = raw_clean.lower()
        
        for pattern, neg_type in negative_pay_status_patterns:
            match = re.search(pattern, check_text, re.IGNORECASE)
            if match:
                date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', raw_section)
                balance_match = re.search(r'\$?([\d,]+)', raw_section)
                
                receipt = f"Account: {account_name} | Pay Status: {pay_status[:80]}"
                
                account_id = account.get('account_number', '') or account.get('account_id', '')
                dedup_key = f"{account_name}|{account_id}|{neg_type}"
                
                negative_item = {
                    'type': neg_type,
                    'account_name': account_name,
                    'account_id': account_id,
                    'dedup_key': dedup_key,
                    'page': page,
                    'rule': 'NEG_FROM_ACCOUNT',
                    'date': date_match.group(1) if date_match else 'NOT_FOUND',
                    'amount': balance_match.group(1) if balance_match else 'NOT_FOUND',
                    'context': raw_section[:300],
                    'receipt_snippet': receipt[:200],
                    'confidence': 'HIGH' if date_match else 'MEDIUM',
                }
                
                if not any(ni.get('dedup_key') == dedup_key for ni in negative_items):
                    negative_items.append(negative_item)
                break
    
    return negative_items

def parse_negative_items(text, bureau='unknown', accounts=None):
    """FIX 3+4: Negatives from account blocks only, skip definition pages."""
    reject_counters = {
        'header_only': 0,
        'definition_page_skip': 0,
        'disclaimer_boilerplate': 0,
        'missing_date_and_linkage': 0,
        'keyword_only_no_context': 0,
        'global_scan_disabled': 0,
    }
    
    if accounts:
        negative_items = extract_negatives_from_accounts(accounts)
        reject_counters['global_scan_disabled'] = 1
        return negative_items, reject_counters
    
    negative_items = []
    disclaimer_phrases = ['information', 'this means', 'report contains', 'disclosure']
    
    negative_keywords = [
        'late payment', 'collection', 'charge off', 'charged off',
        'bankruptcy', 'foreclosure', 'repossession', 'judgment',
        'tax lien', 'delinquent', 'past due', '30 days late',
        '60 days late', '90 days late', '120 days late', 'written off'
    ]
    
    lines = text.split('\n')
    current_page = 1
    
    for i, line in enumerate(lines):
        if 'Page ' in line and ' of ' in line:
            page_match = re.search(r'Page\s+(\d+)\s+of', line)
            if page_match:
                current_page = int(page_match.group(1))
        
        if current_page <= 6:
            context = '\n'.join(lines[max(0,i-5):min(len(lines),i+5)])
            if is_definition_page(context):
                reject_counters['definition_page_skip'] += 1
                continue
        
        line_lower = line.lower()
        
        if any(phrase in line_lower for phrase in disclaimer_phrases):
            continue
        
        for keyword in negative_keywords:
            if keyword in line_lower:
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 3)
                context = '\n'.join(lines[context_start:context_end])
                
                context_lower = context.lower()
                if any(phrase in context_lower for phrase in disclaimer_phrases):
                    reject_counters['disclaimer_boilerplate'] += 1
                    break
                
                date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', context)
                amount_match = re.search(r'\$?([\d,]+\.?\d*)', context)
                account_link = re.search(r'(?:account|creditor|subscriber)[:\s]+([A-Za-z0-9\s]+)', context, re.IGNORECASE)
                
                has_date = bool(date_match)
                has_linkage = bool(account_link) or bool(amount_match and len(amount_match.group(1)) > 2)
                has_meaningful_context = len(context.strip()) > 30 and keyword in context_lower
                
                if keyword == 'bankruptcy' and not has_date and not has_linkage:
                    if len(line.strip()) < 20:
                        reject_counters['keyword_only_no_context'] += 1
                        break
                
                if has_date or has_linkage or has_meaningful_context:
                    confidence = 'HIGH' if has_date else ('MEDIUM' if has_linkage else 'LOW')
                    negative_item = {
                        'type': keyword.title(),
                        'context': context[:300],
                        'page': current_page,
                        'rule': 'GENERIC_NEG_KEYWORD',
                        'date': date_match.group(1) if date_match else 'NOT_FOUND',
                        'amount': amount_match.group(1) if amount_match else 'NOT_FOUND',
                        'receipt_snippet': context[:120].replace('\n', ' '),
                        'confidence': confidence,
                    }
                    if not any(ni['context'] == negative_item['context'] for ni in negative_items):
                        negative_items.append(negative_item)
                else:
                    reject_counters['missing_date_and_linkage'] += 1
                break
    
    return negative_items, reject_counters

def parse_public_records(text):
    public_records = []

    pr_section = None
    pr_patterns = [
        (r'(?:^|\n)Public Records?\s*\n(.*?)(?=\n(?:Inquiries|Account Name|Accounts with|Satisfactory|Credit Accounts|Hard Inquiries|Soft Inquiries|Consumer Statement|$))', re.DOTALL | re.IGNORECASE),
        (r'(?:^|\n)(?:Negative Information\s*\(Collections and Bankruptcy Public Records\))\s*\n(.*?)(?=\n(?:Inquiries|Credit Accounts|$))', re.DOTALL | re.IGNORECASE),
        (r'(?:Public Record Information)\s*\n(.*?)(?=\n(?:Inquiries|Account Information|Credit Items|$))', re.DOTALL | re.IGNORECASE),
    ]
    for pat, flags in pr_patterns:
        m = re.search(pat, text, flags)
        if m:
            pr_section = m.group(1)
            break

    if not pr_section:
        return public_records

    if re.search(r'no\s+public\s+records?\s+(?:reported|found|on\s+file)', pr_section, re.IGNORECASE):
        return public_records

    record_patterns = [
        (r'Bankruptcy.*?(?:Chapter\s*\d+)?.*?(?:Filed|Discharged)?.*?(\d{1,2}/\d{1,2}/\d{2,4})?', 'Bankruptcy'),
        (r'Tax Lien.*?\$?([\d,]+)?.*?(\d{1,2}/\d{1,2}/\d{2,4})?', 'Tax Lien'),
        (r'Civil Judgment.*?\$?([\d,]+)?.*?(\d{1,2}/\d{1,2}/\d{2,4})?', 'Civil Judgment'),
        (r'Foreclosure.*?(\d{1,2}/\d{1,2}/\d{2,4})?', 'Foreclosure')
    ]
    for pattern, record_type in record_patterns:
        matches = re.finditer(pattern, pr_section, re.IGNORECASE)
        for match in matches:
            record = {'type': record_type, 'raw_text': match.group(0)[:200], 'details': {}}
            date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', match.group(0))
            if date_match:
                record['details']['date'] = date_match.group(1)
            amount_match = re.search(r'\$?([\d,]+)', match.group(0))
            if amount_match:
                record['details']['amount'] = amount_match.group(1)
            public_records.append(record)
    return public_records

def extract_labeled_name(text):
    name_label_patterns = [
        r'(?:^|\n)\s*Prepared\s+[Ff]or:?\s*\n\s*([A-Z][A-Z\-\' ]+?)(?:\n|$)',
        r'(?:^|\n)\s*(?:Consumer\s+Name|File\s+Name|Reported\s+Name)\s*[:\s]+([A-Za-z][a-zA-Z\-\']+(?:\s+[A-Za-z]\.?\s*)?[A-Za-z][a-zA-Z\-\']+(?:\s+[A-Za-z][a-zA-Z\-\']+)?)',
        r'(?:^|\n)\s*(?:Consumer\s+Name|File\s+Name|Reported\s+Name)\s*[:\s]*\n\s*([A-Za-z][a-zA-Z\-\']+(?:\s+[A-Za-z]\.?\s*)?[A-Za-z][a-zA-Z\-\']+(?:\s+[A-Za-z][a-zA-Z\-\']+)?)',
        r'(?:^|\n)\s*Name\s*:\s+([A-Za-z][a-zA-Z\-\']+(?:\s+[A-Za-z]\.?\s*)?[A-Za-z][a-zA-Z\-\']+(?:\s+[A-Za-z][a-zA-Z\-\']+)?)',
        r'(?:^|\n)\s*(?:Your\s+Name|Primary\s+Name|Name\s+on\s+File)\s*[:\s]+([A-Za-z][a-zA-Z\-\']+(?:\s+[A-Za-z]\.?\s*)?[A-Za-z][a-zA-Z\-\']+(?:\s+[A-Za-z][a-zA-Z\-\']+)?)',
        r'(?:^|\n)\s*(?:Your\s+Name|Primary\s+Name|Name\s+on\s+File)\s*[:\s]*\n\s*([A-Za-z][a-zA-Z\-\']+(?:\s+[A-Za-z]\.?\s*)?[A-Za-z][a-zA-Z\-\']+(?:\s+[A-Za-z][a-zA-Z\-\']+)?)',
        r'(?:^|\n)\s*Personal\s+Information\s*\n\s*(?:Name\s*[:\s]*)?([A-Z][A-Z\-\' ]{3,}?)(?:\n|$)',
        r'(?:^|\n)\s*(?:Name|Consumer)\s*\n\s*([A-Z][a-zA-Z\-\']+(?:\s+[A-Za-z]\.?\s*)?[A-Za-z][a-zA-Z\-\']+(?:\s+[A-Za-z][a-zA-Z\-\']+)?)\s*(?:\n|$)',
        r'(?:^|\n)\s*(?:Identification|Personal\s+Details?)\s*\n(?:.*\n){0,2}\s*([A-Z][a-zA-Z\-\']+\s+[A-Z][a-zA-Z\-\']+(?:\s+[A-Z][a-zA-Z\-\']+)?)\s*(?:\n|$)',
    ]
    
    exclusion_phrases = ['statement', 'report', 'consumer', 'credit', 'disclosure',
                         'response center', 'dispute center', 'service center',
                         'transunion', 'experian', 'equifax',
                         'consumer relations', 'consumer response', 'consumer assistance',
                         'investigation department', 'dispute department']
    
    candidates = []
    for pattern in name_label_patterns:
        matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
        for match in matches:
            candidate = ' '.join(match.group(1).strip().split())
            
            candidate_lower = candidate.lower()
            if any(phrase in candidate_lower for phrase in exclusion_phrases):
                continue
            if any(bp in candidate_lower for bp in BOILERPLATE_NAMES):
                continue
            
            cap_tokens = [t for t in candidate.split() if t and t[0].isupper() and any(c.isalpha() for c in t)]
            if len(cap_tokens) < 2:
                continue
            
            candidates.append(candidate)
    
    if not candidates:
        return None
    
    if len(candidates) == 1:
        return candidates[0]
    
    candidate_counts = {}
    for c in candidates:
        normalized = ' '.join(c.split()).upper()
        candidate_counts[normalized] = candidate_counts.get(normalized, 0) + 1
    
    best_normalized = max(candidate_counts, key=lambda k: candidate_counts[k])
    for c in candidates:
        if ' '.join(c.split()).upper() == best_normalized:
            return c
    
    return candidates[0]

def parse_personal_info(text):
    personal_info = {}
    
    extracted_name = extract_labeled_name(text)
    if extracted_name:
        personal_info['name'] = extracted_name
    
    if 'name' not in personal_info:
        name_patterns = [
            r'(?:Consumer|Name|Full\s+Name|Consumer\s+Name|Prepared\s+For)[:\s]+([A-Z][A-Za-z\s,.\'-]+?)(?:\n|$)',
            r'(?:Personal\s+Information)\s*\n\s*([A-Z][A-Za-z\s,.\'-]+?)(?:\n)',
        ]
        for p in name_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m and len(m.group(1).strip()) > 3:
                candidate_name = m.group(1).strip()
                candidate_lower = candidate_name.lower()
                if not any(bp in candidate_lower for bp in BOILERPLATE_NAMES):
                    personal_info['name'] = candidate_name
                    break
    
    ssn_patterns = [
        r'(?:SSN|Social\s+Security(?:\s+Number)?)\s*[:\s#]+\s*(XXX-XX-\d{4}|\*+\d{4}|\d{3}-\d{2}-\d{4})',
        r'(?:SSN|Social)[:\s#]*(?:[\d*X]{3}[-\s]?[\d*X]{2}[-\s]?)(\d{4})',
        r'(?:Last\s+(?:4|Four)\s+(?:of\s+)?SSN)[:\s]+(\d{4})',
        r'(?:SSN)\s*\n\s*(?:XXX-XX-|[\*X]+-?)(\d{4})',
    ]
    for p in ssn_patterns:
        ssn_match = re.search(p, text, re.IGNORECASE)
        if ssn_match:
            personal_info['ssn'] = ssn_match.group(1).strip()
            break
    
    personal_section = text
    accounts_pos = re.search(r'\n\s*Accounts?\b', text, re.IGNORECASE)
    if accounts_pos:
        personal_section = text[:accounts_pos.start()]

    address_patterns_personal = [
        r'(?:Current\s+Address|Mailing\s+Address)[:\s]+(.+?)(?:\n|Report|Date|Since)',
        r'(?:Residence|Home\s+Address)[:\s]+(.+?)(?:\n|$)',
        r'(?:Current\s+Address)\s*\n\s*(.+?)(?:\n\s*(?:Date|Other|Phone|Previous))',
    ]
    address_patterns_fallback = [
        r'(\d+\s+[A-Za-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Way|Circle|Cir|Court|Ct|Place|Pl)[.,]?\s+.+?)(?:\n|$)',
        r'(?:Address)\s*\n\s*(.+?\d{5}(?:-\d{4})?)',
    ]
    for pattern in address_patterns_personal:
        address_match = re.search(pattern, personal_section, re.IGNORECASE)
        if address_match:
            candidate_addr = address_match.group(1).strip()[:200]
            candidate_addr_lower = candidate_addr.lower().strip()
            if any(candidate_addr_lower == bp or candidate_addr_lower.replace(' ', '') == bp.replace(' ', '') for bp in BOILERPLATE_ADDRESSES):
                continue
            personal_info['address'] = candidate_addr
            break
    if 'address' not in personal_info:
        for pattern in address_patterns_fallback:
            address_match = re.search(pattern, personal_section, re.IGNORECASE)
            if address_match:
                candidate_addr = address_match.group(1).strip()[:200]
                candidate_addr_lower = candidate_addr.lower().strip()
                if any(candidate_addr_lower == bp or candidate_addr_lower.replace(' ', '') == bp.replace(' ', '') for bp in BOILERPLATE_ADDRESSES):
                    continue
                personal_info['address'] = candidate_addr
                break
    if 'address' not in personal_info:
        full_addr_match = re.search(
            r'(\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:ST|CT|CIR|DR|LN|AVE|RD|BLVD|WAY|PL|TRL|LOOP|HWY)\b[,.]?\s+[A-Za-z]+(?:\s+[A-Za-z]+)*,?\s+[A-Z]{2},?\s+\d{5}(?:-\d{4})?)',
            personal_section, re.IGNORECASE
        )
        if full_addr_match:
            personal_info['address'] = full_addr_match.group(1).strip()
    
    dob_patterns = [
        r'(?:Date\s+of\s+Birth|DOB|Birth\s*Date|Born)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(?:Date\s+of\s+Birth|DOB|Birth\s*Date)\s*\n\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(?:Year\s+of\s+Birth|YOB)[:\s]+(\d{4})',
        r'(?:Year\s+of\s+Birth)\s*\n\s*(\d{4})',
    ]
    for p in dob_patterns:
        dob_match = re.search(p, text, re.IGNORECASE)
        if dob_match:
            personal_info['dob'] = dob_match.group(1).strip()
            break
    
    return personal_info

def parse_credit_report_data(text, bureau='unknown'):
    accounts, accounts_rejects = parse_accounts(text, bureau)
    inquiries, inquiries_rejects = parse_inquiries(text, bureau)
    negative_items, negatives_rejects = parse_negative_items(text, bureau=bureau, accounts=accounts)
    
    parsed_data = {
        'bureau': bureau,
        'personal_info': parse_personal_info(text),
        'accounts': accounts,
        'inquiries': inquiries,
        'negative_items': negative_items,
        'public_records': parse_public_records(text),
        'summary_stats': {},
        'reject_counters': {
            'accounts': accounts_rejects,
            'inquiries': inquiries_rejects,
            'negative_items': negatives_rejects,
        }
    }
    parsed_data['summary_stats'] = {
        'total_accounts_found': len(parsed_data['accounts']),
        'total_inquiries_found': len(parsed_data['inquiries']),
        'total_negative_items_found': len(parsed_data['negative_items']),
        'total_public_records_found': len(parsed_data['public_records']),
        'personal_info_fields': len([v for v in parsed_data['personal_info'].values() if v])
    }
    return parsed_data
