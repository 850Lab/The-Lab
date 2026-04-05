"""
Multi-round dispute execution state stored only on ``workflow_sessions.metadata`` (JSON).

* ``dispute_selection.dispute_round_number`` — engine-maintained round counter (authoritative).
* ``dispute_selection.round_number`` — mirror for clients (same value after sync).
* ``dispute_selection.prior_outcomes`` — append-only log: per-response intakes + round transitions.
* ``dispute_selection.unresolved_items`` — derived from cumulative disputed ids + ``claim_outcomes``.

Item-level bureau outcomes (structured, not full parsing): ``deleted``, ``updated``,
``verified``, ``no_response``. Disposition for strategy: ``resolved`` | ``unresolved`` |
``needs_escalation``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from services.workflow.repository import fetch_session, merge_into_workflow_metadata

# Normalized labels for per-item bureau outcomes (intake / manual).
BUREAU_ITEM_OUTCOMES: Tuple[str, ...] = ("deleted", "updated", "verified", "no_response")

_OUTCOME_ALIASES: Dict[str, str] = {
    "deleted": "deleted",
    "delete": "deleted",
    "deletion": "deleted",
    "removed": "deleted",
    "updated": "updated",
    "update": "updated",
    "corrected": "updated",
    "modified": "updated",
    "verified": "verified",
    "verify": "verified",
    "verified_accurate": "verified",
    "accurate": "verified",
    "no_response": "no_response",
    "none": "no_response",
    "no answer": "no_response",
    "non_answer": "no_response",
    "stall": "no_response",
}


def normalize_bureau_item_outcome(raw: str) -> str:
    k = (raw or "").strip().lower().replace(" ", "_")
    if k in BUREAU_ITEM_OUTCOMES:
        return k
    return _OUTCOME_ALIASES.get(k, k if k in BUREAU_ITEM_OUTCOMES else "updated")


def item_disposition(bureau_outcome: str) -> str:
    """
    Map normalized bureau outcome to program disposition.

    * resolved — stop selecting this item for further rounds (deleted or verified accurate).
    * needs_escalation — bureau non-response / stall bucket.
    * unresolved — still in play (including ``updated`` partials).
    """
    o = (bureau_outcome or "").strip().lower()
    if o in ("deleted", "verified"):
        return "resolved"
    if o == "no_response":
        return "needs_escalation"
    if o == "updated":
        return "unresolved"
    return "unresolved"


def extract_item_outcomes_from_parsed_summary(parsed_summary: Dict[str, Any]) -> Dict[str, str]:
    """``item_outcomes``: [{ reviewClaimId, bureauOutcome }] → claim_id → normalized outcome."""
    out: Dict[str, str] = {}
    raw = parsed_summary.get("item_outcomes")
    if not isinstance(raw, list):
        return out
    for row in raw:
        if not isinstance(row, dict):
            continue
        cid = str(
            row.get("reviewClaimId")
            or row.get("review_claim_id")
            or row.get("claimId")
            or ""
        ).strip()
        if not cid:
            continue
        bo = str(row.get("bureauOutcome") or row.get("bureau_outcome") or "").strip()
        if not bo:
            continue
        out[cid] = normalize_bureau_item_outcome(bo)
    return out


def _ds_from_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    ds = meta.get("dispute_selection")
    if not isinstance(ds, dict):
        return {}
    return dict(ds)


def _round_from_ds(ds: Dict[str, Any]) -> int:
    try:
        return max(1, int(ds.get("dispute_round_number") or ds.get("round_number") or 1))
    except (TypeError, ValueError):
        return 1


def _cumulative_from_ds(ds: Dict[str, Any]) -> Set[str]:
    cum: Set[str] = set()
    for key in ("cumulative_disputed_review_claim_ids", "previously_disputed_claim_ids"):
        raw = ds.get(key)
        if isinstance(raw, list):
            cum |= {str(x) for x in raw if x}
    return cum


def _claim_outcomes_from_ds(ds: Dict[str, Any]) -> Dict[str, str]:
    raw = ds.get("claim_outcomes")
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in raw.items():
        if k is None or v is None:
            continue
        key = str(k).strip()
        if not key:
            continue
        out[key] = normalize_bureau_item_outcome(str(v).strip().lower())
    return out


def build_unresolved_items(cumulative_ids: Set[str], claim_outcomes: Dict[str, str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for cid in sorted(cumulative_ids):
        oc = (claim_outcomes.get(cid) or "").strip().lower()
        if not oc:
            disp = "unresolved"
            norm = "unknown"
        else:
            norm = normalize_bureau_item_outcome(oc)
            disp = item_disposition(norm)
        if disp == "resolved":
            continue
        row: Dict[str, Any] = {
            "reviewClaimId": cid,
            "bureauOutcome": norm,
            "disposition": disp,
        }
        if disp == "needs_escalation":
            row["escalationSuggested"] = True
        rows.append(row)
    return rows


def merge_item_and_claim_outcomes_into_metadata(
    workflow_id: str,
    parsed_summary: Dict[str, Any],
) -> None:
    """Fold ``item_outcomes`` + ``claim_outcomes`` from parsed_summary into dispute_selection."""
    if not isinstance(parsed_summary, dict):
        return
    from_items = extract_item_outcomes_from_parsed_summary(parsed_summary)
    raw_co = parsed_summary.get("claim_outcomes")
    from_claim: Dict[str, str] = {}
    if isinstance(raw_co, dict):
        for k, v in raw_co.items():
            if k is None or v is None:
                continue
            key = str(k).strip()
            if not key:
                continue
            from_claim[key] = normalize_bureau_item_outcome(str(v).strip().lower())

    if not from_items and not from_claim:
        return

    def _mut(meta: Dict[str, Any]) -> None:
        ds = _ds_from_meta(meta)
        cur = _claim_outcomes_from_ds(ds)
        merged = {**cur, **from_items, **from_claim}
        ds["claim_outcomes"] = merged
        meta["dispute_selection"] = ds

    merge_into_workflow_metadata(workflow_id, _mut)


def refresh_round_execution_projection(
    workflow_id: str,
    *,
    intake_record: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Recompute ``unresolved_items`` and ``round_number``; optionally append ``prior_outcomes``.
    """
    sess = fetch_session(workflow_id)
    if not sess:
        return

    def _mut(meta: Dict[str, Any]) -> None:
        ds = _ds_from_meta(meta)
        rnd = _round_from_ds(ds)
        ds["round_number"] = rnd
        cumulative = _cumulative_from_ds(ds)
        outcomes = _claim_outcomes_from_ds(ds)
        ds["unresolved_items"] = build_unresolved_items(cumulative, outcomes)
        if intake_record:
            prior = ds.get("prior_outcomes")
            if not isinstance(prior, list):
                prior = []
            prior = list(prior) + [intake_record]
            ds["prior_outcomes"] = prior[-48:]
        from services.workflow.escalation_engine import apply_escalation_fields_to_ds

        ds = apply_escalation_fields_to_ds(ds)
        meta["dispute_selection"] = ds

    merge_into_workflow_metadata(workflow_id, _mut)


