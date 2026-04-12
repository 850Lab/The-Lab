"""
Score and rank strategy paths for a declared objective (explicit dimensions, no LLM).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from services.case_intelligence.models import CanonicalCaseIntelligenceV1
from services.strategy_paths.models import MultiPathStrategyBundle, StrategyGeneratedPath
from services.strategy_patterns.facts import CaseFactSnapshot, build_case_fact_snapshot
from services.strategy_patterns.models import PatternEvaluationResult, StrategyPatternEvaluationBundle

from .models import PathDimensionScores, ScoredStrategyPath, StrategyScoringBundle
from .objectives import get_objective_config, normalize_weights

SCORING_SCHEMA_VERSION = "strategy_scoring.v1"
SCORING_ENGINE_VERSION = "strategy_scoring_engine.v1"


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _timing_score(path: StrategyGeneratedPath) -> float:
    t = (path.timing_class or "unknown").strip().lower()
    if t == "expedited":
        return 100.0
    if t == "standard":
        return 72.0
    if t == "extended":
        return 44.0
    return 24.0


def _readiness_score(path: StrategyGeneratedPath) -> float:
    r = (path.readiness_state or "conditional").strip().lower()
    if r == "ready_now":
        return 100.0
    if r == "conditional":
        return 58.0
    return 6.0


def _effort_efficiency_score(path: StrategyGeneratedPath) -> float:
    e = (path.effort_class or "medium").strip().lower()
    if e == "low":
        return 100.0
    if e == "medium":
        return 62.0
    return 32.0


def _risk_acceptability_score(path: StrategyGeneratedPath) -> float:
    """Higher = lower operational risk class (better for credible fast track)."""
    r = (path.risk_class or "medium").strip().lower()
    if r == "low":
        return 92.0
    if r == "medium":
        return 70.0
    return 38.0


def _evidence_strength_for_path(path: StrategyGeneratedPath, facts: CaseFactSnapshot) -> Tuple[float, List[str]]:
    factors: List[str] = []
    doc = facts.documentation_sufficiency
    base = 38.0
    if doc == "rich":
        base = 94.0
        factors.append("case_documentation_sufficiency_rich")
    elif doc == "partial":
        base = 68.0
        factors.append("case_documentation_sufficiency_partial")
    elif doc == "thin":
        base = 42.0
        factors.append("case_documentation_sufficiency_thin")
    else:
        factors.append("case_documentation_sufficiency_unknown")

    pid = path.path_id.lower()
    fam = (path.path_family or "").lower()
    if "thin" in pid or (fam == "documentation" and "thin" in path.path_name.lower()):
        base = min(base, 48.0)
        factors.append("path_profile_docs_thin_conservative")
    if path.path_id == "path_docs_supported_standard" and doc == "rich":
        base = max(base, 90.0)
        factors.append("path_docs_supported_standard_with_case_rich_docs")

    return _clamp(base), factors


def _blocker_clearance_score(path: StrategyGeneratedPath) -> Tuple[float, List[str], List[str]]:
    n = len(path.blockers or [])
    if n == 0:
        return 100.0, ["no_path_blockers_listed"], []
    penalty = min(88.0, 11.0 * n)
    score = _clamp(100.0 - penalty)
    neg = [f"path_has_{n}_blocker_entries"]
    return score, [], neg


def _prior_action_favor_score(facts: CaseFactSnapshot) -> Tuple[float, List[str], List[str]]:
    pos: List[str] = []
    neg: List[str] = []
    s = 100.0
    if facts.letter_count_for_scope > 0:
        s -= 18.0
        neg.append("prior_letters_on_scope")
    if facts.cumulative_disputed_count > 0:
        s -= 12.0
        neg.append("cumulative_disputed_review_claim_ids_present")
    if facts.unresolved_dispute_count > 0:
        s -= 24.0
        neg.append("unresolved_prior_dispute_ids_present")
    if not neg:
        pos.append("no_prior_round_penalties_from_action_history_summary")
    return _clamp(s), pos, neg


def _signal_richness_score(
    path: StrategyGeneratedPath,
    facts: CaseFactSnapshot,
    ev_by_id: Dict[str, PatternEvaluationResult],
) -> Tuple[float, List[str], List[str]]:
    pos: List[str] = []
    neg: List[str] = []
    raw = (
        min(55.0, 14.0 * facts.contradiction_count)
        + min(30.0, 6.0 * len(facts.strategy_signal_names))
        + min(25.0, 10.0 * facts.multi_bureau_normalized_groups)
    )
    base = _clamp(28.0 + raw)

    fam = (path.path_family or "").lower()
    if fam == "composed_contradiction":
        base += 14.0
        pos.append("composed_contradiction_path_family")
    elif fam == "contradiction":
        base += 8.0
        pos.append("contradiction_led_path_family")
    elif fam == "duplicate":
        base += 6.0
        pos.append("duplicate_cleanup_path_family")

    # Pattern evaluation support for this path's source patterns
    confs: List[float] = []
    for pid in path.source_pattern_ids:
        ev = ev_by_id.get(pid)
        if ev and ev.matched:
            m = (ev.match_confidence or "medium").lower()
            confs.append(1.0 if m == "high" else 0.72 if m == "medium" else 0.45)
    if confs:
        boost = 12.0 * (sum(confs) / len(confs))
        base += boost
        pos.append("matched_source_patterns_with_stated_match_confidence")
    elif path.source_pattern_ids:
        neg.append("no_matched_pattern_evaluations_for_listed_source_patterns")

    return _clamp(base), pos, neg


def _compute_dimensions(
    path: StrategyGeneratedPath,
    facts: CaseFactSnapshot,
    ev_by_id: Dict[str, PatternEvaluationResult],
) -> Tuple[PathDimensionScores, List[str], List[str], List[str]]:
    pos: List[str] = []
    neg: List[str] = []
    trade: List[str] = []

    t = _timing_score(path)
    pos.append(f"timing_class_{path.timing_class}")

    r = _readiness_score(path)
    if path.readiness_state == "conditional":
        trade.append("readiness_conditional_review_blockers_and_history_before_committing")
    elif path.readiness_state == "blocked":
        neg.append("readiness_state_blocked")

    ev, ev_pos = _evidence_strength_for_path(path, facts)
    pos.extend(ev_pos)

    blk, bpos, bneg = _blocker_clearance_score(path)
    pos.extend(bpos)
    neg.extend(bneg)

    eff = _effort_efficiency_score(path)
    if eff < 55.0:
        trade.append("higher_effort_burden_for_speed_objective")

    risk = _risk_acceptability_score(path)
    if risk < 60.0:
        trade.append("elevated_risk_class_vs_credible_fast_track")

    paf, ppos, pneg = _prior_action_favor_score(facts)
    pos.extend(ppos)
    neg.extend(pneg)

    sig, spos, sneg = _signal_richness_score(path, facts, ev_by_id)
    pos.extend(spos)
    neg.extend(sneg)

    dims = PathDimensionScores(
        timing_score=t,
        readiness_score=r,
        evidence_strength_score=ev,
        blocker_clearance_score=blk,
        effort_efficiency_score=eff,
        risk_acceptability_score=risk,
        prior_action_favor_score=paf,
        signal_richness_score=sig,
    )
    return dims, pos, neg, trade


def _weighted_total(dims: PathDimensionScores, weights: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
    dmap = {
        "timing_score": dims.timing_score,
        "readiness_score": dims.readiness_score,
        "evidence_strength_score": dims.evidence_strength_score,
        "blocker_clearance_score": dims.blocker_clearance_score,
        "effort_efficiency_score": dims.effort_efficiency_score,
        "risk_acceptability_score": dims.risk_acceptability_score,
        "prior_action_favor_score": dims.prior_action_favor_score,
        "signal_richness_score": dims.signal_richness_score,
    }
    contrib: Dict[str, float] = {}
    total = 0.0
    for k, w in weights.items():
        v = dmap[k] * w
        contrib[k] = v
        total += v
    return _clamp(total), contrib


def score_strategy_paths(
    case_intelligence: CanonicalCaseIntelligenceV1,
    pattern_bundle: StrategyPatternEvaluationBundle,
    path_bundle: MultiPathStrategyBundle,
    *,
    objective: str = "fastest_credible_result",
) -> StrategyScoringBundle:
    """
    Score every path in ``path_bundle``, rank deterministically (tie-break: path_id asc).

    Primary and fallbacks are drawn only from **active_scorable** paths (not suppressed, not blocked).
    """
    notes: List[str] = []
    try:
        obj_desc, weights = get_objective_config(objective)
    except KeyError:
        notes.append(f"unknown_objective_{objective}_defaulting_to_fastest_credible_result")
        objective = "fastest_credible_result"
        obj_desc, weights = get_objective_config(objective)

    weights = normalize_weights(weights)

    facts = build_case_fact_snapshot(case_intelligence)
    ev_by_id = {e.pattern_id: e for e in pattern_bundle.evaluations}

    scored_rows: List[Tuple[StrategyGeneratedPath, PathDimensionScores, float, Dict[str, float], List[str], List[str], List[str]]] = []

    for path in path_bundle.all_paths:
        dims, pos, neg, trade = _compute_dimensions(path, facts, ev_by_id)
        total, contrib = _weighted_total(dims, weights)

        if path.suppressed:
            total = min(total * 0.12, 10.0)
            neg.append("path_marked_suppressed_by_generator")
            notes.append(f"suppressed_path_score_capped:{path.path_id}")

        if path.readiness_state == "blocked" and not path.suppressed:
            total = min(total, 35.0)
            neg.append("readiness_blocked_total_capped_for_credibility")

        scored_rows.append((path, dims, total, contrib, pos, neg, trade))

    # Sort by score then path_id (deterministic)
    scored_rows.sort(key=lambda row: (-row[2], row[0].path_id))

    global_rank = 0
    final_scored: List[ScoredStrategyPath] = []

    # Bucket sorts for within-bucket rank
    def bucket_key(p: StrategyGeneratedPath) -> str:
        if p.suppressed:
            return "suppressed"
        if p.readiness_state == "blocked":
            return "blocked"
        return "active_scorable"

    bucket_lists: Dict[str, List[Tuple[StrategyGeneratedPath, float]]] = {
        "active_scorable": [],
        "blocked": [],
        "suppressed": [],
    }
    for path, _, total, _, _, _, _ in scored_rows:
        bucket_lists[bucket_key(path)].append((path, total))

    for b in bucket_lists:
        bucket_lists[b].sort(key=lambda x: (-x[1], x[0].path_id))

    within_counter = {k: 0 for k in bucket_lists}

    for path, dims, total, contrib, pos, neg, trade in scored_rows:
        global_rank += 1
        b = bucket_key(path)
        within_counter[b] += 1
        wr = within_counter[b]

        if path.suppressed:
            role = "suppressed"
        elif path.readiness_state == "blocked":
            role = "blocked"
        else:
            role = "fallback"

        expl_parts = [
            f"objective={objective}",
            f"total={total:.2f}",
            f"timing={dims.timing_score:.1f}",
            f"readiness={dims.readiness_score:.1f}",
            f"evidence={dims.evidence_strength_score:.1f}",
            f"blocker_clearance={dims.blocker_clearance_score:.1f}",
        ]
        explanation = "; ".join(expl_parts)

        final_scored.append(
            ScoredStrategyPath(
                path_id=path.path_id,
                ranking_bucket=b,
                rank_within_bucket=wr,
                global_rank=global_rank,
                dimension_scores=dims,
                dimension_weights_used=dict(weights),
                weighted_contributions=contrib,
                total_score=total,
                explanation=explanation,
                positive_factors=sorted(set(pos))[:12],
                negative_factors=sorted(set(neg))[:12],
                tradeoffs=sorted(set(trade))[:8],
                role=role,
            )
        )

    active_ids = [p.path_id for p, _ in bucket_lists["active_scorable"]]
    blocked_ids = [p.path_id for p, _ in bucket_lists["blocked"]]
    suppressed_ids = [p.path_id for p, _ in bucket_lists["suppressed"]]

    primary: Optional[str] = active_ids[0] if active_ids else None
    fallbacks = active_ids[1:] if len(active_ids) > 1 else []

    for sp in final_scored:
        if primary and sp.path_id == primary:
            sp.role = "primary"
        elif sp.ranking_bucket == "active_scorable" and sp.path_id != primary:
            sp.role = "fallback"

    if primary:
        best = next(x for x in final_scored if x.path_id == primary)
        if best.total_score < 22.0:
            notes.append("low_total_score_primary_treat_as_low_confidence_recommendation")
    else:
        notes.append("no_active_scorable_path_primary_left_empty")

    return StrategyScoringBundle(
        schema_version=SCORING_SCHEMA_VERSION,
        scoring_version=SCORING_ENGINE_VERSION,
        objective_id=objective,
        objective_description=obj_desc,
        case_intelligence_schema=case_intelligence.schema_version,
        pattern_evaluation_schema=pattern_bundle.schema_version,
        path_bundle_schema=path_bundle.schema_version,
        path_generation_version=path_bundle.generation_version,
        scored_paths=final_scored,
        ranked_active_scorable_path_ids=list(active_ids),
        ranked_blocked_path_ids=list(blocked_ids),
        ranked_suppressed_path_ids=list(suppressed_ids),
        recommended_primary_path_id=primary,
        fallback_path_ids_ordered=list(fallbacks),
        scoring_notes=sorted(set(notes)),
    )


def score_strategy_paths_for_workflow(
    workflow_id: str,
    user_id: int,
    *,
    objective: str = "fastest_credible_result",
) -> StrategyScoringBundle:
    from services.case_intelligence import build_canonical_case_intelligence_for_workflow
    from services.strategy_patterns import evaluate_strategy_patterns
    from services.strategy_paths import generate_strategy_paths

    ci = build_canonical_case_intelligence_for_workflow(workflow_id, user_id)
    pb = evaluate_strategy_patterns(ci)
    paths = generate_strategy_paths(ci, pb)
    return score_strategy_paths(ci, pb, paths, objective=objective)
