from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from claims import Claim, ClaimType

from .models import NormalizedAccountGroup


def _scrub_creditor(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s[:48] if s else "unknown"


def _last4(fields: Dict) -> str:
    for k in ("last4", "account_last4", "account_number", "account"):
        v = fields.get(k)
        if v is None:
            continue
        digits = re.sub(r"\D", "", str(v))
        if len(digits) >= 4:
            return digits[-4:]
        if digits:
            return digits
    return ""


def fingerprint_for_claim(c: Claim) -> Optional[Tuple[str, str]]:
    """
    (scrubbed_creditor, last4_or_empty) for tradeline-like claims only.
    Returns None for claims that are not account/tradeline anchors.
    """
    if c.claim_type not in (
        ClaimType.ACCOUNT_PRESENT,
        ClaimType.BALANCE_REPORTED,
        ClaimType.STATUS_REPORTED,
        ClaimType.LATE_PAYMENT_REPORTED,
        ClaimType.DUPLICATE_DETECTED,
        ClaimType.DATE_REPORTED,
    ):
        return None
    fields = c.fields or {}
    ck = (fields.get("canonical_account_key") or "").strip()
    creditor = (
        fields.get("creditor")
        or fields.get("account_name")
        or c.entity
        or ""
    )
    scrub = _scrub_creditor(str(creditor))
    if ck:
        fp = f"ck:{ck.lower()}"
        return scrub or "unknown", fp
    l4 = _last4(fields)
    if not scrub and not l4:
        return None
    return scrub, f"{scrub}|{l4}"


def build_normalized_account_groups(raw_claims: List[Claim]) -> List[NormalizedAccountGroup]:
    """
    Group raw claims by conservative fingerprint. Same fingerprint across bureaus
    yields one group with multi-bureau presence (linkage_confidence medium unless canonical key).
    """
    by_fp: Dict[str, List[Claim]] = defaultdict(list)
    for c in raw_claims:
        fp_t = fingerprint_for_claim(c)
        if not fp_t:
            continue
        _, fp = fp_t
        by_fp[fp].append(c)

    groups: List[NormalizedAccountGroup] = []
    for fp, claims in by_fp.items():
        bureaus = sorted({(c.source or "unknown").lower() for c in claims})
        creditors = []
        canonical_hits = 0
        for c in claims:
            ck = (c.fields or {}).get("canonical_account_key")
            if ck:
                canonical_hits += 1
            cr = (c.fields or {}).get("creditor") or (c.fields or {}).get("account_name") or c.entity
            if cr:
                creditors.append(str(cr).strip())
        norm_cred = _scrub_creditor(creditors[0]) if creditors else "unknown"
        if canonical_hits >= 1 and len(claims) >= 1:
            linkage = "high"
            notes = ["canonical_account_key present on at least one supporting claim"]
        elif len(bureaus) > 1:
            linkage = "medium"
            notes = ["same heuristic fingerprint observed on multiple bureaus"]
        else:
            linkage = "low"
            notes = ["single-bureau fingerprint only; verify before cross-bureau strategy"]

        gid = f"ag_{hashlib.sha256(fp.encode()).hexdigest()[:10]}"
        ids = [c.claim_id for c in claims[:12]]
        groups.append(
            NormalizedAccountGroup(
                group_id=gid,
                normalized_creditor=norm_cred,
                fingerprint_key=fp,
                bureaus_present=bureaus,
                raw_claim_ids_sample=ids,
                linkage_confidence=linkage,
                linkage_notes=notes,
            )
        )

    groups.sort(key=lambda g: (-len(g.bureaus_present), g.normalized_creditor))
    return groups
