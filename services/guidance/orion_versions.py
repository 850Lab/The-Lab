"""
Canonical ORION layer version strings for audit, drift detection, and operator tooling.

ORION is deterministic and versioned per sub-layer. These values are the single source of truth
for audit payloads; bundle payloads may also embed matching fields (e.g. prioritizationVersion).
Do NOT inject AI logic into ORION layers; AI consumes ORION outputs downstream only.
"""

from __future__ import annotations

from typing import Dict

from services.guidance.action_explanation import ACTION_EXPLANATION_VERSION
from services.guidance.delivery_prioritization import DELIVERY_PRIORITIZATION_VERSION
from services.guidance.ux_surface_contract import UX_SURFACE_CONTRACT_VERSION

# Action readiness ranking / catalog — versioned as a layer even though API dicts omit a field today.
ORION_ACTION_READINESS_VERSION = "orion_action_readiness_v1"

ORION_VERSIONS: Dict[str, str] = {
    "action_readiness": ORION_ACTION_READINESS_VERSION,
    "action_explanation": ACTION_EXPLANATION_VERSION,
    "delivery_prioritization": DELIVERY_PRIORITIZATION_VERSION,
    "ux_surface_contract": UX_SURFACE_CONTRACT_VERSION,
}


def orion_versions_for_audit_response() -> Dict[str, str]:
    """CamelCase keys aligned with audit-level API fields."""
    return {
        "actionReadinessVersion": ORION_VERSIONS["action_readiness"],
        "actionExplanationVersion": ORION_VERSIONS["action_explanation"],
        "deliveryPrioritizationVersion": ORION_VERSIONS["delivery_prioritization"],
        "uxSurfaceContractVersion": ORION_VERSIONS["ux_surface_contract"],
    }

