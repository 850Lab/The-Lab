"""
Structured timing triggers for execution blocks (not prose-only scheduling).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class TimingTrigger:
    """
    kind examples:
    - immediate
    - after_parallel_group_complete
    - after_mail_receipt_confirmed
    - after_calendar_days
    - after_block_ids
    - conditional_on_outcome
    """

    kind: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "payload": dict(self.payload)}
