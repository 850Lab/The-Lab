"""
========================================================================
PHASE 1 REGRESSION TEST — TRANSUNION
========================================================================
This test validates TransUnion extraction against the frozen baseline.
If ANY value differs, output a diff and STOP execution.

Baseline: artifacts/tu_phase1_baseline.json
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pdfplumber
import re

def load_extraction_functions():
    with open('app.py', 'r') as f:
        app_code = f.read()
    
    exec_globals = {'re': re, 'pdfplumber': pdfplumber, '__builtins__': __builtins__}
    code_start = app_code.find('BUREAU_PATTERNS = {')
    code_end = app_code.find("if 'uploaded_reports'")
    exec(app_code[code_start:code_end], exec_globals)
    
    return exec_globals

def run_tu_extraction(pdf_path, funcs):
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + f"\nPage {page.page_number} of {len(pdf.pages)}\n"
    
    bureau = funcs['detect_bureau'](full_text)
    accounts, _ = funcs['parse_accounts'](full_text, bureau)
    inquiries, _ = funcs['parse_inquiries'](full_text, bureau)
    negatives, _ = funcs['parse_negative_items'](full_text, bureau=bureau, accounts=accounts)
    
    return {
        'bureau': bureau,
        'accounts': accounts,
        'inquiries': inquiries,
        'negatives': negatives
    }

def compare_to_baseline(extracted, baseline):
    diffs = []
    
    if extracted['bureau'] != baseline['bureau']:
        diffs.append(f"Bureau: expected '{baseline['bureau']}', got '{extracted['bureau']}'")
    
    if len(extracted['accounts']) != baseline['extracted']['accounts']:
        diffs.append(f"Accounts count: expected {baseline['extracted']['accounts']}, got {len(extracted['accounts'])}")
    
    if len(extracted['inquiries']) != baseline['extracted']['hard_inquiries']:
        diffs.append(f"Hard inquiries count: expected {baseline['extracted']['hard_inquiries']}, got {len(extracted['inquiries'])}")
    
    if len(extracted['negatives']) != baseline['extracted']['negatives']:
        diffs.append(f"Negatives count: expected {baseline['extracted']['negatives']}, got {len(extracted['negatives'])}")
    
    extracted_acct_nums = sorted(list(set(a.get('account_number', '') for a in extracted['accounts'])))
    if extracted_acct_nums != baseline['account_numbers']:
        diffs.append(f"Account numbers differ:\n  Expected: {baseline['account_numbers']}\n  Got: {extracted_acct_nums}")
    
    extracted_neg_keys = sorted([n.get('dedup_key', '') for n in extracted['negatives']])
    if extracted_neg_keys != baseline['negative_dedup_keys']:
        diffs.append(f"Negative dedup keys differ:\n  Expected: {baseline['negative_dedup_keys']}\n  Got: {extracted_neg_keys}")
    
    return diffs

def test_transunion_regression():
    pdf_path = "attached_assets/View_Your_Report_|_TransUnion_Credit_Report_1769539038890.pdf"
    baseline_path = "artifacts/tu_phase1_baseline.json"
    
    if not os.path.exists(pdf_path):
        print(f"SKIP: Test PDF not found at {pdf_path}")
        return True
    
    if not os.path.exists(baseline_path):
        print(f"FAIL: Baseline not found at {baseline_path}")
        return False
    
    with open(baseline_path, 'r') as f:
        baseline = json.load(f)
    
    funcs = load_extraction_functions()
    extracted = run_tu_extraction(pdf_path, funcs)
    
    diffs = compare_to_baseline(extracted, baseline)
    
    if diffs:
        print("=" * 60)
        print("REGRESSION DETECTED - EXTRACTION DIFFERS FROM BASELINE")
        print("=" * 60)
        for diff in diffs:
            print(f"\n  - {diff}")
        print("\n" + "=" * 60)
        print("STOP: Fix the regression before proceeding.")
        return False
    else:
        print("=" * 60)
        print("TRANSUNION PHASE 1 REGRESSION TEST PASSED")
        print("=" * 60)
        print(f"  Accounts: {len(extracted['accounts'])} (baseline: {baseline['extracted']['accounts']})")
        print(f"  Hard Inquiries: {len(extracted['inquiries'])} (baseline: {baseline['extracted']['hard_inquiries']})")
        print(f"  Negatives: {len(extracted['negatives'])} (baseline: {baseline['extracted']['negatives']})")
        print(f"  Unique Account Numbers: {len(baseline['account_numbers'])}")
        return True

if __name__ == '__main__':
    success = test_transunion_regression()
    sys.exit(0 if success else 1)
