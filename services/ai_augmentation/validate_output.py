"""
Reject unsafe or invalid AI outputs before storage.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple

from .schema import (
    CONFIDENCE_CLASSES,
    ENTITY_KIND_GUIDANCE,
    ENTITY_KIND_PIVOT,
    ENTITY_KIND_SCENARIO,
    ENTITY_KIND_WORKFLOW,
    OUTPUT_CATEGORIES_V1,
)

_MAX_CONTENT_SUMMARY_LEN = 8000
_MAX_TRACE_ENTRIES = 64
_MAX_TRACE_LINE_LEN = 500
_MAX_RELATED_ENTITIES = 64

_PROHIBITED_OUTPUT_ROOT_KEYS = frozenset(
    {
        "execution_command",
        "workflow_mutation",
        "canonical_patch",
        "scenario_patch",
        "pivot_patch",
        "guidance_patch",
        "trigger_id",
        "side_effect",
        "raw_document",
        "webhook",
    }
)

_IMPERATIVE_PATTERNS = (
    re.compile(r"(?i)\bexecute\s*:\s*"),
    re.compile(r"(?i)\binvoke\s+workflow\b"),
    re.compile(r"(?i)\btrigger\s+(workflow|execution)\b"),
    re.compile(r"(?i)\bsystem\s*:\s*override\b"),
)


def collect_allowed_entity_ids(sanitized_payload: Dict[str, Any]) -> Dict[str, Set[str]]:
    ids: Dict[str, Set[str]] = {
        ENTITY_KIND_GUIDANCE: set(),
        ENTITY_KIND_SCENARIO: set(),
        ENTITY_KIND_PIVOT: set(),
        ENTITY_KIND_WORKFLOW: set(),
    }
    wf = str(sanitized_payload.get("workflow_id") or "")
    if wf:
        ids[ENTITY_KIND_WORKFLOW].add(wf)

    gv = sanitized_payload.get("guidance_view")
    if isinstance(gv, dict):
        for gid in gv.get("global_priority_order") or []:
            if gid:
                ids[ENTITY_KIND_GUIDANCE].add(str(gid))
        for g in gv.get("grouped_guidance") or []:
            if not isinstance(g, dict):
                continue
            for gid in g.get("guidance_ids") or []:
                if gid:
                    ids[ENTITY_KIND_GUIDANCE].add(str(gid))

    for s in sanitized_payload.get("scenarios") or []:
        if isinstance(s, dict) and s.get("scenario_id"):
            ids[ENTITY_KIND_SCENARIO].add(str(s["scenario_id"]))

    for p in sanitized_payload.get("pivots") or []:
        if isinstance(p, dict) and p.get("pivot_id"):
            ids[ENTITY_KIND_PIVOT].add(str(p["pivot_id"]))

    return ids


def validate_ai_output(
    output: Dict[str, Any],
    request_envelope: Dict[str, Any],
    *,
    prompt_registry_version: str,
) -> List[str]:
    errors: List[str] = []

    if not output.get("non_authoritative", False):
        errors.append("non_authoritative_must_be_true")

    cat = str(output.get("output_category") or "")
    if cat not in OUTPUT_CATEGORIES_V1:
        errors.append(f"invalid_output_category:{cat}")

    conf = output.get("confidence_class")
    if isinstance(conf, (int, float)):
        errors.append("confidence_must_not_be_numeric")
    elif str(conf) not in CONFIDENCE_CLASSES:
        errors.append(f"invalid_confidence_class:{conf}")

    for k in _PROHIBITED_OUTPUT_ROOT_KEYS:
        if k in output:
            errors.append(f"prohibited_field:{k}")

    summary = output.get("content_summary")
    if not isinstance(summary, str):
        errors.append("content_summary_must_be_string")
    else:
        if len(summary) > _MAX_CONTENT_SUMMARY_LEN:
            errors.append("content_summary_too_long")
        for pat in _IMPERATIVE_PATTERNS:
            if pat.search(summary):
                errors.append("content_summary_blocked_imperative_pattern")
                break

    trace = output.get("explanation_trace")
    if not isinstance(trace, list):
        errors.append("explanation_trace_must_be_list")
    else:
        if len(trace) > _MAX_TRACE_ENTRIES:
            errors.append("explanation_trace_too_long")
        for line in trace:
            if not isinstance(line, str):
                errors.append("explanation_trace_non_string")
                break
            if len(line) > _MAX_TRACE_LINE_LEN:
                errors.append("explanation_trace_line_too_long")
                break

    rel = output.get("related_entities")
    if not isinstance(rel, list):
        errors.append("related_entities_must_be_list")
    elif len(rel) > _MAX_RELATED_ENTITIES:
        errors.append("related_entities_too_many")
    else:
        payload = request_envelope.get("sanitized_payload") or {}
        if not isinstance(payload, dict):
            errors.append("envelope_missing_sanitized_payload")
        else:
            allowed = collect_allowed_entity_ids(payload)
            for ent in rel:
                if not isinstance(ent, dict):
                    errors.append("related_entity_not_object")
                    break
                kind = str(ent.get("entity_kind") or "")
                eid = str(ent.get("entity_id") or "")
                if kind not in allowed:
                    errors.append(f"unknown_entity_kind:{kind}")
                    continue
                if eid not in allowed[kind]:
                    errors.append(f"unknown_entity_id:{kind}:{eid}")

    prov = output.get("provenance")
    if not isinstance(prov, dict):
        errors.append("provenance_must_be_object")
    else:
        if str(prov.get("input_digest") or "") != str(request_envelope.get("input_digest") or ""):
            errors.append("provenance_input_digest_mismatch")

    if prompt_registry_version and isinstance(prov, dict):
        if str(prov.get("prompt_registry_version") or "") != str(prompt_registry_version):
            errors.append("provenance_prompt_registry_mismatch")

    return errors


def partition_validation_result(errors: List[str]) -> Tuple[bool, List[str]]:
    return (len(errors) == 0, errors)
