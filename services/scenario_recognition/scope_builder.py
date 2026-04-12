"""
Build evaluation scopes from a normalized evaluation context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Scope:
    scope_type: str
    scope_key: str
    slice_data: Optional[Dict[str, Any]] = None


def build_scopes(context: Dict[str, Any]) -> List[Scope]:
    scopes: List[Scope] = []
    wf = str(context.get("workflow_id") or "workflow_default")
    scopes.append(Scope(scope_type="workflow", scope_key=wf, slice_data=None))

    slices = context.get("cross_bureau_slices") or []
    if isinstance(slices, list):
        for s in slices:
            if not isinstance(s, dict):
                continue
            fp = str(s.get("account_fingerprint") or "").strip()
            if not fp:
                continue
            scopes.append(Scope(scope_type="account_fingerprint", scope_key=fp, slice_data=s))
    return scopes
