"""
850 Lab Bureau ID Gate

Philosophy: We do not scan what we can't clearly identify.
Wrong bureau = wrong truth.

This module detects which credit bureau generated a report
before any parsing begins. If we can't identify exactly one
bureau, we stop with a Red Light Rule.
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum


class Bureau(Enum):
    TRANSUNION = "TRANSUNION"
    EXPERIAN = "EXPERIAN"
    EQUIFAX = "EQUIFAX"


@dataclass
class BureauMatch:
    """A single bureau marker found in the report."""
    bureau: Bureau
    marker_text: str
    position: int
    marker_type: str


@dataclass
class BureauDetectionResult:
    """Result of bureau detection - either success or Red Light."""
    success: bool
    bureau: Optional[Bureau]
    confidence: str
    receipt: Optional[Dict]
    red_light: bool
    red_light_reason: Optional[str]
    matches_found: List[BureauMatch]
    
    def to_truth_field(self) -> Dict:
        """Convert to Truth Sheet field format."""
        if not self.success:
            return {
                "value": "NOT_FOUND",
                "how_sure_we_are": "NOT_FOUND",
                "receipt": None
            }
        return {
            "value": self.bureau.value,
            "how_sure_we_are": self.confidence,
            "receipt": self.receipt
        }


TRANSUNION_MARKERS = [
    (r"TransUnion", "brand_name"),
    (r"TRANSUNION", "brand_name_caps"),
    (r"Trans\s*Union", "brand_name_spaced"),
    (r"TransUnion\s+Consumer\s+Relations", "consumer_relations"),
    (r"TransUnion\s+LLC", "legal_name"),
    (r"P\.?O\.?\s*Box\s*2000,?\s*Chester,?\s*PA", "mailing_address"),
    (r"transunion\.com", "website"),
    (r"TU\s+File\s+Number", "file_reference"),
    (r"TransUnion\s+Credit\s+Report", "report_header"),
    (r"VantageScore.*TransUnion", "score_attribution"),
]

EXPERIAN_MARKERS = [
    (r"Experian", "brand_name"),
    (r"EXPERIAN", "brand_name_caps"),
    (r"Experian\s+Consumer\s+Services", "consumer_services"),
    (r"Experian\s+Information\s+Solutions", "legal_name"),
    (r"P\.?O\.?\s*Box\s*4500,?\s*Allen,?\s*TX", "mailing_address"),
    (r"experian\.com", "website"),
    (r"Experian\s+Credit\s+Report", "report_header"),
    (r"Report\s+Number.*EXP", "report_number"),
    (r"Experian\s+File\s+Number", "file_reference"),
]

EQUIFAX_MARKERS = [
    (r"Equifax", "brand_name"),
    (r"EQUIFAX", "brand_name_caps"),
    (r"Equifax\s+Information\s+Services", "legal_name"),
    (r"Equifax\s+Credit\s+Information\s+Services", "full_legal_name"),
    (r"P\.?O\.?\s*Box\s*740241,?\s*Atlanta,?\s*GA", "mailing_address"),
    (r"equifax\.com", "website"),
    (r"Equifax\s+Credit\s+Report", "report_header"),
    (r"EFX\s+File", "file_reference"),
    (r"Confirmation\s+Number.*EFX", "confirmation_number"),
]


def _find_markers(text: str, patterns: List[tuple], bureau: Bureau) -> List[BureauMatch]:
    """Find all matching markers for a specific bureau."""
    matches = []
    for pattern, marker_type in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matches.append(BureauMatch(
                bureau=bureau,
                marker_text=match.group(0),
                position=match.start(),
                marker_type=marker_type
            ))
    return matches


def _extract_snippet(text: str, position: int, context_chars: int = 50) -> str:
    """Extract a snippet of text around a position for the receipt."""
    start = max(0, position - context_chars)
    end = min(len(text), position + context_chars)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _estimate_page(text: str, position: int) -> str:
    """Estimate page number based on position in text."""
    text_before = text[:position]
    page_breaks = len(re.findall(r'\f|Page\s+\d+|PAGE\s+\d+', text_before))
    return str(page_breaks + 1)


def detect_bureau(raw_text: str) -> BureauDetectionResult:
    """
    Detect which credit bureau generated this report.
    
    This is the Bureau ID Gate - we must identify exactly one bureau
    before any parsing begins. If we can't, we trigger a Red Light.
    
    Args:
        raw_text: The raw extracted text from the credit report
        
    Returns:
        BureauDetectionResult with success/failure and details
    """
    if not raw_text or not raw_text.strip():
        return BureauDetectionResult(
            success=False,
            bureau=None,
            confidence="NOT_FOUND",
            receipt=None,
            red_light=True,
            red_light_reason="Red Light Rule: No report text to analyze. We need actual report content to identify the bureau.",
            matches_found=[]
        )
    
    transunion_matches = _find_markers(raw_text, TRANSUNION_MARKERS, Bureau.TRANSUNION)
    experian_matches = _find_markers(raw_text, EXPERIAN_MARKERS, Bureau.EXPERIAN)
    equifax_matches = _find_markers(raw_text, EQUIFAX_MARKERS, Bureau.EQUIFAX)
    
    all_matches = transunion_matches + experian_matches + equifax_matches
    
    bureaus_found = set()
    if transunion_matches:
        bureaus_found.add(Bureau.TRANSUNION)
    if experian_matches:
        bureaus_found.add(Bureau.EXPERIAN)
    if equifax_matches:
        bureaus_found.add(Bureau.EQUIFAX)
    
    if len(bureaus_found) == 0:
        return BureauDetectionResult(
            success=False,
            bureau=None,
            confidence="NOT_FOUND",
            receipt=None,
            red_light=True,
            red_light_reason="Red Light Rule: Could not identify the credit bureau. None of our known markers (TransUnion, Experian, Equifax) were found in this report.",
            matches_found=all_matches
        )
    
    if len(bureaus_found) > 1:
        tu_score = len(transunion_matches)
        exp_score = len(experian_matches)
        eq_score = len(equifax_matches)
        max_score = max(tu_score, exp_score, eq_score)
        min_score = min(tu_score, exp_score, eq_score)

        if max_score > 0 and min_score > 0 and max_score <= min_score * 3:
            bureau_names = ", ".join(b.value for b in bureaus_found)
            return BureauDetectionResult(
                success=False,
                bureau=None,
                confidence="NOT_FOUND",
                receipt=None,
                red_light=True,
                red_light_reason=f"Red Light Rule: This appears to be a combined multi-bureau report ({bureau_names}). Please upload individual single-bureau reports for accurate parsing.",
                matches_found=all_matches
            )

        score_map = {Bureau.TRANSUNION: tu_score, Bureau.EXPERIAN: exp_score, Bureau.EQUIFAX: eq_score}
        detected_bureau = max(score_map, key=score_map.get)
        matches = {Bureau.TRANSUNION: transunion_matches, Bureau.EXPERIAN: experian_matches, Bureau.EQUIFAX: equifax_matches}[detected_bureau]
        best_match = min(matches, key=lambda m: m.position)
        receipt = {
            "page": _estimate_page(raw_text, best_match.position),
            "section": "Report Header / Bureau Identification",
            "snippet": _extract_snippet(raw_text, best_match.position)
        }
        return BureauDetectionResult(
            success=True,
            bureau=detected_bureau,
            confidence="LOW",
            receipt=receipt,
            red_light=False,
            red_light_reason=None,
            matches_found=matches
        )
    
    detected_bureau = list(bureaus_found)[0]
    
    if detected_bureau == Bureau.TRANSUNION:
        matches = transunion_matches
    elif detected_bureau == Bureau.EXPERIAN:
        matches = experian_matches
    else:
        matches = equifax_matches
    
    best_match = min(matches, key=lambda m: m.position)
    
    if len(matches) >= 3:
        confidence = "HIGH"
    elif len(matches) >= 2:
        confidence = "MED"
    else:
        confidence = "LOW"
    
    receipt = {
        "page": _estimate_page(raw_text, best_match.position),
        "section": "Report Header / Bureau Identification",
        "snippet": _extract_snippet(raw_text, best_match.position)
    }
    
    return BureauDetectionResult(
        success=True,
        bureau=detected_bureau,
        confidence=confidence,
        receipt=receipt,
        red_light=False,
        red_light_reason=None,
        matches_found=matches
    )


def gate_check(raw_text: str) -> Dict:
    """
    Run the Bureau ID Gate check.
    
    This is the main entry point. Returns a structured result
    that can be used to either proceed with scanning or stop.
    
    Returns dict with:
        - passed: bool - whether we can proceed
        - bureau: str or None - detected bureau name
        - truth_field: dict - ready to insert into Truth Sheet meta
        - error: dict or None - structured error if gate failed
    """
    result = detect_bureau(raw_text)
    
    if result.success:
        return {
            "passed": True,
            "bureau": result.bureau.value,
            "truth_field": result.to_truth_field(),
            "error": None,
            "match_count": len(result.matches_found),
            "confidence": result.confidence
        }
    else:
        return {
            "passed": False,
            "bureau": None,
            "truth_field": result.to_truth_field(),
            "error": {
                "type": "bureau_gate_failed",
                "red_light": True,
                "reason": result.red_light_reason,
                "bureaus_detected": [m.bureau.value for m in result.matches_found],
                "markers_found": [
                    {"bureau": m.bureau.value, "text": m.marker_text, "type": m.marker_type}
                    for m in result.matches_found[:10]
                ]
            },
            "match_count": 0,
            "confidence": "NOT_FOUND"
        }


if __name__ == "__main__":
    test_texts = [
        ("TransUnion Credit Report\nFile Number: TU-123456\nTransUnion LLC\ntransunion.com", "TransUnion report"),
        ("Experian Credit Report\nExperian Information Solutions\nP.O. Box 4500, Allen, TX", "Experian report"),
        ("EQUIFAX Credit Report\nEquifax Information Services\nConfirmation Number: EFX-789", "Equifax report"),
        ("TransUnion Credit Report\nExperian Information\nEquifax Data", "Mixed bureaus"),
        ("Some random text without any bureau markers", "No bureau"),
        ("", "Empty text"),
    ]
    
    print("Bureau ID Gate Tests\n" + "=" * 50)
    for text, description in test_texts:
        result = gate_check(text)
        status = "✅ PASSED" if result["passed"] else "🚨 RED LIGHT"
        bureau = result["bureau"] or "None"
        print(f"\n{description}:")
        print(f"  {status} | Bureau: {bureau} | Confidence: {result['confidence']}")
        if result["error"]:
            print(f"  Reason: {result['error']['reason'][:80]}...")
