"""
Match strategy patterns against CanonicalCaseIntelligenceV1.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from services.case_intelligence.models import CanonicalCaseIntelligenceV1

from .conditions import evaluate_exclusion, evaluate_requirement
from .facts import CaseFactSnapshot, build_case_fact_snapshot
from .models import (
    PatternEvaluationResult,
    StrategyPatternDefinition,
    StrategyPatternEvaluationBundle,
)
from .registry_v1 import LIBRARY_VERSION, load_pattern_library_v1

_LEVERAGE_OPTIONAL_RESOLVERS: Dict[str, Callable[[CaseFactSnapshot], bool]] = {
    "leverage_cross_bureau_balance_delta": lambda f: "cross_bureau_balance_mismatch"
    in f.contradiction_types
    or any("cross_bureau" in n.lower() and "balance" in n.lower() for n in f.strategy_signal_names),
    "leverage_status_inconsistency": lambda f: "cross_bureau_status_inconsistency" in f.contradiction_types
    or any("status" in n.lower() and "inconsist" in n.lower() for n in f.strategy_signal_names),
}


def _signal_label_satisfied(facts: CaseFactSnapshot, label: str) -> bool:
    """
    Map pattern-library signal labels to observable facts (explicit, not prose).
    """
    lb = label.strip().lower()
    if lb == "contradiction_record_present":
        return facts.contradiction_count > 0
    if lb == "proof_rich":
        return facts.documentation_sufficiency == "rich"
    if lb == "proof_partial_or_thin":
        return facts.documentation_sufficiency in ("thin", "partial", "unknown")
    if lb == "duplicate_tradeline_review_surface":
        return any("duplicate_tradeline" in n.lower() for n in facts.strategy_signal_names) or (
            "duplicate_tradeline_with_negatives" in facts.contradiction_types
        )
    if lb == "eligible_dispute_pool":
        return facts.candidate_dispute_items >= 1
    if lb == "prior_letter_activity":
        return facts.letter_count_for_scope >= 1 or facts.cumulative_disputed_count >= 1
    if lb == "identity_case_classification":
        return "identity" in facts.case_type_summary
    if lb == "high_severity_review_items":
        return any("high_severity" in n.lower() or "severity_high" in n.lower() for n in facts.strategy_signal_names)
    if lb in _LEVERAGE_OPTIONAL_RESOLVERS:
        return _LEVERAGE_OPTIONAL_RESOLVERS[lb](facts)
    if lb.startswith("leverage_"):
        tail = lb[len("leverage_") :].replace("_", "")
        return any(tail and tail in n.lower().replace("_", "") for n in facts.strategy_signal_names) or any(
            tail and tail in ct.replace("_", "") for ct in facts.contradiction_types
        )
    if lb == "unresolved_disputes":
        return facts.unresolved_dispute_count > 0
    if lb == "cross_bureau_tradeline_footprint":
        return any("cross_bureau" in n.lower() for n in facts.strategy_signal_names) or (
            facts.multi_bureau_normalized_groups >= 1
        )
    return any(lb in n.lower() for n in facts.strategy_signal_names)


def _optional_signal_satisfied(facts: CaseFactSnapshot, label: str) -> bool:
    return _signal_label_satisfied(facts, label)


def _gate_match_confidence(pattern_conf: str, facts: CaseFactSnapshot) -> str:
    """Downgrade when documentation state is unknown (weaker observability)."""
    pc = pattern_conf.strip().lower()
    if facts.documentation_sufficiency == "unknown":
        if pc == "high":
            return "medium"
        if pc == "medium":
            return "low"
    return pc


def _evaluate_pattern(
    pattern: StrategyPatternDefinition,
    facts: CaseFactSnapshot,
    ci: CanonicalCaseIntelligenceV1,
) -> PatternEvaluationResult:
    matched_req: List[str] = []
    missing_req: List[str] = []
    results: List[Tuple[bool, str]] = [
        evaluate_requirement(facts, r) for r in pattern.applies_when
    ]

    if pattern.applies_logic.strip().lower() == "any":
        applies_ok = any(ok for ok, _ in results)
        applicability_score = 1.0 if applies_ok else 0.0
        for ok, msg in results:
            if ok:
                matched_req.append(msg)
            else:
                missing_req.append(msg)
        if not applies_ok:
            missing_req = [m for _, m in results]
    else:
        applies_ok = all(ok for ok, _ in results)
        n = max(len(results), 1)
        applicability_score = sum(1 for ok, _ in results if ok) / n
        for ok, msg in results:
            (matched_req if ok else missing_req).append(msg)

    exclusion_hits: List[str] = []
    excluded = False
    for ex in pattern.excludes_when:
        fires, msg = evaluate_exclusion(facts, ex)
        if fires:
            exclusion_hits.append(msg)
            excluded = True

    doc_ok = True
    if pattern.required_documentation_states:
        allowed = {x.lower() for x in pattern.required_documentation_states}
        if facts.documentation_sufficiency not in allowed:
            doc_ok = False
            missing_req.append(
                f"documentation: need sufficiency in {sorted(allowed)}, "
                f"got {facts.documentation_sufficiency}"
            )

    req_sig_ok = True
    matched_sig: List[str] = []
    for lab in pattern.required_signals:
        if _signal_label_satisfied(facts, lab):
            matched_sig.append(lab)
        else:
            req_sig_ok = False
            missing_req.append(f"required_signal:{lab}")

    missing_opt: List[str] = []
    for lab in pattern.optional_signals:
        if not _optional_signal_satisfied(facts, lab):
            missing_opt.append(lab)

    matched = applies_ok and not excluded and doc_ok and req_sig_ok

    explanation_parts = [
        f"pattern={pattern.pattern_id} applies_logic={pattern.applies_logic}",
        f"applies_ok={applies_ok} excluded={excluded} doc_gate={doc_ok} required_signals_ok={req_sig_ok}",
    ]
    if exclusion_hits:
        explanation_parts.append("exclusions:" + "; ".join(exclusion_hits))

    caution: List[str] = []
    if pattern.pattern_id == "pat_prior_dispute_caution" and matched:
        caution.append("review_prior_rounds_and_outcomes_before_escalating")
    if facts.unresolved_dispute_count and pattern.pattern_family == "negative_tradeline":
        caution.append("unresolved_prior_dispute_ids_present")

    mconf = _gate_match_confidence(pattern.confidence_class, facts) if matched else "low"

    return PatternEvaluationResult(
        pattern_id=pattern.pattern_id,
        pattern_version=pattern.version,
        matched=matched,
        applicability_score=round(applicability_score, 4),
        match_confidence=mconf,
        matched_requirements=matched_req,
        missing_requirements=missing_req,
        exclusion_hits=exclusion_hits,
        matched_signals_used=matched_sig,
        missing_optional_signals=missing_opt,
        explanation=" | ".join(explanation_parts),
        caution_flags=caution,
    )


def evaluate_strategy_patterns(
    case_intelligence: CanonicalCaseIntelligenceV1,
    *,
    library: Tuple[StrategyPatternDefinition, ...] | None = None,
) -> StrategyPatternEvaluationBundle:
    """
    Evaluate every active pattern in the library against the given case intelligence object.

    Ordering: evaluations sorted by ``pattern_id`` (stable). ``matchedPatternIds`` and
    ``unmatchedPatternIds`` are sorted lexicographically.
    """
    patterns = library if library is not None else load_pattern_library_v1()
    active = [p for p in patterns if p.active]
    facts = build_case_fact_snapshot(case_intelligence)

    evaluations: List[PatternEvaluationResult] = []
    for p in sorted(active, key=lambda x: x.pattern_id):
        evaluations.append(_evaluate_pattern(p, facts, case_intelligence))

    matched_ids = sorted({e.pattern_id for e in evaluations if e.matched})
    unmatched_ids = sorted({e.pattern_id for e in evaluations if not e.matched})

    matched_first = [e for e in evaluations if e.matched]
    rest = [e for e in evaluations if not e.matched]
    ordered = sorted(matched_first, key=lambda x: x.pattern_id) + sorted(
        rest, key=lambda x: x.pattern_id
    )

    return StrategyPatternEvaluationBundle(
        schema_version="strategy_pattern_evaluation.v1",
        case_intelligence_schema=case_intelligence.schema_version,
        library_version=LIBRARY_VERSION,
        evaluations=ordered,
        matched_pattern_ids=matched_ids,
        unmatched_pattern_ids=unmatched_ids,
    )


def evaluate_strategy_patterns_for_workflow(
    workflow_id: str,
    user_id: int,
) -> StrategyPatternEvaluationBundle:
    """
    Thin facade: build case intelligence from workflow, then evaluate patterns.
    """
    from services.case_intelligence import build_canonical_case_intelligence_for_workflow

    ci = build_canonical_case_intelligence_for_workflow(workflow_id, user_id)
    return evaluate_strategy_patterns(ci)
