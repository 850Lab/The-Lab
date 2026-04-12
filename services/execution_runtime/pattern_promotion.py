"""
Pattern promotion / candidate signals — review-only suggestions from pattern_summary.

Does not modify execution runtime or playbooks. No ML.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

def _slugify(text: str, max_len: int = 48) -> str:
    t = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return (t[:max_len] if t else "item")


def _candidate_id(kind: str, *parts: str) -> str:
    payload = "|".join(str(p) for p in parts)
    h = hashlib.sha256(f"{kind}|{payload}".encode("utf-8")).hexdigest()[:16]
    return f"{kind[:4]}_{h}"


def _first_last_from_samples(samples: List[Dict[str, Any]]) -> Tuple[str, str]:
    dates = sorted(
        str(s.get("recordedAt") or "")
        for s in samples
        if s.get("recordedAt")
    )
    if not dates:
        return "", ""
    return dates[0], dates[-1]


def _complete_dominates(notes_by_outcome: List[Dict[str, Any]]) -> bool:
    total = sum(int(x.get("count") or 0) for x in notes_by_outcome)
    if total <= 0:
        return False
    complete = next(
        (int(x.get("count") or 0) for x in notes_by_outcome if x.get("outcomeKey") == "complete"),
        0,
    )
    return complete >= total * 0.5


def _confidence_predefined(cluster_count: int, min_cluster: int) -> float:
    if cluster_count <= 0:
        return 0.0
    ratio = min(1.0, cluster_count / max(min_cluster * 3, 1))
    return round(min(0.95, 0.45 + 0.5 * ratio), 4)


def _confidence_signal(phrase_count: int, n: int, min_phrase: int) -> float:
    base = 0.4 if n >= 3 else 0.35
    ratio = min(1.0, phrase_count / max(min_phrase * 4, 1))
    bonus = 0.08 if n >= 3 else 0.0
    return round(min(0.92, base + 0.45 * ratio + bonus), 4)


def _confidence_branch(diversity_ratio: float) -> float:
    return round(min(0.9, 0.5 + 0.4 * min(1.0, diversity_ratio)), 4)


def _confidence_mapping(phrase_count: int, cluster_count: int, min_phrase: int, min_cluster: int) -> float:
    pc = min(1.0, phrase_count / max(min_phrase * 3, 1))
    cc = min(1.0, cluster_count / max(min_cluster * 3, 1))
    return round(min(0.88, 0.42 + 0.28 * pc + 0.28 * cc), 4)


def _sort_candidates(cands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stable ordering: (-evidence.count, kind, candidateId)."""

    def key(c: Dict[str, Any]) -> Tuple[int, str, str]:
        ev = c.get("evidence") or {}
        cnt = int(ev.get("count") or 0)
        kind = str(c.get("kind") or "")
        return (-cnt, kind, str(c.get("candidateId") or ""))

    return sorted(cands, key=key)


def _cap_per_kind(
    cands: List[Dict[str, Any]], max_per: int
) -> List[Dict[str, Any]]:
    by_kind: Dict[str, List[Dict[str, Any]]] = {}
    for c in cands:
        k = str(c.get("kind") or "")
        by_kind.setdefault(k, []).append(c)
    out: List[Dict[str, Any]] = []
    for _k, lst in sorted(by_kind.items(), key=lambda x: x[0]):
        ranked = _sort_candidates(lst)
        out.extend(ranked[:max_per])
    return out


