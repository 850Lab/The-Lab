from __future__ import annotations

from typing import Any, Dict, List, Set

from review_claims import CreditImpact, ReviewClaim, ReviewType, Severity

from services.customer_dispute_strategy import (
    filter_eligible_dispute_items,
    parse_workflow_metadata_value,
    dispute_selection_context_from_meta,
    RESOLVED_DISPUTE_OUTCOMES,
)

from .contradictions import detect_contradictions
from .grouping import build_normalized_account_groups
from .models import (
    ActionHistorySummary,
    CanonicalCaseIntelligenceV1,
    CaseIntelligenceInputs,
    ConfidenceSectionNote,
    DocumentationStateSummary,
    GoalConstraintState,
    StrategySignalRecord,
    BureauFootprintEntry,
)


def _report_ids_from_scope(report_scope: List[Dict[str, Any]]) -> Set[int]:
    out: Set[int] = set()
    for r in report_scope:
        rid = r.get("reportId") if isinstance(r, dict) else None
        if rid is None:
            continue
        try:
            out.add(int(rid))
        except (TypeError, ValueError):
            pass
    return out


def _raw_claim_counts_by_bureau(raw_claims):
    from claims import Claim

    d: Dict[str, int] = {}
    for c in raw_claims:
        if not isinstance(c, Claim):
            continue
        b = (c.source or "unknown").lower()
        d[b] = d.get(b, 0) + 1
    return d


def _classify_case_type(
    review_claims: List[ReviewClaim],
    multi_bureau_groups: int,
    contradiction_count: int,
) -> str:
    by_t: Dict[ReviewType, int] = {}
    for rc in review_claims:
        by_t[rc.review_type] = by_t.get(rc.review_type, 0) + 1
    neg = by_t.get(ReviewType.NEGATIVE_IMPACT, 0)
    dup = by_t.get(ReviewType.DUPLICATE_ACCOUNT, 0)
    acc = by_t.get(ReviewType.ACCURACY_VERIFICATION, 0)
    idv = by_t.get(ReviewType.IDENTITY_VERIFICATION, 0)

    if multi_bureau_groups >= 2 and contradiction_count > 0:
        return "multi_bureau_with_grounded_conflicts"
    if dup >= 2 or (dup >= 1 and neg >= 1):
        return "duplicate_and_negative_mix"
    if neg >= 3:
        return "negative_heavy"
    if acc >= neg and acc > 0:
        return "accuracy_forward"
    if idv >= 2 and neg == 0:
        return "identity_forward"
    if neg >= 1:
        return "negative_forward"
    return "mixed_review"


def _build_documentation_summary(flags: Dict[str, Any]) -> DocumentationStateSummary:
    has_id = bool(flags.get("hasGovernmentId"))
    has_addr = bool(flags.get("hasAddressProof"))
    has_sig = bool(flags.get("hasSignature"))
    missing: List[str] = []
    if not has_id:
        missing.append("government_id")
    if not has_addr:
        missing.append("address_proof")
    if not has_sig:
        missing.append("signature")

    if has_id and has_addr and has_sig:
        suff = "rich"
        richness = "high"
    elif has_id or has_addr:
        suff = "partial"
        richness = "medium"
    elif not missing:
        suff = "unknown"
        richness = "low"
    else:
        suff = "thin"
        richness = "low"

    return DocumentationStateSummary(
        has_government_id=has_id,
        has_address_proof=has_addr,
        has_signature=has_sig,
        sufficiency=suff,
        missing_doc_flags=missing,
        evidence_richness=richness,
    )


def _action_history_from_inputs(
    meta: Dict[str, Any],
    letter_records: List[Dict[str, Any]],
    report_ids: Set[int],
) -> ActionHistorySummary:
    rnd, cumulative, outcomes = dispute_selection_context_from_meta(meta)
    unresolved = sorted(
        cid
        for cid in cumulative
        if (outcomes.get(cid) or "").strip().lower() not in RESOLVED_DISPUTE_OUTCOMES
    )
    letters_in_scope: List[Dict[str, Any]] = []
    for row in letter_records:
        if not isinstance(row, dict):
            continue
        rid = row.get("report_id")
        try:
            r_int = int(rid) if rid is not None else None
        except (TypeError, ValueError):
            r_int = None
        if report_ids and r_int is not None and r_int not in report_ids:
            continue
        letters_in_scope.append(row)
    bureaus = sorted(
        {str(r.get("bureau") or "").lower() for r in letters_in_scope if r.get("bureau")}
    )
    return ActionHistorySummary(
        cumulative_disputed_review_claim_ids=sorted(cumulative),
        claim_outcomes=dict(outcomes),
        dispute_round_number=rnd,
        letter_count_for_scope=len(letters_in_scope),
        letter_bureaus_distinct=bureaus,
        unresolved_disputed_ids=unresolved,
    )


