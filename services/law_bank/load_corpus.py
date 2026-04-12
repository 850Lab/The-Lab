"""
Load V1 law units from bundled JSON. Verifies content integrity hash.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from packaging.version import Version, InvalidVersion

from services.law_bank.schema import (
    ENFORCEMENT_SHAPE_VALUES,
    LEVERAGE_TYPE_VALUES,
    STATUS_VALUES,
)


_CORPUS_PATH = Path(__file__).resolve().parent / "corpus" / "units.json"


def _canonical_json_for_hash(unit: Dict[str, Any]) -> str:
    body = {k: v for k, v in unit.items() if k != "contentHash"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def compute_content_hash(unit: Dict[str, Any]) -> str:
    payload = _canonical_json_for_hash(unit)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_unit(unit: Dict[str, Any], *, index: int) -> None:
    required = [
        "unitId",
        "version",
        "status",
        "title",
        "summary",
        "domains",
        "subjectMatterTags",
        "leverageType",
        "enforcementShape",
        "triggerConditions",
        "leverageImpact",
        "applicabilityNotes",
        "relatedOutcomePatterns",
        "primaryCitations",
        "effectiveAsOf",
        "reviewedAt",
        "reviewedBy",
        "contentHash",
    ]
    for k in required:
        if k not in unit:
            raise ValueError(f"units[{index}] missing required field {k!r}")
    if unit["status"] not in STATUS_VALUES:
        raise ValueError(f"units[{index}] invalid status {unit['status']!r}")
    if unit["leverageType"] not in LEVERAGE_TYPE_VALUES:
        raise ValueError(f"units[{index}] invalid leverageType")
    if unit["enforcementShape"] not in ENFORCEMENT_SHAPE_VALUES:
        raise ValueError(f"units[{index}] invalid enforcementShape")
    if not isinstance(unit.get("primaryCitations"), list) or not unit["primaryCitations"]:
        raise ValueError(f"units[{index}] primaryCitations must be non-empty list")
    expected = compute_content_hash(unit)
    if unit.get("contentHash") != expected:
        raise ValueError(
            f"units[{index}] contentHash mismatch for unitId={unit.get('unitId')!r}"
        )
    try:
        Version(str(unit["version"]))
    except InvalidVersion as e:
        raise ValueError(f"units[{index}] invalid semver version") from e


@lru_cache(maxsize=1)
def load_published_units() -> tuple[Dict[str, Any], ...]:
    """
    Load corpus and return only published units as an immutable tuple (deterministic order file order).
    """
    raw = _CORPUS_PATH.read_text(encoding="utf-8-sig")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("corpus/units.json must be a JSON array")
    out: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"units[{i}] must be an object")
        _validate_unit(item, index=i)
        if item["status"] == "published":
            out.append(item)
    return tuple(out)