def build_pattern_promotion_candidates(
    pattern_summary: Dict[str, Any],
    *,
    min_cluster_count: int = 3,
    min_phrase_count: int = 3,
    max_candidates_per_kind: int = 50,
) -> Dict[str, Any]:
    """
    Build review-only promotion candidates from pattern_summary only (no DB).
    """
    clusters = list(pattern_summary.get("exactNoteClusters") or [])
    top_phrases = list(pattern_summary.get("topPhrases") or [])
    notes_by_outcome = list(pattern_summary.get("notesByOutcomeKey") or [])
    heur = pattern_summary.get("heuristics") or {}
    diversity_blocks = list(heur.get("blocksWithHighNoteDiversity") or [])

    predefined: List[Dict[str, Any]] = []
    for cl in clusters:
        norm = str(cl.get("normalizedNote") or "")
        cnt = int(cl.get("count") or 0)
        if cnt < min_cluster_count:
            continue
        if norm.lower().startswith("intent:"):
            continue
        if not _complete_dominates(notes_by_outcome):
            continue
        samples = list(cl.get("samples") or [])
        sample_notes = list(cl.get("sampleNotes") or [])
        first_seen, last_seen = _first_last_from_samples(samples)
        slug = _slugify(norm)
        cid = _candidate_id("pre", norm, str(cnt))
        conf = _confidence_predefined(cnt, min_cluster_count)
        strength = "strong" if conf >= 0.72 else "moderate"
        predefined.append(
            {
                "candidateId": cid,
                "kind": "predefined_outcome_candidate",
                "strength": strength,
                "confidenceScore": conf,
                "title": f'Predefined outcome for note cluster "{slug}"',
                "rationale": (
                    f'Cluster "{norm}" appears {cnt} times with "complete" as the dominant '
                    "outcome in this window; consider a named predefined outcome to reduce ambiguity."
                ),
                "evidence": {
                    "count": cnt,
                    "normalizedNote": norm,
                    "outcomeKeyHint": "complete",
                },
                "proposedArtifact": {
                    "type": "predefined_outcome",
                    "suggestedKey": f"cluster_{slug}",
                    "normalizedNote": norm,
                },
                "sampleNotes": sample_notes[:5],
                "firstSeenAt": first_seen,
                "lastSeenAt": last_seen,
            }
        )

    signals: List[Dict[str, Any]] = []
    for ph in top_phrases:
        phrase = str(ph.get("phrase") or "")
        pc = int(ph.get("count") or 0)
        n = int(ph.get("n") or 0)
        if pc < min_phrase_count:
            continue
        if n == 3:
            pass
        elif n == 2 and pc >= min_phrase_count + 3:
            pass
        else:
            continue
        cid = _candidate_id("sig", phrase, str(n), str(pc))
        conf = _confidence_signal(pc, n, min_phrase_count)
        strength = "strong" if n >= 3 and conf >= 0.65 else "moderate"
        sig_id = f"phrase_{_slugify(phrase.replace(' ', '_'))}"
        signals.append(
            {
                "candidateId": cid,
                "kind": "signal_label_candidate",
                "strength": strength,
                "confidenceScore": conf,
                "title": f'Signal label for phrase "{phrase}"',
                "rationale": (
                    f'Phrase "{phrase}" (n={n}) recurs {pc} times; consider promoting it to a '
                    "first-class signal label for routing or analytics alignment."
                ),
                "evidence": {"count": pc, "phrase": phrase, "n": n},
                "proposedArtifact": {
                    "type": "signal_label",
                    "suggestedSignalId": sig_id,
                    "phrase": phrase,
                    "n": n,
                },
                "sampleNotes": [],
                "firstSeenAt": "",
                "lastSeenAt": "",
            }
        )

    branches: List[Dict[str, Any]] = []
    for div in diversity_blocks:
        bid = str(div.get("blockId") or "")
        ratio = float(div.get("diversityRatio") or 0.0)
        n_notes = int(div.get("uniqueNotes") or 0)
        total_notes = int(div.get("totalNotes") or 0)
        cid = _candidate_id("br", bid, str(n_notes), str(total_notes))
        conf = _confidence_branch(ratio)
        strength = "strong" if ratio >= 0.65 else "moderate"
        branches.append(
            {
                "candidateId": cid,
                "kind": "branch_expansion_candidate",
                "strength": strength,
                "confidenceScore": conf,
                "title": f"Branch expansion for block {bid}",
                "rationale": (
                    f"Block {bid} shows high distinct-note diversity ({n_notes} distinct notes / "
                    f"{total_notes} total, ratio {ratio:.2f}); consider explicit branches or sub-outcomes."
                ),
                "evidence": {
                    "count": n_notes,
                    "blockId": bid,
                    "diversityRatio": ratio,
                    "totalNotes": total_notes,
                },
                "proposedArtifact": {
                    "type": "branch_expansion",
                    "blockId": bid,
                    "uniqueNotes": n_notes,
                },
                "sampleNotes": [],
                "firstSeenAt": "",
                "lastSeenAt": "",
            }
        )

    sorted_clusters = sorted(
        clusters,
        key=lambda c: (-int(c.get("count") or 0), str(c.get("normalizedNote") or "")),
    )

    mappings: List[Dict[str, Any]] = []
    for ph in top_phrases:
        phrase = str(ph.get("phrase") or "")
        pc = int(ph.get("count") or 0)
        n = int(ph.get("n") or 0)
        if pc < min_phrase_count or n != 3:
            continue
        needle = phrase.lower().strip()
        if len(needle) < 2:
            continue
        chosen: Optional[Dict[str, Any]] = None
        for cl in sorted_clusters:
            norm = str(cl.get("normalizedNote") or "").lower()
            if needle in norm:
                chosen = cl
                break
        if not chosen:
            continue
        norm = str(chosen.get("normalizedNote") or "")
        cc = int(chosen.get("count") or 0)
        if cc < min_cluster_count:
            continue
        samples = list(chosen.get("samples") or [])
        sample_notes = list(chosen.get("sampleNotes") or [])
        first_seen, last_seen = _first_last_from_samples(samples)
        cid = _candidate_id("map", phrase, norm, str(pc), str(cc))
        conf = _confidence_mapping(pc, cc, min_phrase_count, min_cluster_count)
        strength = "strong" if conf >= 0.68 else "moderate"
        sig_id = f"phrase_{_slugify(phrase.replace(' ', '_'))}"
        mappings.append(
            {
                "candidateId": cid,
                "kind": "phrase_signal_mapping_candidate",
                "strength": strength,
                "confidenceScore": conf,
                "title": f'Map phrase "{phrase}" to signal on cluster',
                "rationale": (
                    f'Phrase "{phrase}" appears in normalized cluster note; link phrase to signal '
                    f'"{sig_id}" for consistent handling.'
                ),
                "evidence": {
                    "count": min(pc, cc),
                    "phrase": phrase,
                    "normalizedNote": norm,
                    "phraseCount": pc,
                    "clusterCount": cc,
                },
                "proposedArtifact": {
                    "type": "phrase_signal_mapping",
                    "phrase": phrase,
                    "signalId": sig_id,
                    "normalizedNote": norm,
                },
                "sampleNotes": sample_notes[:5],
                "firstSeenAt": first_seen,
                "lastSeenAt": last_seen,
            }
        )

    merged = predefined + signals + branches + mappings
    merged = _cap_per_kind(merged, max_candidates_per_kind)
    ordered = _sort_candidates(merged)

    returned_by_kind = Counter(str(c.get("kind") or "") for c in ordered)

    return {
        "candidates": ordered,
        "meta": {
            "minClusterCount": min_cluster_count,
            "minPhraseCount": min_phrase_count,
            "maxCandidatesPerKind": max_candidates_per_kind,
            "countsByKind": dict(returned_by_kind),
        },
    }
