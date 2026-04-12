"""
Materialize execution guidance from scored path + upstream bundles (path-driven playbooks).
"""

from __future__ import annotations

from typing import List, Optional

from services.case_intelligence.models import CanonicalCaseIntelligenceV1
from services.strategy_paths.models import MultiPathStrategyBundle, StrategyGeneratedPath
from services.strategy_patterns.models import StrategyPatternEvaluationBundle
from services.strategy_scoring.models import StrategyScoringBundle

from .models import ExecutionGuidanceBlock, ExecutionGuidanceBundle
from .registry_docs_thin_v1 import PLAYBOOK_ID as DOCS_THIN_PLAYBOOK_ID
from .registry_docs_thin_v1 import PLAYBOOK_VERSION as DOCS_THIN_PLAYBOOK_VERSION
from .registry_docs_thin_v1 import build_docs_thin_blocks
from .registry_spa_v1 import PLAYBOOK_ID as SPA_PLAYBOOK_ID
from .registry_spa_v1 import PLAYBOOK_VERSION as SPA_PLAYBOOK_VERSION
from .registry_spa_v1 import build_spa_blocks
from .triggers import TimingTrigger

SCHEMA_VERSION = "execution_guidance.v1"
TEMPLATE_PLAYBOOK_ID = "path_template_synthesis_v1"
TEMPLATE_PLAYBOOK_VERSION = "1.0.0"

PATH_DOCS_THIN = "path_docs_thin_conservative_first"

SPA_PATH_IDS = frozenset(
    {
        "path_cross_bureau_inconsistency_fast",
        "path_inconsistency_led_challenge",
        "path_duplicate_reporting_cleanup",
        "path_docs_supported_standard",
        "path_standard_negative_first_pass",
    }
)


def _path_by_id(bundle: MultiPathStrategyBundle, path_id: str) -> Optional[StrategyGeneratedPath]:
    for p in bundle.all_paths:
        if p.path_id == path_id:
            return p
    return None


def _fix_synthesis_chain(blocks: List[ExecutionGuidanceBlock]) -> List[ExecutionGuidanceBlock]:
    if not blocks:
        return blocks
    out: List[ExecutionGuidanceBlock] = []
    for i, b in enumerate(blocks):
        prev_bid = blocks[i - 1].block_id if i > 0 else None
        tt = (
            TimingTrigger("immediate", {})
            if i == 0
            else TimingTrigger("after_block_ids", {"blockIds": [prev_bid]})
        )
        nxt = {"complete": [blocks[i + 1].block_id]} if i < len(blocks) - 1 else {}
        out.append(
            ExecutionGuidanceBlock(
                block_id=b.block_id,
                path_id=b.path_id,
                block_type=b.block_type,
                action_name=b.action_name,
                actor=b.actor,
                channel=b.channel,
                timing_trigger=tt,
                prerequisites=list(b.prerequisites),
                instructions=b.instructions,
                script_objective=b.script_objective,
                prohibited_actions=list(b.prohibited_actions),
                caution_notes=list(b.caution_notes),
                expected_outcomes=list(b.expected_outcomes),
                signal_capture_targets=list(b.signal_capture_targets),
                next_by_outcome=nxt,
                readiness_state=b.readiness_state,
                explanation=b.explanation,
            )
        )
    return out


def _synthesize_from_path_template(path: StrategyGeneratedPath) -> Tuple[List[ExecutionGuidanceBlock], List[ParallelGroup], List[str], List[str]]:
    raw: List[ExecutionGuidanceBlock] = []
    for i, step in enumerate(path.action_sequence_template):
        bid = f"{path.path_id}_tpl_{i}"
        raw.append(
            ExecutionGuidanceBlock(
                block_id=bid,
                path_id=path.path_id,
                block_type="interpret_path_template_step",
                action_name=step.replace("_", " ").title(),
                actor="hybrid",
                channel="internal_review",
                timing_trigger=TimingTrigger("immediate", {}),
                prerequisites=[],
                instructions=(
                    f"Execute this step from the strategy path template: {step!r}. "
                    "Use existing workflow tools (letters, mail, uploads) as applicable. "
                    "All actions must be truthful and lawful."
                ),
                script_objective=None,
                prohibited_actions=["misrepresentation", "fraudulent_claims"],
                caution_notes=["Template step only — detailed playbook not yet authored for this path."],
                expected_outcomes=["step_complete"],
                signal_capture_targets=[],
                next_by_outcome={},
                readiness_state=path.readiness_state,
                explanation=f"Synthesized from path.action_sequence_template step {step!r}.",
            )
        )
    fixed = _fix_synthesis_chain(raw)
    if not fixed:
        return [], [], [], []
    return fixed, [], [fixed[0].block_id], [fixed[-1].block_id]


