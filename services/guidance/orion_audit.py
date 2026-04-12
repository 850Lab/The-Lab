"""
Read-only ORION bundle snapshots for operators and debugging.

Does not mutate workflow, steps, or guidance event logs when built via customer_orion_bundle_for_api(..., persist_guidance=False).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.guidance.guidance_engine import customer_orion_bundle_for_api
from services.guidance.orion_versions import orion_versions_for_audit_response


def audit_orion_bundle_for_workflow(workflow_id: Optional[str]) -> Dict[str, Any]:
    """
    Single snapshot: customer-visible ORION bundle + canonical version metadata + timestamp.

    Read-only with respect to persistence: guidance evaluation is invoked with persist_guidance=False.
    """
    wf = (workflow_id or "").strip()
    bundle = customer_orion_bundle_for_api(
        wf if wf else None,
        persist_guidance=False,
    )
    return {
        "workflowId": wf or None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "guidance": bundle.get("guidance"),
        "bestAction": bundle.get("bestAction"),
        "bestActionExplanation": bundle.get("bestActionExplanation"),
        "deliveryPrioritization": bundle.get("deliveryPrioritization"),
        "uxSurfaceContract": bundle.get("uxSurfaceContract"),
        "versions": orion_versions_for_audit_response(),
    }
