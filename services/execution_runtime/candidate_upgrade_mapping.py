"""
Candidate review / upgrade mapping — pure transform from promotion candidates to proposals.

No persistence, no writes to playbooks or runtime. No ML.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

# promotion candidate kind -> (output list is keyed in return dict separately)
_KIND_TO_UPGRADE_TYPE: Dict[str, str] = {
    "predefined_outcome_candidate": "predefined_outcome",
    "signal_label_candidate": "signal_label",
    "branch_expansion_candidate": "branch_expansion",
    "phrase_signal_mapping_candidate": "phrase_signal_mapping",
}


def _evidence_scalar_summary(ev: Dict[str, Any]) -> str:
    """Deterministic key=value; ... string from flat scalar evidence fields."""
    if not ev:
        return ""
    parts: List[str] = []
    for k in sorted(ev.keys()):
        v = ev[k]
        if v is None:
            continue
        if isinstance(v, (dict, list, tuple, set)):
            continue
        parts.append(f"{k}={v}")
    return "; ".join(parts)


def _evidence_count(ev: Dict[str, Any]) -> int:
    n = int(ev.get("count") or 0)
    return max(0, n)


def _priority_score(confidence: float, evidence_count: int) -> float:
    """confidenceScore plus a bounded count term (deterministic, inspectable)."""
    cnt = max(0, evidence_count)
    count_term = min(1.0, cnt / 25.0)
    return round(float(confidence) + count_term, 4)


def _affected_block_ids(ev: Dict[str, Any]) -> List[str]:
    bid = ev.get("blockId")
    if bid is None or bid == "":
        return []
    return [str(bid)]


def _upgrade_difficulty(upgrade_type: str, ev: Dict[str, Any]) -> str:
    if upgrade_type in ("signal_label", "predefined_outcome"):
        return "low"
    if upgrade_type == "phrase_signal_mapping":
        return "medium"
    if upgrade_type == "branch_expansion":
        ratio = float(ev.get("diversityRatio") or 0.0)
        uniq = int(ev.get("count") or 0)
        if ratio >= 0.65 or uniq >= 6:
            return "high"
        return "medium"
    return "medium"


def _proposal_from_candidate(
    candidate: Dict[str, Any],
    upgrade_type: str,
) -> Optional[Dict[str, Any]]:
    cid = str(candidate.get("candidateId") or "").strip()
    if not cid:
        return None
    ev = candidate.get("evidence")
    if not isinstance(ev, dict):
        ev = {}
    artifact = candidate.get("proposedArtifact")
    if not isinstance(artifact, dict):
        artifact = {}
    conf_raw = candidate.get("confidenceScore")
    try:
        confidence = float(conf_raw) if conf_raw is not None else 0.0
    except (TypeError, ValueError):
        confidence = 0.0
    conf_rounded = round(min(1.0, max(0.0, confidence)), 4)
    ec = _evidence_count(ev)

    strength = candidate.get("strength")
    strength_str = str(strength) if strength in ("strong", "moderate") else None

    proposal: Dict[str, Any] = {
        "sourceCandidateId": cid,
        "upgradeType": upgrade_type,
        "suggestedTargetArtifact": copy.deepcopy(artifact),
        "rationale": str(candidate.get("rationale") or ""),
        "supportingEvidenceSummary": _evidence_scalar_summary(ev),
        "reviewStatus": "pending",
        "priorityScore": _priority_score(conf_rounded, ec),
        "affectedBlockIds": _affected_block_ids(ev),
        "upgradeDifficulty": _upgrade_difficulty(upgrade_type, ev),
        "confidenceScore": conf_rounded,
    }
    if strength_str is not None:
        proposal["strength"] = strength_str
    return proposal


def build_candidate_upgrade_proposals(
    candidates: List[Dict[str, Any]],
    *,
    max_proposals_per_type: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Map promotion candidates into grouped, review-only upgrade proposals.

    Unknown candidate kinds are skipped (counted in meta).
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "proposedPredefinedOutcomes": [],
        "proposedSignalLabels": [],
        "proposedBranchExpansions": [],
        "proposedPhraseSignalMappings": [],
    }
    kind_to_bucket_key: Dict[str, str] = {
        "predefined_outcome_candidate": "proposedPredefinedOutcomes",
        "signal_label_candidate": "proposedSignalLabels",
        "branch_expansion_candidate": "proposedBranchExpansions",
        "phrase_signal_mapping_candidate": "proposedPhraseSignalMappings",
    }

    skipped_unknown = 0
    skipped_missing_id = 0
    skipped_non_object = 0

    for c in candidates:
        if not isinstance(c, dict):
            skipped_non_object += 1
            continue
        kind = str(c.get("kind") or "")
        bucket_key = kind_to_bucket_key.get(kind)
        upgrade_type = _KIND_TO_UPGRADE_TYPE.get(kind)
        if not bucket_key or not upgrade_type:
            skipped_unknown += 1
            continue
        prop = _proposal_from_candidate(c, upgrade_type)
        if prop is None:
            skipped_missing_id += 1
            continue
        buckets[bucket_key].append(prop)

    cap = max_proposals_per_type
    if cap is not None:
        cap = max(1, int(cap))

    result_lists: Dict[str, Any] = {}
    counts_returned: Dict[str, int] = {}
    for key, items in buckets.items():
        ordered = sorted(items, key=lambda p: str(p.get("sourceCandidateId") or ""))
        if cap is not None:
            ordered = ordered[:cap]
        result_lists[key] = ordered
        counts_returned[key] = len(ordered)

    meta = {
        "skippedUnknownKindCount": skipped_unknown,
        "skippedMissingCandidateIdCount": skipped_missing_id,
        "skippedNonObjectCount": skipped_non_object,
        "maxProposalsPerType": cap,
        "counts": counts_returned,
    }

    return {
        **result_lists,
        "meta": meta,
    }