def append_intake_to_round_history(
    workflow_id: str,
    *,
    response_id: str,
    document_classification: Optional[str],
    reasoning_safe: Optional[str],
) -> None:
    sess = fetch_session(workflow_id)
    if not sess:
        return
    meta = sess.get("metadata") if isinstance(sess.get("metadata"), dict) else {}
    ds = _ds_from_meta(meta)
    rnd = _round_from_ds(ds)
    outcomes = _claim_outcomes_from_ds(ds)
    cumulative = _cumulative_from_ds(ds)
    unresolved = build_unresolved_items(cumulative, outcomes)
    intake_record = {
        "kind": "response_intake",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "responseId": str(response_id),
        "roundNumber": rnd,
        "documentClassification": document_classification,
        "reasoningSafe": (reasoning_safe or "")[:500] if reasoning_safe else None,
        "claimOutcomeSnapshot": dict(outcomes),
        "unresolvedItems": unresolved,
    }
    refresh_round_execution_projection(workflow_id, intake_record=intake_record)


def snapshot_round_close_before_next(workflow_id: str) -> None:
    """
    Call immediately before incrementing ``dispute_round_number`` (e.g. begin-next-round).
    Records a boundary snapshot on ``prior_outcomes``.
    """
    sess = fetch_session(workflow_id)
    if not sess:
        return
    meta = sess.get("metadata") if isinstance(sess.get("metadata"), dict) else {}
    ds = _ds_from_meta(meta)
    prev = _round_from_ds(ds)
    outcomes = _claim_outcomes_from_ds(ds)
    cumulative = _cumulative_from_ds(ds)
    unresolved = build_unresolved_items(cumulative, outcomes)
    transition = {
        "kind": "round_transition",
        "closedAt": datetime.now(timezone.utc).isoformat(),
        "fromRound": prev,
        "toRound": prev + 1,
        "claimOutcomesSnapshot": dict(outcomes),
        "unresolvedItemsAtClose": unresolved,
    }

    def _mut(meta2: Dict[str, Any]) -> None:
        ds2 = _ds_from_meta(meta2)
        prior = ds2.get("prior_outcomes")
        if not isinstance(prior, list):
            prior = []
        prior = list(prior) + [transition]
        ds2["prior_outcomes"] = prior[-48:]
        from services.workflow.escalation_engine import apply_escalation_fields_to_ds

        ds2 = apply_escalation_fields_to_ds(ds2)
        meta2["dispute_selection"] = ds2

    merge_into_workflow_metadata(workflow_id, _mut)


def round_execution_public_view(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Subset safe to embed in dispute strategy API (round/outcome spine; see ``escalationGuide`` for actions)."""
    ds = _ds_from_meta(meta)
    rnd = _round_from_ds(ds)
    prior = ds.get("prior_outcomes")
    if not isinstance(prior, list):
        prior = []
    unresolved = ds.get("unresolved_items")
    if not isinstance(unresolved, list):
        unresolved = build_unresolved_items(_cumulative_from_ds(ds), _claim_outcomes_from_ds(ds))
    return {
        "roundNumber": rnd,
        "priorOutcomesCount": len(prior),
        "unresolvedItems": unresolved,
        "lastRoundTransition": next(
            (x for x in reversed(prior) if isinstance(x, dict) and x.get("kind") == "round_transition"),
            None,
        ),
    }
