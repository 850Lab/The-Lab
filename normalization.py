"""
normalization.py | 850 Lab Parser Machine
Data normalization layer for cleaning parsed credit report data
Includes canonical entity resolution to prevent inflated counts
"""

import re
import json
import hashlib
import uuid


def canonicalize_creditor_name(name):
    """
    Normalize creditor name to a canonical form for deduplication.
    Handles variations like 'CAPITAL ONE', 'Capital One Bank', 'CAPITAL ONE NA'
    """
    if not name or not isinstance(name, str):
        return ''
    
    name = name.upper().strip()
    
    # Remove common suffixes that don't change identity
    suffixes_to_remove = [
        r'\s*,?\s*(N\.?A\.?|NA|NATIONAL ASSOCIATION)$',
        r'\s*,?\s*(LLC|INC|CORP|CORPORATION|CO|COMPANY)\.?$',
        r'\s*,?\s*(BANK|BANKING|FSB|CREDIT UNION|CU)$',
        r'\s*,?\s*(USA|US|AMERICA|AMERICAN)$',
        r'\s*,?\s*\d{4,}$',  # Account numbers at end
        r'\s*[#]\d+$',  # Account number with #
    ]
    
    for pattern in suffixes_to_remove:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
    # Remove punctuation and extra whitespace
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Common abbreviation mappings
    abbreviations = {
        'CAP ONE': 'CAPITAL ONE',
        'CAPONE': 'CAPITAL ONE',
        'AMEX': 'AMERICAN EXPRESS',
        'CITI': 'CITIBANK',
        'JPMCB': 'JPMORGAN CHASE',
        'CHASE': 'JPMORGAN CHASE',
        'SYNCB': 'SYNCHRONY',
        'BOA': 'BANK OF AMERICA',
        'BOFA': 'BANK OF AMERICA',
        'WELLS': 'WELLS FARGO',
        'WF': 'WELLS FARGO',
        'DISCOVER FIN': 'DISCOVER',
        'DISCOVERBANK': 'DISCOVER',
    }
    
    for abbr, full in abbreviations.items():
        if name == abbr or name.startswith(abbr + ' '):
            name = name.replace(abbr, full, 1)
            break
    
    return name


def resolve_canonical_accounts(accounts):
    """
    Merge accounts across sections into canonical entities.
    Same creditor appearing in multiple sections = one account with merged attributes.
    
    PRESERVES all original account fields via deep merge.
    Returns list of canonical accounts with all attributes merged.
    """
    if not accounts:
        return []
    
    # Group by canonical creditor name + account number (if available)
    canonical_map = {}
    
    for account in accounts:
        name = account.get('account_name', '')
        canonical_name = canonicalize_creditor_name(name)
        
        # Use fallback ID for accounts without recognizable names (don't drop them)
        if not canonical_name or canonical_name == 'NOT PROVIDED':
            # Generate fallback key from available data
            account_num = str(account.get('account_number', '')).strip()
            balance = str(account.get('balance', '')).strip()
            if account_num:
                canonical_name = f"UNKNOWN_{account_num[-6:]}"
            elif balance:
                canonical_name = f"UNKNOWN_BAL_{balance}"
            else:
                # Skip truly empty accounts
                continue
        
        # Build canonical key using stable identifiers
        # Key insight: opened_date + creditor + bureau uniquely identifies a tradeline
        # Different accounts from same creditor have different opened dates
        bureau = account.get('bureau', '') or ''
        
        # Extract all available identifiers (normalized)
        raw_account_num = str(account.get('account_number', '')).strip()
        account_num = raw_account_num if raw_account_num and raw_account_num != 'Not Provided' else ''
        opened_date = str(account.get('opened_date', '')).strip()
        opened_date = opened_date if opened_date and opened_date != 'Not Provided' else ''
        
        # Build composite key - prioritize stable identifiers
        if account_num:
            # Account number is definitive
            canonical_key = f"{canonical_name}|{account_num}|{bureau}"
        elif opened_date:
            # Opened date + creditor is unique per tradeline
            canonical_key = f"{canonical_name}|{opened_date}|{bureau}"
        else:
            # No stable identifiers - don't merge, keep separate
            # Use a unique key per account entry to preserve all data
            unique_id = f"{canonical_name}_{id(account)}_{bureau}"
            canonical_key = unique_id
        
        if canonical_key not in canonical_map:
            # Copy ALL fields from original account (preserve everything)
            canonical_account = account.copy()
            canonical_account['canonical_name'] = canonical_name
            canonical_account['negative_attributes'] = []
            canonical_account['_source_sections'] = 1
            canonical_map[canonical_key] = canonical_account
        else:
            # Deep merge - prefer non-empty values for ALL keys
            existing = canonical_map[canonical_key]
            existing['_source_sections'] += 1
            
            for key, value in account.items():
                if key in ('canonical_name', 'negative_attributes', '_source_sections'):
                    continue
                # Prefer non-empty, non-placeholder values
                existing_val = existing.get(key)
                if (not existing_val or existing_val == 'Not Provided' or existing_val == ''):
                    if value and value != 'Not Provided' and value != '':
                        existing[key] = value
    
    return list(canonical_map.values())


