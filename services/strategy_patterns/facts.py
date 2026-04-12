"""
Derive a flat fact view from CanonicalCaseIntelligenceV1 for explicit matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set

from services.case_intelligence.models import CanonicalCaseIntelligenceV1


@dataclass(frozen=True)
class CaseFactSnapshot:
    contradiction_count: int
    contradiction_types: frozenset
    strategy_signal_names: frozenset
    case_type_summary: str
    multi_bureau_normalized_groups: int
    bureau_coverage_count: int
    documentation_sufficiency: str
    candidate_dispute_items: int
    total_review_claims: int
    letter_count_for_scope: int
    cumulative_disputed_count: int
    unresolved_dispute_count: int
    readiness_blockers: tuple
    objective_source: str


def build_case_fact_snapshot(ci: CanonicalCaseIntelligenceV1) -> CaseFactSnapshot:
    cs = ci.case_summary or {}
    try:
        cc = int(cs.get("contradictionCount") or 0)
    except (TypeError, ValueError):
        cc = 0
    try:
        mb = int(cs.get("multiBureauNormalizedGroups") or 0)
    except (TypeError, ValueError):
        mb = 0
    try:
        cand = int(cs.get("candidateDisputeItemsEligibleNow") or 0)
    except (TypeError, ValueError):
        cand = 0
    try:
        trc = int(cs.get("totalReviewClaims") or 0)
    except (TypeError, ValueError):
        trc = 0

    ctype = str(cs.get("caseTypeSummary") or "").strip().lower()

    c_types = frozenset(c.signal_type for c in ci.contradictions)
    sigs = frozenset(s.name for s in ci.strategy_signals)

    cov = ci.identity.get("bureauCoverage") or []
    bureau_n = 0
    if isinstance(cov, list):
        bureau_n = len([x for x in cov if isinstance(x, dict) and x.get("bureau")])

    doc_s = (ci.documentation.sufficiency or "unknown").strip().lower()

    ah = ci.action_history
    cum = len(ah.cumulative_disputed_review_claim_ids)
    unr = len(ah.unresolved_disputed_ids)

    blockers = tuple(sorted(ci.goal_constraints.readiness_blockers or []))
    obj_src = (ci.goal_constraints.objective_source or "unknown").strip().lower()

    return CaseFactSnapshot(
        contradiction_count=cc,
        contradiction_types=c_types,
        strategy_signal_names=sigs,
        case_type_summary=ctype,
        multi_bureau_normalized_groups=mb,
        bureau_coverage_count=bureau_n,
        documentation_sufficiency=doc_s,
        candidate_dispute_items=cand,
        total_review_claims=trc,
        letter_count_for_scope=int(ah.letter_count_for_scope or 0),
        cumulative_disputed_count=cum,
        unresolved_dispute_count=unr,
        readiness_blockers=blockers,
        objective_source=obj_src,
    )
