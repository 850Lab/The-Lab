"""
Rebuild intake-facing summaries from persisted reports (same extract → compress as upload pipeline).

Used by the workflow HTTP API for React analyze/review steps.

When ``workflow_id`` is set and metadata holds a matching ``intake_claims_snapshot_v1``,
compressed claims are read from that snapshot (dual-write path) instead of recomputing.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

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


def build_customer_intake_summary(
    user_id: int,
    *,
    report_limit: int = 25,
    only_report_ids: Optional[List[int]] = None,
    workflow_id: Optional[str] = None,
) -> Dict[str, Any]:
    if only_report_ids is not None:
        rows = db.get_reports_with_parsed_for_user_by_ids(user_id, only_report_ids)
    else:
        rows = db.get_recent_reports_with_parsed_for_user(user_id, limit=report_limit)

    report_summaries: List[Dict[str, Any]] = []
    id_list: List[int] = []

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
        if rid is not None:
            try:
                id_list.append(int(rid))
            except (TypeError, ValueError):
                pass

    claims_provenance = "recomputed"
    claim_dicts: List[Dict[str, Any]] = []

    if workflow_id:
        from services.workflow.claims_snapshot import try_load_snapshot_claim_dicts

        snap = try_load_snapshot_claim_dicts(workflow_id, id_list)
        if snap:
            claim_dicts = snap[0]
            claims_provenance = "snapshot_v1"

    if not claim_dicts:
        all_raw_claims: List[Any] = []
        for row in rows:
            pd = _parsed_dict(row.get("parsed_data"))
            bureau = (row.get("bureau") or "unknown").lower()
            rid = row.get("id")
            try:
                all_raw_claims.extend(extract_claims(pd, bureau))
            except Exception as exc:
                _log.warning("extract_claims failed for report %s: %s", rid, exc)

        compressed: List[ReviewClaim] = compress_claims(all_raw_claims)
        claim_dicts = [c.to_dict() for c in compressed]

    by_type: Dict[str, int] = {}
    for d in claim_dicts:
        rt = (d.get("review_type") or "").strip()
        if rt:
            by_type[rt] = by_type.get(rt, 0) + 1

    total_accounts = sum(s["counts"]["accounts"] for s in report_summaries)

    out: Dict[str, Any] = {
        "reports": report_summaries,
        "reviewClaims": claim_dicts,
        "reviewClaimsCount": len(claim_dicts),
        "aggregates": {
            "reportCount": len(report_summaries),
            "totalAccountsExtracted": total_accounts,
            "claimsByReviewType": by_type,
        },
    }
    if workflow_id:
        out["claimsProvenance"] = {"source": claims_provenance}
    return out
