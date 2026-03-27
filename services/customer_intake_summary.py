"""
Rebuild intake-facing summaries from persisted reports (same extract → compress as upload pipeline).

Used by the workflow HTTP API for React analyze/review steps — no duplicate parsing logic.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

import database as db
from claims import extract_claims
from review_claims import ReviewClaim, compress_claims
from services.report_metrics import count_hard_inquiries

_log = logging.getLogger(__name__)


def _parsed_dict(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def build_customer_intake_summary(user_id: int, *, report_limit: int = 25) -> Dict[str, Any]:
    rows = db.get_recent_reports_with_parsed_for_user(user_id, limit=report_limit)
    report_summaries: List[Dict[str, Any]] = []
    all_raw_claims: List[Any] = []

    for row in rows:
        pd = _parsed_dict(row.get("parsed_data"))
        bureau = (row.get("bureau") or "unknown").lower()
        rid = row.get("id")
        fn = row.get("file_name") or ""
        ud = row.get("upload_date")
        ud_s = ud.isoformat() if hasattr(ud, "isoformat") else (str(ud) if ud else None)

        accts = pd.get("accounts") or []
        negs = pd.get("negative_items") or []
        inqs = pd.get("inquiries") or []

        report_summaries.append(
            {
                "reportId": rid,
                "bureau": bureau,
                "fileName": fn,
                "uploadDate": ud_s,
                "counts": {
                    "accounts": len(accts),
                    "negativeItems": len(negs),
                    "hardInquiries": count_hard_inquiries(pd),
                    "inquiries": len(inqs),
                },
            }
        )
        try:
            all_raw_claims.extend(extract_claims(pd, bureau))
        except Exception as exc:
            _log.warning("extract_claims failed for report %s: %s", rid, exc)

    compressed: List[ReviewClaim] = compress_claims(all_raw_claims)
    claim_dicts = [c.to_dict() for c in compressed]

    by_type: Dict[str, int] = {}
    for c in compressed:
        k = c.review_type.value
        by_type[k] = by_type.get(k, 0) + 1

    total_accounts = sum(s["counts"]["accounts"] for s in report_summaries)

    return {
        "reports": report_summaries,
        "reviewClaims": claim_dicts,
        "reviewClaimsCount": len(claim_dicts),
        "aggregates": {
            "reportCount": len(report_summaries),
            "totalAccountsExtracted": total_accounts,
            "claimsByReviewType": by_type,
        },
    }