def resolve_canonical_inquiries(inquiries):
    """
    Deduplicate inquiries by creditor + date + type.
    Same creditor on same date = one inquiry.
    
    PRESERVES all original inquiry fields via deep merge.
    """
    if not inquiries:
        return []
    
    canonical_map = {}
    
    for inquiry in inquiries:
        raw_text = inquiry.get('raw_text', '')
        date = inquiry.get('date', 'Unknown')
        inq_type = inquiry.get('type', 'Unknown')
        
        # Extract creditor name from raw text
        creditor = extract_creditor_from_inquiry(raw_text)
        canonical_creditor = canonicalize_creditor_name(creditor) if creditor else raw_text[:30].upper()
        
        # Normalize date format
        normalized_date = normalize_date(date)
        
        # Include bureau to keep bureau-specific inquiries separate
        bureau = inquiry.get('bureau', '') or ''
        
        # Canonical key: creditor + date + type + bureau
        canonical_key = f"{canonical_creditor}|{normalized_date}|{inq_type.lower()}|{bureau}"
        
        if canonical_key not in canonical_map:
            # Copy ALL fields from original inquiry (preserve everything)
            canonical_inquiry = inquiry.copy()
            # Add canonical metadata under NEW keys only - don't overwrite original fields
            canonical_inquiry['_canonical_creditor'] = canonical_creditor
            canonical_inquiry['_extracted_creditor'] = creditor
            canonical_inquiry['_source_count'] = 1
            canonical_map[canonical_key] = canonical_inquiry
        else:
            # Deep merge - prefer non-empty values
            existing = canonical_map[canonical_key]
            existing['_source_count'] += 1
            
            for key, value in inquiry.items():
                if key in ('_canonical_creditor', '_extracted_creditor', '_source_count'):
                    continue
                existing_val = existing.get(key)
                if (not existing_val or existing_val == 'Not Provided' or existing_val == 'Unknown'):
                    if value and value != 'Not Provided' and value != 'Unknown':
                        existing[key] = value
    
    return list(canonical_map.values())


def extract_creditor_from_inquiry(raw_text):
    """Extract creditor name from inquiry raw text"""
    if not raw_text:
        return None
    
    # Common patterns: "Date Creditor Type" or "Creditor Date"
    # Remove date patterns first
    text = re.sub(r'\d{1,2}/\d{1,2}/\d{2,4}', '', raw_text)
    text = re.sub(r'(Hard|Soft)\s*Inquiry', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Inquiry|Credit\s*Check', '', text, flags=re.IGNORECASE)
    text = text.strip()
    
    if text and len(text) > 2:
        return text
    return None


def normalize_date(date_str):
    """Normalize date to consistent format for comparison"""
    if not date_str or date_str == 'Unknown':
        return 'unknown'
    
    # Try to extract MM/DD/YYYY or similar
    match = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})', str(date_str))
    if match:
        month, day, year = match.groups()
        if len(year) == 2:
            year = '20' + year if int(year) < 50 else '19' + year
        return f"{int(month):02d}/{int(day):02d}/{year}"
    
    return date_str.strip().lower()


