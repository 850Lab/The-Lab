"""
Non-blocking O.R.I.O.N. evaluation after workflow mutations (daemon threads).
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

_log = logging.getLogger(__name__)


def schedule_guidance_evaluation(
    workflow_id: str,
    latest_event: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Fire-and-forget ``evaluate_guidance`` — never blocks callers, never raises.
    """
    wf = (workflow_id or "").strip()
    if not wf:
        return

    hint = dict(latest_event) if isinstance(latest_event, dict) else None

    def _run() -> None:
        try:
            from services.guidance.guidance_engine import evaluate_guidance

            evaluate_guidance(None, wf, hint)
        except Exception:
            _log.debug("ORION scheduled eval failed wf=%s", wf, exc_info=True)

    t = threading.Thread(
        target=_run,
        name=f"orion-{wf[:10]}",
        daemon=True,
    )
    t.start()