def _goal_state(
    meta: Dict[str, Any],
    authoritative_step_id: str | None,
    documentation: DocumentationStateSummary,
    eligible_dispute_count: int,
) -> GoalConstraintState:
    objective = meta.get("caseObjective") or meta.get("user_objective")
    if isinstance(objective, dict):
        objective = objective.get("label") or objective.get("text")
    obj_str = str(objective).strip() if objective else None
    if obj_str:
        src = "workflow_metadata"
    else:
        obj_str = None
        src = "unknown"

    blockers: List[str] = []
    if documentation.sufficiency == "thin":
        blockers.append("proof_attachment_incomplete")
    if eligible_dispute_count == 0:
        blockers.append("no_high_confidence_dispute_candidates")

    deps: List[str] = []
    if eligible_dispute_count > 0:
        deps.append("consumer_review_and_selection")
    if documentation.sufficiency != "rich":
        deps.append("identity_and_address_proof_for_mailing_readiness")

    timing = "unknown"
    if authoritative_step_id:
        timing = f"workflow_head_{authoritative_step_id}"

    return GoalConstraintState(
        stated_objective=obj_str,
        objective_source=src,
        timing_sensitivity=timing,
        readiness_blockers=blockers,
        next_dependencies=deps,
    )


def _build_strategy_signals(
    review_claims: List[ReviewClaim],
    groups,
    contradictions,
    eligible: List[ReviewClaim],
    multi_bureau_group_count: int,
) -> List[StrategySignalRecord]:
    sigs: List[StrategySignalRecord] = []

    high_sev = sum(
        1 for rc in review_claims if rc.impact_assessment.severity == Severity.HIGH
    )
    if high_sev:
        sigs.append(
            StrategySignalRecord(
                name="high_severity_review_items",
                tier="risk",
                detail=f"{high_sev} review item(s) carry HIGH severity in the compression layer assessment.",
                confidence="medium",
            )
        )

    neg_credit = sum(
        1
        for rc in review_claims
        if rc.impact_assessment.credit_impact == CreditImpact.NEGATIVE
    )
    if neg_credit >= 2:
        sigs.append(
            StrategySignalRecord(
                name="multiple_negative_credit_impact_buckets",
                tier="risk",
                detail=f"{neg_credit} review buckets tagged with negative credit impact.",
                confidence="medium",
            )
        )

    if multi_bureau_group_count >= 1:
        sigs.append(
            StrategySignalRecord(
                name="cross_bureau_tradeline_footprint",
                tier="hygiene",
                detail=(
                    f"{multi_bureau_group_count} normalized account fingerprint(s) appear on more than one bureau."
                ),
                confidence="medium",
            )
        )

    for c in contradictions:
        if c.signal_type == "cross_bureau_balance_mismatch":
            sigs.append(
                StrategySignalRecord(
                    name="leverage_cross_bureau_balance_delta",
                    tier="leverage",
                    detail=c.description,
                    confidence=c.confidence,
                )
            )
        elif c.signal_type == "cross_bureau_status_inconsistency":
            sigs.append(
                StrategySignalRecord(
                    name="leverage_status_inconsistency",
                    tier="leverage",
                    detail=c.description,
                    confidence="low",
                )
            )

    dup_rc = sum(1 for rc in review_claims if rc.review_type == ReviewType.DUPLICATE_ACCOUNT)
    if dup_rc:
        sigs.append(
            StrategySignalRecord(
                name="duplicate_tradeline_review_surface",
                tier="leverage",
                detail=f"{dup_rc} duplicate-account review item(s) present — validate single-obligation story.",
                confidence="medium",
            )
        )

    if len(eligible) == 0 and len(review_claims) > 0:
        sigs.append(
            StrategySignalRecord(
                name="dispute_pool_requires_confirmation",
                tier="timing",
                detail="No high-confidence eligible dispute items without changing review posture.",
                confidence="high",
            )
        )

    return sigs


