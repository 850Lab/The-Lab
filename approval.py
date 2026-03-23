"""
approval.py | 850 Lab Parser Machine
Immutable Contracts - Node 5: User Approval Semantics (CLOSED)

Creates and validates approval snapshots.
Material changes invalidate approval. No approval drift allowed.
"""

from __future__ import annotations
import uuid
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from constants import SYSTEM_ERROR_UI_STATE


@dataclass
class Approval:
    approval_id: str
    user_id: str
    approved_at: str
    capacity_limit: int
    approved_letters: List[Tuple[str, str, str]]
    approved_items: List[str]
    approved_postures: List[str]
    approved_targets: List[str]
    state_hash: str = ""


def _compute_state_hash(
    approved_letters: List[Tuple[str, str, str]],
    approved_items: List[str],
    approved_postures: List[str],
    approved_targets: List[str],
    capacity_limit: int,
) -> str:
    state = {
        "letters": [list(lk) for lk in sorted(approved_letters)],
        "items": sorted(approved_items),
        "postures": sorted(approved_postures),
        "targets": sorted(approved_targets),
        "capacity": capacity_limit,
    }
    canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def create_approval(
    user_id: str,
    capacity_limit: int,
    approved_letters: List[Tuple[str, str, str]],
    approved_items: List[str],
    approved_postures: List[str],
    approved_targets: List[str],
) -> Approval:
    approval_id = str(uuid.uuid4())
    approved_at = datetime.utcnow().isoformat()

    state_hash = _compute_state_hash(
        approved_letters,
        approved_items,
        approved_postures,
        approved_targets,
        capacity_limit,
    )

    return Approval(
        approval_id=approval_id,
        user_id=user_id,
        approved_at=approved_at,
        capacity_limit=capacity_limit,
        approved_letters=approved_letters,
        approved_items=approved_items,
        approved_postures=approved_postures,
        approved_targets=approved_targets,
        state_hash=state_hash,
    )


def approval_is_valid(approval: Approval, current_state_snapshot: Dict[str, Any]) -> bool:
    current_letters = current_state_snapshot.get("approved_letters", [])
    current_items = current_state_snapshot.get("approved_items", [])
    current_postures = current_state_snapshot.get("approved_postures", [])
    current_targets = current_state_snapshot.get("approved_targets", [])
    current_capacity = current_state_snapshot.get("capacity_limit", approval.capacity_limit)

    current_hash = _compute_state_hash(
        current_letters,
        current_items,
        current_postures,
        current_targets,
        current_capacity,
    )

    return approval.state_hash == current_hash
