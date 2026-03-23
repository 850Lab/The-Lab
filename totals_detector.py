import re


def detect_section_totals(plain_text, bureau):
    text_lower = plain_text.lower()

    accounts = _extract_total(text_lower, [
        r'(?:total\s+(?:number\s+of\s+)?accounts|number\s+of\s+accounts|total\s+accounts)\s*[:\s]\s*(\d+)',
        r'accounts?\s*:\s*(\d+)',
    ])

    inquiries = _extract_total(text_lower, [
        r'(?:total\s+(?:number\s+of\s+)?inquiries|number\s+of\s+inquiries|total\s+inquiries)\s*[:\s]\s*(\d+)',
        r'inquiries?\s*:\s*(\d+)',
    ])

    negative_items = _extract_total(text_lower, [
        r'(?:total\s+(?:number\s+of\s+)?negative\s+items?|negative\s+items?|adverse\s+items?)\s*[:\s]\s*(\d+)',
    ])

    public_records = _extract_total(text_lower, [
        r'(?:total\s+(?:number\s+of\s+)?public\s+records?)\s*[:\s]\s*(\d+)',
        r'(\d+)\s+public\s+records?\b',
    ])

    if bureau == 'transunion' and accounts is None:
        section_count = _count_accounts_from_section_headers(plain_text)
        if section_count is not None:
            accounts = section_count

    if bureau == 'transunion' and inquiries is None:
        tu_inq = _count_transunion_inquiries(plain_text)
        if tu_inq is not None:
            inquiries = tu_inq

    if bureau == 'transunion' and public_records is None:
        tu_pr = _count_transunion_public_records(plain_text)
        if tu_pr is not None:
            public_records = tu_pr

    if bureau == 'equifax' and accounts is None:
        eq_count = _count_accounts_equifax(plain_text)
        if eq_count is not None:
            accounts = eq_count

    if bureau == 'equifax' and inquiries is None:
        eq_hard = len(re.findall(r'\bHard\b\s+\d{1,2}/\d{1,2}/\d{4}', plain_text))
        if eq_hard > 0:
            inquiries = eq_hard

    if bureau == 'equifax' and public_records is None:
        eq_pr = _count_equifax_public_records(plain_text)
        if eq_pr is not None:
            public_records = eq_pr

    if bureau == 'experian':
        glance = _parse_experian_at_a_glance(plain_text)
        if glance.get('accounts') is not None:
            accounts = glance['accounts']
        if glance.get('inquiries') is not None:
            inquiries = glance['inquiries']
        if glance.get('public_records') is not None:
            public_records = glance['public_records']

    threeb = _parse_3b_summary(plain_text, bureau)
    if threeb:
        if threeb.get('accounts') is not None and accounts is None:
            accounts = threeb['accounts']
        if threeb.get('inquiries') is not None and inquiries is None:
            inquiries = threeb['inquiries']
        if threeb.get('public_records') is not None and public_records is None:
            public_records = threeb['public_records']

    return {
        "accounts": accounts,
        "inquiries": inquiries,
        "negative_items": negative_items,
        "public_records": public_records,
    }


