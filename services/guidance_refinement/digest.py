"""
Stable input digest for guidance refinement.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_refinement_input_digest(context: Dict[str, Any], rules_version: str) -> str:
    items = context.get("guidance_items") or []
    pivots = context.get("pivots") or []
    scenarios = context.get("scenarios") or []
    payload = {
        "workflow_id": context.get("workflow_id"),
        "evaluation_run_id": context.get("evaluation_run_id"),
        "step_context": context.get("step_context"),
        "guidance_items": sorted(
            items,
            key=lambda x: str(x.get("guidance_id") or ""),
        ),
        "pivots": sorted(pivots, key=lambda x: str(x.get("pivot_id") or "")),
        "scenarios": sorted(scenarios, key=lambda x: str(x.get("scenario_id") or "")),
        "rules_version": rules_version,
    }
    h = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{h}"
