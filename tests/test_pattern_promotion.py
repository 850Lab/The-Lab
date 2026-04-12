"""Pattern promotion candidates: deterministic, review-only (no runtime writes)."""

from __future__ import annotations

import copy
import json

from services.execution_runtime.pattern_promotion import build_pattern_promotion_candidates


def _base_summary() -> dict:
    return {
        "exactNoteClusters": [],
        "topPhrases": [],
        "notesByOutcomeKey": [
            {"outcomeKey": "complete", "count": 20},
            {"outcomeKey": "skipped", "count": 5},
        ],
        "heuristics": {"blocksWithHighNoteDiversity": []},
    }


def test_predefined_outcome_candidate_when_complete_dominates():
    summary = _base_summary()
    summary["exactNoteClusters"] = [
        {
            "normalizedNote": "payment declined",
            "count": 3,
            "samples": [
                {"runId": "r1", "blockId": "b1", "recordedAt": "2026-01-01T00:00:00Z"},
                {"runId": "r2", "blockId": "b1", "recordedAt": "2026-01-03T00:00:00Z"},
                {"runId": "r3", "blockId": "b1", "recordedAt": "2026-01-02T00:00:00Z"},
            ],
            "sampleNotes": ["Payment declined", "payment declined", "PAYMENT declined"],
        }
    ]
    out = build_pattern_promotion_candidates(summary)
    kinds = [c["kind"] for c in out["candidates"]]
    assert "predefined_outcome_candidate" in kinds
    pre = next(c for c in out["candidates"] if c["kind"] == "predefined_outcome_candidate")
    assert pre["strength"] in ("strong", "moderate")
    assert 0.0 <= pre["confidenceScore"] <= 1.0
    assert pre["evidence"]["normalizedNote"] == "payment declined"
    assert pre["evidence"]["count"] == 3
    assert len(pre["sampleNotes"]) >= 1
    assert pre["firstSeenAt"] == "2026-01-01T00:00:00Z"
    assert pre["lastSeenAt"] == "2026-01-03T00:00:00Z"
    assert pre["proposedArtifact"]["type"] == "predefined_outcome"


def test_predefined_skips_intent_prefix_and_incomplete_dominance():
    summary = _base_summary()
    summary["notesByOutcomeKey"] = [
        {"outcomeKey": "complete", "count": 3},
        {"outcomeKey": "error", "count": 10},
    ]
    summary["exactNoteClusters"] = [
        {
            "normalizedNote": "intent:could_not_complete",
            "count": 5,
            "samples": [],
            "sampleNotes": [],
        },
        {
            "normalizedNote": "ok note",
            "count": 5,
            "samples": [],
            "sampleNotes": ["ok"],
        },
    ]
    out = build_pattern_promotion_candidates(summary)
    assert all(c["kind"] != "predefined_outcome_candidate" for c in out["candidates"])


def test_signal_label_candidate_trigram_preferred():
    summary = _base_summary()
    summary["topPhrases"] = [{"phrase": "foo bar baz", "n": 3, "count": 4}]
    out = build_pattern_promotion_candidates(summary, min_phrase_count=3)
    sig = [c for c in out["candidates"] if c["kind"] == "signal_label_candidate"]
    assert len(sig) == 1
    assert sig[0]["evidence"]["phrase"] == "foo bar baz"
    assert sig[0]["evidence"]["n"] == 3
    assert sig[0]["proposedArtifact"]["suggestedSignalId"].startswith("phrase_")


def test_signal_label_bigram_moderate_bar():
    summary = _base_summary()
    summary["topPhrases"] = [{"phrase": "foo bar", "n": 2, "count": 6}]
    out = build_pattern_promotion_candidates(summary, min_phrase_count=3)
    sig = [c for c in out["candidates"] if c["kind"] == "signal_label_candidate"]
    assert len(sig) == 1
    assert sig[0]["strength"] == "moderate"