def link_negative_items_to_accounts(negative_items, canonical_accounts):
    """
    Link negative items as attributes to their corresponding canonical accounts.
    Returns: (updated_accounts, unlinked_negative_items)
    
    Negative items that can be matched to an account become attributes.
    Only truly orphan negative items (public records, etc.) remain standalone.
    """
    if not negative_items:
        return canonical_accounts, []
    
    unlinked = []
    
    for item in negative_items:
        context = item.get('context', '') or ''
        keyword = item.get('keyword', '')
        
        # Try to find matching account
        matched = False
        for account in canonical_accounts:
            account_name = account.get('account_name', '')
            canonical_name = account.get('canonical_name', '')
            
            # Check if negative item context mentions this account
            if account_name and len(account_name) > 3:
                if account_name.lower() in context.lower():
                    account['negative_attributes'].append({
                        'type': keyword,
                        'date': item.get('date'),
                        'amount': item.get('amount'),
                        'context': context[:200]
                    })
                    matched = True
                    break
            
            if canonical_name and len(canonical_name) > 3:
                if canonical_name.lower() in context.lower():
                    account['negative_attributes'].append({
                        'type': keyword,
                        'date': item.get('date'),
                        'amount': item.get('amount'),
                        'context': context[:200]
                    })
                    matched = True
                    break
        
        if not matched:
            # Keep as standalone only if it's a public record type
            public_record_keywords = ['bankruptcy', 'judgment', 'tax lien', 'foreclosure']
            if any(kw in keyword.lower() for kw in public_record_keywords):
                unlinked.append(item)
    
    return canonical_accounts, unlinked


def count_canonical_accounts(accounts):
    """
    Count unique canonical accounts for summary metrics only.
    Uses conservative matching to avoid over-counting.
    Does NOT modify the account list.
    """
    if not accounts:
        return 0
    
    seen_keys = set()
    for account in accounts:
        name = account.get('account_name', '')
        canonical_name = canonicalize_creditor_name(name)
        if not canonical_name:
            canonical_name = 'UNKNOWN'
        
        bureau = account.get('bureau', '') or ''
        account_num = str(account.get('account_number', '')).strip()
        account_num = account_num if account_num and account_num != 'Not Provided' else ''
        opened_date = str(account.get('opened_date', '')).strip()
        opened_date = opened_date if opened_date and opened_date != 'Not Provided' else ''
        
        # Build deterministic key for counting
        if account_num:
            key = f"{canonical_name}|{account_num}|{bureau}"
        elif opened_date:
            key = f"{canonical_name}|{opened_date}|{bureau}"
        else:
            # Use content hash for deterministic deduplication
            # Same content = same hash = counts as one
            balance = str(account.get('balance', '')).strip()
            status = str(account.get('status', '')).strip()[:20]
            content_str = f"{canonical_name}|{balance}|{status}|{bureau}"
            content_hash = hashlib.md5(content_str.encode()).hexdigest()[:12]
            key = f"hash_{content_hash}"
        
        seen_keys.add(key)
    
    return len(seen_keys)


def count_canonical_inquiries(inquiries):
    """
    Count unique canonical inquiries for summary metrics only.
    Does NOT modify the inquiry list.
    """
    if not inquiries:
        return 0
    
    seen_keys = set()
    for inquiry in inquiries:
        raw_text = inquiry.get('raw_text', '')
        date = inquiry.get('date', 'Unknown')
        inq_type = inquiry.get('type', 'Unknown')
        bureau = inquiry.get('bureau', '') or ''
        
        creditor = extract_creditor_from_inquiry(raw_text)
        canonical_creditor = canonicalize_creditor_name(creditor) if creditor else raw_text[:30].upper()
        normalized_date = normalize_date(date)
        
        key = f"{canonical_creditor}|{normalized_date}|{inq_type.lower()}|{bureau}"
        seen_keys.add(key)
    
    return len(seen_keys)


