"""
Deterministic pattern summaries over execution outcome notes (operator tooling).

No ML, embeddings, or probabilistic clustering — counts, normalization, and n-grams only.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .outcomes_query import OUTCOME_FLAT_CAP, list_execution_outcomes

# --- Heuristic thresholds (inspectable, tunable) ---
MIN_BLOCK_SAMPLES_FOR_DIVERSITY = 5
NOTE_DIVERSITY_RATIO_THRESHOLD = 0.4
MAX_SAMPLES_PER_CLUSTER = 5
MIN_PHRASE_COUNT = 2

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "for",
        "from",
        "had",
        "has",
        "have",
        "i",
        "if",
        "in",
        "is",
        "it",
        "its",
        "me",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "so",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "with",
        "yes",
        "you",
        "your",
    }
)


def normalize_note_text(raw: str) -> str:
    """strip, collapse whitespace, lowercase (for clustering / phrases)."""
    t = (raw or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t.lower()


def _tokenize_for_phrases(normalized_note: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", normalized_note)


def _filtered_tokens(normalized_note: str) -> List[str]:
    return [w for w in _tokenize_for_phrases(normalized_note) if w and w not in _STOPWORDS]


def _add_ngrams(tokens: List[str], n: int, counts: Counter) -> None:
    if len(tokens) < n:
        return
    for i in range(0, len(tokens) - n + 1):
        phrase = " ".join(tokens[i : i + n])
        if phrase.strip():
            counts[(phrase, n)] += 1


def summarize_execution_outcome_patterns(
    *,
    workflow_id: Optional[str] = None,
    run_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    run_scan_limit: int = 200,
    max_notes_rows: int = OUTCOME_FLAT_CAP,
    top_k: int = 30,
) -> Dict[str, Any]:
    """
    Fetch ``user_reported`` outcomes with non-empty notes, then aggregate deterministically.
    """
    cap = max(1, min(int(max_notes_rows), OUTCOME_FLAT_CAP))
    scan = max(1, min(int(run_scan_limit), 500))
    tk = max(1, min(int(top_k), 200))

    rows = list_execution_outcomes(
        workflow_id=workflow_id,
        run_id=run_id,
        since=since,
        until=until,
        has_notes=True,
        source="user_reported",
        limit=scan,
        max_flat_rows=cap,
    )
    truncated = len(rows) >= cap

    by_block: Counter = Counter()
    by_outcome: Counter = Counter()
    cluster_samples: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    cluster_raw_notes: Dict[str, List[str]] = defaultdict(list)
    cluster_counts: Counter = Counter()

    phrase_counter: Counter = Counter()
    complete_non_intent = 0
    not_sure_hits = 0
    block_norm_sets: Dict[str, set] = defaultdict(set)
    block_totals: Dict[str, int] = defaultdict(int)

    for r in rows:
        original = str(r.get("notes") or "")
        norm = normalize_note_text(original)
        bid = str(r.get("blockId") or "")
        okey = str(r.get("outcomeKey") or "")
        by_block[bid] += 1
        by_outcome[okey] += 1

        if norm:
            cluster_counts[norm] += 1
            samples = cluster_samples[norm]
            if len(samples) < MAX_SAMPLES_PER_CLUSTER:
                samples.append(
                    {
                        "runId": str(r.get("runId") or ""),
                        "blockId": bid,
                        "recordedAt": str(r.get("recordedAt") or ""),
                    }
                )
            raws = cluster_raw_notes[norm]
            if original.strip() and len(raws) < MAX_SAMPLES_PER_CLUSTER and original not in raws:
                raws.append(original)

        toks = _filtered_tokens(norm)
        _add_ngrams(toks, 2, phrase_counter)
        _add_ngrams(toks, 3, phrase_counter)

        if okey == "complete" and norm:
            if not norm.startswith("intent:"):
                complete_non_intent += 1

        flags = r.get("externalFlagsSnapshot") or {}
        if isinstance(flags, dict) and flags.get("notSure") is True:
            not_sure_hits += 1

        if bid and norm:
            block_norm_sets[bid].add(norm)
            block_totals[bid] += 1

    def sort_counter_items(c: Counter) -> List[Tuple[str, int]]:
        items = [(k, int(v)) for k, v in c.items() if k]
        items.sort(key=lambda x: (-x[1], x[0]))
        return items[:tk]

    notes_by_block = [{"blockId": b, "count": n} for b, n in sort_counter_items(by_block)]
    notes_by_outcome = [{"outcomeKey": k, "count": n} for k, n in sort_counter_items(by_outcome)]

    exact_clusters: List[Dict[str, Any]] = []
    for norm in sorted(cluster_counts.keys()):
        cnt = cluster_counts[norm]
        samples = cluster_samples.get(norm, [])
        samples_sorted = sorted(
            samples,
            key=lambda s: (s.get("recordedAt") or "", s.get("runId") or "", s.get("blockId") or ""),
        )
        exact_clusters.append(
            {
                "normalizedNote": norm,
                "count": cnt,
                "samples": samples_sorted[:MAX_SAMPLES_PER_CLUSTER],
                "sampleNotes": list(cluster_raw_notes.get(norm, [])[:MAX_SAMPLES_PER_CLUSTER]),
            }
        )
    exact_clusters.sort(key=lambda x: (-x["count"], x["normalizedNote"]))
    exact_clusters = exact_clusters[:tk]

    phrase_list: List[Dict[str, Any]] = []
    for (phrase, ngram_n), c in phrase_counter.items():
        if c >= MIN_PHRASE_COUNT:
            phrase_list.append({"phrase": phrase, "n": ngram_n, "count": c})
    phrase_list.sort(key=lambda x: (-x["count"], x["phrase"], x["n"]))
    phrase_list = phrase_list[:tk]

    n_rows = len(rows)
    not_sure_rate = round(not_sure_hits / n_rows, 6) if n_rows else 0.0

    diversity_blocks: List[Dict[str, Any]] = []
    for bid, total in sorted(block_totals.items()):
        if total < MIN_BLOCK_SAMPLES_FOR_DIVERSITY:
            continue
        uniq = len(block_norm_sets.get(bid, set()))
        ratio = uniq / total if total else 0.0
        if ratio >= NOTE_DIVERSITY_RATIO_THRESHOLD:
            diversity_blocks.append(
                {
                    "blockId": bid,
                    "uniqueNotes": uniq,
                    "totalNotes": total,
                    "diversityRatio": round(ratio, 6),
                }
            )
    diversity_blocks.sort(key=lambda x: (-x["diversityRatio"], -x["totalNotes"], x["blockId"]))
    diversity_blocks = diversity_blocks[:tk]

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "generatedAt": generated_at,
        "filtersEcho": {
            "workflowId": workflow_id,
            "runId": run_id,
            "since": since,
            "until": until,
            "runScanLimit": scan,
            "maxNotesRows": cap,
            "topK": tk,
            "source": "user_reported",
            "hasNotes": True,
        },
        "recordsIncluded": n_rows,
        "truncated": truncated,
        "notesByBlockId": notes_by_block,
        "notesByOutcomeKey": notes_by_outcome,
        "exactNoteClusters": exact_clusters,
        "topPhrases": phrase_list,
        "heuristics": {
            "completeWithNonIntentNotes": complete_non_intent,
            "notSureRateAmongNotes": not_sure_rate,
            "blocksWithHighNoteDiversity": diversity_blocks,
        },
    }
