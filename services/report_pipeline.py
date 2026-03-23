"""
Streamlit-free Upload → Parse pipeline (same steps as app_real.py UPLOAD card).

Primary entry: process_uploaded_reports(pdf_files, options)

UploadPipelineBatch is a thin wrapper for incremental processing (e.g. per st.status)
using the same underlying logic.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, Union

import database as db
import diagnostics_store as diag_store
from aggregator import compute_unified_summary
from claims import extract_claims
from classifier import classify_accounts, compute_negative_items, count_by_classification
from completeness import compute_completeness
from layout_extract import extract_layout, to_plain_text
from normalization import normalize_parsed_data
from parsers import (
    detect_bureau,
    extract_text_from_pdf,
    parse_credit_report_data,
    run_tu_diagnostics,
)
from review_claims import compress_claims
from totals_detector import (
    detect_section_totals_with_sources,
    detect_totals_mode_with_sources,
    self_verify_totals,
)
from translator import (
    build_account_records,
    canonical_records_to_parsed_accounts,
    detect_tu_variant_from_text,
)

from .report_metrics import (
    count_hard_inquiries,
    compute_exactness,
    compute_report_totals,
    is_hard_inquiry,
)

_log = logging.getLogger(__name__)

PdfInput = Union[bytes, bytearray, Tuple[str, bytes], Any]


class UploadProgress(Protocol):
    def update(self, label: str, state: str = "running") -> None: ...
    def write(self, message: str) -> None: ...


class NoOpUploadProgress:
    def update(self, label: str, state: str = "running") -> None:
        pass

    def write(self, message: str) -> None:
        pass


@dataclass
class _UploadPipelineContext:
    user_id: int
    use_ocr: bool
    debug_mode: bool
    dev_mode: bool
    on_report_saved: Optional[Callable[[str, str], None]]

    all_claims: List[Any] = field(default_factory=list)
    diagnostic_logs: List[Dict[str, Any]] = field(default_factory=list)
    uploaded_reports: Dict[str, Any] = field(default_factory=dict)
    extracted_claims: Dict[str, Any] = field(default_factory=dict)
    reports_processed: int = 0
    plain_text: Optional[str] = None
    layout: Any = None


def _normalize_pdf_inputs(pdf_files: List[PdfInput]) -> List[Tuple[str, bytes]]:
    """Turn mixed file inputs into (filename, pdf_bytes)."""
    out: List[Tuple[str, bytes]] = []
    for i, item in enumerate(pdf_files):
        if isinstance(item, (bytes, bytearray)):
            out.append((f"upload_{i + 1}.pdf", bytes(item)))
            continue
        if isinstance(item, tuple) and len(item) == 2:
            name, data = item[0], item[1]
            if not isinstance(data, (bytes, bytearray)):
                raise TypeError("Tuple pdf entry must be (str, bytes)")
            out.append((str(name), bytes(data)))
            continue
        if hasattr(item, "read") and hasattr(item, "seek"):
            raw_name = getattr(item, "name", None) or f"upload_{i + 1}.pdf"
            if isinstance(raw_name, str):
                name = raw_name.replace("\\", "/").split("/")[-1]
            else:
                name = f"upload_{i + 1}.pdf"
            data = item.read()
            item.seek(0)
            out.append((name, bytes(data)))
            continue
        raise TypeError(f"Unsupported pdf_files entry at index {i}: {type(item)!r}")
    return out


def _options_dict_to_context(options: Dict[str, Any]) -> _UploadPipelineContext:
    user_id = options.get("user_id")
    if user_id is None:
        raise ValueError("options['user_id'] is required for report persistence")
    return _UploadPipelineContext(
        user_id=int(user_id),
        use_ocr=bool(options.get("use_ocr", False)),
        debug_mode=bool(options.get("debug", options.get("debug_mode", False))),
        dev_mode=bool(options.get("dev_mode", False)),
        on_report_saved=options.get("on_report_saved"),
    )


def _process_single_pdf(
    ctx: _UploadPipelineContext,
    filename: str,
    pdf_bytes: bytes,
    progress: UploadProgress,
) -> Optional[str]:
    """
    One PDF through the full extract → bureau → parse → layout/translator → classify →
    claims → diag_store → save_report path. Returns None on success, or skip reason.
    """
    progress.update(label=f"Reading {filename}...", state="running")
    progress.write("Opening your PDF and extracting text...")

    file_hash = hashlib.sha256(pdf_bytes).hexdigest()[:16]
    upload_id = f"UPL_{file_hash}"
    upload_time = datetime.now().isoformat()

    pdf_io = BytesIO(pdf_bytes)
    full_text, page_texts, num_pages, _pdf_extract_error = extract_text_from_pdf(
        pdf_io, ctx.use_ocr
    )

    if not full_text:
        return "no_text"

    progress.write(f"Read {num_pages} pages successfully.")
    progress.update(label=f"Identifying bureau for {filename}...", state="running")
    progress.write("Detecting which credit bureau this report is from...")
    bureau, bureau_scores, bureau_evidence = detect_bureau(
        full_text, debug=ctx.debug_mode, return_details=True
    )

    diag_store.record_upload(
        bureau_guess=bureau,
        file_type="pdf",
        file_size_bytes=len(pdf_bytes),
        page_count=num_pages,
        file_name=filename,
    )

    diag_store.record_raw_text_sample(
        sample=full_text[:1000] if full_text else "",
        enabled=ctx.debug_mode,
    )

    diag: Dict[str, Any] = {
        "upload_id": upload_id,
        "filename": filename,
        "file_hash": file_hash,
        "upload_time": upload_time,
        "detected_bureau": bureau,
        "text_length": len(full_text),
        "first_200_chars": full_text[:200].replace("\n", " ")[:100],
    }
    ctx.diagnostic_logs.append(diag)

    if ctx.debug_mode:
        _log.debug("[UPLOAD_DIAG] %s", json.dumps(diag, indent=2))

    if bureau == "3bureau":
        progress.update(label=f"{filename} — 3-bureau report detected", state="error")
        return "3bureau"

    if bureau == "unknown":
        progress.update(label=f"{filename} — Bureau not identified", state="error")
        return "unknown"

    bureau_display = (
        bureau.replace("transunion", "TransUnion")
        .replace("experian", "Experian")
        .replace("equifax", "Equifax")
    )
    progress.write(f"Detected **{bureau_display}** report.")

    progress.update(label=f"Parsing accounts from {bureau_display} report...", state="running")
    progress.write("Extracting accounts, balances, and payment history...")
    try:
        parsed_data = parse_credit_report_data(full_text, bureau)
    except Exception as parse_err:
        diag_store.record_error("parse_credit_report_data", str(parse_err), parse_err)
        raise

    progress.update(label=f"Deep-reading {bureau_display} report layout...", state="running")
    progress.write("Analyzing page layout for additional detail...")
    translator_used = False
    translator_count = 0
    existing_accounts_count = len(parsed_data.get("accounts", []))
    layout_plain_text: Optional[str] = None
    tu_variant_layout = None
    try:
        layout = extract_layout(pdf_bytes)
        layout_plain_text = to_plain_text(layout)
        tu_variant_layout = detect_tu_variant_from_text(layout_plain_text)
        if bureau == "transunion":
            canonical_records = build_account_records(layout, tu_variant_layout)
            translator_count = len(canonical_records)
            if translator_count > 0 and translator_count >= existing_accounts_count:
                translated_accounts = canonical_records_to_parsed_accounts(canonical_records)
                parsed_data["accounts"] = translated_accounts
                translator_used = True
                if ctx.debug_mode:
                    _log.debug(
                        "[TRANSLATOR] Used layout translator: %s accounts (was %s)",
                        translator_count,
                        existing_accounts_count,
                    )
            elif ctx.debug_mode:
                _log.debug(
                    "[TRANSLATOR] Kept regex parser: %s accounts (translator found %s)",
                    existing_accounts_count,
                    translator_count,
                )
        if ctx.dev_mode or ctx.debug_mode:
            ctx.layout = layout
        ctx.plain_text = layout_plain_text
    except Exception as layout_err:
        if ctx.debug_mode:
            _log.debug("[TRANSLATOR] Layout extraction failed: %s", layout_err)
        layout_plain_text = full_text
        tu_variant_layout = None
        ctx.plain_text = full_text

    progress.update(label="Classifying accounts and identifying issues...", state="running")
    progress.write("Checking for negative items, inquiries, and potential disputes...")
    tu_diag = run_tu_diagnostics(
        full_text, bureau, bureau_scores, bureau_evidence, parsed_data
    )
    if translator_used:
        tu_diag["translator"] = {
            "used": True,
            "translator_accounts": translator_count,
            "regex_accounts": existing_accounts_count,
        }
    diag["tu_diagnostics"] = tu_diag

    source_type = "ocr" if ctx.use_ocr else "unknown"
    parsed_data = normalize_parsed_data(parsed_data, source_type=source_type)

    classify_text = layout_plain_text if layout_plain_text else full_text
    classify_accounts(
        parsed_data.get("accounts", []),
        classify_text,
        variant=tu_variant_layout if bureau == "transunion" else None,
        bureau=bureau,
    )
    cls_neg = compute_negative_items(parsed_data.get("accounts", []))
    if cls_neg or not parsed_data.get("negative_items"):
        parsed_data["negative_items"] = cls_neg
    parsed_data["classification_counts"] = count_by_classification(
        parsed_data.get("accounts", [])
    )
    if ctx.debug_mode:
        cls_counts = parsed_data["classification_counts"]
        _log.debug(
            "[CLASSIFIER] Adverse=%s, Good=%s, Unknown=%s",
            cls_counts.get("ADVERSE", 0),
            cls_counts.get("GOOD_STANDING", 0),
            cls_counts.get("UNKNOWN", 0),
        )

    progress.update(label="Saving results...", state="running")
    progress.write("Storing your parsed report securely...")
    try:
        report_id = db.save_report(
            bureau, filename, parsed_data, full_text, user_id=ctx.user_id
        )
        if ctx.on_report_saved:
            ctx.on_report_saved(bureau, filename)
    except Exception:
        report_id = None

    report_data = {
        "upload_id": upload_id,
        "file_name": filename,
        "file_hash": file_hash,
        "bureau": bureau,
        "parsed_data": parsed_data,
        "full_text": full_text,
        "num_pages": num_pages,
        "report_id": report_id,
        "upload_time": upload_time,
    }

    snapshot_key = upload_id
    ctx.uploaded_reports[snapshot_key] = report_data

    claims = extract_claims(parsed_data, bureau)
    ctx.extracted_claims[snapshot_key] = claims

    ctx.all_claims.extend(claims)
    ctx.reports_processed += 1

    accounts_count = len(parsed_data.get("accounts", []))
    all_inquiries = parsed_data.get("inquiries", [])
    hard_inq = len([i for i in all_inquiries if is_hard_inquiry(i)])
    soft_inq = len([i for i in all_inquiries if not is_hard_inquiry(i)])
    neg_count = len(parsed_data.get("negative_items", []))
    public_records_count = len(parsed_data.get("public_records", []))

    personal_info = parsed_data.get("personal_info", {})
    personal_fields_found = [k for k, v in personal_info.items() if v]

    missing_critical = []
    if not personal_info.get("name"):
        missing_critical.append("name")
    if not personal_info.get("address"):
        missing_critical.append("address")

    reject_counters = parsed_data.get("reject_counters", {})
    dedupe_rules = [
        "smart_account_dedupe_key",
        "smart_inquiry_dedupe_key",
        "smart_negative_dedupe_key",
    ]

    confidence_signals = []
    if parsed_data.get("confidence_level"):
        confidence_signals.append(f"Overall: {parsed_data.get('confidence_level')}")
    for acct in parsed_data.get("accounts", [])[:3]:
        if acct.get("confidence"):
            confidence_signals.append(f"Account: {acct.get('confidence')}")

    diag_store.record_extraction(
        accounts_found=accounts_count,
        inquiries_found=len(all_inquiries),
        public_records_found=public_records_count,
        negative_items_found=neg_count,
        personal_info_fields=personal_fields_found,
        missing_critical_fields=missing_critical,
        dedupe_rules=dedupe_rules,
        confidence_signals=confidence_signals[:5],
        reject_counters=reject_counters,
    )

    diag["snapshot_counts"] = {
        "accounts": accounts_count,
        "hard_inquiries": hard_inq,
        "soft_inquiries": soft_inq,
        "negative_items": neg_count,
    }

    if ctx.debug_mode:
        _log.debug(
            "[SNAPSHOT_BIND] upload_id=%s, bureau=%s, report_id=%s",
            upload_id,
            bureau,
            report_id,
        )
        _log.debug(
            "[SNAPSHOT_COUNTS] accounts=%s, hard_inq=%s, soft_inq=%s, neg=%s",
            accounts_count,
            hard_inq,
            soft_inq,
            neg_count,
        )

    progress.update(
        label=f"{bureau_display} report analyzed — {accounts_count} accounts, {neg_count} negative items found",
        state="complete",
    )
    return None


def _finalize_upload_context(ctx: _UploadPipelineContext) -> Dict[str, Any]:
    review_claims = compress_claims(ctx.all_claims)

    completeness_report = None
    totals_confidence = None
    exactness = None
    report_totals = None
    parsed_totals = None
    review_exactness_state = None
    unified_summary = None

    if ctx.reports_processed > 0:
        first_report = list(ctx.uploaded_reports.values())[0]
        first_text = first_report.get("full_text", "")
        first_bureau = first_report.get("bureau", "unknown")
        first_parsed = first_report.get("parsed_data", {})
        completeness_text = ctx.plain_text if ctx.plain_text else first_text
        c_totals, c_sources = detect_section_totals_with_sources(
            completeness_text, first_bureau
        )
        c_mode = detect_totals_mode_with_sources(
            c_totals, c_sources, first_bureau, completeness_text
        )
        personal_info = first_parsed.get("personal_info", {})
        pif_count = sum(
            1 for k in ["name", "address", "dob", "ssn_last4"] if personal_info.get(k)
        )
        c_extracted = {
            "accounts": len(first_parsed.get("accounts", [])),
            "inquiries": count_hard_inquiries(first_parsed),
            "negative_items": len(first_parsed.get("negative_items", [])),
            "public_records": len(first_parsed.get("public_records", [])),
            "personal_info_fields": pif_count,
        }
        sv = self_verify_totals(completeness_text, first_bureau, c_extracted)
        completeness_report = compute_completeness(
            first_bureau, c_totals, c_extracted, totals_mode=c_mode, self_verification=sv
        )
        totals_confidence = completeness_report.totals_confidence
        exactness = completeness_report.exactness
        rt = compute_report_totals(first_text, first_bureau)
        pt, _ = compute_exactness(rt, first_parsed)
        report_totals = rt
        parsed_totals = pt
        review_exactness_state = completeness_report.exactness
        unified_summary = compute_unified_summary(ctx.uploaded_reports)

    return {
        "uploaded_reports": dict(ctx.uploaded_reports),
        "extracted_claims": dict(ctx.extracted_claims),
        "review_claims": review_claims,
        "diagnostics": list(ctx.diagnostic_logs),
        "completeness_report": completeness_report,
        "unified_summary": unified_summary,
        "report_totals": report_totals,
        "parsed_totals": parsed_totals,
        "totals_confidence": totals_confidence,
        "exactness": exactness,
        "review_exactness_state": review_exactness_state,
        "plain_text": ctx.plain_text,
        "layout": ctx.layout,
        "reports_processed": ctx.reports_processed,
    }


def process_uploaded_reports(
    pdf_files: List[PdfInput],
    options: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run the full UPLOAD pipeline (same steps as app_real.py).

    Inputs:
        pdf_files: list of raw bytes, (filename, bytes), or file-like objects with
            read(), seek(), and optional .name.
        options: dict with at least user_id; optional use_ocr, debug / debug_mode,
            dev_mode, on_report_saved(bureau, filename).

    Returns:
        dict with uploaded_reports, extracted_claims, review_claims, diagnostics,
        completeness_report, unified_summary, report_totals, parsed_totals, plus
        totals_confidence, exactness, review_exactness_state, plain_text, layout,
        reports_processed, file_skips (list of {filename, reason} for skipped inputs).
    """
    ctx = _options_dict_to_context(options)
    pairs = _normalize_pdf_inputs(pdf_files)
    progress = NoOpUploadProgress()
    file_skips: List[Dict[str, str]] = []

    for filename, pdf_bytes in pairs:
        skip = _process_single_pdf(ctx, filename, pdf_bytes, progress)
        if skip:
            file_skips.append({"filename": filename, "reason": skip})

    out = _finalize_upload_context(ctx)
    out["file_skips"] = file_skips
    return out


