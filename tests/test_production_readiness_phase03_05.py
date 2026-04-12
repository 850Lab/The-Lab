"""
Production readiness — Phases 3–5: pattern mining, promotion, candidate upgrade mapping.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from services.execution_runtime.candidate_upgrade_mapping import (
    _priority_score,
    build_candidate_upgrade_proposals,
)
from services.execution_runtime.pattern_mining import summarize_execution_outcome_patterns
from services.execution_runtime.pattern_promotion import build_pattern_promotion_candidates


class TestPhase03PatternMining:
    def test_repeated_outcomes_cluster_same_normalized_note(self):
        rows = [
            {
                "runId": "r2",
                "blockId": "b1",
                "outcomeKey": "complete",
                "notes": "same text",
                "recordedAt": "2026-01-02T00:00:00Z",
                "externalFlagsSnapshot": {},
                "workflowId": "wf",
                "userId": 1,
                "runCreatedAt": "",
                "runUpdatedAt": "",
                "matchedSignalTargetIds": [],
                "guidanceSchemaVersion": "",
                "playbookId": "",
                "playbookVersion": "",
            },
            {
                "runId": "r1",
                "blockId": "b1",
                "outcomeKey": "complete",
                "notes": "SAME   TEXT",
                "recordedAt": "2026-01-01T00:00:00Z",
                "externalFlagsSnapshot": {},
                "workflowId": "wf",
                "userId": 1,
                "runCreatedAt": "",
                "runUpdatedAt": "",
                "matchedSignalTargetIds": [],
                "guidanceSchemaVersion": "",
                "playbookId": "",
                "playbookVersion": "",
            },
        ]
        with patch(
            "services.execution_runtime.pattern_mining.list_execution_outcomes",
            return_value=rows,
        ):
            a = summarize_execution_outcome_patterns(run_scan_limit=50, max_notes_rows=100, top_k=10)
            b = summarize_execution_outcome_patterns(run_scan_limit=50, max_notes_rows=100, top_k=10)

        def _strip_ts(d):
            d = dict(d)
            d.pop("generatedAt", None)
            return d

        assert _strip_ts(a) == _strip_ts(b)
        clusters = {c["normalizedNote"]: c["count"] for c in a["exactNoteClusters"]}
        assert clusters.get("same text") == 2

    def test_dissimilar_notes_do_not_share_exact_cluster(self):
        rows = [
            {
                "runId": "r1",
                "blockId": "b1",
                "outcomeKey": "complete",
                "notes": "alpha unique",
                "recordedAt": "2026-01-01T00:00:00Z",
                "externalFlagsSnapshot": {},
                "workflowId": "wf",
                "userId": 1,
                "runCreatedAt": "",
                "runUpdatedAt": "",
                "matchedSignalTargetIds": [],
                "guidanceSchemaVersion": "",
                "playbookId": "",
                "playbookVersion": "",
            },
            {
                "runId": "r2",
                "blockId": "b1",
                "outcomeKey": "complete",
                "notes": "beta unique",
                "recordedAt": "2026-01-02T00:00:00Z",
                "externalFlagsSnapshot": {},
                "workflowId": "wf",
                "userId": 1,
                "runCreatedAt": "",
                "runUpdatedAt": "",
                "matchedSignalTargetIds": [],
                "guidanceSchemaVersion": "",
                "playbookId": "",
                "playbookVersion": "",
            },
        ]
        with patch(
            "services.execution_runtime.pattern_mining.list_execution_outcomes",
            return_value=rows,
        ):
            out = summarize_execution_outcome_patterns(run_scan_limit=50, max_notes_rows=100, top_k=10)
        notes = {c["normalizedNote"] for c in out["exactNoteClusters"]}
        assert "alpha unique" in notes
        assert "beta unique" in notes
        assert not any(c["count"] > 1 for c in out["exactNoteClusters"])

    def test_mining_reproducible_from_same_rows(self):
        rows = [
            {
                "runId": "r1",
                "blockId": "b1",
                "outcomeKey": "skipped",
                "notes": "payment declined",
                "recordedAt": "2026-01-01T00:00:00Z",
                "externalFlagsSnapshot": {},
                "workflowId": "wf",
                "userId": 1,
                "runCreatedAt": "",
                "runUpdatedAt": "",
                "matchedSignalTargetIds": [],
                "guidanceSchemaVersion": "",
                "playbookId": "",
                "playbookVersion": "",
            },
        ]
        with patch(
            "services.execution_runtime.pattern_mining.list_execution_outcomes",
            return_value=rows,
        ):
            x = summarize_execution_outcome_patterns(run_scan_limit=10, max_notes_rows=50, top_k=5)
            y = summarize_execution_outcome_patterns(run_scan_limit=10, max_notes_rows=50, top_k=5)
        x.pop("generatedAt", None)
        y.pop("generatedAt", None)
        assert x == y


class TestPhase04PatternPromotion:
    def test_no_predefined_candidate_when_counts_below_threshold(self):
        summary = {
            "exactNoteClusters": [
                {
                    "normalizedNote": "rare note",
                    "count": 1,
                    "samples": [{"runId": "r1", "blockId": "b1", "recordedAt": "2026-01-01T00:00:00Z"}],
                    "sampleNotes": ["rare note"],
                }
            ],
            "topPhrases": [],
            "notesByOutcomeKey": [{"outcomeKey": "complete", "count": 1}],
            "heuristics": {"blocksWithHighNoteDiversity": []},
        }
        out = build_pattern_promotion_candidates(summary)
        kinds = [c["kind"] for c in out["candidates"]]
        assert "predefined_outcome_candidate" not in kinds

    def test_promotion_carries_traceable_samples(self):
        summary = {
            "exactNoteClusters": [
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
            ],
            "topPhrases": [],
            "notesByOutcomeKey": [
                {"outcomeKey": "complete", "count": 20},
                {"outcomeKey": "skipped", "count": 5},
            ],
            "heuristics": {"blocksWithHighNoteDiversity": []},
        }
        out = build_pattern_promotion_candidates(summary)
        pre = next(c for c in out["candidates"] if c["kind"] == "predefined_outcome_candidate")
        assert pre["evidence"]["normalizedNote"] == "payment declined"
        assert pre["evidence"]["count"] == 3
        run_ids = {s["runId"] for s in pre["evidence"].get("samples", [])}
        assert run_ids <= {"r1", "r2", "r3"}

    def test_intent_prefix_cluster_does_not_yield_predefined_promotion(self):
        summary = {
            "exactNoteClusters": [
                {
                    "normalizedNote": "intent:could_not_complete",
                    "count": 5,
                    "samples": [],
                    "sampleNotes": [],
                }
            ],
            "topPhrases": [],
            "notesByOutcomeKey": [
                {"outcomeKey": "complete", "count": 3},
                {"outcomeKey": "error", "count": 10},
            ],
            "heuristics": {"blocksWithHighNoteDiversity": []},
        }
        out = build_pattern_promotion_candidates(summary)
        assert all(c["kind"] != "predefined_outcome_candidate" for c in out["candidates"])


class TestPhase05CandidateUpgradeMapping:
    def test_proposals_contain_structured_evidence_summary_fields(self):
        cands = [
            {
                "candidateId": "s1",
                "kind": "signal_label_candidate",
                "evidence": {"count": 5, "phrase": "foo bar baz", "n": 3},
                "proposedArtifact": {"type": "signal_label", "suggestedSignalId": "phrase_x"},
                "confidenceScore": 0.8,
                "strength": "strong",
                "rationale": "freq",
            }
        ]
        out = build_candidate_upgrade_proposals(cands)
        sig = out["proposedSignalLabels"][0]
        assert "supportingEvidenceSummary" in sig
        assert "phrase=foo bar baz" in sig["supportingEvidenceSummary"]

    def test_priority_score_deterministic(self):
        assert _priority_score(0.9, 10) == _priority_score(0.9, 10)
        assert _priority_score(0.9, 20) > _priority_score(0.9, 0)

    def test_same_candidates_same_proposal_bundle(self):
        cands = [
            {
                "candidateId": "p1",
                "kind": "predefined_outcome_candidate",
                "evidence": {"count": 3},
                "proposedArtifact": {"type": "predefined_outcome", "suggestedKey": "k"},
                "confidenceScore": 0.7,
                "strength": "strong",
                "rationale": "x",
            }
        ]
        a = build_candidate_upgrade_proposals(cands)
        b = build_candidate_upgrade_proposals(cands)
        assert a == b