def extract_stable_tokens_from_raw_section(raw_section):
    """
    Extract stable tokens from raw_section for Experian fingerprinting.
    
    Looks for:
    - Account number (full or last 4 digits)
    - Date patterns that might be opened date
    - Credit limit/high credit amounts
    - Bureau reference IDs
    
    Returns dict of extracted stable tokens (empty if none found).
    """
    tokens = {}
    
    if not raw_section:
        return tokens
    
    text = str(raw_section)
    
    # Account number patterns - from most specific to least
    account_patterns = [
        # Full account number (compact)
        r'(?:Account|Acct)\s*(?:Number|#|No\.?)?[:\s]+(\d{6,16})',
        # Account with spaces/hyphens (capture and normalize)
        r'(?:Account|Acct)\s*(?:Number|#|No\.?)?[:\s]+([\d][\d\s\-]{5,20}[\d])',
        # Last 4 with masking (xxxx1234, ****1234, ...1234)
        r'(?:Account|Acct)[#:\s]*(?:x{4,}|\.{4,}|\*{4,})(\d{4})',
        r'#\s*(?:x{4,}|\.{4,}|\*{4,})(\d{4})',
        # Ending in pattern
        r'(?:ending in|last 4)[:\s]*(\d{4})',
        # Bureau reference/subscriber ID (numeric or alphanumeric)
        r'(?:Reference|Subscriber|ECO|ID)[:\s#]*([\dA-Z]{6,12})',
        # Alphanumeric account identifier
        r'(?:Account|Acct)\s*(?:Number|#|No\.?)?[:\s]+([A-Z0-9]{8,16})',
        # Standalone digit sequence (8+ digits) - unlabeled account numbers
        r'\b(\d{8,16})\b',
    ]
    for pattern in account_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Normalize: remove spaces and hyphens
            account_id = re.sub(r'[\s\-]', '', match.group(1))
            if len(account_id) >= 4:
                tokens['account_id'] = account_id
            break
    
    # Opened date patterns - specific labels
    opened_patterns = [
        r'(?:Date Opened|Opened|Open Date|Date of Account)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(?:Date Opened|Opened|Open Date|Date of Account)[:\s]+(\w{3,9}\s+\d{1,2},?\s+\d{2,4})',
        r'(?:Date Opened|Opened|Open Date|Date of Account)[:\s]+(\w{3}\s+\d{4})',
    ]
    for pattern in opened_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            tokens['opened'] = match.group(1)
            break
    
    # High credit/credit limit patterns
    credit_patterns = [
        r'(?:High Credit|Credit Limit|Highest Balance|Original Amount)[:\s]+\$?([\d,\.]+)',
    ]
    for pattern in credit_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(1).replace(',', '').split('.')[0]
            try:
                if val and int(val) > 0:
                    tokens['high_credit'] = val
            except ValueError:
                pass
            break
    
    # Original creditor patterns (for collections/charge-offs)
    orig_patterns = [
        r'(?:Original Creditor|Sold To|Transferred To)[:\s]+([A-Za-z][A-Za-z0-9\s&\-]{2,30})',
    ]
    for pattern in orig_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            tokens['original'] = match.group(1).strip().upper()[:20]
            break
    
    return tokens


