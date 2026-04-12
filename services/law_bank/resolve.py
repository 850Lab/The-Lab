"""
Deterministic law unit resolution (published units only, structured context only).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Set

from packaging.version import InvalidVersion, Version

from services.law_bank.load_corpus import load_published_units
from services.law_bank.schema import law_unit_ref_from_unit


def _ctx_tags(ctx: Mapping[str, Any]) -> Set[str]:
    raw = ctx.get("subjectMatterTagsPresent")
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw if x is not None and str(x).strip()}


def _ctx_flags(ctx: Mapping[str, Any]) -> Dict[str, bool]:
    raw = ctx.get("outcomePatternFlags")
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, bool] = {}
    for k, v in raw.items():
        if isinstance(v, bool):
            out[str(k)] = v
    return out


def _match_bool_trigger(
    ctx: Mapping[str, Any], key: str, required: bool
) -> bool:
    if key not in ctx:
        return False
    v = ctx[key]
    if not isinstance(v, bool):
        return False
    return v == required


def _match_int_compare(
    ctx: Mapping[str, Any],
    key: str,
    bound: int,
    *,
    gte: bool,
) -> bool:
    if key not in ctx:
        return False
    try:
        cur = int(ctx[key])
    except (TypeError, ValueError):
        return False
    return cur >= bound if gte else cur <= bound


def _match_subject_matter_tags_any(
    ctx: Mapping[str, Any], required_any: List[Any]
) -> bool:
    tags = _ctx_tags(ctx)
    need = {str(x) for x in required_any if x is not None and str(x).strip()}
    if not need:
        return True
    return bool(tags & need)


def _match_subject_matter_tags_all(
    ctx: Mapping[str, Any], required_all: List[Any]
) -> bool:
    tags = _ctx_tags(ctx)
    need = [str(x) for x in required_all if x is not None and str(x).strip()]
    if not need:
        return True
    return all(t in tags for t in need)


def _match_authoritative_step_any(
    ctx: Mapping[str, Any], steps: List[Any]
) -> bool:
    if "authoritativeStepId" not in ctx:
        return False
    cur = str(ctx.get("authoritativeStepId") or "")
    allowed = {str(x) for x in steps if x is not None and str(x).strip()}
    return cur in allowed


def _match_outcome_patterns_any(
    ctx: Mapping[str, Any], patterns: List[Any]
) -> bool:
    flags = _ctx_flags(ctx)
    for p in patterns:
        pid = str(p).strip()
        if not pid:
            continue
        if flags.get(pid) is True:
            return True
    return False


def _match_outcome_patterns_all(
    ctx: Mapping[str, Any], patterns: List[Any]
) -> bool:
    flags = _ctx_flags(ctx)
    for p in patterns:
        pid = str(p).strip()
        if not pid:
            return False
        if flags.get(pid) is not True:
            return False
    return True


def unit_matches_context(unit: Dict[str, Any], ctx: Mapping[str, Any]) -> bool:
    tc = unit.get("triggerConditions")
    if not isinstance(tc, dict):
        return False

    if "subjectMatterTagsAny" in tc:
        v = tc["subjectMatterTagsAny"]
        if not isinstance(v, list) or not _match_subject_matter_tags_any(ctx, v):
            return False

    if "subjectMatterTagsAll" in tc:
        v = tc["subjectMatterTagsAll"]
        if not isinstance(v, list) or not _match_subject_matter_tags_all(ctx, v):
            return False

    if "disputeRoundGte" in tc:
        try:
            b = int(tc["disputeRoundGte"])
        except (TypeError, ValueError):
            return False
        if not _match_int_compare(ctx, "disputeRound", b, gte=True):
            return False

    if "disputeRoundLte" in tc:
        try:
            b = int(tc["disputeRoundLte"])
        except (TypeError, ValueError):
            return False
        if not _match_int_compare(ctx, "disputeRound", b, gte=False):
            return False

    if "authoritativeStepIdAny" in tc:
        v = tc["authoritativeStepIdAny"]
        if not isinstance(v, list) or not _match_authoritative_step_any(ctx, v):
            return False

    for key in (
        "hasBureauTarget",
        "hasFurnisherTarget",
        "identityContext",
        "escalationEligible",
        "hasCollectionAccountSignals",
        "hasInquirySignals",
    ):
        if key not in tc:
            continue
        req = tc[key]
        if not isinstance(req, bool):
            return False
        if not _match_bool_trigger(ctx, key, req):
            return False

    if "requiredOutcomePatternsAny" in tc:
        v = tc["requiredOutcomePatternsAny"]
        if not isinstance(v, list) or not _match_outcome_patterns_any(ctx, v):
            return False

    if "requiredOutcomePatternsAll" in tc:
        v = tc["requiredOutcomePatternsAll"]
        if not isinstance(v, list) or not _match_outcome_patterns_all(ctx, v):
            return False

    return True


def _pick_highest_version_per_unit(
    units: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    for u in units:
        uid = str(u.get("unitId") or "")
        if not uid:
            continue
        prev = best.get(uid)
        if prev is None:
            best[uid] = u
            continue
        try:
            if Version(str(u["version"])) > Version(str(prev["version"])):
                best[uid] = u
        except InvalidVersion:
            continue
    return best


def resolve_law_units(
    context: Dict[str, Any],
    *,
    _published_units: Optional[tuple[Dict[str, Any], ...]] = None,
) -> List[Dict[str, Any]]:
    """
    Return LawUnitRef dicts for published units matching structured context.

    I/O only when resolving default corpus via load_published_units(); pass
    ``_published_units`` in tests to keep calls deterministic without disk.
    """
    corpus = _published_units if _published_units is not None else load_published_units()
    matched = [u for u in corpus if unit_matches_context(u, context)]
    deduped = _pick_highest_version_per_unit(matched)
    ordered_ids = sorted(deduped.keys())
    return [law_unit_ref_from_unit(deduped[uid]) for uid in ordered_ids]
