"""
Workflow-scoped snapshot of compressed review claims for intake + strategy reuse.

Dual-write: populated after a successful ``report_upload_parse`` job when hooks have
advanced the workflow. Invalidated when the user's report id set no longer matches.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from review_claims import ReviewClaim

from services.workflow.repository import fetch_session, merge_into_workflow_metadata

_log = logging.getLogger(__name__)

_SNAPSHOT_KEY = "intake_claims_snapshot_v1"


def persist_intake_claims_snapshot(
    workflow_id: str,
    *,
    report_ids: List[int],
    compressed_claims: List[ReviewClaim],
) -> None:
    """Store compressed claim dicts + sorted report ids for later fast path."""
    wf = (workflow_id or "").strip()
    if not wf or not compressed_claims:
        return
    ids_sorted = sorted({int(x) for x in report_ids if x is not None})
    claim_dicts = [c.to_dict() for c in compressed_claims]

    def mutator(meta: Dict[str, Any]) -> None:
        meta[_SNAPSHOT_KEY] = {
            "reportIds": ids_sorted,
            "claimDicts": claim_dicts,
        }

    try:
        merge_into_workflow_metadata(wf, mutator)
    except Exception:
        _log.warning("persist_intake_claims_snapshot failed wf=%s", wf, exc_info=True)


def try_load_snapshot_claim_dicts(
    workflow_id: Optional[str],
    current_report_ids: List[int],
) -> Optional[Tuple[List[Dict[str, Any]], str]]:
    """
    If session metadata snapshot matches ``current_report_ids`` (sorted set), return
    (claim_dicts, source) with source ``snapshot``; else None.
    """
    if not workflow_id:
        return None
    sess = fetch_session(workflow_id.strip())
    if not sess:
        return None
    meta = sess.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    if not isinstance(meta, dict):
        return None
    snap = meta.get(_SNAPSHOT_KEY)
    if not isinstance(snap, dict):
        return None
    stored_ids = snap.get("reportIds")
    if not isinstance(stored_ids, list):
        return None
    want = sorted({int(x) for x in current_report_ids if x is not None})
    got = sorted({int(x) for x in stored_ids})
    if want != got:
        return None
    raw = snap.get("claimDicts")
    if not isinstance(raw, list) or not raw:
        return None
    return (raw, "snapshot")
