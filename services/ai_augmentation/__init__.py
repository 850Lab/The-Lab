"""
Phase 15 — AI augmentation (peripheral, non-authoritative).

AI must sit on top of ORION: consume guidance / readiness / explanation / contracts from the
customer bundle or APIs; do not replace or mutate deterministic ORION evaluation inside
``services.guidance``.
"""

from __future__ import annotations

from .api import create_default_stub_provider, is_ai_augmentation_enabled, run_ai_augmentation
from .generator import (
    AiAugmentationProvider,
    OpenAiConfiguredProvider,
    StubDeterministicProvider,
    load_prompt_registry_metadata,
    select_provider,
)
from .input_contract import build_ai_augmentation_request, build_sanitized_model_payload, compute_ai_input_digest
from .schema import AI_OUTPUT_SCHEMA_VERSION, OUTPUT_CATEGORIES_V1, ai_output_dict
from .store import AppendOnlyJsonlStore, InMemoryAiOutputStore
from .validate_output import collect_allowed_entity_ids, validate_ai_output
from .intelligent_explanation import (
    INTELLIGENT_EXPLANATION_FAMILY,
    build_intelligent_explanation_input,
    build_intelligent_explanation_prompt_messages,
    contract_completeness_from_orion_bundle,
    generate_intelligent_explanation,
    internal_intelligent_explanation_audit,
)
from .intelligent_scripts import (
    INTELLIGENT_SCRIPT_FAMILY,
    build_intelligent_script_input,
    build_intelligent_script_prompt_messages,
    generate_intelligent_script,
    internal_intelligent_script_audit,
    validate_customer_ai_script_against_orion,
)

__all__ = [
    "AI_OUTPUT_SCHEMA_VERSION",
    "AiAugmentationProvider",
    "AppendOnlyJsonlStore",
    "InMemoryAiOutputStore",
    "OpenAiConfiguredProvider",
    "OUTPUT_CATEGORIES_V1",
    "StubDeterministicProvider",
    "ai_output_dict",
    "INTELLIGENT_EXPLANATION_FAMILY",
    "build_ai_augmentation_request",
    "build_intelligent_explanation_input",
    "build_intelligent_explanation_prompt_messages",
    "build_sanitized_model_payload",
    "collect_allowed_entity_ids",
    "compute_ai_input_digest",
    "contract_completeness_from_orion_bundle",
    "create_default_stub_provider",
    "generate_intelligent_explanation",
    "internal_intelligent_explanation_audit",
    "INTELLIGENT_SCRIPT_FAMILY",
    "build_intelligent_script_input",
    "build_intelligent_script_prompt_messages",
    "generate_intelligent_script",
    "internal_intelligent_script_audit",
    "validate_customer_ai_script_against_orion",
    "is_ai_augmentation_enabled",
    "load_prompt_registry_metadata",
    "run_ai_augmentation",
    "select_provider",
    "validate_ai_output",
]