def build_canonical_account_key(account):
    """
    Build deterministic canonical key for account deduplication.
    
    Four-tier hierarchy:
    1. acct - validated account number (definitive)
    2. date - interpretable opened date (definitive)
    3. triad - ALL THREE secondary identifiers present (high confidence)
    4. experian_fp - fingerprint from raw_section tokens (for Experian section duplicates)
    5. isolated - insufficient identifiers (keep separate, flag for review)
    
    EXCLUDES section-variant fields: balance, status, payment_status, remarks
    
    Returns: (key, confidence_level)
    """
    name = account.get('account_name', '')
    canonical_name = canonicalize_creditor_name(name)
    if not canonical_name:
        canonical_name = 'UNKNOWN'
    
    bureau = account.get('bureau', '') or ''
    
    # Helper to clean and validate field values
    def clean_field(value):
        v = str(value).strip() if value else ''
        return v if v and v != 'Not Provided' and v != 'Unknown' else ''
    
    # Extract stable fields only (cross-section stable)
    account_number = clean_field(account.get('account_number'))
    opened_date = clean_field(account.get('opened_date')) or clean_field(account.get('date_opened'))
    high_credit = clean_field(account.get('high_credit')) or clean_field(account.get('credit_limit'))
    account_type = clean_field(account.get('account_type'))[:20]
    original_creditor = clean_field(account.get('original_creditor'))

    is_masked = len(account_number) <= 6 if account_number else False

    # Priority 1: Full (unmasked) account number is definitive
    if account_number and not is_masked:
        return f"acct|{canonical_name}|{account_number}|{bureau}", 'definitive'

    # Priority 1b: Masked account number needs additional differentiators
    # Student loan servicers often have multiple loans with the same last-4 digits
    if account_number and is_masked:
        extras = []
        if opened_date:
            extras.append(opened_date)
        if high_credit:
            extras.append(high_credit)
        extra_str = '|'.join(extras) if extras else ''
        return f"acct|{canonical_name}|{account_number}|{extra_str}|{bureau}", 'definitive'

    # Priority 2: Opened date uniquely identifies a tradeline
    if opened_date:
        return f"date|{canonical_name}|{opened_date}|{bureau}", 'definitive'
    
    # Priority 3: All THREE secondary identifiers (triad - high confidence)
    if high_credit and account_type and original_creditor:
        return f"triad|{canonical_name}|{high_credit}|{account_type}|{original_creditor}|{bureau}", 'triad'
    
    # Priority 4: Experian fingerprint from raw_section
    # Extract stable tokens that appear across sections but differ between accounts
    raw_section = account.get('raw_section', '')
    stable_tokens = extract_stable_tokens_from_raw_section(raw_section)
    
    # If we found stable tokens, use them for fingerprinting
    if stable_tokens:
        # Combine extracted tokens with available secondary identifiers
        fp_data = {'canonical_name': canonical_name, 'bureau': bureau}
        fp_data.update(stable_tokens)
        if high_credit:
            fp_data['high_credit'] = high_credit
        if account_type:
            fp_data['account_type'] = account_type
        if original_creditor:
            fp_data['original_creditor'] = original_creditor
        
        fp_str = json.dumps(fp_data, sort_keys=True)
        fp_hash = hashlib.md5(fp_str.encode()).hexdigest()[:12]
        return f"experian_fp|{fp_hash}", 'experian_fp'
    
    # Priority 5: Insufficient identifiers
    # Use deterministic hash with genuinely stable fragments:
    # - Digit runs (account numbers, amounts - stable across sections)
    # - Canonical creditor name
    sparse_data = {'canonical_name': canonical_name, 'bureau': bureau}
    if high_credit:
        sparse_data['high_credit'] = high_credit
    if account_type:
        sparse_data['account_type'] = account_type
    if original_creditor:
        sparse_data['original_creditor'] = original_creditor
    
    # Extract digit runs as stable identifiers (account numbers, amounts)
    if raw_section:
        # Find all digit sequences of 4+ characters
        digit_runs = re.findall(r'\d{4,}', str(raw_section))
        if digit_runs:
            # Sort and deduplicate for determinism
            unique_digits = sorted(set(digit_runs))
            # Take up to 5 longest runs (most likely to be account numbers)
            unique_digits.sort(key=len, reverse=True)
            sparse_data['digits'] = '|'.join(unique_digits[:5])
    
    sparse_str = json.dumps(sparse_data, sort_keys=True)
    sparse_hash = hashlib.md5(sparse_str.encode()).hexdigest()[:12]
    return f"isolated|{sparse_hash}", 'isolated'


def build_canonical_account_key_wrapper(account):
    """Wrapper that returns only the key (for backward compatibility)"""
    key, _ = build_canonical_account_key(account)
    return key


def canonicalize_accounts(accounts):
    """
    Merge accounts across sections into canonical entities.
    Same account in different sections (e.g., Account Info, Negative Info) = one entity.
    
    Uses five-tier deterministic key hierarchy and preserves all fields via deep merge.
    Stores confidence level for downstream processing and UI display.
    """
    if not accounts:
        return []
    
    canonical_map = {}
    
    for account in accounts:
        key, confidence = build_canonical_account_key(account)
        
        if key not in canonical_map:
            # Copy all fields from original account
            canonical_account = account.copy()
            canonical_account['_canonical_key'] = key
            canonical_account['_canonical_confidence'] = confidence
            canonical_account['_source_count'] = 1
            if 'negative_attributes' not in canonical_account:
                canonical_account['negative_attributes'] = []
            canonical_map[key] = canonical_account
        else:
            # Merge attributes - prefer non-empty values
            existing = canonical_map[key]
            existing['_source_count'] += 1
            
            for field, value in account.items():
                if field in ('_canonical_key', '_canonical_confidence', '_source_count', 'negative_attributes'):
                    continue
                existing_val = existing.get(field)
                if not existing_val or existing_val == 'Not Provided':
                    if value and value != 'Not Provided':
                        existing[field] = value
    
    return list(canonical_map.values())


