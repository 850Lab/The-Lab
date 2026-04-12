"""
Minimal isolated API: optional generate + validate + store.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .generator import AiAugmentationProvider, StubDeterministicProvider, load_prompt_registry_metadata, select_provider
from .input_contract import build_ai_augmentation_request
from .validate_output import validate_ai_output


def is_ai_augmentation_enabled(config: Optional[Dict[str, Any]] = None) -> bool:
    if config is None:
        return False
    return bool(config.get("enabled"))


def run_ai_augmentation(
    *,
    workflow_id: str,
    evaluation_run_id: str,
    output_category: str,
    guidance_view: Optional[Dict[str, Any]] = None,
    scenarios: Optional[List[Dict[str, Any]]] = None,
    pivots: Optional[List[Dict[str, Any]]] = None,
    canonical_summary: Optional[Dict[str, Any]] = None,
    created_at: str = "",
    config: Optional[Dict[str, Any]] = None,
    store: Optional[Any] = None,
    provider: Optional[AiAugmentationProvider] = None,
    extra_raw_request_fields: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    When disabled or config None, returns None without touching store or provider.
    Deterministic inputs are not mutated.
    """
    if not is_ai_augmentation_enabled(config):
        return None

    envelope = build_ai_augmentation_request(
        workflow_id=workflow_id,
        evaluation_run_id=evaluation_run_id,
        output_category=output_category,
        guidance_view=guidance_view,
        scenarios=scenarios,
        pivots=pivots,
        canonical_summary=canonical_summary,
        created_at=created_at,
        extra_forbidden_top_level=extra_raw_request_fields,
    )

    prov = provider
    if prov is None:
        prov = select_provider(
            (config or {}).get("provider"),
            openai_api_key=(config or {}).get("openai_api_key"),
        )

    meta = load_prompt_registry_metadata()
    candidate = prov.generate(envelope)
    errors = validate_ai_output(
        candidate,
        envelope,
        prompt_registry_version=str(meta.get("registry_version") or ""),
    )
    if errors:
        return {"ok": False, "errors": errors, "candidate": candidate}

    if store is not None:
        store.append(
            workflow_id=workflow_id,
            evaluation_run_id=evaluation_run_id,
            ai_output=candidate,
        )
    return {"ok": True, "ai_output": candidate, "request_envelope": envelope}


def create_default_stub_provider() -> StubDeterministicProvider:
    return StubDeterministicProvider()
