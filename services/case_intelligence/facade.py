"""
Workflow-bound entry: loads persisted reports, claims, metadata, proof, letters; composes canonical object.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

import database as db
from claims import extract_claims
from review_claims import ReviewClaim

from services.customer_intake_summary import build_customer_intake_summary
from services.customer_proof_service import build_proof_context_payload
from services.workflow.engine import compute_authoritative_step
from services.workflow.repository import fetch_session, fetch_steps

from .compose import build_canonical_case_intelligence
from .models import CanonicalCaseIntelligenceV1, CaseIntelligenceInputs

_log = logging.getLogger(__name__)


def _parsed_row_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    pd = row.get("parsed_data")
    if pd is None:
        return {}
    if isinstance(pd, dict):
        return pd
    if isinstance(pd, str):
        try:
            out = json.loads(pd)
            return out if isinstance(out, dict) else {}
        except Exception:
            return {}
    return {}


def build_canonical_case_intelligence_for_workflow(
    workflow_id: str,
    user_id: int,
) -> CanonicalCaseIntelligenceV1:
    """
    Load everything the app already persists for this workflow owner and return
    ``CanonicalCaseIntelligenceV1``.

    Raises:
        ValueError: missing session or user mismatch.
    """
    wf = (workflow_id or "").strip()
    uid = int(user_id)
    sess = fetch_session(wf)
    if not sess:
        raise ValueError("workflow session not found")
    if int(sess["user_id"]) != uid:
        raise ValueError("workflow user_id does not match caller")

    summary = build_customer_intake_summary(uid, workflow_id=wf)
    report_scope: List[Dict[str, Any]] = list(summary.get("reports") or [])
    id_list: List[int] = []
    for r in report_scope:
        if not isinstance(r, dict):
            continue
        try:
            id_list.append(int(r["reportId"]))
        except (KeyError, TypeError, ValueError):
            pass

    rows = (
        db.get_reports_with_parsed_for_user_by_ids(uid, id_list)
        if id_list
        else db.get_recent_reports_with_parsed_for_user(uid, limit=25)
    )

    raw_claims = []
    for row in rows:
        pd = _parsed_row_dict(row)
        bureau = (row.get("bureau") or "unknown").lower()
        try:
            raw_claims.extend(extract_claims(pd, bureau))
        except Exception as exc:
            _log.warning(
                "extract_claims failed in case_intelligence rid=%s: %s",
                row.get("id"),
                exc,
            )

    review_dicts = summary.get("reviewClaims") or []
    review_claims = [
        ReviewClaim.from_dict(d) for d in review_dicts if isinstance(d, dict)
    ]

    meta = sess.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    if not isinstance(meta, dict):
        meta = {}

    ds = meta.get("dispute_selection") or {}
    selected: List[str] = []
    if isinstance(ds, dict):
        raw_sel = ds.get("draft_selected_review_claim_ids") or ds.get(
            "selected_review_claim_ids"
        )
        if isinstance(raw_sel, list):
            selected = [str(x) for x in raw_sel if x]

    letters = db.get_all_letters_for_user(uid)
    proof = build_proof_context_payload(uid, wf)
    proof_flags = {
        "hasGovernmentId": bool(proof.get("hasGovernmentId")),
        "hasAddressProof": bool(proof.get("hasAddressProof")),
        "hasSignature": bool(proof.get("hasSignature")),
    }

    steps = fetch_steps(wf)
    smap = {s["step_id"]: s for s in steps}
    head, _phase = compute_authoritative_step(smap)

    inputs = CaseIntelligenceInputs(
        workflow_id=wf,
        user_id=uid,
        report_scope=report_scope,
        raw_claims=raw_claims,
        review_claims=review_claims,
        workflow_metadata=meta,
        selected_review_claim_ids=selected,
        proof_flags=proof_flags,
        letter_records=letters,
        authoritative_step_id=head,
    )
    return build_canonical_case_intelligence(inputs)
