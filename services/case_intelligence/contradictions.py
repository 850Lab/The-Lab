from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Set

from claims import Claim, ClaimType
from review_claims import ReviewClaim, ReviewType

from .grouping import fingerprint_for_claim
from .models import ContradictionRecord


def _parse_money(s: str) -> Optional[float]:
    if not s:
        return None
    t = re.sub(r"[^\d.\-]", "", str(s))
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def detect_contradictions(
    raw_claims: List[Claim],
    review_claims: List[ReviewClaim],
) -> List[ContradictionRecord]:
    """
    Grounded contradictions only: cross-bureau numeric balance differences,
    incompatible status keywords for the same fingerprint, duplicate review surfaces.
    """
    out: List[ContradictionRecord] = []

    # Balance mismatch across bureaus for same fingerprint
    bal_by_fp_bureau: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for c in raw_claims:
        if c.claim_type != ClaimType.BALANCE_REPORTED:
            continue
        fp_t = fingerprint_for_claim(c)
        if not fp_t:
            continue
        _, fp = fp_t
        bureau = (c.source or "unknown").lower()
        bal = _parse_money(str((c.fields or {}).get("balance", "")))
        if bal is not None and bal >= 0:
            bal_by_fp_bureau[fp][bureau].append(bal)

    for fp, by_b in bal_by_fp_bureau.items():
        if len(by_b) < 2:
            continue
        medians = []
        for b, vals in by_b.items():
            if not vals:
                continue
            medians.append((b, sorted(vals)[len(vals) // 2]))
        if len(medians) < 2:
            continue
        medians.sort(key=lambda x: x[1])
        low_b, low_v = medians[0]
        high_b, high_v = medians[-1]
        if low_v <= 0:
            continue
        rel = (high_v - low_v) / max(low_v, 1.0)
        if rel > 0.05 or abs(high_v - low_v) >= 100:
            involved: List[str] = []
            for c in raw_claims:
                if c.claim_type != ClaimType.BALANCE_REPORTED:
                    continue
                ft = fingerprint_for_claim(c)
                if ft and ft[1] == fp:
                    involved.append(c.claim_id)
            out.append(
                ContradictionRecord(
                    signal_type="cross_bureau_balance_mismatch",
                    description=(
                        f"Balance medians differ materially for the same fingerprint across "
                        f"{low_b} (~{low_v:.0f}) vs {high_b} (~{high_v:.0f})."
                    ),
                    grounded_in="parsed_balance_reported_claims_by_fingerprint",
                    involved_raw_claim_ids=involved[:40],
                    confidence="medium",
                )
            )

    # Status incompatibility across bureaus (open vs charged off / collection)
    stat_by_fp: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
    for c in raw_claims:
        if c.claim_type != ClaimType.STATUS_REPORTED:
            continue
        fp_t = fingerprint_for_claim(c)
        if not fp_t:
            continue
        _, fp = fp_t
        bureau = (c.source or "unknown").lower()
        st = str((c.fields or {}).get("status", "")).lower()
        if st:
            stat_by_fp[fp][bureau].add(st)

    pos_open = ("open", "current", "pays as agreed")
    neg_closed = ("charge", "collection", "repossession", "foreclosure", "closed")

    for fp, by_b in stat_by_fp.items():
        if len(by_b) < 2:
            continue
        texts = [" ".join(v) for v in by_b.values()]
        has_openish = any(any(p in t for p in pos_open) for t in texts)
        has_negish = any(any(p in t for p in neg_closed) for t in texts)
        if has_openish and has_negish:
            involved: List[str] = []
            for c in raw_claims:
                if c.claim_type != ClaimType.STATUS_REPORTED:
                    continue
                ft = fingerprint_for_claim(c)
                if ft and ft[1] == fp:
                    involved.append(c.claim_id)
            out.append(
                ContradictionRecord(
                    signal_type="cross_bureau_status_inconsistency",
                    description=(
                        "Status language across bureaus mixes 'open/current' style with "
                        "'charge-off/collection/closed' style for the same account fingerprint."
                    ),
                    grounded_in="parsed_status_reported_claims_by_fingerprint",
                    involved_raw_claim_ids=involved[:40],
                    confidence="low",
                )
            )

    # Review-layer duplicate + multi-bureau negative on overlapping entities (light signal)
    dup_ids = [rc.review_claim_id for rc in review_claims if rc.review_type == ReviewType.DUPLICATE_ACCOUNT]
    if dup_ids:
        neg = [rc for rc in review_claims if rc.review_type == ReviewType.NEGATIVE_IMPACT]
        creditors = {((rc.entities or {}).get("account_name") or "").lower() for rc in neg}
        if any(c for c in creditors if c):
            out.append(
                ContradictionRecord(
                    signal_type="duplicate_tradeline_with_negatives",
                    description=(
                        "Duplicate-account review items coexist with negative-impact review items; "
                        "verify whether the same obligation is represented more than once."
                    ),
                    grounded_in="review_claim_types_cooccurrence",
                    involved_review_claim_ids=dup_ids[:20],
                    confidence="medium",
                )
            )

    return out
