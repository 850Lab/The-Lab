"""
S3 — org program participant report intake helpers (/api/me/report*).

Eligibility: active org_user membership + program enrollment row for that org.
Reuses claims + review_claims pipeline on persisted ``reports.parsed_data``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import database as db
from claims import extract_claims
from review_claims import compress_claims

from services.org_service import get_active_membership_for_user
from services.program_enrollment_service import get_enrollment


def get_enrolled_org_participant_context(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Returns org + enrollment ids for save_report linkage, or None if user is not
    an enrolled program participant.
    """
    m = get_active_membership_for_user(user_id)
    if not m or m.get("role") != "org_user":
        return None
    oid = int(m["organization_id"])
    enr = get_enrollment(oid, user_id)
    if not enr:
        return None
    return {
        "membership": m,
        "enrollment": enr,
        "organization_id": oid,
        "organization_program_enrollment_id": int(enr["id"]),
    }


def _load_report_row_for_user(
    user_id: int, report_id: Optional[int]
) -> Optional[Dict[str, Any]]:
    if report_id is not None:
        row = db.get_report(int(report_id), user_id=user_id)
        if not row:
            return None
        return row
    rows = db.get_recent_reports_with_parsed_for_user(user_id, limit=1)
    return rows[0] if rows else None


def _normalize_parsed_data(raw: Any) -> Dict[str, Any]:
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


def build_findings_payload(
    user_id: int,
    report_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Rebuild review claims + DB violations from stored parse (no PDF).
    Safe for S4 dispute selection (reviewClaims shape).
    """
    report = _load_report_row_for_user(user_id, report_id)
    if not report:
        return {
            "processingStatus": "no_report",
            "summary": None,
            "reviewClaims": [],
            "violations": [],
            "reportId": None,
        }

    rid = int(report["id"])
    bureau = (report.get("bureau") or "unknown").strip() or "unknown"
    parsed_data = _normalize_parsed_data(report.get("parsed_data"))

    raw_claims = extract_claims(parsed_data, bureau)
    review_claims = compress_claims(raw_claims)
    review_dicts: List[Dict[str, Any]] = [rc.to_dict() for rc in review_claims]

    violations = db.get_violations_for_report(rid)
    for v in violations:
        td = v.get("triggering_data")
        if isinstance(td, str):
            try:
                v["triggering_data"] = json.loads(td)
            except Exception:
                v["triggering_data"] = {}

    summary = {
        "reportId": rid,
        "bureau": bureau,
        "uploadDate": report.get("upload_date"),
        "accountsCount": len(parsed_data.get("accounts") or []),
        "negativeItemsCount": len(parsed_data.get("negative_items") or []),
        "hardInquiriesCount": len(
            [i for i in (parsed_data.get("inquiries") or []) if _inq_hard(i)]
        ),
        "reviewClaimsCount": len(review_dicts),
        "violationsCount": len(violations),
    }

    return {
        "processingStatus": "complete",
        "summary": summary,
        "reviewClaims": review_dicts,
        "violations": violations,
        "reportId": rid,
    }


def _inq_hard(inq: Any) -> bool:
    try:
        from services.report_metrics import is_hard_inquiry

        return bool(is_hard_inquiry(inq))
    except Exception:
        return False
