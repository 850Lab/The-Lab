"""
Structured guidance returned to API clients and stored in ``guidance_events``.

ORION V1.1: delivery contract (display eligibility, channel, cooldown, recommended action).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

GuidanceType = Literal["nudge", "warning", "instruction", "optimization"]
DeliveryChannel = Literal["inline", "banner", "passive", "internal_only"]
RecommendedActionType = Literal[
    "navigate",
    "retry",
    "review",
    "wait",
    "upload",
    "confirm",
    "internal_only",
]


@dataclass
class GuidanceResponse:
    """Single evaluated guidance item (O.R.I.O.N. output) including delivery metadata."""

    guidance_id: str
    rule_key: str
    type: GuidanceType
    message: str
    step_id: str
    priority: int
    trigger_source: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # V1.1 delivery
    display_eligible: bool = True
    delivery_channel: DeliveryChannel = "inline"
    cooldown_seconds: int = 0
    recommended_action: Optional[Dict[str, Any]] = None
    # Legacy human-readable list (audit / older clients)
    suggested_actions: List[str] = field(default_factory=list)

    def is_user_deliverable(self) -> bool:
        """True if this should be exposed on customer workflow API payloads."""
        if not self.display_eligible:
            return False
        if self.delivery_channel == "internal_only":
            return False
        return True

    def to_api_dict(self) -> Dict[str, Any]:
        """Full API-safe shape (operators + clients)."""
        ts = self.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        out: Dict[str, Any] = {
            "guidanceId": self.guidance_id,
            "ruleKey": self.rule_key,
            "type": self.type,
            "message": self.message,
            "stepId": self.step_id,
            "priority": self.priority,
            "triggerSource": self.trigger_source or self.rule_key,
            "timestamp": ts.isoformat(),
            "displayEligible": self.display_eligible,
            "deliveryChannel": self.delivery_channel,
            "cooldownSeconds": int(self.cooldown_seconds),
            "recommendedAction": self.recommended_action,
        }
        if self.suggested_actions:
            out["suggestedActions"] = list(self.suggested_actions)
        return out

    def to_user_api_dict(self) -> Optional[Dict[str, Any]]:
        """Customer-facing payload; null-equivalent when not deliverable."""
        if not self.is_user_deliverable():
            return None
        d = self.to_api_dict()
        # Keep contract minimal for UX surfaces
        d.pop("suggestedActions", None)
        return d