def detect_section_totals_with_sources(plain_text, bureau):
    text_lower = plain_text.lower()
    sources = {}

    accounts = _extract_total(text_lower, [
        r'(?:total\s+(?:number\s+of\s+)?accounts|number\s+of\s+accounts|total\s+accounts)\s*[:\s]\s*(\d+)',
        r'accounts?\s*:\s*(\d+)',
    ])
    if accounts is not None:
        sources['accounts'] = 'explicit'

    inquiries = _extract_total(text_lower, [
        r'(?:total\s+(?:number\s+of\s+)?inquiries|number\s+of\s+inquiries|total\s+inquiries)\s*[:\s]\s*(\d+)',
        r'inquiries?\s*:\s*(\d+)',
    ])
    if inquiries is not None:
        sources['inquiries'] = 'explicit'

    negative_items = _extract_total(text_lower, [
        r'(?:total\s+(?:number\s+of\s+)?negative\s+items?|negative\s+items?|adverse\s+items?)\s*[:\s]\s*(\d+)',
    ])
    if negative_items is not None:
        sources['negative_items'] = 'explicit'

    public_records = _extract_total(text_lower, [
        r'(?:total\s+(?:number\s+of\s+)?public\s+records?)\s*[:\s]\s*(\d+)',
        r'(\d+)\s+public\s+records?\b',
    ])
    if public_records is not None:
        sources['public_records'] = 'explicit'

    if bureau == 'transunion' and accounts is None:
        section_count = _count_accounts_from_section_headers(plain_text)
        if section_count is not None:
            accounts = section_count
            sources['accounts'] = 'section_derived'

    if bureau == 'transunion' and inquiries is None:
        tu_inq = _count_transunion_inquiries(plain_text)
        if tu_inq is not None:
            inquiries = tu_inq
            sources['inquiries'] = 'section_derived'

    if bureau == 'transunion' and public_records is None:
        tu_pr = _count_transunion_public_records(plain_text)
        if tu_pr is not None:
            public_records = tu_pr
            sources['public_records'] = 'section_derived'

    if bureau == 'equifax' and accounts is None:
        eq_count = _count_accounts_equifax(plain_text)
        if eq_count is not None:
            accounts = eq_count
            sources['accounts'] = 'section_derived'

    if bureau == 'equifax' and inquiries is None:
        eq_hard = len(re.findall(r'\bHard\b\s+\d{1,2}/\d{1,2}/\d{4}', plain_text))
        if eq_hard > 0:
            inquiries = eq_hard
            sources['inquiries'] = 'section_derived'

    if bureau == 'equifax' and public_records is None:
        eq_pr = _count_equifax_public_records(plain_text)
        if eq_pr is not None:
            public_records = eq_pr
            sources['public_records'] = 'section_derived'

    if bureau == 'experian':
        glance = _parse_experian_at_a_glance(plain_text)
        if glance.get('accounts') is not None:
            accounts = glance['accounts']
            sources['accounts'] = 'explicit'
        if glance.get('inquiries') is not None:
            inquiries = glance['inquiries']
            sources['inquiries'] = 'explicit'
        if glance.get('public_records') is not None:
            public_records = glance['public_records']
            sources['public_records'] = 'explicit'

    threeb = _parse_3b_summary(plain_text, bureau)
    if threeb:
        if threeb.get('accounts') is not None and accounts is None:
            accounts = threeb['accounts']
            sources['accounts'] = 'explicit'
        if threeb.get('inquiries') is not None and inquiries is None:
            inquiries = threeb['inquiries']
            sources['inquiries'] = 'explicit'
        if threeb.get('public_records') is not None and public_records is None:
            public_records = threeb['public_records']
            sources['public_records'] = 'explicit'

    if bureau == 'transunion' and negative_items is None:
        tu_neg = _count_transunion_negative_items(plain_text)
        if tu_neg is not None:
            negative_items = tu_neg
            sources['negative_items'] = 'section_derived'

    if bureau == 'equifax' and negative_items is None:
        eq_neg = _count_equifax_negative_items(plain_text)
        if eq_neg is not None:
            negative_items = eq_neg
            sources['negative_items'] = 'section_derived'

    if bureau == 'experian' and negative_items is None:
        exp_neg = _count_experian_negative_items(plain_text)
        if exp_neg is not None:
            negative_items = exp_neg
            sources['negative_items'] = 'section_derived'

    if bureau == 'experian' and accounts is None:
        exp_acct = _count_experian_accounts(plain_text)
        if exp_acct is not None:
            accounts = exp_acct
            sources['accounts'] = 'section_derived'

    if bureau == 'experian' and inquiries is None:
        exp_inq = _count_experian_inquiries(plain_text)
        if exp_inq is not None:
            inquiries = exp_inq
            sources['inquiries'] = 'section_derived'

    if bureau == 'experian' and public_records is None:
        exp_pr = _count_experian_public_records(plain_text)
        if exp_pr is not None:
            public_records = exp_pr
            sources['public_records'] = 'section_derived'

    totals = {
        "accounts": accounts,
        "inquiries": inquiries,
        "negative_items": negative_items,
        "public_records": public_records,
    }

    return totals, sources


def compute_totals_confidence(totals):
    non_none = sum(1 for v in totals.values() if v is not None)
    if non_none >= 3:
        return "HIGH"
    elif non_none >= 1:
        return "MED"
    else:
        return "LOW"


def compute_totals_confidence_with_sources(totals, sources):
    non_none = sum(1 for v in totals.values() if v is not None)
    explicit_count = sum(1 for v in sources.values() if v == 'explicit')
    derived_count = sum(1 for v in sources.values() if v == 'section_derived')

    if explicit_count >= 3:
        return "HIGH"
    elif explicit_count >= 1 and non_none >= 3:
        return "HIGH"
    elif non_none >= 3:
        return "HIGH"
    elif non_none >= 1:
        return "MED"
    else:
        return "LOW"


