"""
Visitor-safe payloads for ``POST /api/public/demo/run``.

**Always** applied before the JSON response leaves the API (unless
``PUBLIC_DEMO_SKIP_VISITOR_MASK=1``, which is for local debugging only).

Letter bodies from parsing are replaced with **scenario-styled** synthetic letters per bureau
(fictional consumer + public mailing addresses). Scenario ``category`` (general / law_backed /
thin_file) sets easy-reading explainer text (~simple school reading level) about what the letter
is for, while the outer format stays bureau-ready.

Optional: ``letter_body`` / ``letter_preview`` in ``visitor_placeholders`` JSON override
(``{bureau}`` allowed).
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any, Dict

_log = logging.getLogger(__name__)

_SAFE_DEFAULTS: Dict[str, Any] = {
    "report_file_name": "Synthetic bureau sample — public demo (no real consumer PII).pdf",
    "omit_review_claim_details": True,
    "strategy_round_summary": (
        "Priorities are computed from this run’s fixture using the same engine as members; "
        "wording here is generic for the public demo."
    ),
    "strategy_rationale": (
        "Public demo — detailed rationale is only shown inside your authenticated workflow."
    ),
}

_BUREAU_RECIPIENT_LINES: Dict[str, str] = {
    "equifax": (
        "Equifax Information Services LLC\n"
        "P.O. Box 740256\n"
        "Atlanta, GA 30374-0256"
    ),
    "transunion": (
        "TransUnion LLC\n"
        "Consumer Dispute Center\n"
        "P.O. Box 2000\n"
        "Chester, PA 19016"
    ),
    "experian": (
        "Experian\n"
        "P.O. Box 4500\n"
        "Allen, TX 75013"
    ),
}


def _normalize_bureau_key(raw: Any) -> str:
    b = str(raw or "").lower().replace(" ", "")
    if "equifax" in b:
        return "equifax"
    if "experian" in b:
        return "experian"
    if "transunion" in b:
        return "transunion"
    return "equifax"


def _scenario_category(scenario_id: str) -> str:
    from services.public_demo_fixtures_manifest import demo_scenarios

    meta = demo_scenarios().get((scenario_id or "").strip()) or {}
    return str(meta.get("category") or "general").strip().lower()


def _scenario_easy_read_block(category: str) -> str:
    """Short, simple text for demo visitors — tied to scenario category."""
    if category == "law_backed":
        return (
            "YOUR DEMO SCENARIO (EASY READ)\n"
            "You picked the demo about rules and rights. In real life, some fights use fair-credit "
            "laws and time limits. This sample shows how a letter can sound when that path fits. "
            "This is only a demo. It is not legal advice.\n"
            "\n"
        )
    if category == "thin_file":
        return (
            "YOUR DEMO SCENARIO (EASY READ)\n"
            "You picked the thin file demo. A thin file means you do not have many accounts on your "
            "report yet. The idea is to fix wrong items and also grow good credit over time.\n"
            "\n"
        )
    return (
        "YOUR DEMO SCENARIO (EASY READ)\n"
        "You picked the general cleanup demo. It is for people who want late pays, collections, "
        "or other bad marks checked. The program helps pick what to work on first.\n"
        "\n"
    )


def _synthetic_dispute_letter_body(
    bureau_key: str,
    bureau_display: str,
    scenario_id: str,
) -> str:
    """Same dispute letter shape as production; easy-read blocks explain purpose + scenario."""
    block = _BUREAU_RECIPIENT_LINES.get(bureau_key) or _BUREAU_RECIPIENT_LINES["equifax"]
    today_s = date.today().strftime("%B %d, %Y")
    cat = _scenario_category(scenario_id)
    scenario_easy = _scenario_easy_read_block(cat)
    return (
        f"SAM PLECONSUMER\n"
        f"123 Example Street\n"
        f"Demo City, XX 00000\n"
        f"\n"
        f"{today_s}\n"
        f"\n"
        f"{block}\n"
        f"\n"
        f"Subject: Request for Reinvestigation (FCRA § 611)\n"
        f"(Plain words: Please look again at items on my credit report that I think are wrong.)\n"
        f"\n"
        f"To Whom It May Concern:\n"
        f"\n"
        f"WHAT THIS LETTER IS FOR (EASY READ)\n"
        f"This is a sample from the public demo. A real letter like this goes to {bureau_display}. "
        f"It tells the bureau to check my report. If something is wrong, they should fix it or take "
        f"it off. When you use the real program, your letter lists the items you picked.\n"
        f"\n"
        f"{scenario_easy}"
        f"WHO IS WRITING (FAKE DEMO INFO ONLY — NOT A REAL PERSON)\n"
        f"  Last four of Social Security number: XXX-XX-0000\n"
        f"  Date of birth: 01/01/1990\n"
        f"\n"
        f"FORMAL DISPUTE LANGUAGE (SAME SHAPE AS A REAL LETTER)\n"
        f"I request a reinvestigation of the disputed items on my {bureau_display} consumer report "
        f"under the Fair Credit Reporting Act. (Reinvestigation means: look again and check if the "
        f"facts are right.) Some information may be incomplete, inaccurate, or cannot be verified.\n"
        f"\n"
        f"Please review each item. If you cannot show it is fully correct, please update or delete "
        f"it. Thank you for your time.\n"
        f"\n"
        f"Sincerely,\n"
        f"\n"
        f"Sam P. Consumer\n"
    )


def _synthetic_letter_preview(body: str, max_len: int = 480) -> str:
    if len(body) <= max_len:
        return body
    cut = body[: max_len - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def _effective_placeholders(scenario_id: str) -> Dict[str, Any]:
    from services.public_demo_fixtures_manifest import demo_scenarios

    meta = demo_scenarios().get((scenario_id or "").strip()) or {}
    custom = meta.get("visitor_placeholders")
    if not isinstance(custom, dict):
        custom = {}
    merged = dict(_SAFE_DEFAULTS)
    merged.update({k: v for k, v in custom.items() if v is not None})
    return merged


def apply_public_demo_visitor_mask(result: Dict[str, Any], scenario_id: str) -> None:
    """
    Strip or replace fields that could identify a real person in the browser.

    Opt-out (local only): ``PUBLIC_DEMO_SKIP_VISITOR_MASK=1``.
    """
    if (os.environ.get("PUBLIC_DEMO_SKIP_VISITOR_MASK") or "").strip() == "1":
        _log.warning(
            "PUBLIC_DEMO_SKIP_VISITOR_MASK=1 — public demo JSON may include raw letter text (privacy risk)"
        )
        return

    ph = _effective_placeholders(scenario_id)

    intake = result.get("intake")
    if isinstance(intake, dict):
        reports = intake.get("reports") or []
        if isinstance(reports, list) and len(reports) > 1:
            for rep in reports:
                if not isinstance(rep, dict):
                    continue
                br = str(rep.get("bureau") or "bureau").strip() or "bureau"
                rep["fileName"] = f"Synthetic {br.title()} sample — public demo (no PII).pdf"
        else:
            fn = (ph.get("report_file_name") or "").strip() or str(
                _SAFE_DEFAULTS["report_file_name"]
            )
            for rep in reports:
                if isinstance(rep, dict):
                    rep["fileName"] = fn
        if ph.get("omit_review_claim_details"):
            intake["reviewClaims"] = []
            intake["reviewClaimsTruncated"] = False
            intake.pop("reviewClaimsOmitted", None)

    strat = result.get("strategy")
    if isinstance(strat, dict):
        rs = ph.get("strategy_round_summary")
        if isinstance(rs, str) and rs.strip():
            strat["roundSummary"] = rs.strip()
        rat = ph.get("strategy_rationale")
        if isinstance(rat, str) and rat.strip():
            strat["rationale"] = rat.strip()

    letters = result.get("letters")
    if not isinstance(letters, list) or not letters:
        return

    custom_body_t = ph.get("letter_body")
    custom_prev_t = ph.get("letter_preview")
    use_custom_body = isinstance(custom_body_t, str) and custom_body_t.strip() != ""
    use_custom_prev = isinstance(custom_prev_t, str) and custom_prev_t.strip() != ""

    for L in letters:
        if not isinstance(L, dict):
            continue
        bureau_display = (L.get("bureauDisplay") or L.get("bureau") or "Bureau").strip()
        bureau_key = _normalize_bureau_key(L.get("bureau"))

        if use_custom_body:
            raw_b = custom_body_t.strip()
            try:
                body = raw_b.format(bureau=bureau_display)
            except (KeyError, ValueError):
                body = raw_b
        else:
            body = _synthetic_dispute_letter_body(bureau_key, bureau_display, scenario_id)

        if use_custom_prev:
            raw_p = custom_prev_t.strip()
            try:
                preview = raw_p.format(bureau=bureau_display)
            except (KeyError, ValueError):
                preview = raw_p
        else:
            preview = _synthetic_letter_preview(body)

        L["body"] = body
        L["preview"] = preview
        L["charCount"] = len(body)