def canonicalize_inquiries(inquiries):
    """
    Merge inquiries by creditor + date + type + bureau.
    Same inquiry in different sections = one entity.
    """
    if not inquiries:
        return []
    
    canonical_map = {}
    
    for inquiry in inquiries:
        raw_text = inquiry.get('raw_text', '')
        date = inquiry.get('date', 'Unknown')
        inq_type = inquiry.get('type', 'Unknown')
        bureau = inquiry.get('bureau', '') or ''
        
        creditor = extract_creditor_from_inquiry(raw_text)
        canonical_creditor = canonicalize_creditor_name(creditor) if creditor else raw_text[:30].upper()
        normalized_date = normalize_date(date)
        
        key = f"{canonical_creditor}|{normalized_date}|{inq_type.lower()}|{bureau}"
        
        if key not in canonical_map:
            canonical_inquiry = inquiry.copy()
            canonical_inquiry['_canonical_key'] = key
            canonical_inquiry['_source_count'] = 1
            canonical_map[key] = canonical_inquiry
        else:
            existing = canonical_map[key]
            existing['_source_count'] += 1
            # Merge any missing fields
            for field, value in inquiry.items():
                if field in ('_canonical_key', '_source_count'):
                    continue
                existing_val = existing.get(field)
                if not existing_val or existing_val == 'Not Provided' or existing_val == 'Unknown':
                    if value and value != 'Not Provided' and value != 'Unknown':
                        existing[field] = value
    
    return list(canonical_map.values())


def normalize_parsed_data(parsed_data, source_type='unknown'):
    """
    Normalize parsed credit report data before violation detection.
    
    Pipeline:
    1. Basic field normalization (clean placeholders, remove repeated tokens)
    2. Canonical entity resolution (merge duplicates across sections)
    3. Link negative items to canonical accounts
    4. Calculate summary stats from canonical entity counts
    
    Args:
        parsed_data: Raw parsed data from PDF extraction
        source_type: 'disclosure', 'monitoring', or 'ocr' to determine confidence
    """
    normalized = parsed_data.copy()
    
    # Step 1: Basic field normalization
    if 'accounts' in normalized:
        normalized['accounts'] = normalize_accounts(normalized['accounts'])
    
    if 'inquiries' in normalized:
        normalized['inquiries'] = normalize_inquiries(normalized['inquiries'])
    
    if 'negative_items' in normalized:
        normalized['negative_items'] = normalize_negative_items(normalized['negative_items'])
    
    if 'personal_info' in normalized:
        normalized['personal_info'] = normalize_personal_info(normalized['personal_info'])
    
    # Step 2: Canonical entity resolution
    if 'accounts' in normalized:
        normalized['accounts'] = canonicalize_accounts(normalized['accounts'])
    
    if 'inquiries' in normalized:
        normalized['inquiries'] = canonicalize_inquiries(normalized['inquiries'])
    
    # Step 3: Link negative items to canonical accounts (adds metadata only)
    # IMPORTANT: Keep original negative_items list intact for violation detection
    if 'negative_items' in normalized and 'accounts' in normalized:
        # Link negatives to accounts as additional metadata
        link_negative_items_to_accounts(
            normalized['negative_items'],
            normalized['accounts']
        )
        # DO NOT modify negative_items - violation engine depends on it
    
    # Count accounts with linked negative attributes (for display)
    accounts_with_negatives = sum(
        1 for acc in normalized.get('accounts', [])
        if acc.get('negative_attributes')
    )
    
    # Total linked negative attributes across all accounts
    total_linked_negatives = sum(
        len(acc.get('negative_attributes', []))
        for acc in normalized.get('accounts', [])
    )
    
    normalized['confidence_level'] = determine_confidence_level(normalized, source_type)
    
    # Step 4: Summary stats from CANONICAL entities
    # Accounts and inquiries are now canonical (merged across sections)
    normalized['summary_stats'] = {
        'total_accounts_found': len(normalized.get('accounts', [])),
        'total_inquiries_found': len(normalized.get('inquiries', [])),
        'total_negative_items_found': len(normalized.get('negative_items', [])),
        'total_public_records_found': len(normalized.get('public_records', [])),
        'personal_info_fields': len([v for v in normalized.get('personal_info', {}).values() if v and v != 'Not Provided']),
        'accounts_with_negative_info': accounts_with_negatives,
        'linked_negative_attributes': total_linked_negatives
    }
    
    return normalized