def detect_totals_mode(totals, bureau, plain_text):
    text_lower = plain_text.lower()

    has_explicit = _extract_total(text_lower, [
        r'(?:total\s+(?:number\s+of\s+)?accounts|number\s+of\s+accounts|total\s+accounts)\s*[:\s]\s*(\d+)',
    ])

    has_section_headers = (
        "accounts with adverse information" in text_lower
        or "satisfactory accounts" in text_lower
    )

    has_eq_credit_accounts = "credit accounts" in text_lower
    has_at_a_glance = "at a" in text_lower and "glance" in text_lower

    if has_explicit is not None:
        return "EXPLICIT"
    elif has_at_a_glance and bureau == 'experian':
        return "EXPLICIT"
    elif has_section_headers:
        return "SECTION_DERIVED"
    elif has_eq_credit_accounts and bureau == 'equifax':
        return "SECTION_DERIVED"
    else:
        return "NONE"


def detect_totals_mode_with_sources(totals, sources, bureau, plain_text):
    text_lower = plain_text.lower()

    has_explicit = _extract_total(text_lower, [
        r'(?:total\s+(?:number\s+of\s+)?accounts|number\s+of\s+accounts|total\s+accounts)\s*[:\s]\s*(\d+)',
    ])

    has_at_a_glance = "at a" in text_lower and "glance" in text_lower

    if has_explicit is not None:
        return "EXPLICIT"
    elif has_at_a_glance and bureau == 'experian':
        return "EXPLICIT"

    has_any_explicit = any(v == 'explicit' for v in sources.values())
    if has_any_explicit:
        return "EXPLICIT"

    has_any_derived = any(v == 'section_derived' for v in sources.values())
    if has_any_derived:
        return "SECTION_DERIVED"

    has_section_headers = (
        "accounts with adverse information" in text_lower
        or "satisfactory accounts" in text_lower
    )
    has_eq_credit_accounts = "credit accounts" in text_lower

    if has_section_headers:
        return "SECTION_DERIVED"
    elif has_eq_credit_accounts and bureau == 'equifax':
        return "SECTION_DERIVED"

    return "NONE"


def self_verify_totals(plain_text, bureau, extracted_counts):
    independent_counts, sources = detect_section_totals_with_sources(plain_text, bureau)

    matches = 0
    checked = 0
    matched_sections = []

    for section in ['accounts', 'inquiries', 'public_records']:
        ind_val = independent_counts.get(section)
        ext_val = extracted_counts.get(section, 0)

        if ind_val is not None and ext_val is not None:
            checked += 1
            if ind_val == ext_val:
                matches += 1
                matched_sections.append(section)

    if matches >= 2:
        confidence = "HIGH" if matches >= 3 else "MED"
        return {
            "verified": True,
            "confidence": confidence,
            "matches": matches,
            "checked": checked,
            "matched_sections": matched_sections,
            "independent_counts": independent_counts,
            "sources": sources,
        }
    elif matches == 1 and checked >= 1:
        return {
            "verified": True,
            "confidence": "MED",
            "matches": matches,
            "checked": checked,
            "matched_sections": matched_sections,
            "independent_counts": independent_counts,
            "sources": sources,
        }
    else:
        return {
            "verified": False,
            "confidence": "LOW",
            "matches": matches,
            "checked": checked,
            "matched_sections": [],
            "independent_counts": independent_counts,
            "sources": sources,
        }


def _count_transunion_negative_items(plain_text):
    adverse_match = re.search(
        r'Accounts with adverse',
        plain_text,
        re.IGNORECASE,
    )
    if not adverse_match:
        return None

    satisfactory_idx = plain_text.find('Satisfactory Accounts')
    if satisfactory_idx == -1:
        satisfactory_idx = len(plain_text)

    section = plain_text[adverse_match.start():satisfactory_idx]

    acr_count = len(re.findall(r'^Account Name$', section, re.MULTILINE))
    osc_count = len(re.findall(
        r'^[A-Z][A-Z0-9\s/&\.\-]+?\s+(?:\d{5,}\*+|\*{4,}\d+)$',
        section,
        re.MULTILINE,
    ))

    count = max(acr_count, osc_count)
    if count > 0:
        return count

    return 0


def _count_equifax_negative_items(plain_text):
    neg_match = re.search(
        r'Negative Information\s*(?:\(Collections and Bankruptcy Public Records\))?',
        plain_text,
        re.IGNORECASE,
    )
    if not neg_match:
        return None

    end_markers = ['Credit Accounts', 'Inquiries', 'Personal Information']
    section_end = len(plain_text)
    for marker in end_markers:
        idx = plain_text.find(marker, neg_match.end())
        if idx != -1 and idx < section_end:
            section_end = idx

    section = plain_text[neg_match.end():section_end]

    count = len(re.findall(r'Account Number:', section))
    if count > 0:
        return count

    return 0