@dataclass
class UploadPipelineResult:
    uploaded_reports: Dict[str, Any]
    extracted_claims: Dict[str, Any]
    review_claims: List[Any]
    diagnostic_logs: List[Dict[str, Any]]
    reports_processed: int
    plain_text: Optional[str]
    layout: Any
    completeness_report: Any
    totals_confidence: Any
    exactness: Any
    report_totals: Any
    parsed_totals: Any
    review_exactness_state: Any
    unified_summary: Any


@dataclass
class UploadPipelineBatch:
    """Incremental wrapper around the same pipeline (for Streamlit per-file status)."""

    user_id: int
    use_ocr: bool = False
    debug_mode: bool = False
    dev_mode: bool = False
    on_report_saved: Optional[Callable[[str, str], None]] = None

    _ctx: _UploadPipelineContext = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._ctx = _UploadPipelineContext(
            user_id=self.user_id,
            use_ocr=self.use_ocr,
            debug_mode=self.debug_mode,
            dev_mode=self.dev_mode,
            on_report_saved=self.on_report_saved,
        )

    def reset(self) -> None:
        self._ctx = _UploadPipelineContext(
            user_id=self.user_id,
            use_ocr=self.use_ocr,
            debug_mode=self.debug_mode,
            dev_mode=self.dev_mode,
            on_report_saved=self.on_report_saved,
        )

    @property
    def all_claims(self) -> List[Any]:
        return self._ctx.all_claims

    @property
    def diagnostic_logs(self) -> List[Dict[str, Any]]:
        return self._ctx.diagnostic_logs

    @property
    def uploaded_reports(self) -> Dict[str, Any]:
        return self._ctx.uploaded_reports

    @property
    def extracted_claims(self) -> Dict[str, Any]:
        return self._ctx.extracted_claims

    @property
    def reports_processed(self) -> int:
        return self._ctx.reports_processed

    @property
    def plain_text(self) -> Optional[str]:
        return self._ctx.plain_text

    @property
    def layout(self) -> Any:
        return self._ctx.layout

    def process_file(
        self,
        filename: str,
        pdf_bytes: bytes,
        progress: Optional[UploadProgress] = None,
    ) -> Optional[str]:
        p = progress or NoOpUploadProgress()
        return _process_single_pdf(self._ctx, filename, pdf_bytes, p)

    def finalize(self) -> UploadPipelineResult:
        d = _finalize_upload_context(self._ctx)
        return UploadPipelineResult(
            uploaded_reports=d["uploaded_reports"],
            extracted_claims=d["extracted_claims"],
            review_claims=d["review_claims"],
            diagnostic_logs=d["diagnostics"],
            reports_processed=d["reports_processed"],
            plain_text=d["plain_text"],
            layout=d["layout"],
            completeness_report=d["completeness_report"],
            totals_confidence=d["totals_confidence"],
            exactness=d["exactness"],
            report_totals=d["report_totals"],
            parsed_totals=d["parsed_totals"],
            review_exactness_state=d["review_exactness_state"],
            unified_summary=d["unified_summary"],
        )
