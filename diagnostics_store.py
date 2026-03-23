"""
Diagnostics Store - In-memory store for capturing upload/parsing diagnostics.

This module provides a singleton diagnostics store that captures:
- Last upload file info (bureau, file type, size, pages)
- Extraction results (accounts, inquiries, public records, negatives)
- Missing fields and errors
- Dedupe rules applied
"""

import os
import traceback
from datetime import datetime
from typing import Optional, Dict, List, Any

_diagnostics_store: Dict[str, Any] = {
    "last_upload": None,
    "last_extraction": None,
    "errors": [],
    "self_check_results": None,
    "raw_text_debug": {
        "enabled": False,
        "sample_excerpt": "",
    }
}


def reset_diagnostics():
    """Reset all diagnostics to initial state."""
    global _diagnostics_store
    _diagnostics_store = {
        "last_upload": None,
        "last_extraction": None,
        "errors": [],
        "self_check_results": None,
        "raw_text_debug": {
            "enabled": False,
            "sample_excerpt": "",
        }
    }


def record_upload(
    bureau_guess: str,
    file_type: str,
    file_size_bytes: int,
    page_count: int,
    file_name: str = ""
):
    """Record upload metadata."""
    global _diagnostics_store
    _diagnostics_store["last_upload"] = {
        "timestamp": datetime.now().isoformat(),
        "bureau_guess": bureau_guess,
        "file_type": file_type,
        "file_size_bytes": file_size_bytes,
        "pages": page_count,
        "file_name": file_name,
    }
    _diagnostics_store["errors"] = []


def record_extraction(
    accounts_found: int,
    inquiries_found: int,
    public_records_found: int,
    negative_items_found: int,
    personal_info_fields: List[str],
    missing_critical_fields: List[str],
    dedupe_rules: List[str],
    confidence_signals: List[str],
    reject_counters: Optional[Dict[str, int]] = None
):
    """Record extraction results."""
    global _diagnostics_store
    _diagnostics_store["last_extraction"] = {
        "timestamp": datetime.now().isoformat(),
        "accounts_found": accounts_found,
        "inquiries_found": inquiries_found,
        "public_records_found": public_records_found,
        "negative_items_found": negative_items_found,
        "personal_info_fields_found": personal_info_fields,
        "missing_critical_fields": missing_critical_fields,
        "dedupe_rules_in_use": dedupe_rules,
        "confidence_or_quality_signals": confidence_signals,
        "reject_counters": reject_counters or {},
    }


def record_error(where: str, message: str, exception: Optional[Exception] = None):
    """Record an error that occurred during processing."""
    global _diagnostics_store
    stack = ""
    if exception:
        stack = traceback.format_exc()
    
    _diagnostics_store["errors"].append({
        "timestamp": datetime.now().isoformat(),
        "where": where,
        "message": message,
        "stack": stack[:500] if stack else "",
    })


def record_raw_text_sample(sample: str, enabled: bool = True):
    """Record a sample of raw extracted text for debugging."""
    global _diagnostics_store
    _diagnostics_store["raw_text_debug"] = {
        "enabled": enabled,
        "sample_excerpt": sample[:1000] if (sample and enabled) else "",
        "how_to_enable": "Set DEBUG_RAW_TEXT=1 environment variable or enable Debug mode in sidebar" if not enabled else "",
    }


def record_self_check_results(results: List[Dict[str, Any]]):
    """Record self-check results."""
    global _diagnostics_store
    _diagnostics_store["self_check_results"] = results


def get_last_upload() -> Optional[Dict[str, Any]]:
    """Get the last upload info."""
    return _diagnostics_store.get("last_upload")


def get_last_extraction() -> Optional[Dict[str, Any]]:
    """Get the last extraction results."""
    return _diagnostics_store.get("last_extraction")


def get_errors() -> List[Dict[str, Any]]:
    """Get all recorded errors."""
    return _diagnostics_store.get("errors", [])


def get_raw_text_debug() -> Dict[str, Any]:
    """Get raw text debug info."""
    return _diagnostics_store.get("raw_text_debug", {})


def get_self_check_results() -> Optional[List[Dict[str, Any]]]:
    """Get self-check results."""
    return _diagnostics_store.get("self_check_results")


def get_full_diagnostics() -> Dict[str, Any]:
    """Get complete diagnostics snapshot."""
    upload = _diagnostics_store.get("last_upload") or {}
    extraction = _diagnostics_store.get("last_extraction") or {}
    
    return {
        "input": {
            "bureau_guess": upload.get("bureau_guess", ""),
            "file_type": upload.get("file_type", ""),
            "pages": upload.get("pages"),
            "file_size_bytes": upload.get("file_size_bytes"),
        },
        "extraction": {
            "accounts_found": extraction.get("accounts_found"),
            "inquiries_found": extraction.get("inquiries_found"),
            "public_records_found": extraction.get("public_records_found"),
            "negative_items_found": extraction.get("negative_items_found"),
            "personal_info_fields_found": extraction.get("personal_info_fields_found", []),
            "missing_critical_fields": extraction.get("missing_critical_fields", []),
            "dedupe_rules_in_use": extraction.get("dedupe_rules_in_use", []),
            "confidence_or_quality_signals": extraction.get("confidence_or_quality_signals", []),
        },
        "errors": get_errors(),
        "raw_text_debug": get_raw_text_debug(),
    }
