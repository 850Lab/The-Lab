"""
Compose 2–4 distinct strategy paths from case intelligence + pattern evaluation bundle.

Explicit rules only — no scoring, no execution planning, no external research.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Set, Tuple

from services.case_intelligence.models import CanonicalCaseIntelligenceV1
from services.strategy_patterns.facts import CaseFactSnapshot, build_case_fact_snapshot
from services.strategy_patterns.models import (
    PatternEvaluationResult,
    StrategyPatternDefinition,
    StrategyPatternEvaluationBundle,
)
from services.strategy_patterns.registry_v1 import LIBRARY_VERSION as PATTERN_LIB_VERSION
from services.strategy_patterns.registry_v1 import load_pattern_library_v1

from .models import MultiPathStrategyBundle, StrategyGeneratedPath

GENERATION_VERSION = "strategy_paths.v1"
BUNDLE_SCHEMA = "multi_path_strategy.v1"

# Pattern ids (must match registry_v1)
PAT_IDENTITY = "pat_identity_forward_review"
PAT_INCONSISTENCY = "pat_inconsistency_led_challenge"
PAT_DUPLICATE = "pat_duplicate_tradeline_challenge"
PAT_DOC_RICH = "pat_documentation_rich_standard"
PAT_DOC_THIN = "pat_documentation_thin_guided"
PAT_MULTI = "pat_multi_bureau_coordination"
PAT_STANDARD = "pat_standard_negative_pool"
PAT_PRIOR = "pat_prior_dispute_caution"

# Path ids
PATH_IDENTITY = "path_identity_ownership_first"
PATH_CROSS = "path_cross_bureau_inconsistency_fast"
PATH_INCONSISTENCY = "path_inconsistency_led_challenge"
PATH_DUPLICATE = "path_duplicate_reporting_cleanup"
PATH_DOC_RICH = "path_docs_supported_standard"
PATH_DOC_THIN = "path_docs_thin_conservative_first"
PATH_STANDARD = "path_standard_negative_first_pass"
PATH_PRIOR = "path_prior_round_caution_escalation_ready"
PATH_AWAIT = "path_await_case_signals"

MAX_ACTIVE_PATHS = 4

# Priority when capping (higher priority first)
_PATH_PRIORITY: Tuple[str, ...] = (
    PATH_IDENTITY,
    PATH_CROSS,
    PATH_INCONSISTENCY,
    PATH_DUPLICATE,
    PATH_DOC_RICH,
    PATH_DOC_THIN,
    PATH_STANDARD,
    PATH_PRIOR,
)

_PATTERN_TO_FALLBACK_PATH: Dict[str, str] = {
    PAT_INCONSISTENCY: PATH_DOC_THIN,
    PAT_DUPLICATE: PATH_STANDARD,
    PAT_DOC_RICH: PATH_DOC_THIN,
    PAT_MULTI: PATH_INCONSISTENCY,
}


def _pattern_map() -> Dict[str, StrategyPatternDefinition]:
    return {p.pattern_id: p for p in load_pattern_library_v1()}


def _merge_action_templates(pattern_ids: Tuple[str, ...], extra: Tuple[str, ...] = ()) -> Tuple[str, ...]:
    defs = _pattern_map()
    out: List[str] = []
    for step in extra:
        if step not in out:
            out.append(step)
    for pid in pattern_ids:
        p = defs.get(pid)
        if not p:
            continue
        for s in p.action_sequence_template:
            if s not in out:
                out.append(s)
    out.extend(
        s
        for s in ("wait_review_responses_window", "escalate_if_unresolved_after_deadline")
        if s not in out
    )
    return tuple(out)


def _fallback_paths_for_patterns(pattern_ids: Tuple[str, ...]) -> Tuple[str, ...]:
    fb: List[str] = []
    for pid in pattern_ids:
        mapped = _PATTERN_TO_FALLBACK_PATH.get(pid)
        if mapped and mapped not in fb:
            fb.append(mapped)
    return tuple(fb)


def _aggregate_caution(
    evaluations_by_id: Dict[str, PatternEvaluationResult],
    pattern_ids: Tuple[str, ...],
) -> List[str]:
    flags: List[str] = []
    seen: Set[str] = set()
    for pid in pattern_ids:
        ev = evaluations_by_id.get(pid)
        if not ev:
            continue
        for f in ev.caution_flags:
            if f not in seen:
                seen.add(f)
                flags.append(f)
    return flags


def _fact_blockers(facts: CaseFactSnapshot) -> List[str]:
    b: List[str] = []
    if facts.readiness_blockers:
        b.append(f"goal_readiness_blockers:{','.join(facts.readiness_blockers)}")
    if facts.documentation_sufficiency == "unknown":
        b.append("documentation_sufficiency_unknown_reduces_observability")
    return b


def _readiness_for_challenge(facts: CaseFactSnapshot) -> Tuple[str, List[str]]:
    block: List[str] = []
    if facts.candidate_dispute_items < 1:
        block.append("no_eligible_dispute_candidates")
        return "blocked", block
    if facts.unresolved_dispute_count > 0 or facts.letter_count_for_scope > 0:
        block.extend(
            x
            for x in (
                "prior_letter_or_dispute_history_present_review_outcomes"
                if facts.letter_count_for_scope > 0 or facts.cumulative_disputed_count > 0
                else None,
                "unresolved_prior_dispute_ids_present"
                if facts.unresolved_dispute_count > 0
                else None,
            )
            if x
        )
        return "conditional", block
    return "ready_now", []


def _build_eval_index(bundle: StrategyPatternEvaluationBundle) -> Dict[str, PatternEvaluationResult]:
    return {e.pattern_id: e for e in bundle.evaluations}


def generate_strategy_paths(
    case_intelligence: CanonicalCaseIntelligenceV1,
    pattern_bundle: StrategyPatternEvaluationBundle,
) -> MultiPathStrategyBundle:
    """
    Produce a small set of composed paths (typically 2–4 when the case supports it).

    Ordering: ``all_paths`` sorted by ``path_id``. Candidate/blocked/suppressed id lists sorted.
    """
    facts = build_case_fact_snapshot(case_intelligence)
    matched: Set[str] = set(pattern_bundle.matched_pattern_ids)
    ev_by_id = _build_eval_index(pattern_bundle)
    defs = _pattern_map()
    notes: List[str] = []
    raw_paths: List[StrategyGeneratedPath] = []

    def add(path: StrategyGeneratedPath) -> None:
        raw_paths.append(path)

    identity_on = PAT_IDENTITY in matched
    inconsistency_on = PAT_INCONSISTENCY in matched
    multi_on = PAT_MULTI in matched
    dup_on = PAT_DUPLICATE in matched
    rich_on = PAT_DOC_RICH in matched
    thin_on = PAT_DOC_THIN in matched
    standard_on = PAT_STANDARD in matched
    prior_on = PAT_PRIOR in matched

    # --- Identity-first path (never merged into standard tradeline path)
    if identity_on:
        id_readiness, id_block = ("ready_now", [])
        if facts.candidate_dispute_items < 1:
            id_readiness, id_block = "conditional", ["no_eligible_dispute_candidates_tradeline_rounds_deferred"]
        if facts.total_review_claims < 1:
            id_readiness = "blocked"
            id_block = list(dict.fromkeys(id_block + ["no_review_claim_surface"]))
        add(
            StrategyGeneratedPath(
                path_id=PATH_IDENTITY,
                path_name="Identity / ownership first",
                path_family="identity",
                version="1.0.0",
                path_objective="Resolve identity-linked review items before broad tradeline dispute waves.",
                source_pattern_ids=(PAT_IDENTITY,),
                path_summary="Prioritize identity cleanup given case classification from intelligence.",
                why_it_applies=f"Matched {PAT_IDENTITY}; caseTypeSummary indicates identity concern.",
                prerequisites=["identity_case_classification_from_intelligence"],
                blockers=_fact_blockers(facts) + id_block,
                timing_class=defs[PAT_IDENTITY].timing_class,
                effort_class="high",
                risk_class="medium",
                aggressiveness_class=defs[PAT_IDENTITY].aggressiveness_class,
                action_sequence_template=tuple(defs[PAT_IDENTITY].action_sequence_template)
                + ("wait_review_responses_window", "reassess_tradeline_strategy"),
                fallback_path_ids=(PATH_STANDARD,),
                caution_flags=_aggregate_caution(ev_by_id, (PAT_IDENTITY,)),
                readiness_state=id_readiness,
                explanation="Separated from generic tradeline paths per identity-forward composition rule.",
            )
        )

    # --- Composed cross-bureau + inconsistency fast path
    if inconsistency_on and multi_on:
        ch_ready, ch_block = _readiness_for_challenge(facts)
        fb = _fallback_paths_for_patterns((PAT_INCONSISTENCY, PAT_MULTI))
        add(
            StrategyGeneratedPath(
                path_id=PATH_CROSS,
                path_name="Cross-bureau inconsistency fast challenge",
                path_family="composed_contradiction",
                version="1.0.0",
                path_objective="Use multi-bureau footprint plus grounded inconsistencies for coordinated challenge.",
                source_pattern_ids=(PAT_INCONSISTENCY, PAT_MULTI),
                path_summary="Composes inconsistency-led and multi-bureau coordination patterns into one route.",
                why_it_applies=(
                    f"Matched {PAT_INCONSISTENCY} and {PAT_MULTI}; multi-bureau groups and contradiction signals "
                    "co-present."
                ),
                prerequisites=["contradiction_records_present", "multi_bureau_normalized_groups_ge_1", "bureau_coverage_ge_2"],
                blockers=_fact_blockers(facts) + ch_block,
                timing_class="expedited",
                effort_class="high",
                risk_class="medium",
                aggressiveness_class="elevated",
                action_sequence_template=_merge_action_templates(
                    (PAT_INCONSISTENCY, PAT_MULTI),
                    ("initial_challenge_coordinate_across_bureaus",),
                ),
                fallback_path_ids=fb if fb else (PATH_DOC_THIN,),
                caution_flags=_aggregate_caution(ev_by_id, (PAT_INCONSISTENCY, PAT_MULTI)),
                readiness_state=ch_ready,
                explanation="Explicit composition of two matched patterns; not a 1:1 pattern echo.",
            )
        )
        notes.append("composed_cross_bureau_plus_inconsistency")
    elif inconsistency_on:
        ch_ready, ch_block = _readiness_for_challenge(facts)
        add(
            StrategyGeneratedPath(
                path_id=PATH_INCONSISTENCY,
                path_name="Inconsistency-led challenge",
                path_family="contradiction",
                version="1.0.0",
                path_objective="Challenge items using grounded inconsistency signals from intelligence.",
                source_pattern_ids=(PAT_INCONSISTENCY,),
                path_summary="Single-bureau or partial footprint inconsistency route without full multi-bureau compose.",
                why_it_applies=f"Matched {PAT_INCONSISTENCY}; {PAT_MULTI} not matched so cross-bureau compose omitted.",
                prerequisites=["contradiction_records_present"],
                blockers=_fact_blockers(facts) + ch_block,
                timing_class=defs[PAT_INCONSISTENCY].timing_class,
                effort_class="medium",
                risk_class="medium",
                aggressiveness_class=defs[PAT_INCONSISTENCY].aggressiveness_class,
                action_sequence_template=_merge_action_templates((PAT_INCONSISTENCY,)),
                fallback_path_ids=(PATH_DOC_THIN,),
                caution_flags=_aggregate_caution(ev_by_id, (PAT_INCONSISTENCY,)),
                readiness_state=ch_ready,
                explanation="Inconsistency path without multi-bureau composition.",
            )
        )

    if dup_on:
        ch_ready, ch_block = _readiness_for_challenge(facts)
        add(
            StrategyGeneratedPath(
                path_id=PATH_DUPLICATE,
                path_name="Duplicate reporting cleanup",
                path_family="duplicate",
                version="1.0.0",
                path_objective="Align duplicate tradeline representations before or alongside disputes.",
                source_pattern_ids=(PAT_DUPLICATE,),
                path_summary="Distinct from generic inconsistency compose when duplicate signal stands alone.",
                why_it_applies=f"Matched {PAT_DUPLICATE}.",
                prerequisites=["duplicate_tradeline_signal_or_duplicate_contradiction"],
                blockers=_fact_blockers(facts) + ch_block,
                timing_class=defs[PAT_DUPLICATE].timing_class,
                effort_class="medium",
                risk_class="low",
                aggressiveness_class=defs[PAT_DUPLICATE].aggressiveness_class,
                action_sequence_template=tuple(defs[PAT_DUPLICATE].action_sequence_template)
                + ("wait_review_responses_window",),
                fallback_path_ids=(PATH_STANDARD,),
                caution_flags=_aggregate_caution(ev_by_id, (PAT_DUPLICATE,)),
                readiness_state=ch_ready,
                explanation="Duplicate-focused route; may coexist with inconsistency paths when both match.",
            )
        )

    if rich_on:
        ch_ready, ch_block = _readiness_for_challenge(facts)
        add(
            StrategyGeneratedPath(
                path_id=PATH_DOC_RICH,
                path_name="Documentation-supported standard challenge",
                path_family="documentation",
                version="1.0.0",
                path_objective="Proceed with standard dispute selection backed by rich proof posture.",
                source_pattern_ids=(PAT_DOC_RICH,),
                path_summary="Separate from contradiction-led routes; emphasizes proof-backed progression.",
                why_it_applies=f"Matched {PAT_DOC_RICH}; documentation sufficiency rich.",
                prerequisites=["documentation_sufficiency_rich", "eligible_dispute_candidates"],
                blockers=_fact_blockers(facts) + ch_block,
                timing_class=defs[PAT_DOC_RICH].timing_class,
                effort_class="low",
                risk_class="low",
                aggressiveness_class=defs[PAT_DOC_RICH].aggressiveness_class,
                action_sequence_template=tuple(defs[PAT_DOC_RICH].action_sequence_template)
                + ("wait_review_responses_window", "fallback_if_blocked"),
                fallback_path_ids=(PATH_DOC_THIN,),
                caution_flags=_aggregate_caution(ev_by_id, (PAT_DOC_RICH,)),
                readiness_state=ch_ready,
                explanation="Docs-rich path kept distinct from inconsistency-fast compose when both apply.",
            )
        )

    if thin_on:
        thin_ready = "ready_now"
        thin_block = list(_fact_blockers(facts))
        if facts.candidate_dispute_items < 1:
            thin_ready = "conditional"
            thin_block.append("limited_dispute_pool_gather_proof_then_reassess")
        if prior_on:
            thin_fb: Tuple[str, ...] = (PATH_PRIOR,)
        elif standard_on:
            thin_fb = (PATH_STANDARD,)
        else:
            thin_fb = ()
        add(
            StrategyGeneratedPath(
                path_id=PATH_DOC_THIN,
                path_name="Documentation-thin conservative first pass",
                path_family="documentation",
                version="1.0.0",
                path_objective="Strengthen proof posture before aggressive multi-round disputes.",
                source_pattern_ids=(PAT_DOC_THIN,),
                path_summary="Conservative route when sufficiency is thin, partial, or unknown.",
                why_it_applies=f"Matched {PAT_DOC_THIN}; documentation not rich.",
                prerequisites=["review_surface_present"],
                blockers=thin_block,
                timing_class=defs[PAT_DOC_THIN].timing_class,
                effort_class="high",
                risk_class="low",
                aggressiveness_class=defs[PAT_DOC_THIN].aggressiveness_class,
                action_sequence_template=tuple(defs[PAT_DOC_THIN].action_sequence_template)
                + ("reassess_eligibility", "narrow_dispute_round"),
                fallback_path_ids=thin_fb,
                caution_flags=_aggregate_caution(ev_by_id, (PAT_DOC_THIN,)),
                readiness_state=thin_ready,
                explanation="Conservative path grounded in documentation state from intelligence.",
            )
        )

    if standard_on:
        suppressed = False
        reason = ""
        if identity_on:
            suppressed = True
            reason = "identity_case_defer_standard_tradeline_pool"
            notes.append("suppressed_standard_negative_due_to_identity_priority")
        ch_ready, ch_block = _readiness_for_challenge(facts)
        if suppressed:
            ch_ready = "blocked"
            ch_block = list(dict.fromkeys(ch_block + [reason]))
        add(
            StrategyGeneratedPath(
                path_id=PATH_STANDARD,
                path_name="Standard negative-item first pass",
                path_family="negative_tradeline",
                version="1.0.0",
                path_objective="First-round dispute selection without contradiction-led leverage.",
                source_pattern_ids=(PAT_STANDARD,),
                path_summary="Baseline pool path when eligible negatives exist and contradiction-led patterns are absent.",
                why_it_applies=f"Matched {PAT_STANDARD}.",
                prerequisites=["eligible_dispute_candidates", "contradiction_count_zero_per_intelligence"],
                blockers=_fact_blockers(facts) + ch_block,
                timing_class=defs[PAT_STANDARD].timing_class,
                effort_class="medium",
                risk_class="medium",
                aggressiveness_class=defs[PAT_STANDARD].aggressiveness_class,
                action_sequence_template=tuple(defs[PAT_STANDARD].action_sequence_template)
                + ("wait_review_responses_window",),
                fallback_path_ids=(PATH_PRIOR,),
                caution_flags=_aggregate_caution(ev_by_id, (PAT_STANDARD,)),
                readiness_state=ch_ready,
                explanation="Not merged with identity path when identity matched; suppressed instead.",
                suppressed=suppressed,
                suppression_reason=reason,
            )
        )

    if prior_on:
        add(
            StrategyGeneratedPath(
                path_id=PATH_PRIOR,
                path_name="Prior-round caution / escalation-ready review",
                path_family="action_history",
                version="1.0.0",
                path_objective="Review outcomes of prior letters or disputes before new rounds or escalation.",
                source_pattern_ids=(PAT_PRIOR,),
                path_summary="Caution route when prior activity exists; complements other paths via flags.",
                why_it_applies=f"Matched {PAT_PRIOR}; letter or cumulative disputed activity present.",
                prerequisites=["prior_dispute_or_letter_history"],
                blockers=_fact_blockers(facts),
                timing_class="unknown",
                effort_class="medium",
                risk_class="high",
                aggressiveness_class="conservative",
                action_sequence_template=tuple(defs[PAT_PRIOR].action_sequence_template)
                + ("escalation_ready_if_unresolved",),
                fallback_path_ids=(),
                caution_flags=_aggregate_caution(ev_by_id, (PAT_PRIOR,)),
                readiness_state="conditional",
                explanation="Does not replace challenge paths; surfaces operational caution for later scoring.",
            )
        )

    if not raw_paths:
        reasons: List[str] = []
        if not matched:
            reasons.append("no_strategy_patterns_matched")
        if facts.total_review_claims < 1:
            reasons.append("no_review_claim_surface")
        if facts.candidate_dispute_items < 1:
            reasons.append("no_eligible_dispute_candidates")
        notes.append("emit_structural_await_path")
        add(
            StrategyGeneratedPath(
                path_id=PATH_AWAIT,
                path_name="Await stronger case signals",
                path_family="structural",
                version="1.0.0",
                path_objective="Hold path generation until intelligence yields matchable patterns or eligibility.",
                source_pattern_ids=(),
                path_summary="Low-signal or blocked case surface — no composed routes yet.",
                why_it_applies="No matched patterns produced actionable composed paths.",
                prerequisites=["future_pattern_matches_or_eligibility"],
                blockers=_fact_blockers(facts) + reasons,
                timing_class="unknown",
                effort_class="low",
                risk_class="low",
                aggressiveness_class="conservative",
                action_sequence_template=("refresh_intelligence_inputs", "re_run_pattern_evaluation", "recompose_paths"),
                fallback_path_ids=(),
                caution_flags=[],
                readiness_state="blocked",
                explanation="Grounded absence path — not fabricated variety.",
            )
        )

    priority_index = {pid: i for i, pid in enumerate(_PATH_PRIORITY)}
    nonsuppressed = [p for p in raw_paths if not p.suppressed]
    nonsuppressed_sorted = sorted(nonsuppressed, key=lambda p: priority_index.get(p.path_id, 999))
    if len(nonsuppressed_sorted) > MAX_ACTIVE_PATHS:
        keep_ids = {p.path_id for p in nonsuppressed_sorted[:MAX_ACTIVE_PATHS]}
        notes.append(f"capped_paths_at_{MAX_ACTIVE_PATHS}")
        capped_list: List[StrategyGeneratedPath] = []
        for p in raw_paths:
            if (
                not p.suppressed
                and p.path_id not in keep_ids
                and p.path_id != PATH_AWAIT
            ):
                capped_list.append(
                    replace(p, suppressed=True, suppression_reason="lower_priority_within_max_paths")
                )
            else:
                capped_list.append(p)
        raw_paths = capped_list

    all_paths = sorted(raw_paths, key=lambda p: p.path_id)

    active_candidate_path_ids: List[str] = []
    blocked_path_ids: List[str] = []
    suppressed_path_ids: List[str] = []
    for p in all_paths:
        if p.suppressed:
            suppressed_path_ids.append(p.path_id)
            continue
        if p.readiness_state == "blocked":
            blocked_path_ids.append(p.path_id)
        elif p.readiness_state in ("ready_now", "conditional"):
            active_candidate_path_ids.append(p.path_id)

    return MultiPathStrategyBundle(
        schema_version=BUNDLE_SCHEMA,
        case_intelligence_schema=case_intelligence.schema_version,
        pattern_evaluation_schema=pattern_bundle.schema_version,
        pattern_library_version=PATTERN_LIB_VERSION,
        generation_version=GENERATION_VERSION,
        all_paths=all_paths,
        active_candidate_path_ids=sorted(active_candidate_path_ids),
        blocked_path_ids=sorted(blocked_path_ids),
        suppressed_path_ids=sorted(suppressed_path_ids),
        generation_notes=sorted(notes),
    )


def generate_strategy_paths_for_workflow(workflow_id: str, user_id: int) -> MultiPathStrategyBundle:
    """Build case intelligence, evaluate patterns, then compose paths (DB-backed intelligence)."""
    from services.case_intelligence import build_canonical_case_intelligence_for_workflow
    from services.strategy_patterns import evaluate_strategy_patterns

    ci = build_canonical_case_intelligence_for_workflow(workflow_id, user_id)
    pb = evaluate_strategy_patterns(ci)
    return generate_strategy_paths(ci, pb)