def build_canonical_case_intelligence(inputs: CaseIntelligenceInputs) -> CanonicalCaseIntelligenceV1:
    """
    Core entry: assemble the canonical object from explicit inputs (testable, no I/O).
    """
    meta = parse_workflow_metadata_value(inputs.workflow_metadata)
    report_ids = _report_ids_from_scope(inputs.report_scope)
    raw_by_b = _raw_claim_counts_by_bureau(inputs.raw_claims)
    bureau_entries = _report_scope_to_serializable(inputs.report_scope, raw_by_b)

    groups = build_normalized_account_groups(inputs.raw_claims)
    multi_bureau_gc = sum(1 for g in groups if len(g.bureaus_present) > 1)

    contradictions = detect_contradictions(inputs.raw_claims, inputs.review_claims)

    rnd, cumulative, outcomes = dispute_selection_context_from_meta(meta)
    eligible = filter_eligible_dispute_items(
        inputs.review_claims,
        round_number=rnd,
        cumulative_disputed_ids=cumulative,
        claim_outcomes=outcomes,
    )

    doc = _build_documentation_summary(inputs.proof_flags)
    action = _action_history_from_inputs(meta, inputs.letter_records, report_ids)
    goals = _goal_state(meta, inputs.authoritative_step_id, doc, len(eligible))

    case_type = _classify_case_type(
        inputs.review_claims,
        multi_bureau_gc,
        len(contradictions),
    )

    neg_items = sum(
        s.get("counts", {}).get("negativeItems", 0)
        for s in inputs.report_scope
        if isinstance(s, dict)
    )

    strategy_signals = _build_strategy_signals(
        inputs.review_claims,
        groups,
        contradictions,
        eligible,
        multi_bureau_gc,
    )

    explainability: List[str] = [
        "Case intelligence is derived from persisted parse outputs, extracted claims, "
        "compressed review claims, and workflow metadata — no web research.",
        f"Eligible dispute candidates (high-confidence, current round rules): {len(eligible)}.",
        f"Normalized account groups (heuristic): {len(groups)}.",
    ]

    confidence_notes: List[ConfidenceSectionNote] = [
        ConfidenceSectionNote(
            section="account_grouping",
            level="medium",
            rationale="Grouping uses creditor scrub + last4 / canonical_account_key when present; false merges possible.",
        ),
        ConfidenceSectionNote(
            section="contradictions",
            level="medium",
            rationale="Numeric balance parsing ignores formatting edge cases; confirm manually before letters.",
        ),
        ConfidenceSectionNote(
            section="documentation",
            level="high" if doc.sufficiency != "unknown" else "low",
            rationale="Based solely on proof doc rows and signature presence in application DB.",
        ),
        ConfidenceSectionNote(
            section="objective",
            level="high" if goals.stated_objective else "low",
            rationale="Objective only when stored in workflow metadata keys caseObjective / user_objective.",
        ),
    ]

    identity = {
        "workflowId": inputs.workflow_id,
        "userId": inputs.user_id,
        "reportScope": inputs.report_scope,
        "bureauCoverage": [e.to_dict() for e in bureau_entries],
        "selectedReviewClaimIds": list(inputs.selected_review_claim_ids),
    }

    footprint = ", ".join(f"{e.bureau}:{len(e.report_ids)}r" for e in bureau_entries) or "none"

    case_summary = {
        "caseTypeSummary": case_type,
        "totalNegativeItemsParsed": int(neg_items),
        "totalReviewClaims": len(inputs.review_claims),
        "candidateDisputeItemsEligibleNow": len(eligible),
        "activeBureauAccountFootprintSummary": footprint,
        "contradictionCount": len(contradictions),
        "multiBureauNormalizedGroups": multi_bureau_gc,
    }

    return CanonicalCaseIntelligenceV1(
        schema_version="case_intelligence.v1",
        identity=identity,
        case_summary=case_summary,
        account_groups=groups,
        strategy_signals=strategy_signals,
        contradictions=contradictions,
        documentation=doc,
        action_history=action,
        goal_constraints=goals,
        confidence_notes=confidence_notes,
        explainability=explainability,
    )


def _report_scope_to_serializable(report_scope, raw_by_b):
    """Reuse BureauFootprintEntry builder from scope + raw claim counts."""
    by_b: Dict[str, List[int]] = {}
    for r in report_scope:
        if not isinstance(r, dict):
            continue
        b = str(r.get("bureau") or "unknown").lower()
        rid = r.get("reportId")
        by_b.setdefault(b, [])
        if rid is not None:
            try:
                by_b[b].append(int(rid))
            except (TypeError, ValueError):
                pass
    entries: List[BureauFootprintEntry] = []
    for b in sorted(by_b.keys()):
        entries.append(
            BureauFootprintEntry(
                bureau=b,
                report_ids=sorted(set(by_b[b])),
                tradeline_observations=raw_by_b.get(b, 0),
            )
        )
    return entries