def test_branch_expansion_from_diversity_blocks():
    summary = _base_summary()
    summary["heuristics"]["blocksWithHighNoteDiversity"] = [
        {
            "blockId": "bx",
            "uniqueNotes": 4,
            "totalNotes": 8,
            "diversityRatio": 0.5,
        }
    ]
    out = build_pattern_promotion_candidates(summary)
    br = [c for c in out["candidates"] if c["kind"] == "branch_expansion_candidate"]
    assert len(br) == 1
    assert br[0]["evidence"]["blockId"] == "bx"
    assert br[0]["evidence"]["count"] == 4


def test_phrase_signal_mapping_deterministic_cluster():
    summary = _base_summary()
    summary["exactNoteClusters"] = [
        {
            "normalizedNote": "later user payment failed here",
            "count": 2,
            "samples": [{"runId": "r1", "blockId": "b1", "recordedAt": "2026-01-05T00:00:00Z"}],
            "sampleNotes": ["raw a"],
        },
        {
            "normalizedNote": "user payment failed today",
            "count": 5,
            "samples": [{"runId": "r2", "blockId": "b1", "recordedAt": "2026-01-06T00:00:00Z"}],
            "sampleNotes": ["User payment failed today"],
        },
    ]
    summary["topPhrases"] = [{"phrase": "user payment failed", "n": 3, "count": 5}]
    out = build_pattern_promotion_candidates(summary)
    maps = [c for c in out["candidates"] if c["kind"] == "phrase_signal_mapping_candidate"]
    assert len(maps) == 1
    assert maps[0]["evidence"]["normalizedNote"] == "user payment failed today"
    assert maps[0]["sampleNotes"] == ["User payment failed today"]


def test_stable_ordering_by_evidence_count_kind_candidate_id():
    summary = _base_summary()
    summary["heuristics"]["blocksWithHighNoteDiversity"] = [
        {
            "blockId": "b_low",
            "uniqueNotes": 3,
            "totalNotes": 6,
            "diversityRatio": 0.5,
        },
    ]
    summary["topPhrases"] = [{"phrase": "x y z", "n": 3, "count": 3}]
    out = build_pattern_promotion_candidates(summary, min_phrase_count=3)
    ids_a = [c["candidateId"] for c in out["candidates"]]
    out2 = build_pattern_promotion_candidates(summary, min_phrase_count=3)
    ids_b = [c["candidateId"] for c in out2["candidates"]]
    assert ids_a == ids_b
    keys = [
        (-(c["evidence"].get("count") or 0), c["kind"], c["candidateId"])
        for c in out["candidates"]
    ]
    assert keys == sorted(keys)


def test_min_cluster_threshold_drops_predefined():
    summary = _base_summary()
    summary["exactNoteClusters"] = [
        {
            "normalizedNote": "rare",
            "count": 2,
            "samples": [],
            "sampleNotes": ["rare", "rare"],
        }
    ]
    out = build_pattern_promotion_candidates(summary, min_cluster_count=3)
    assert all(c["kind"] != "predefined_outcome_candidate" for c in out["candidates"])


def test_max_candidates_per_kind_cap():
    summary = _base_summary()
    summary["exactNoteClusters"] = [
        {
            "normalizedNote": f"note {i}",
            "count": 4,
            "samples": [],
            "sampleNotes": [f"raw {i}"],
        }
        for i in range(3)
    ]
    out = build_pattern_promotion_candidates(summary, max_candidates_per_kind=2)
    pres = [c for c in out["candidates"] if c["kind"] == "predefined_outcome_candidate"]
    assert len(pres) <= 2


def test_json_serialization_determinism():
    summary = _base_summary()
    summary["topPhrases"] = [{"phrase": "a b c", "n": 3, "count": 3}]
    a = json.dumps(
        build_pattern_promotion_candidates(summary, min_phrase_count=3),
        sort_keys=True,
    )
    b = json.dumps(
        build_pattern_promotion_candidates(summary, min_phrase_count=3),
        sort_keys=True,
    )
    assert a == b
