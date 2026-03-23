"""
audit_counts.py | 850 Lab Parser Machine
Standalone audit script to diagnose count inflation issues.
Run: python audit_counts.py path/to/report.pdf
"""

import sys
import re
import json
from io import BytesIO
from collections import defaultdict
from datetime import datetime

try:
    from normalization import (
        canonicalize_creditor_name,
        normalize_parsed_data,
        extract_creditor_from_inquiry
    )
except ImportError:
    def canonicalize_creditor_name(name):
        if not name:
            return ''
        return name.upper().strip()[:30]
    
    def normalize_parsed_data(parsed_data, source_type='unknown'):
        return parsed_data
    
    def extract_creditor_from_inquiry(raw_text):
        return raw_text[:50] if raw_text else None


BUREAU_PATTERNS = {
    'equifax': {
        'identifiers': ['equifax', 'equifax information services', 'EFX'],
        'account_pattern': r'(?:Account\s*(?:Name|Number)?[:\s]+)(.+?)(?:\n|Account Status)',
        'balance_pattern': r'(?:Balance|Current Balance)[:\s]+\$?([\d,]+\.?\d*)',
        'status_pattern': r'(?:Account Status|Status)[:\s]+(\w+)',
        'opened_pattern': r'(?:Date Opened|Opened)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
        'high_credit_pattern': r'(?:High Credit|Credit Limit)[:\s]+\$?([\d,]+)',
    },
    'experian': {
        'identifiers': ['experian', 'experian information solutions'],
        'account_pattern': r'(?:Creditor Name|Account)[:\s]+(.+?)(?:\n|Status)',
        'balance_pattern': r'(?:Balance Owed|Balance)[:\s]+\$?([\d,]+\.?\d*)',
        'status_pattern': r'(?:Status|Account Status)[:\s]+(\w+)',
        'opened_pattern': r'(?:Open Date|Date Opened)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
        'high_credit_pattern': r'(?:Highest Balance|Credit Limit)[:\s]+\$?([\d,]+)',
    },
    'transunion': {
        'identifiers': ['transunion', 'trans union'],
        'account_pattern': r'(?:Subscriber Name|Creditor)[:\s]+(.+?)(?:\n|Account)',
        'balance_pattern': r'(?:Current Balance|Balance)[:\s]+\$?([\d,]+\.?\d*)',
        'status_pattern': r'(?:Pay Status|Account Status)[:\s]+(\w+)',
        'opened_pattern': r'(?:Date Opened|Opened)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
        'high_credit_pattern': r'(?:High Balance|Credit Limit)[:\s]+\$?([\d,]+)',
    }
}


def detect_bureau(text):
    text_lower = text.lower()
    for bureau, patterns in BUREAU_PATTERNS.items():
        for identifier in patterns['identifiers']:
            if identifier.lower() in text_lower:
                return bureau
    return 'unknown'


def extract_text_from_pdf_file(pdf_path):
    """Extract text from PDF file path"""
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    import pdfplumber
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        full_text = ""
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                full_text += f"\n--- Page {i + 1} ---\n{page_text}\n"
    return full_text


def parse_accounts(text, bureau):
    accounts = []
    patterns = BUREAU_PATTERNS.get(bureau, BUREAU_PATTERNS['equifax'])
    account_sections = re.split(r'\n(?=(?:Account|Creditor|Subscriber))', text, flags=re.IGNORECASE)
    
    for section in account_sections:
        if len(section) < 50:
            continue
        account = {}
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
        
        if account.get('account_name') or account.get('balance'):
            account['raw_section'] = section[:300]
            account['bureau'] = bureau
            accounts.append(account)
    return accounts


