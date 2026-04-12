"""Deterministic execution outcome pattern mining (no DB for core logic)."""

from __future__ import annotations

from unittest.mock import patch

from services.execution_runtime.pattern_mining import (
    MIN_BLOCK_SAMPLES_FOR_DIVERSITY,
    MIN_PHRASE_COUNT,
    NOTE_DIVERSITY_RATIO_THRESHOLD,
    normalize_note_text,
    summarize_execution_outcome_patterns,
)


def test_normalize_note_text_collapses_and_lowercases():
    assert normalize_note_text("  Hello   World\n") == "hello world"
    assert normalize_note_text("") == ""


def test_summarize_clusters_and_ordering():
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
        {
            "runId": "r3",
            "blockId": "b2",
            "outcomeKey": "complete",
            "notes": "unique note here",
            "recordedAt": "2026-01-03T00:00:00Z",
            "externalFlagsSnapshot": {"notSure": True},
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

    assert out["recordsIncluded"] == 3
    clusters = {c["normalizedNote"]: c["count"] for c in out["exactNoteClusters"]}
    assert clusters["same text"] == 2
    assert clusters["unique note here"] == 1
    # sorted by (-count, normalizedNote): "same text" before "unique note here"
    assert out["exactNoteClusters"][0]["normalizedNote"] == "same text"
    samples = out["exactNoteClusters"][0]["samples"]
    assert samples[0]["runId"] == "r1" and samples[1]["runId"] == "r2"
    sn = out["exactNoteClusters"][0]["sampleNotes"]
    assert "same text" in sn and "SAME   TEXT" in sn

    by_block = {x["blockId"]: x["count"] for x in out["notesByBlockId"]}
    assert by_block["b1"] == 2 and by_block["b2"] == 1

    assert out["heuristics"]["completeWithNonIntentNotes"] == 3
    assert out["heuristics"]["notSureRateAmongNotes"] > 0


def test_phrases_require_min_count_two():
    rows = [
        {
            "runId": "r1",
            "blockId": "b1",
            "outcomeKey": "complete",
            "notes": "foo bar baz",
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
            "notes": "foo bar qux",
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
        out = summarize_execution_outcome_patterns(top_k=20)
    phrases = {(p["phrase"], p["n"]): p["count"] for p in out["topPhrases"]}
    assert ("foo bar", 2) in phrases
    assert phrases[("foo bar", 2)] >= MIN_PHRASE_COUNT
    singleton_phrases = [p for p in out["topPhrases"] if p["count"] < MIN_PHRASE_COUNT]
    assert singleton_phrases == []


def test_intent_prefix_excluded_from_complete_non_intent():
    rows = [
        {
            "runId": "r1",
            "blockId": "b1",
            "outcomeKey": "complete",
            "notes": "intent:could_not_complete",
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
            "notes": "real user words",
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
        out = summarize_execution_outcome_patterns()
    assert out["heuristics"]["completeWithNonIntentNotes"] == 1


def test_high_note_diversity_heuristic():
    # block bx: 5 rows, 3 distinct normalized notes -> ratio 0.6 >= threshold, total >= min samples
    notes_vals = ["a", "b", "a", "c", "a"]
    rows = []
    for i, n in enumerate(notes_vals):
        rows.append(
            {
                "runId": f"r{i}",
                "blockId": "bx",
                "outcomeKey": "complete",
                "notes": n,
                "recordedAt": f"2026-01-0{i+1}T00:00:00Z",
                "externalFlagsSnapshot": {},
                "workflowId": "wf",
                "userId": 1,
                "runCreatedAt": "",
                "runUpdatedAt": "",
                "matchedSignalTargetIds": [],
                "guidanceSchemaVersion": "",
                "playbookId": "",
                "playbookVersion": "",
            }
        )
    with patch(
        "services.execution_runtime.pattern_mining.list_execution_outcomes",
        return_value=rows,
    ):
        out = summarize_execution_outcome_patterns()
    div = out["heuristics"]["blocksWithHighNoteDiversity"]
    assert any(d["blockId"] == "bx" for d in div)
    bx = next(d for d in div if d["blockId"] == "bx")
    assert bx["totalNotes"] == MIN_BLOCK_SAMPLES_FOR_DIVERSITY
    assert bx["uniqueNotes"] == 3
    assert bx["diversityRatio"] >= NOTE_DIVERSITY_RATIO_THRESHOLD


def test_truncated_flag_when_at_cap():
    rows = [
        {
            "runId": f"r{i}",
            "blockId": "b1",
            "outcomeKey": "complete",
            "notes": f"n{i}",
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
        }
        for i in range(3)
    ]
    with patch(
        "services.execution_runtime.pattern_mining.list_execution_outcomes",
        return_value=rows,
    ):
        out = summarize_execution_outcome_patterns(max_notes_rows=3)
    assert out["truncated"] is True
    assert out["recordsIncluded"] == 3
