"""Candidate upgrade mapping: pure transform, review-only."""

from __future__ import annotations

import json

import pytest

from services.execution_runtime.candidate_upgrade_mapping import (
    _priority_score,
    build_candidate_upgrade_proposals,
)


def _minimal_candidate(
    *,
    kind: str,
    candidate_id: str,
    upgrade_evidence: dict | None = None,
    proposed: dict | None = None,
    confidence: float = 0.7,
    strength: str = "strong",
    rationale: str = "because",
) -> dict:
    ev = upgrade_evidence if upgrade_evidence is not None else {"count": 3}
    return {
        "candidateId": candidate_id,
        "kind": kind,
        "evidence": ev,
        "proposedArtifact": proposed or {"type": "x"},
        "confidenceScore": confidence,
        "strength": strength,
        "rationale": rationale,
    }


def test_maps_each_kind_to_correct_bucket():
    cands = [
        _minimal_candidate(
            kind="predefined_outcome_candidate",
            candidate_id="p1",
            proposed={"type": "predefined_outcome", "suggestedKey": "k"},
        ),
        _minimal_candidate(
            kind="signal_label_candidate",
            candidate_id="s1",
            proposed={"type": "signal_label", "suggestedSignalId": "sig"},
            upgrade_evidence={"count": 5, "phrase": "a b c", "n": 3},
        ),
        _minimal_candidate(
            kind="branch_expansion_candidate",
            candidate_id="b1",
            proposed={"type": "branch_expansion", "blockId": "bx"},
            upgrade_evidence={
                "count": 4,
                "blockId": "bx",
                "diversityRatio": 0.5,
                "totalNotes": 8,
            },
        ),
        _minimal_candidate(
            kind="phrase_signal_mapping_candidate",
            candidate_id="m1",
            proposed={"type": "phrase_signal_mapping", "phrase": "a b c"},
            upgrade_evidence={"count": 3, "phrase": "a b c", "normalizedNote": "x"},
        ),
    ]
    out = build_candidate_upgrade_proposals(cands)
    assert len(out["proposedPredefinedOutcomes"]) == 1
    assert len(out["proposedSignalLabels"]) == 1
    assert len(out["proposedBranchExpansions"]) == 1
    assert len(out["proposedPhraseSignalMappings"]) == 1

    pre = out["proposedPredefinedOutcomes"][0]
    assert pre["sourceCandidateId"] == "p1"
    assert pre["upgradeType"] == "predefined_outcome"
    assert pre["reviewStatus"] == "pending"
    assert pre["suggestedTargetArtifact"]["suggestedKey"] == "k"
    assert pre["strength"] == "strong"
    assert 0.0 <= pre["confidenceScore"] <= 1.0

    sig = out["proposedSignalLabels"][0]
    assert sig["upgradeType"] == "signal_label"
    assert sig["upgradeDifficulty"] == "low"
    assert "phrase=a b c" in sig["supportingEvidenceSummary"]

    br = out["proposedBranchExpansions"][0]
    assert br["upgradeType"] == "branch_expansion"
    assert br["affectedBlockIds"] == ["bx"]
    assert br["upgradeDifficulty"] == "medium"

    mp = out["proposedPhraseSignalMappings"][0]
    assert mp["upgradeType"] == "phrase_signal_mapping"
    assert mp["upgradeDifficulty"] == "medium"
    assert mp["affectedBlockIds"] == []


def test_unknown_kind_skipped_and_meta_counted():
    out = build_candidate_upgrade_proposals(
        [
            _minimal_candidate(
                kind="predefined_outcome_candidate",
                candidate_id="ok",
            ),
            {"kind": "weird_kind", "candidateId": "x"},
            {"kind": "", "candidateId": "y"},
            "not-a-dict",
        ]
    )
    assert out["meta"]["skippedUnknownKindCount"] == 2
    assert out["meta"]["skippedNonObjectCount"] == 1
    assert len(out["proposedPredefinedOutcomes"]) == 1


def test_missing_candidate_id_skipped():
    out = build_candidate_upgrade_proposals(
        [
            {
                "kind": "predefined_outcome_candidate",
                "candidateId": "",
                "evidence": {"count": 1},
                "proposedArtifact": {},
                "rationale": "",
            }
        ]
    )
    assert out["meta"]["skippedMissingCandidateIdCount"] == 1
    assert out["proposedPredefinedOutcomes"] == []


def test_ordering_by_source_candidate_id():
    out = build_candidate_upgrade_proposals(
        [
            _minimal_candidate(
                kind="signal_label_candidate",
                candidate_id="zzz",
            ),
            _minimal_candidate(
                kind="signal_label_candidate",
                candidate_id="aaa",
            ),
        ]
    )
    ids = [p["sourceCandidateId"] for p in out["proposedSignalLabels"]]
    assert ids == ["aaa", "zzz"]


def test_truncation_max_proposals_per_type():
    out = build_candidate_upgrade_proposals(
        [
            _minimal_candidate(kind="signal_label_candidate", candidate_id=f"s{i}")
            for i in range(5)
        ],
        max_proposals_per_type=2,
    )
    assert len(out["proposedSignalLabels"]) == 2
    assert out["meta"]["maxProposalsPerType"] == 2


def test_deterministic_json():
    cands = [
        _minimal_candidate(kind="branch_expansion_candidate", candidate_id="b2"),
        _minimal_candidate(kind="signal_label_candidate", candidate_id="s2"),
    ]
    a = json.dumps(build_candidate_upgrade_proposals(cands), sort_keys=True)
    b = json.dumps(build_candidate_upgrade_proposals(cands), sort_keys=True)
    assert a == b


def test_priority_score_formula():
    assert _priority_score(0.5, 0) == pytest.approx(0.5)
    assert _priority_score(0.8, 50) == pytest.approx(1.8)
    assert _priority_score(0.0, 25) == pytest.approx(1.0)


def test_supporting_evidence_summary_sorted_keys():
    out = build_candidate_upgrade_proposals(
        [
            _minimal_candidate(
                kind="predefined_outcome_candidate",
                candidate_id="p9",
                upgrade_evidence={"zebra": 1, "alpha": 2, "count": 1},
            )
        ]
    )
    summary = out["proposedPredefinedOutcomes"][0]["supportingEvidenceSummary"]
    assert summary.startswith("alpha=2; count=1; zebra=1")


def test_branch_high_difficulty_when_ratio_high():
    out = build_candidate_upgrade_proposals(
        [
            _minimal_candidate(
                kind="branch_expansion_candidate",
                candidate_id="bh",
                upgrade_evidence={
                    "count": 3,
                    "blockId": "b1",
                    "diversityRatio": 0.7,
                    "totalNotes": 10,
                },
            )
        ]
    )
    assert out["proposedBranchExpansions"][0]["upgradeDifficulty"] == "high"