def parse_inquiries(text, bureau):
    inquiries = []
    inquiry_patterns = [
        r'(?:Inquiry|Inquiries?)\s*[:\-]?\s*(.+?)(?=\n\n|\Z)',
        r'(\d{1,2}/\d{1,2}/\d{2,4})\s+(.+?)\s+(?:Inquiry|Credit Check)',
        r'(?:Date|On)\s*(\d{1,2}/\d{1,2}/\d{2,4})\s+(.+?)(?:\n|$)'
    ]
    
    for pattern in inquiry_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
        for match in matches:
            inquiry_text = match.group(0).strip()
            if len(inquiry_text) > 10 and len(inquiry_text) < 300:
                date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', inquiry_text)
                inquiry = {
                    'raw_text': inquiry_text,
                    'date': date_match.group(1) if date_match else 'Unknown',
                    'type': 'Hard Inquiry' if 'hard' in inquiry_text.lower() else 'Inquiry',
                    'bureau': bureau
                }
                if inquiry not in inquiries:
                    inquiries.append(inquiry)
    return inquiries


def parse_negative_items(text):
    negative_items = []
    negative_keywords = [
        'late payment', 'collection', 'charge off', 'charged off',
        'bankruptcy', 'foreclosure', 'repossession', 'judgment',
        'tax lien', 'delinquent', 'past due', '30 days late',
        '60 days late', '90 days late', '120 days late', 'written off'
    ]
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for keyword in negative_keywords:
            if keyword in line_lower:
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 3)
                context = '\n'.join(lines[context_start:context_end])
                date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', context)
                amount_match = re.search(r'\$?([\d,]+\.?\d*)', context)
                negative_item = {
                    'type': keyword.title(),
                    'context': context[:300],
                    'date': date_match.group(1) if date_match else 'Unknown',
                    'amount': amount_match.group(1) if amount_match else 'Unknown'
                }
                if not any(ni['context'] == negative_item['context'] for ni in negative_items):
                    negative_items.append(negative_item)
                break
    return negative_items


def parse_credit_report_data(text, bureau='unknown'):
    return {
        'bureau': bureau,
        'accounts': parse_accounts(text, bureau),
        'inquiries': parse_inquiries(text, bureau),
        'negative_items': parse_negative_items(text),
    }


def build_account_dedupe_key(account):
    """Build deterministic key for account deduplication"""
    name = canonicalize_creditor_name(account.get('account_name', ''))
    
    last4 = ''
    account_num = account.get('account_number', '') or ''
    if account_num:
        last4 = account_num[-4:] if len(account_num) >= 4 else account_num
    
    opened = account.get('date_opened', '') or ''
    acct_type = account.get('account_type', '') or ''
    
    if name and (last4 or opened):
        return f"{name}|{last4}|{opened}|{acct_type}"
    
    balance = account.get('balance', '') or ''
    status = account.get('status', '') or ''
    return f"{name}|{balance}|{status}|FALLBACK"


def build_inquiry_dedupe_key(inquiry):
    """Build deterministic key for inquiry deduplication"""
    raw_text = inquiry.get('raw_text', '')
    creditor = extract_creditor_from_inquiry(raw_text) if raw_text else ''
    creditor_norm = canonicalize_creditor_name(creditor) if creditor else raw_text[:30].upper()
    
    date = inquiry.get('date', 'Unknown')
    bureau = inquiry.get('bureau', '')
    
    return f"{creditor_norm}|{date}|{bureau}"


def classify_inquiry_type(inquiry):
    """Classify inquiry as HARD, SOFT, or UNKNOWN"""
    raw_text = (inquiry.get('raw_text', '') or '').lower()
    inq_type = (inquiry.get('type', '') or '').lower()
    
    hard_indicators = ['hard inquiry', 'hard pull', 'credit application']
    soft_indicators = ['soft', 'account review', 'promotional', 'preapproved', 
                       'pre-approved', 'consumer disclosure', 'account monitoring']
    
    if 'hard' in inq_type or any(h in raw_text for h in hard_indicators):
        return 'HARD'
    if any(s in raw_text for s in soft_indicators):
        return 'SOFT'
    return 'UNKNOWN'