def determine_confidence_level(parsed_data, source_type='unknown'):
    """
    Determine confidence level based on source type and data quality.
    
    Returns:
        'HIGH' - Bureau disclosure (direct from bureau, complete data)
        'MEDIUM' - Credit monitoring export (third-party aggregator)
        'LOW' - Scanned/OCR-based report (may have extraction errors)
    """
    if source_type == 'disclosure':
        return 'HIGH'
    elif source_type == 'monitoring':
        return 'MEDIUM'
    elif source_type == 'ocr':
        return 'LOW'
    
    accounts = parsed_data.get('accounts', [])
    personal_info = parsed_data.get('personal_info', {})
    
    has_complete_accounts = len(accounts) > 0 and all(
        acc.get('account_name') and acc.get('account_name') != 'Not Provided'
        for acc in accounts[:5]
    )
    has_complete_personal = bool(personal_info.get('name')) and bool(personal_info.get('address'))
    
    incomplete_count = sum(1 for acc in accounts if 
        acc.get('balance', 'Not Provided') == 'Not Provided' or
        acc.get('status', 'Not Provided') == 'Not Provided'
    )
    
    if has_complete_accounts and has_complete_personal and incomplete_count < len(accounts) * 0.2:
        return 'HIGH'
    elif has_complete_accounts or has_complete_personal:
        return 'MEDIUM'
    else:
        return 'LOW'

def remove_repeated_tokens(text):
    """Remove repeated consecutive tokens like 'Closed Closed Closed'"""
    if not text or not isinstance(text, str):
        return text
    
    words = text.split()
    if len(words) <= 1:
        return text
    
    cleaned = [words[0]]
    for word in words[1:]:
        if word.lower() != cleaned[-1].lower():
            cleaned.append(word)
    
    return ' '.join(cleaned)

def clean_placeholder_value(value):
    """Clean placeholder values and repeated patterns"""
    if not value or not isinstance(value, str):
        return value
    
    value = remove_repeated_tokens(value.strip())
    
    placeholder_patterns = [
        r'^(Individual\s*)+$',
        r'^(N/A\s*)+$',
        r'^(Unknown\s*)+$',
        r'^(None\s*)+$',
        r'^[\*\-\_]+$',
        r'^\s*$'
    ]
    
    for pattern in placeholder_patterns:
        if re.match(pattern, value, re.IGNORECASE):
            return None
    
    return value

def normalize_field(value, default=None):
    """Normalize a single field value"""
    if default is None:
        default = 'Not Provided'
    
    if value is None:
        return default
    
    if isinstance(value, str):
        cleaned = clean_placeholder_value(value)
        if not cleaned or cleaned.strip() == '':
            return default
        return cleaned
    
    return value

def normalize_accounts(accounts):
    """
    Normalize account fields only (no deduplication).
    Deduplication happens in canonicalize_accounts using stable identifiers.
    """
    if not accounts:
        return []
    
    normalized = []
    
    for account in accounts:
        normalized_account = {}
        
        for key, value in account.items():
            if key == 'raw_section':
                normalized_account[key] = value
            else:
                normalized_account[key] = normalize_field(value)
        
        name = normalized_account.get('account_name', '').lower().strip()
        
        # Only skip truly empty accounts
        if name and name != 'not provided' and len(name) > 2:
            normalized.append(normalized_account)
    
    return normalized

def normalize_inquiries(inquiries):
    """
    Normalize inquiry fields only (no deduplication).
    Deduplication happens in canonicalize_inquiries using stable identifiers.
    """
    if not inquiries:
        return []
    
    normalized = []
    
    for inquiry in inquiries:
        normalized_inquiry = {}
        
        for key, value in inquiry.items():
            normalized_inquiry[key] = normalize_field(value)
        
        raw = normalized_inquiry.get('raw_text', '').lower().strip()[:50]
        
        # Only skip truly empty inquiries
        if raw and raw != 'not provided':
            normalized.append(normalized_inquiry)
    
    return normalized

def normalize_negative_items(items):
    """Normalize negative items list"""
    if not items:
        return []
    
    normalized = []
    seen_contexts = set()
    
    for item in items:
        normalized_item = {}
        
        for key, value in item.items():
            if key == 'context':
                normalized_item[key] = value
            else:
                normalized_item[key] = normalize_field(value)
        
        context_key = item.get('context', '')[:100].lower().strip()
        
        if context_key in seen_contexts:
            continue
        
        if context_key:
            seen_contexts.add(context_key)
            normalized.append(normalized_item)
    
    return normalized

def normalize_personal_info(info):
    """Normalize personal info dictionary"""
    if not info:
        return {}
    
    normalized = {}
    
    for key, value in info.items():
        normalized[key] = normalize_field(value, default=None)
        if normalized[key] is None:
            del normalized[key]
    
    return normalized
