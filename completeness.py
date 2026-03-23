from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SectionCompleteness:
    section: str
    expected_total: Optional[int]
    extracted_total: int
    delta: Optional[int]
    section_pass: Optional[bool]


@dataclass
class CompletenessReport:
    bureau: str
    totals_confidence: str
    exactness: str
    sections: dict = field(default_factory=dict)
    mode: str = "STANDARD"
    verification_method: str = "standard"
    matched_sections: list = field(default_factory=list)


def compute_completeness(bureau, totals, extracted_counts, totals_mode=None,
                         self_verification=None):
    from totals_detector import compute_totals_confidence

    totals_conf = compute_totals_confidence(totals)

    section_names = ["accounts", "inquiries", "negative_items", "public_records", "personal_info_fields"]
    sections = {}

    for s in section_names:
        expected = totals.get(s)
        extracted = extracted_counts.get(s, 0)

        if expected is None:
            delta = None
            section_pass = None
        else:
            delta = extracted - expected
            section_pass = (delta == 0)

        sections[s] = SectionCompleteness(
            section=s,
            expected_total=expected,
            extracted_total=extracted,
            delta=delta,
            section_pass=section_pass,
        )

    has_any_expected = any(sc.expected_total is not None for sc in sections.values())
    all_pass = all(
        sc.section_pass is True
        for sc in sections.values()
        if sc.expected_total is not None
    )

    if totals_mode is None:
        totals_mode = "STANDARD"

    verification_method = "standard"
    matched_sections = []

    if totals_conf == "HIGH" and all_pass and has_any_expected:
        if totals_mode == "SECTION_DERIVED":
            exactness = "PROVABLE"
            verification_method = "section_derived"
        else:
            exactness = "EXACT"
            verification_method = "explicit"
    elif totals_conf in ("MED",) and all_pass and has_any_expected:
        if totals_mode == "SECTION_DERIVED":
            exactness = "PROVABLE"
            verification_method = "section_derived"
        else:
            exactness = "NOT_EXACT"
    elif totals_conf == "LOW" and not has_any_expected:
        if self_verification and self_verification.get("verified"):
            sv_conf = self_verification["confidence"]
            matched_sections = self_verification.get("matched_sections", [])
            sv_totals = self_verification.get("independent_counts", {})

            for s in section_names:
                sv_val = sv_totals.get(s)
                ext_val = extracted_counts.get(s, 0)
                if sv_val is not None:
                    sections[s] = SectionCompleteness(
                        section=s,
                        expected_total=sv_val,
                        extracted_total=ext_val,
                        delta=ext_val - sv_val,
                        section_pass=(ext_val == sv_val),
                    )

            if sv_conf == "HIGH":
                exactness = "PROVABLE"
                totals_conf = "HIGH"
                verification_method = "self_verified"
            else:
                exactness = "PROVABLE"
                totals_conf = "MED"
                verification_method = "self_verified"
        else:
            exactness = "UNPROVABLE"
    else:
        if self_verification and self_verification.get("verified") and not has_any_expected:
            sv_conf = self_verification["confidence"]
            matched_sections = self_verification.get("matched_sections", [])
            sv_totals = self_verification.get("independent_counts", {})

            for s in section_names:
                sv_val = sv_totals.get(s)
                ext_val = extracted_counts.get(s, 0)
                if sv_val is not None:
                    sections[s] = SectionCompleteness(
                        section=s,
                        expected_total=sv_val,
                        extracted_total=ext_val,
                        delta=ext_val - sv_val,
                        section_pass=(ext_val == sv_val),
                    )

            exactness = "PROVABLE"
            totals_conf = sv_conf
            verification_method = "self_verified"
        else:
            exactness = "NOT_EXACT"

    mode = totals_mode if totals_mode != "STANDARD" else "STANDARD"

    return CompletenessReport(
        bureau=bureau,
        totals_confidence=totals_conf,
        exactness=exactness,
        sections=sections,
        mode=mode,
        verification_method=verification_method,
        matched_sections=matched_sections,
    )
