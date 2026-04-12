"""
Deterministic cross-bureau comparison helpers (normalized values only).

Slice shape (per account fingerprint):

{
  "account_fingerprint": "...",
  "bureaus": {
    "equifax": {
      "values": { "late_payment_indicator": "...", ... },
      "dimension_eligibility": { "late_payment_indicator": true }
    }
  }
}

If ``dimension_eligibility`` is omitted for a bureau, all present dimensions are treated
as eligible (fixtures / internal slices). If present, only dimensions mapped to ``true``
participate in comparisons.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _bureau_row_values(row: Dict[str, Any]) -> Dict[str, Any]:
    if "values" in row and isinstance(row["values"], dict):
        return dict(row["values"])
    return {k: v for k, v in row.items() if not k.startswith("_") and k != "dimension_eligibility"}


def _is_dimension_eligible(row: Dict[str, Any], dimension: str) -> bool:
    de = row.get("dimension_eligibility")
    if de is None:
        return True
    if not isinstance(de, dict):
        return False
    return bool(de.get(dimension))


def bureau_values_for_dimension(slice_data: Dict[str, Any], dimension: str) -> Dict[str, Any]:
    """
    Map bureau_code -> normalized value, or exclude bureau (omit key) when ineligible
    or value is None / empty string.
    """
    out: Dict[str, Any] = {}
    bureaus = slice_data.get("bureaus") or {}
    if not isinstance(bureaus, dict):
        return out
    for bureau, row in bureaus.items():
        if not isinstance(row, dict):
            continue
        if not _is_dimension_eligible(row, dimension):
            continue
        vals = _bureau_row_values(row)
        v = vals.get(dimension)
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        out[str(bureau)] = v
    return out


def count_bureaus_with_dimension(slice_data: Dict[str, Any], dimension: str) -> int:
    return len(bureau_values_for_dimension(slice_data, dimension))


def distinct_normalized_values(values_by_bureau: Dict[str, Any]) -> List[Any]:
    seen: List[Any] = []
    for v in sorted(values_by_bureau.values(), key=lambda x: repr(x)):
        if v not in seen:
            seen.append(v)
    return seen


def mismatch_string_dimensions(values_by_bureau: Dict[str, Any]) -> bool:
    if len(values_by_bureau) < 2:
        return False
    raw = list(values_by_bureau.values())
    norm = [str(x).strip().lower() for x in raw]
    return len(set(norm)) > 1


def mismatch_numeric_dimensions(
    values_by_bureau: Dict[str, Any],
    *,
    tolerance: int = 0,
) -> bool:
    if len(values_by_bureau) < 2:
        return False
    nums: List[int] = []
    for v in values_by_bureau.values():
        try:
            nums.append(int(v))
        except (TypeError, ValueError):
            return False
    lo, hi = min(nums), max(nums)
    return (hi - lo) > int(tolerance)


def mismatch_mixed_balance_or_past_due(
    values_by_bureau: Dict[str, Any],
    *,
    tolerance: int = 0,
) -> bool:
    """
    True if at least two distinct numeric values beyond tolerance, or non-numeric mixed
    with numeric (treated as mismatch), or string inequality.
    """
    if len(values_by_bureau) < 2:
        return False
    parsed: List[Tuple[str, Optional[int]]] = []
    for b, v in sorted(values_by_bureau.items()):
        if isinstance(v, bool):
            return True
        if isinstance(v, int):
            parsed.append((b, int(v)))
            continue
        try:
            parsed.append((b, int(str(v).strip())))
        except (TypeError, ValueError):
            parsed.append((b, None))
    nums = [p[1] for p in parsed if p[1] is not None]
    nulls = sum(1 for p in parsed if p[1] is None)
    if nulls > 0 and len(nums) > 0:
        return True
    if len(nums) >= 2:
        lo, hi = min(nums), max(nums)
        return (hi - lo) > int(tolerance)
    return False


def bureaus_in_slice(slice_data: Dict[str, Any]) -> List[str]:
    b = slice_data.get("bureaus") or {}
    if not isinstance(b, dict):
        return []
    return sorted(str(k) for k in b.keys())
