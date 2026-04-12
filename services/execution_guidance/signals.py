"""
Signal capture targets (e.g. verification probe outcomes). Forward-compatible with transcript hooks.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class VerificationFailureSeverity(str, Enum):
    """Strategic leverage signal only — not a legal finding."""

    weak = "weak"
    medium = "medium"
    strong = "strong"


@dataclass(frozen=True)
class SignalCaptureTarget:
    target_id: str
    description: str
    severity_if_matched: Optional[str] = None  # VerificationFailureSeverity value
    source_hint: str = "user_reported"  # user_reported | transcript_pending

    def to_dict(self) -> Dict[str, Any]:
        return {
            "targetId": self.target_id,
            "description": self.description,
            "severityIfMatched": self.severity_if_matched,
            "sourceHint": self.source_hint,
        }
