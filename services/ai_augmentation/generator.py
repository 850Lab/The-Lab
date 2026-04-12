"""
Model boundary: consumes envelope, returns candidate AIOutput dicts.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

from .input_contract import compute_ai_input_digest
from .schema import (
    CONFIDENCE_MEDIUM,
    ENTITY_KIND_GUIDANCE,
    ENTITY_KIND_WORKFLOW,
    OUTPUT_CATEGORIES_V1,
    ai_output_dict,
)


def load_prompt_registry_metadata() -> Dict[str, Any]:
    """Parse minimal fields from prompts/registry.yaml without PyYAML dependency."""
    path = Path(__file__).resolve().parent / "prompts" / "registry.yaml"
    text = path.read_text(encoding="utf-8")
    version = "prompts@unknown"
    category_types: Dict[str, str] = {}
    current_cat: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0 and stripped.startswith("registry_version:"):
            version = stripped.split(":", 1)[1].strip().strip("\"'")
        elif indent == 2 and stripped.endswith(":") and stripped != "categories:":
            current_cat = stripped[:-1].strip()
        elif indent == 4 and current_cat and stripped.startswith("output_type:"):
            rhs = stripped.split(":", 1)[1].strip().strip("\"'")
            category_types[current_cat] = rhs
    return {"registry_version": version, "category_output_types": category_types}


class AiAugmentationProvider(ABC):
    @abstractmethod
    def generate(self, request_envelope: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class StubDeterministicProvider(AiAugmentationProvider):
    """
    Test/dev provider: deterministic text from envelope digest and category.
    No external network.
    """

    def generate(self, request_envelope: Dict[str, Any]) -> Dict[str, Any]:
        meta = load_prompt_registry_metadata()
        payload = request_envelope.get("sanitized_payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        category = str(payload.get("output_category") or "")
        if category not in OUTPUT_CATEGORIES_V1:
            category = "summary_explanation"
        digest = str(request_envelope.get("input_digest") or compute_ai_input_digest(payload))
        basis = f"{digest}|{category}".encode("utf-8")
        hid = hashlib.sha256(basis).hexdigest()[:20]
        wf = str(payload.get("workflow_id") or "")
        run = str(payload.get("evaluation_run_id") or "")
        output_types = meta.get("category_output_types") or {}
        output_type = str(output_types.get(category) or "narrative_summary")
        content = (
            f"Non-authoritative stub narrative for category={category}. "
            f"Derived from input_digest suffix {digest[-12:]}. "
            f"Not an instruction to execute or change system state."
        )
        related: list[dict[str, str]] = []
        if wf:
            related.append({"entity_kind": ENTITY_KIND_WORKFLOW, "entity_id": wf})
        gv = payload.get("guidance_view")
        if isinstance(gv, dict):
            order = gv.get("global_priority_order") or []
            if isinstance(order, list) and order:
                related.append({"entity_kind": ENTITY_KIND_GUIDANCE, "entity_id": str(order[0])})
        return ai_output_dict(
            ai_output_id=f"aio_stub_{hid}",
            output_type=output_type,
            output_category=category,
            related_entities=related,
            content_summary=content,
            confidence_class=CONFIDENCE_MEDIUM,
            explanation_trace=[
                "stub:hash_payload",
                f"stub:category={category}",
            ],
            created_at=str(payload.get("created_at") or ""),
            ai_engine_version="stub@deterministic-v1",
            provenance={
                "workflow_id": wf,
                "evaluation_run_id": run,
                "input_digest": digest,
                "prompt_registry_version": meta["registry_version"],
                "envelope_version": request_envelope.get("envelope_version"),
            },
            non_authoritative=True,
            ai_guardrail_flags=["stub_provider", "no_vendor_call"],
            insight_scope_alignment="workflow_snapshot",
        )


class OpenAiConfiguredProvider(AiAugmentationProvider):
    """
    Placeholder for future wiring; not used in default tests.
    Instantiating without credentials should raise if generate() is called.
    """

    def __init__(self, *, api_key: str | None) -> None:
        self._api_key = api_key

    def generate(self, request_envelope: Dict[str, Any]) -> Dict[str, Any]:
        if not self._api_key:
            raise RuntimeError("OpenAiConfiguredProvider requires API key; use StubDeterministicProvider in tests")
        raise NotImplementedError("Vendor path not implemented in Phase 15 skeleton")


def select_provider(explicit: str | None, *, openai_api_key: str | None = None) -> AiAugmentationProvider:
    choice = (explicit or "stub").lower()
    if choice == "openai":
        return OpenAiConfiguredProvider(api_key=openai_api_key)
    return StubDeterministicProvider()
