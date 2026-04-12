"""
Phase 15 — AI output schema (non-authoritative, peripheral only).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

AI_OUTPUT_SCHEMA_VERSION = "1.0.0"

OUTPUT_CATEGORY_SUMMARY_EXPLANATION = "summary_explanation"
OUTPUT_CATEGORY_SCENARIO_INTERPRETATION = "scenario_interpretation"
OUTPUT_CATEGORY_STRATEGY_EXPLANATION = "strategy_explanation"
OUTPUT_CATEGORY_ANOMALY_SUGGESTION = "anomaly_suggestion"
OUTPUT_CATEGORY_PATTERN_SUGGESTION = "pattern_suggestion"
OUTPUT_CATEGORY_OPERATOR_ASSIST = "operator_assist"

OUTPUT_CATEGORIES_V1 = frozenset(
    {
        OUTPUT_CATEGORY_SUMMARY_EXPLANATION,
        OUTPUT_CATEGORY_SCENARIO_INTERPRETATION,
        OUTPUT_CATEGORY_STRATEGY_EXPLANATION,
        OUTPUT_CATEGORY_ANOMALY_SUGGESTION,
        OUTPUT_CATEGORY_PATTERN_SUGGESTION,
        OUTPUT_CATEGORY_OPERATOR_ASSIST,
    }
)

CONFIDENCE_LOW = "low"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_HIGH = "high"
CONFIDENCE_UNSPECIFIED = "unspecified"

CONFIDENCE_CLASSES = frozenset(
    {CONFIDENCE_LOW, CONFIDENCE_MEDIUM, CONFIDENCE_HIGH, CONFIDENCE_UNSPECIFIED}
)

ENTITY_KIND_GUIDANCE = "guidance"
ENTITY_KIND_SCENARIO = "scenario"
ENTITY_KIND_PIVOT = "pivot"
ENTITY_KIND_WORKFLOW = "workflow"


def ai_output_dict(
    *,
    ai_output_id: str,
    output_type: str,
    output_category: str,
    related_entities: List[Dict[str, str]],
    content_summary: str,
    confidence_class: str,
    explanation_trace: List[str],
    created_at: str,
    ai_engine_version: str,
    provenance: Dict[str, Any],
    non_authoritative: bool = True,
    version: str = AI_OUTPUT_SCHEMA_VERSION,
    ai_guardrail_flags: Optional[List[str]] = None,
    insight_scope_alignment: Optional[str] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ai_output_id": ai_output_id,
        "version": version,
        "output_type": output_type,
        "output_category": output_category,
        "related_entities": list(related_entities),
        "content_summary": content_summary,
        "confidence_class": confidence_class,
        "explanation_trace": list(explanation_trace),
        "created_at": created_at,
        "ai_engine_version": ai_engine_version,
        "non_authoritative": bool(non_authoritative),
        "provenance": dict(provenance),
    }
    if ai_guardrail_flags:
        out["ai_guardrail_flags"] = sorted(set(ai_guardrail_flags))
    if insight_scope_alignment:
        out["insight_scope_alignment"] = insight_scope_alignment
    return out