def dedupe_items(items, key_builder):
    """Deduplicate items using provided key builder function"""
    seen = {}
    deduped = []
    duplicates = defaultdict(list)
    
    for item in items:
        key = key_builder(item)
        if key in seen:
            duplicates[key].append(item)
        else:
            seen[key] = item
            deduped.append(item)
            duplicates[key].append(item)
    
    return deduped, duplicates


def run_audit(pdf_path):
    """Run full audit on a PDF file"""
    print(f"\n{'='*60}")
    print(f"AUDIT REPORT: {pdf_path}")
    print(f"{'='*60}\n")
    
    print("Extracting text from PDF...")
    text = extract_text_from_pdf_file(pdf_path)
    bureau = detect_bureau(text)
    print(f"Detected bureau: {bureau}")
    print(f"Total text length: {len(text):,} characters\n")
    
    print("Parsing raw data...")
    raw_parsed = parse_credit_report_data(text, bureau)
    
    raw_counts = {
        'accounts': len(raw_parsed['accounts']),
        'inquiries': len(raw_parsed['inquiries']),
        'negative_items': len(raw_parsed['negative_items']),
    }
    
    print("Normalizing data...")
    try:
        normalized = normalize_parsed_data(raw_parsed)
    except Exception as e:
        print(f"Normalization error: {e}")
        normalized = raw_parsed
    
    normalized_counts = {
        'accounts': len(normalized.get('accounts', [])),
        'inquiries': len(normalized.get('inquiries', [])),
        'negative_items': len(normalized.get('negative_items', [])),
    }
    
    print("Deduplicating...\n")
    deduped_accounts, account_dups = dedupe_items(raw_parsed['accounts'], build_account_dedupe_key)
    deduped_inquiries, inquiry_dups = dedupe_items(raw_parsed['inquiries'], build_inquiry_dedupe_key)
    
    deduped_counts = {
        'accounts': len(deduped_accounts),
        'inquiries': len(deduped_inquiries),
        'negative_items': len(raw_parsed['negative_items']),
    }
    
    hard_count = sum(1 for inq in raw_parsed['inquiries'] if classify_inquiry_type(inq) == 'HARD')
    soft_count = sum(1 for inq in raw_parsed['inquiries'] if classify_inquiry_type(inq) == 'SOFT')
    unknown_count = sum(1 for inq in raw_parsed['inquiries'] if classify_inquiry_type(inq) == 'UNKNOWN')
    
    print("="*60)
    print("COUNT SUMMARY")
    print("="*60)
    print(f"{'Category':<20} {'Raw':>10} {'Normalized':>12} {'Deduped':>10}")
    print("-"*60)
    print(f"{'Accounts':<20} {raw_counts['accounts']:>10} {normalized_counts['accounts']:>12} {deduped_counts['accounts']:>10}")
    print(f"{'Inquiries':<20} {raw_counts['inquiries']:>10} {normalized_counts['inquiries']:>12} {deduped_counts['inquiries']:>10}")
    print(f"{'Negative Items':<20} {raw_counts['negative_items']:>10} {normalized_counts['negative_items']:>12} {deduped_counts['negative_items']:>10}")
    print()
    
    print("="*60)
    print("INQUIRY TYPE BREAKDOWN (from raw)")
    print("="*60)
    print(f"HARD:    {hard_count}")
    print(f"SOFT:    {soft_count}")
    print(f"UNKNOWN: {unknown_count}")
    print()
    
    account_dup_groups = [(k, v) for k, v in account_dups.items() if len(v) > 1]
    account_dup_groups.sort(key=lambda x: -len(x[1]))
    
    inquiry_dup_groups = [(k, v) for k, v in inquiry_dups.items() if len(v) > 1]
    inquiry_dup_groups.sort(key=lambda x: -len(x[1]))
    
    print("="*60)
    print(f"ACCOUNT DUPLICATES ({len(account_dup_groups)} groups)")
    print("="*60)
    for i, (key, items) in enumerate(account_dup_groups[:10]):
        print(f"\n[{i+1}] Key: {key}")
        print(f"    Count: {len(items)} duplicates")
        for j, item in enumerate(items[:3]):
            snippet = (item.get('raw_section', '') or '')[:100].replace('\n', ' ')
            print(f"    Sample {j+1}: {item.get('account_name', 'N/A')[:40]}")
            print(f"              Balance: {item.get('balance', 'N/A')}, Status: {item.get('status', 'N/A')}")
            print(f"              Snippet: {snippet}...")
    
    print("\n" + "="*60)
    print(f"INQUIRY DUPLICATES ({len(inquiry_dup_groups)} groups)")
    print("="*60)
    for i, (key, items) in enumerate(inquiry_dup_groups[:10]):
        print(f"\n[{i+1}] Key: {key}")
        print(f"    Count: {len(items)} duplicates")
        for j, item in enumerate(items[:3]):
            raw = (item.get('raw_text', '') or '')[:80].replace('\n', ' ')
            inq_type = classify_inquiry_type(item)
            print(f"    Sample {j+1}: {raw}...")
            print(f"              Date: {item.get('date', 'N/A')}, Type: {inq_type}")
    
    audit_output = {
        'timestamp': datetime.now().isoformat(),
        'pdf_path': pdf_path,
        'bureau': bureau,
        'counts': {
            'raw': raw_counts,
            'normalized': normalized_counts,
            'deduped': deduped_counts
        },
        'inquiry_breakdown': {
            'hard': hard_count,
            'soft': soft_count,
            'unknown': unknown_count
        },
        'duplicate_groups': {
            'accounts': [
                {'key': k, 'count': len(v), 'samples': [
                    {'name': it.get('account_name', ''), 'balance': it.get('balance', ''), 
                     'snippet': (it.get('raw_section', '') or '')[:100]}
                    for it in v[:3]
                ]}
                for k, v in account_dup_groups[:20]
            ],
            'inquiries': [
                {'key': k, 'count': len(v), 'samples': [
                    {'raw': (it.get('raw_text', '') or '')[:100], 'date': it.get('date', ''),
                     'type_classified': classify_inquiry_type(it)}
                    for it in v[:3]
                ]}
                for k, v in inquiry_dup_groups[:20]
            ]
        },
        'sample_accounts': [
            {'name': a.get('account_name', ''), 'balance': a.get('balance', ''),
             'status': a.get('status', ''), 'opened': a.get('date_opened', '')}
            for a in deduped_accounts[:10]
        ],
        'sample_inquiries': [
            {'raw': (i.get('raw_text', '') or '')[:100], 'date': i.get('date', ''),
             'type': classify_inquiry_type(i)}
            for i in deduped_inquiries[:10]
        ]
    }
    
    output_path = 'audit_output.json'
    with open(output_path, 'w') as f:
        json.dump(audit_output, f, indent=2)
    print(f"\n\nFull audit saved to: {output_path}")
    
    return audit_output


def run_audit_on_bytes(pdf_bytes, filename="uploaded"):
    """Run audit on PDF bytes (for integration with Streamlit)"""
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    
    try:
        result = run_audit(tmp_path)
        result['pdf_path'] = filename
        return result
    finally:
        os.unlink(tmp_path)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python audit_counts.py <path_to_pdf>")
        print("\nNo PDF provided. Looking for test files...")
        
        import glob
        pdfs = glob.glob('*.pdf') + glob.glob('attached_assets/*.pdf') + glob.glob('uploads/*.pdf')
        if pdfs:
            print(f"Found PDFs: {pdfs}")
            run_audit(pdfs[0])
        else:
            print("No PDF files found. Please provide a PDF path as argument.")
    else:
        run_audit(sys.argv[1])