def _count_experian_negative_items(plain_text):
    neg_match = re.search(
        r'(?:Potentially Negative|Negative) (?:Items|Information)',
        plain_text,
        re.IGNORECASE,
    )
    if not neg_match:
        return None

    end_markers = ['Accounts in Good Standing', 'Credit Items', 'Inquiries']
    section_end = len(plain_text)
    for marker in end_markers:
        idx = plain_text.find(marker, neg_match.end())
        if idx != -1 and idx < section_end:
            section_end = idx

    section = plain_text[neg_match.end():section_end]

    count = len(re.findall(
        r'(?:Account #|Original Creditor|Status:)',
        section,
    ))
    if count > 0:
        return count // max(1, len(re.findall(r'Status:', section)))

    return 0


def _count_experian_accounts(plain_text):
    count = len(re.findall(r'(?:Account #|Acct #)\s*\S+', plain_text))
    if count > 0:
        return count

    status_blocks = len(re.findall(
        r'Status:\s*(?:Open|Closed|Paid|Collection|Charge[- ]?off)',
        plain_text,
        re.IGNORECASE,
    ))
    if status_blocks > 0:
        return status_blocks

    return None


def _count_experian_inquiries(plain_text):
    inq_section = re.search(
        r'(?:Hard\s+)?Inquiries?\s*\n(.*?)(?:Soft Inquiries|Consumer Statement|End of Report|$)',
        plain_text,
        re.DOTALL | re.IGNORECASE,
    )
    if inq_section:
        section = inq_section.group(1)
        date_count = len(re.findall(r'\d{1,2}/\d{1,2}/\d{4}', section))
        if date_count > 0:
            return date_count

    return None


def _count_experian_public_records(plain_text):
    pr_section = re.search(
        r'Public Records?\s*\n(.*?)(?:Account|Inquir|Credit Items|$)',
        plain_text,
        re.DOTALL | re.IGNORECASE,
    )
    if pr_section:
        section = pr_section.group(1)
        entries = len(re.findall(
            r'(?:Bankruptcy|Chapter\s+\d+|Judgment|Tax Lien|Civil)',
            section,
            re.IGNORECASE,
        ))
        return entries

    if re.search(r'public records?\s*:?\s*(?:none|0|no)\b', plain_text.lower()):
        return 0

    return None


def _count_equifax_public_records(plain_text):
    neg_section = re.search(
        r'Negative Information\s*\(Collections and Bankruptcy Public Records\)(.*?)(?:Inquiries|Credit Accounts)',
        plain_text,
        re.DOTALL | re.IGNORECASE,
    )
    if neg_section:
        section_text = neg_section.group(1)
        bankruptcy_count = len(re.findall(
            r'(?:Bankruptcy|Chapter\s+\d+|Public\s+Record)\s*(?:Filed|Entered|Reported)',
            section_text,
            re.IGNORECASE,
        ))
        collection_count = len(re.findall(
            r'(?:Collection|Charge\s*Off)\s+Account',
            section_text,
            re.IGNORECASE,
        ))
        account_entries = len(re.findall(
            r'Account Number:',
            section_text,
        ))
        total = bankruptcy_count + collection_count + account_entries
        return total
    neg_header = re.search(
        r'Negative Information',
        plain_text,
        re.IGNORECASE,
    )
    if neg_header:
        return 0
    return None


def _count_accounts_equifax(plain_text):
    account_number_count = len(re.findall(
        r'Account Number:\s*\*?\w+',
        plain_text,
    ))
    if account_number_count > 0:
        return account_number_count
    return None


def _count_accounts_from_section_headers(plain_text):
    acr_label_count = len(re.findall(
        r'^Account Name$',
        plain_text,
        re.MULTILINE,
    ))

    osc_header_count = len(re.findall(
        r'^[A-Z][A-Z0-9\s/&\.\-]+?\s+(?:\d{5,}\*+|\*{4,}\d+)$',
        plain_text,
        re.MULTILINE,
    ))

    split_line_count = 0
    lines = plain_text.split('\n')
    for i in range(len(lines) - 2):
        l = lines[i].strip()
        nl = lines[i + 1].strip()
        nnl = lines[i + 2].strip()
        if (re.match(r'^[A-Z][A-Z0-9\s/&\.\-,\']{2,}$', l)
                and re.match(r'^(\d{5,}\*+|\*{4,}\d+)$', nl)
                and nnl == 'Account Information'):
            split_line_count += 1

    best_count = max(osc_header_count, split_line_count)

    if acr_label_count > 0 and best_count >= acr_label_count:
        return best_count
    elif acr_label_count > 0:
        return acr_label_count
    elif best_count > 0:
        return best_count

    return None


