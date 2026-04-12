"""
Stable input digest for pivot evaluation (reproducibility).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_pivot_input_digest(
    scenarios: List[Dict[str, Any]],
    canonical_snapshot: Dict[str, Any] | None,
    evaluation_run_id: str,
) -> str:
    scen_sorted = sorted(
        scenarios,
        key=lambda s: (
            int(s.get("priority") or 0),
            str(s.get("scenario_type") or ""),
            str(s.get("scope_key") or ""),
            str(s.get("scenario_id") or ""),
        ),
    )
    payload = {
        "evaluation_run_id": evaluation_run_id,
        "scenarios": scen_sorted,
        "canonical_snapshot": canonical_snapshot or {},
    }
    h = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{h}"