def resolve_playbook_id(path_id: str) -> str:
    if path_id == PATH_DOCS_THIN:
        return DOCS_THIN_PLAYBOOK_ID
    if path_id in SPA_PATH_IDS:
        return SPA_PLAYBOOK_ID
    return TEMPLATE_PLAYBOOK_ID


def build_execution_guidance_bundle(
    case_intelligence: CanonicalCaseIntelligenceV1,
    pattern_bundle: StrategyPatternEvaluationBundle,
    path_bundle: MultiPathStrategyBundle,
    scoring_bundle: StrategyScoringBundle,
    *,
    primary_path_id: Optional[str] = None,
) -> ExecutionGuidanceBundle:
    """
    Select playbook from **primary strategy path id** (scoring primary unless overridden).
    """
    notes: List[str] = []
    objective_id = scoring_bundle.objective_id
    primary = primary_path_id if primary_path_id is not None else scoring_bundle.recommended_primary_path_id
    notes.append(f"pattern_evaluation_schema:{pattern_bundle.schema_version}")

    if not primary:
        notes.append("no_primary_path_empty_execution_bundle")
        return ExecutionGuidanceBundle(
            schema_version=SCHEMA_VERSION,
            playbook_id=TEMPLATE_PLAYBOOK_ID,
            playbook_version=TEMPLATE_PLAYBOOK_VERSION,
            primary_path_id=None,
            objective_id=objective_id,
            blocks=[],
            parallel_groups=[],
            entry_block_ids=[],
            terminal_block_ids=[],
            case_intelligence_schema=case_intelligence.schema_version,
            pattern_library_version=path_bundle.pattern_library_version,
            path_generation_version=path_bundle.generation_version,
            scoring_version=scoring_bundle.scoring_version,
            generation_notes=sorted(notes),
        )

    path_obj = _path_by_id(path_bundle, primary)
    if not path_obj:
        notes.append("primary_path_id_not_found_in_path_bundle")

    playbook_id = resolve_playbook_id(primary)

    if playbook_id == DOCS_THIN_PLAYBOOK_ID:
        blocks, groups, entries, terminals = build_docs_thin_blocks(primary)
        pb_ver = DOCS_THIN_PLAYBOOK_VERSION
        notes.append("playbook_docs_thin_standard_dispute_v1")
    elif playbook_id == SPA_PLAYBOOK_ID:
        blocks, groups, entries, terminals = build_spa_blocks(primary)
        pb_ver = SPA_PLAYBOOK_VERSION
        notes.append("playbook_spa_synchronized_pressure_v1")
    else:
        if path_obj:
            blocks, groups, entries, terminals = _synthesize_from_path_template(path_obj)
        else:
            blocks, groups, entries, terminals = [], [], [], []
        pb_ver = TEMPLATE_PLAYBOOK_VERSION
        notes.append("playbook_path_template_synthesis_v1")

    blocks = sorted(blocks, key=lambda b: b.block_id)

    return ExecutionGuidanceBundle(
        schema_version=SCHEMA_VERSION,
        playbook_id=playbook_id,
        playbook_version=pb_ver,
        primary_path_id=primary,
        objective_id=objective_id,
        blocks=blocks,
        parallel_groups=groups,
        entry_block_ids=list(entries),
        terminal_block_ids=list(terminals),
        case_intelligence_schema=case_intelligence.schema_version,
        pattern_library_version=path_bundle.pattern_library_version,
        path_generation_version=path_bundle.generation_version,
        scoring_version=scoring_bundle.scoring_version,
        generation_notes=sorted(set(notes)),
    )


def build_execution_guidance_for_workflow(
    workflow_id: str,
    user_id: int,
    *,
    objective: str = "fastest_credible_result",
    primary_path_id: Optional[str] = None,
) -> ExecutionGuidanceBundle:
    from services.case_intelligence import build_canonical_case_intelligence_for_workflow
    from services.strategy_paths import generate_strategy_paths
    from services.strategy_patterns import evaluate_strategy_patterns
    from services.strategy_scoring import score_strategy_paths

    ci = build_canonical_case_intelligence_for_workflow(workflow_id, user_id)
    pb = evaluate_strategy_patterns(ci)
    paths = generate_strategy_paths(ci, pb)
    scored = score_strategy_paths(ci, pb, paths, objective=objective)
    return build_execution_guidance_bundle(ci, pb, paths, scored, primary_path_id=primary_path_id)