def _parse_experian_at_a_glance(plain_text):
    result = {}
    glance_match = re.search(r'(?:At a\s*\n?\s*Glance|At a Glance)\s+(.*?)(?:\n\n|Personal Information)', plain_text, re.DOTALL)
    if glance_match:
        glance_text = glance_match.group(1)
        acct_match = re.search(r'(\d+)\s+Accounts?', glance_text)
        if acct_match:
            result['accounts'] = int(acct_match.group(1))
        inq_match = re.search(r'(\d+)\s+Hard\s+Inquir', glance_text)
        if inq_match:
            result['inquiries'] = int(inq_match.group(1))
        pr_match = re.search(r'(\d+)\s+Public\s+Records?', glance_text)
        if pr_match:
            result['public_records'] = int(pr_match.group(1))
    return result


def _count_transunion_inquiries(plain_text):
    ri_idx = plain_text.find('Regular Inquiries')
    if ri_idx == -1:
        return None

    end_markers = [
        'Account Review Inquiries',
        'Promotional Inquiries',
        'Consumer Statement',
        'Personal Statement',
        'Accounts with',
        'Satisfactory Accounts',
        'Account Name',
    ]
    section_end = len(plain_text)
    for marker in end_markers:
        idx = plain_text.find(marker, ri_idx + 20)
        if idx != -1 and idx < section_end:
            section_end = idx

    garbled_review = re.search(
        r'[Aa]+[Cc]+[Oo]+[Uu]+[Nn]+[Tt]+\s*[Rr]+[Ee]+[Vv]+[Ii]+[Ee]+[Ww]+',
        plain_text[ri_idx + 20:]
    )
    if garbled_review:
        garbled_pos = ri_idx + 20 + garbled_review.start()
        if garbled_pos < section_end:
            section_end = garbled_pos

    inq_text = plain_text[ri_idx:section_end]

    count = len(re.findall(r'Requested On\s*\n?\s*\d{2}/\d{2}/\d{4}', inq_text))
    if count > 0:
        return count

    count = len(re.findall(r'Location Requested On\s*\n[^\n]+\d{2}/\d{2}/\d{4}', inq_text))
    if count > 0:
        return count

    count = len(re.findall(r'Inquiry Type', inq_text))
    if count > 0:
        return count

    return 0


def _count_transunion_public_records(plain_text):
    pr_match = re.search(
        r'(?:^|\n)Public Records?\s*\n(.*?)(?:Inquiries|Account Name|Accounts with|$)',
        plain_text,
        re.DOTALL | re.IGNORECASE,
    )
    if pr_match:
        section = pr_match.group(1)
        entries = len(re.findall(
            r'(?:Bankruptcy|Chapter\s+\d+|Judgment|Tax Lien|Civil Claim)',
            section,
            re.IGNORECASE,
        ))
        return entries

    has_accounts = (
        re.search(r'Accounts with adverse', plain_text, re.IGNORECASE)
        or re.search(r'Satisfactory Accounts', plain_text, re.IGNORECASE)
        or re.search(r'^Account Name$', plain_text, re.MULTILINE)
    )
    if has_accounts:
        return 0

    return None


def _parse_3b_summary(plain_text, bureau):
    summary_match = re.search(
        r'Summary\s*\n\s*Transunion[®]?\s+Experian[®]?\s+Equifax[®]?\s*\n(.*?)(?:Account History|Payment History|\n\n)',
        plain_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not summary_match:
        return None

    summary_text = summary_match.group(1)

    bureau_col = {'transunion': 0, 'experian': 1, 'equifax': 2}.get(bureau)
    if bureau_col is None:
        return None

    result = {}

    for line in summary_text.split('\n'):
        line = line.strip()
        if not line:
            continue

        nums = re.findall(r'(\d+)', line)
        label = re.sub(r'[\d$,]+', '', line).strip().lower().rstrip(':')

        if len(nums) < 3:
            continue

        if 'total accounts' in label or label == 'total accounts':
            result['accounts'] = int(nums[bureau_col])
        elif 'public records' in label:
            result['public_records'] = int(nums[bureau_col])
        elif 'inquiries' in label:
            result['inquiries'] = int(nums[bureau_col])

    return result if result else None


def _extract_total(text_lower, patterns):
    for pattern in patterns:
        m = re.search(pattern, text_lower)
        if m:
            val = int(m.group(1))
            if val > 500:
                continue
            return val
    return None
