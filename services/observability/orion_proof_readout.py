"""
ORION V2.5 — compact internal readout over Proof script client signals (observability_events).

Aggregates session-level (workflow) counts and small dimension breakdowns. Not a dashboard;
safe to call from an admin JSON endpoint only.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.observability.orion_signal_events import ORION_SIGNAL_EVENTS
from services.workflow.observability_events import _coerce_meta_row
from services.workflow.workflow_db import get_workflow_db

_log = logging.getLogger(__name__)

_META_KEYS = (
    "scriptAugmentationStatus",
    "proofScriptRefinementStatus",
    "contractCompleteness",
)


def _norm_dim(v: Any) -> str:
    if v is None:
        return "null"
    s = str(v).strip()
    return s if s else "null"


def _parse_ts(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    s = str(raw).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _empty_dim_counts() -> Dict[str, int]:
    return {
        "sessionsRendered": 0,
        "sessionsVisible": 0,
        "sessionsCompleted": 0,
        "completedAfterVisible": 0,
        "sessionsWithInteractSignal": 0,
    }


def _merge_session_meta(target: Dict[str, Any], incoming: Dict[str, Any]) -> None:
    for k in _META_KEYS:
        if k not in target or target[k] is None:
            v = incoming.get(k)
            if v is not None:
                target[k] = v


def summarize_orion_proof_script_signals_from_rows(
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Pure aggregation for tests. Each row: workflow_id, user_id, event_name, timestamp, metadata (dict or JSON str).
    Rows should be in chronological order (oldest first) for first-occurrence semantics.
    """
    from services.observability.orion_signal_events import (
        ORION_PROOF_SCRIPT_INTERACTED,
        ORION_PROOF_SCRIPT_RENDERED,
        ORION_PROOF_SCRIPT_VISIBLE,
        ORION_PROOF_STEP_COMPLETED,
    )

    by_wf: Dict[str, Dict[str, Any]] = {}

    for r in rows:
        wf = str(r.get("workflow_id") or "").strip()
        if not wf:
            continue
        en = str(r.get("event_name") or "").strip()
        if en not in ORION_SIGNAL_EVENTS:
            continue
        uid = r.get("user_id")
        try:
            uid_i = int(uid) if uid is not None else 0
        except (TypeError, ValueError):
            uid_i = 0
        meta = _coerce_meta_row(r.get("metadata"))
        ts = _parse_ts(r.get("timestamp"))

        b = by_wf.setdefault(
            wf,
            {
                "userId": None,
                "firstRendered": None,
                "firstVisible": None,
                "firstCompleted": None,
                "firstInteract": None,
                "meta": {},
            },
        )
        if uid_i and b["userId"] is None:
            b["userId"] = uid_i

        if en == ORION_PROOF_SCRIPT_RENDERED:
            if b["firstRendered"] is None:
                b["firstRendered"] = ts
                _merge_session_meta(b["meta"], meta)
        elif en == ORION_PROOF_SCRIPT_VISIBLE:
            if b["firstVisible"] is None:
                b["firstVisible"] = ts
                _merge_session_meta(b["meta"], meta)
        elif en == ORION_PROOF_STEP_COMPLETED:
            if b["firstCompleted"] is None:
                b["firstCompleted"] = ts
                _merge_session_meta(b["meta"], meta)
        elif en == ORION_PROOF_SCRIPT_INTERACTED:
            if b["firstInteract"] is None:
                b["firstInteract"] = ts
                _merge_session_meta(b["meta"], meta)

    rendered = {wf for wf, b in by_wf.items() if b["firstRendered"] is not None}
    visible = {wf for wf, b in by_wf.items() if b["firstVisible"] is not None}
    completed = {wf for wf, b in by_wf.items() if b["firstCompleted"] is not None}
    interacted = {wf for wf, b in by_wf.items() if b["firstInteract"] is not None}

    after_visible: set[str] = set()
    for wf in by_wf:
        b = by_wf[wf]
        fv, fc = b["firstVisible"], b["firstCompleted"]
        if fv is None or fc is None:
            continue
        if fv <= fc:
            after_visible.add(wf)

    def distinct_users(wfs: set[str]) -> int:
        uids = {by_wf[wf]["userId"] for wf in wfs if by_wf[wf]["userId"] is not None}
        return len(uids)

    totals = {
        "sessionsRendered": len(rendered),
        "sessionsVisible": len(visible),
        "sessionsCompleted": len(completed),
        "completedAfterVisible": len(after_visible),
        "sessionsWithInteractSignal": len(interacted),
        "distinctUsersRendered": distinct_users(rendered),
        "distinctUsersVisible": distinct_users(visible),
        "distinctUsersCompleted": distinct_users(completed),
        "distinctUsersCompletedAfterVisible": distinct_users(after_visible),
    }

    by_sa: Dict[str, Dict[str, int]] = defaultdict(_empty_dim_counts)
    by_pr: Dict[str, Dict[str, int]] = defaultdict(_empty_dim_counts)
    by_cc: Dict[str, Dict[str, int]] = defaultdict(_empty_dim_counts)

    def bump_dim(
        m: Dict[str, Dict[str, int]],
        key: str,
        *,
        has_r: bool,
        has_v: bool,
        has_c: bool,
        has_av: bool,
        has_i: bool,
    ) -> None:
        d = m[key]
        if has_r:
            d["sessionsRendered"] += 1
        if has_v:
            d["sessionsVisible"] += 1
        if has_c:
            d["sessionsCompleted"] += 1
        if has_av:
            d["completedAfterVisible"] += 1
        if has_i:
            d["sessionsWithInteractSignal"] += 1

    for wf, b in by_wf.items():
        meta = b["meta"]
        sa = _norm_dim(meta.get("scriptAugmentationStatus"))
        pr = _norm_dim(meta.get("proofScriptRefinementStatus"))
        cc = _norm_dim(meta.get("contractCompleteness"))
        has_r = wf in rendered
        has_v = wf in visible
        has_c = wf in completed
        has_av = wf in after_visible
        has_i = wf in interacted
        bump_dim(by_sa, sa, has_r=has_r, has_v=has_v, has_c=has_c, has_av=has_av, has_i=has_i)
        bump_dim(by_pr, pr, has_r=has_r, has_v=has_v, has_c=has_c, has_av=has_av, has_i=has_i)
        bump_dim(by_cc, cc, has_r=has_r, has_v=has_v, has_c=has_c, has_av=has_av, has_i=has_i)

    def sort_map(m: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
        return dict(sorted(m.items(), key=lambda kv: kv[0]))

    return {
        "totals": totals,
        "byScriptAugmentationStatus": sort_map(by_sa),
        "byProofScriptRefinementStatus": sort_map(by_pr),
        "byContractCompleteness": sort_map(by_cc),
        "sessionsRepresented": len(by_wf),
    }


def fetch_orion_proof_signal_rows(
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    event_row_limit: int = 100_000,
) -> List[Dict[str, Any]]:
    """
    Load ORION proof signal rows newest-first, capped; caller reverses for chronological aggregation.
    """
    cap = max(1_000, min(500_000, int(event_row_limit)))
    names = sorted(ORION_SIGNAL_EVENTS)
    where = ["event_name = ANY(%s)"]
    params: List[Any] = [names]
    if since and str(since).strip():
        where.append("timestamp >= %s")
        params.append(str(since).strip()[:64])
    if until and str(until).strip():
        where.append("timestamp <= %s")
        params.append(str(until).strip()[:64])
    params.append(cap)
    sql = f"""
        SELECT workflow_id, user_id, event_name, timestamp, metadata
        FROM observability_events
        WHERE {" AND ".join(where)}
        ORDER BY timestamp DESC, event_id DESC
        LIMIT %s
    """
    out: List[Dict[str, Any]] = []
    try:
        with get_workflow_db(dict_cursor=True) as (conn, cur):
            cur.execute(sql, tuple(params))
            raw_rows = cur.fetchall()
    except Exception:
        _log.warning("fetch_orion_proof_signal_rows failed", exc_info=True)
        return []

    for r in raw_rows:
        d = dict(r) if not isinstance(r, dict) else r
        meta_raw = d.get("metadata")
        if isinstance(meta_raw, str):
            try:
                meta_raw = json.loads(meta_raw)
            except Exception:
                meta_raw = {}
        out.append(
            {
                "workflow_id": d.get("workflow_id"),
                "user_id": d.get("user_id"),
                "event_name": d.get("event_name"),
                "timestamp": d.get("timestamp"),
                "metadata": meta_raw if isinstance(meta_raw, dict) else {},
            }
        )
    out.reverse()
    return out


def summarize_orion_proof_script_signals(
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    event_row_limit: int = 100_000,
) -> Dict[str, Any]:
    rows = fetch_orion_proof_signal_rows(
        since=since,
        until=until,
        event_row_limit=event_row_limit,
    )
    cap = max(1_000, min(500_000, int(event_row_limit)))
    summary = summarize_orion_proof_script_signals_from_rows(rows)
    return {
        "filters": {
            "since": since,
            "until": until,
            "eventRowLimit": cap,
        },
        "sample": {
            "eventRowsUsed": len(rows),
            "likelyTruncated": len(rows) >= cap,
        },
        "note": (
            "Session = workflow_id. completedAfterVisible = first visible at or before first completion. "
            "If eventRowLimit cuts the tail of history, oldest events drop first and a few sessions may look "
            "incomplete; narrow with since/until or raise the cap."
        ),
        **summary,
    }
