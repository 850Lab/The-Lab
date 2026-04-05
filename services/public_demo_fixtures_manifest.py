"""
Fixture PDF paths and scenario copy for the public ``/demo`` API.

Primary source: ``config/public_demo_scenarios.json`` (edit without code changes).
Fallback: embedded defaults if the file is missing or invalid.

Kept free of ``customer_dispute_strategy`` / workflow imports so launch checks and
static tooling can verify files exist without circular import issues.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

_log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = REPO_ROOT / "config" / "public_demo_scenarios.json"

_EMBEDDED_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "transunion_acr": {
        "title": "When your report has a lot of damage",
        "description": (
            "Late payments, collections, and charge-offs - see how we'd line up what to fix first. "
            "Sample only; your real report would be yours."
        ),
        "file": "samples/transunion_acr_fixture_sample.pdf",
        "fixture_bundle": [
            "samples/transunion_acr_fixture_sample.pdf",
            "samples/experian_fixture_sample.pdf",
            "samples/equifax_fixture_sample.pdf",
        ],
        "category": "general",
        "category_label": "Clean up my report",
    },
    "experian": {
        "title": "When you need more than a basic 'please fix this'",
        "description": (
            "Some issues involve timing, proof, and what fair-credit rules say. "
            "This demo shows how we highlight that when the facts fit - not legal advice."
        ),
        "file": "samples/experian_fixture_sample.pdf",
        "fixture_bundle": [
            "samples/transunion_acr_fixture_sample.pdf",
            "samples/experian_fixture_sample.pdf",
            "samples/equifax_fixture_sample.pdf",
        ],
        "category": "law_backed",
        "category_label": "Stronger pushback",
    },
    "equifax": {
        "title": "When you're new to credit or don't have many accounts",
        "description": (
            "Few accounts doesn't mean you can't fix mistakes - plus ideas to strengthen your profile over time. "
            "Sample story, not your file."
        ),
        "file": "samples/equifax_fixture_sample.pdf",
        "fixture_bundle": [
            "samples/transunion_acr_fixture_sample.pdf",
            "samples/experian_fixture_sample.pdf",
            "samples/equifax_fixture_sample.pdf",
        ],
        "category": "thin_file",
        "category_label": "Start or rebuild",
    },
}


def _load_demo_scenarios_from_disk() -> Dict[str, Dict[str, Any]]:
    if not _CONFIG_PATH.is_file():
        _log.info("public demo scenarios: using embedded defaults (%s missing)", _CONFIG_PATH)
        return dict(_EMBEDDED_SCENARIOS)
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("scenarios") if isinstance(data, dict) else None
        if not isinstance(raw, dict) or not raw:
            _log.warning("public demo scenarios: invalid JSON shape, using embedded defaults")
            return dict(_EMBEDDED_SCENARIOS)
        return raw
    except Exception as ex:
        _log.warning("public demo scenarios: could not load %s (%s), using embedded defaults", _CONFIG_PATH, ex)
        return dict(_EMBEDDED_SCENARIOS)


# Snapshot at import (e.g. static checks). **Public demo HTTP handlers should call
# ``demo_scenarios()``** so edits to ``config/public_demo_scenarios.json`` apply without
# restarting the API process.
DEMO_SCENARIOS: Dict[str, Dict[str, Any]] = _load_demo_scenarios_from_disk()


def demo_scenarios() -> Dict[str, Dict[str, Any]]:
    """Current scenario config from disk (or embedded fallback). Safe to call per request."""
    return _load_demo_scenarios_from_disk()
