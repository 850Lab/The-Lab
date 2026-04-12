"""
Evaluate RequirementSpec / ExclusionSpec against CaseFactSnapshot.
"""

from __future__ import annotations

from typing import List, Tuple

from .facts import CaseFactSnapshot
from .models import ExclusionOperator, ExclusionSpec, RequirementOperator, RequirementSpec


def _case_summary_int(facts: CaseFactSnapshot, key: str) -> int:
    mapping = {
        "contradictionCount": facts.contradiction_count,
        "multiBureauNormalizedGroups": facts.multi_bureau_normalized_groups,
        "candidateDisputeItemsEligibleNow": facts.candidate_dispute_items,
        "totalReviewClaims": facts.total_review_claims,
        "letterCountForScope": facts.letter_count_for_scope,
        "cumulativeDisputedCount": facts.cumulative_disputed_count,
        "unresolvedDisputeCount": facts.unresolved_dispute_count,
        "bureauCoverageCount": facts.bureau_coverage_count,
    }
    return int(mapping.get(key, 0))


def evaluate_requirement(
    facts: CaseFactSnapshot,
    req: RequirementSpec,
) -> Tuple[bool, str]:
    op = req.op
    if op == RequirementOperator.MIN_INT:
        cur = _case_summary_int(facts, req.field)
        need = int(req.value)
        ok = cur >= need
        return ok, f"{req.req_id}: {req.field} ({cur}) >= {need}" if ok else f"{req.req_id}: need {req.field}>={need}, got {cur}"

    if op == RequirementOperator.MAX_INT:
        cur = _case_summary_int(facts, req.field)
        need = int(req.value)
        ok = cur <= need
        return ok, f"{req.req_id}: {req.field} ({cur}) <= {need}" if ok else f"{req.req_id}: need {req.field}<={need}, got {cur}"

    if op == RequirementOperator.HAS_ANY_CONTRADICTION_TYPE:
        want = req.value
        if isinstance(want, (list, tuple)):
            types = [str(x).strip() for x in want]
        else:
            types = [str(want).strip()]
        hit = [t for t in types if t in facts.contradiction_types]
        ok = len(hit) > 0
        return ok, (
            f"{req.req_id}: contradiction types include {hit}"
            if ok
            else f"{req.req_id}: none of {types} in {sorted(facts.contradiction_types)}"
        )

    if op == RequirementOperator.HAS_ANY_STRATEGY_SIGNAL:
        want = req.value
        if isinstance(want, (list, tuple)):
            needles = [str(x).strip().lower() for x in want if str(x).strip()]
        else:
            needles = [str(want).strip().lower()]
        hits: List[str] = []
        for name in facts.strategy_signal_names:
            nl = name.lower()
            for nd in needles:
                if nd in nl:
                    hits.append(name)
                    break
        ok = len(hits) > 0
        return ok, (
            f"{req.req_id}: matched signals {hits}"
            if ok
            else f"{req.req_id}: no signal containing any of {needles}"
        )

    if op == RequirementOperator.DOCUMENTATION_IN:
        allowed = {str(x).lower() for x in (req.value if isinstance(req.value, (list, tuple)) else [req.value])}
        ok = facts.documentation_sufficiency in allowed
        return ok, (
            f"{req.req_id}: doc sufficiency {facts.documentation_sufficiency} in {sorted(allowed)}"
            if ok
            else f"{req.req_id}: doc {facts.documentation_sufficiency} not in {sorted(allowed)}"
        )

    if op == RequirementOperator.DOCUMENTATION_NOT_IN:
        forbidden = {str(x).lower() for x in (req.value if isinstance(req.value, (list, tuple)) else [req.value])}
        ok = facts.documentation_sufficiency not in forbidden
        return ok, (
            f"{req.req_id}: doc {facts.documentation_sufficiency} not in forbidden"
            if ok
            else f"{req.req_id}: doc {facts.documentation_sufficiency} is forbidden"
        )

    if op == RequirementOperator.CASE_TYPE_SUMMARY_ONE_OF:
        options = {str(x).lower() for x in (req.value if isinstance(req.value, (list, tuple)) else [req.value])}
        ok = facts.case_type_summary in options
        return ok, (
            f"{req.req_id}: case type {facts.case_type_summary!r} in {sorted(options)}"
            if ok
            else f"{req.req_id}: case type {facts.case_type_summary!r} not in {sorted(options)}"
        )

    if op == RequirementOperator.CASE_TYPE_SUMMARY_CONTAINS_ANY:
        subs = [str(x).lower() for x in (req.value if isinstance(req.value, (list, tuple)) else [req.value])]
        hit = [s for s in subs if s in facts.case_type_summary]
        ok = len(hit) > 0
        return ok, (
            f"{req.req_id}: case type contains {hit}"
            if ok
            else f"{req.req_id}: case type {facts.case_type_summary!r} lacks {subs}"
        )

    if op == RequirementOperator.MIN_BUREAU_COVERAGE_COUNT:
        need = int(req.value)
        ok = facts.bureau_coverage_count >= need
        return ok, (
            f"{req.req_id}: bureau coverage {facts.bureau_coverage_count}>={need}"
            if ok
            else f"{req.req_id}: bureau coverage {facts.bureau_coverage_count}<{need}"
        )

    if op == RequirementOperator.READINESS_BLOCKER_ABSENT:
        blocker = str(req.value).strip()
        ok = blocker not in facts.readiness_blockers
        return ok, (
            f"{req.req_id}: blocker {blocker!r} absent"
            if ok
            else f"{req.req_id}: blocker {blocker!r} present"
        )

    return False, f"{req.req_id}: unknown op {op}"


def evaluate_exclusion(facts: CaseFactSnapshot, ex: ExclusionSpec) -> Tuple[bool, str]:
    """Returns (fires_exclusion, reason). If fires_exclusion True, pattern is suppressed."""

    op = ex.op
    if op == ExclusionOperator.DOCUMENTATION_IN:
        bad = {str(x).lower() for x in (ex.value if isinstance(ex.value, (list, tuple)) else [ex.value])}
        fires = facts.documentation_sufficiency in bad
        return fires, f"{ex.ex_id}: doc {facts.documentation_sufficiency} in excluded set {sorted(bad)}"

    if op == ExclusionOperator.NO_CANDIDATE_DISPUTES:
        fires = facts.candidate_dispute_items <= 0
        return fires, f"{ex.ex_id}: candidate disputes {facts.candidate_dispute_items}"

    if op == ExclusionOperator.HAS_READINESS_BLOCKER:
        b = str(ex.value).strip()
        fires = b in facts.readiness_blockers
        return fires, f"{ex.ex_id}: readiness blocker {b!r} -> {fires}"

    if op == ExclusionOperator.MIN_PRIOR_LETTERS:
        need = int(ex.value)
        fires = facts.letter_count_for_scope >= need
        return fires, f"{ex.ex_id}: letters {facts.letter_count_for_scope}>={need}"

    return False, f"{ex.ex_id}: unknown exclusion op {op}"
