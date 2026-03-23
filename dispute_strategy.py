"""
dispute_strategy.py | 850 Lab Parser Machine
AI-Powered Dispute Strategy Engine

PURPOSE:
1. Rank review claims by dispute impact score
2. Select top N claims per dispute round
3. Call LLM to reason about strategy and produce rationale
4. Provide deterministic fallback when LLM is unavailable

GUARDRAILS:
- No legal advice, litigation threats, or guarantees
- Factual disputes only
- FCRA citations only when directly applicable
- Consumer-sourced disputes
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from review_claims import (
    ReviewClaim, ReviewType, CreditImpact, Severity,
    CrossBureauStatus
)
from legal_kb import build_legal_context_for_claims, build_per_claim_legal_context

logger = logging.getLogger(__name__)

DEFAULT_ROUND_SIZE = 5

REVIEW_TYPE_IMPACT_WEIGHT = {
    ReviewType.NEGATIVE_IMPACT: 5,
    ReviewType.ACCURACY_VERIFICATION: 4,
    ReviewType.DUPLICATE_ACCOUNT: 4,
    ReviewType.UNVERIFIABLE_INFORMATION: 3,
    ReviewType.ACCOUNT_OWNERSHIP: 2,
    ReviewType.IDENTITY_VERIFICATION: 1,
}

SEVERITY_WEIGHT = {
    Severity.HIGH: 3,
    Severity.MODERATE: 2,
    Severity.LOW: 1,
    Severity.UNKNOWN: 0,
}

CREDIT_IMPACT_WEIGHT = {
    CreditImpact.NEGATIVE: 3,
    CreditImpact.NEUTRAL: 0,
    CreditImpact.UNKNOWN: 1,
}


@dataclass
class ScoredClaim:
    review_claim: ReviewClaim
    impact_score: float
    score_breakdown: Dict[str, float]
    rank: int = 0


@dataclass
class DisputeRound:
    round_number: int
    selected_claims: List[ScoredClaim]
    excluded_claim_ids: List[str] = field(default_factory=list)
    strategy_rationale: str = ""
    strategy_source: str = "deterministic"


@dataclass
class StrategyRecommendation:
    selected_claims: List[ScoredClaim]
    rationale: str
    round_summary: str
    source: str = "deterministic"
    per_claim_rationale: Dict[str, str] = field(default_factory=dict)


def compute_impact_score(rc: ReviewClaim) -> Tuple[float, Dict[str, float]]:
    breakdown = {}

    type_score = REVIEW_TYPE_IMPACT_WEIGHT.get(rc.review_type, 1)
    breakdown['type_weight'] = float(type_score)

    sev_score = SEVERITY_WEIGHT.get(rc.impact_assessment.severity, 0)
    breakdown['severity'] = float(sev_score)

    impact_score = CREDIT_IMPACT_WEIGHT.get(rc.impact_assessment.credit_impact, 0)
    breakdown['credit_impact'] = float(impact_score)

    cross_bureau = rc.evidence_summary.cross_bureau_status
    cb_score = 2.0 if cross_bureau == CrossBureauStatus.MULTI_BUREAU else 0.0
    breakdown['cross_bureau'] = cb_score

    conf_summary = rc.evidence_summary.claim_confidence_summary
    if conf_summary:
        conf_score = (conf_summary.high * 3 + conf_summary.medium * 1.5) / max(
            conf_summary.high + conf_summary.medium + conf_summary.low, 1
        )
    else:
        conf_score = 1.0
    breakdown['confidence'] = round(conf_score, 2)

    claim_count = len(rc.supporting_claim_ids)
    evidence_score = min(claim_count / 3.0, 2.0)
    breakdown['evidence_density'] = round(evidence_score, 2)

    eligibility = rc.letter_eligibility
    if eligibility and eligibility.letter_ready:
        elig_score = 2.0
    elif eligibility and eligibility.letter_eligible:
        elig_score = 1.0
    else:
        elig_score = 0.0
    breakdown['letter_readiness'] = elig_score

    total = (
        type_score * 2.0
        + sev_score * 1.5
        + impact_score * 2.0
        + cb_score * 1.5
        + conf_score * 1.0
        + evidence_score * 1.0
        + elig_score * 1.0
    )
    breakdown['total'] = round(total, 2)

    return total, breakdown


def rank_claims(
    review_claims: List[ReviewClaim],
    excluded_ids: Optional[List[str]] = None,
) -> List[ScoredClaim]:
    excluded = set(excluded_ids or [])

    eligible = [
        rc for rc in review_claims
        if rc.review_claim_id not in excluded
        and rc.review_type != ReviewType.IDENTITY_VERIFICATION
    ]

    scored = []
    for rc in eligible:
        total, breakdown = compute_impact_score(rc)
        scored.append(ScoredClaim(
            review_claim=rc,
            impact_score=total,
            score_breakdown=breakdown,
        ))

    scored.sort(key=lambda s: -s.impact_score)
    for i, sc in enumerate(scored):
        sc.rank = i + 1

    return scored


def select_round(
    scored_claims: List[ScoredClaim],
    round_size: int = DEFAULT_ROUND_SIZE,
) -> List[ScoredClaim]:
    seen_accounts = set()
    selected = []

    for sc in scored_claims:
        if len(selected) >= round_size:
            break
        acct = sc.review_claim.entities.get('account_name', '')
        acct_key = acct.lower().strip() if acct else sc.review_claim.review_claim_id
        if acct_key in seen_accounts:
            continue
        seen_accounts.add(acct_key)
        selected.append(sc)

    return selected


def _build_deterministic_rationale(selected: List[ScoredClaim], total_eligible: int) -> str:
    lines = []
    lines.append(f"Selected {len(selected)} of {total_eligible} eligible items for this dispute round.")
    lines.append("Items are ranked by impact score, prioritizing:")
    lines.append("- Negative credit impact (late payments, collections, charge-offs)")
    lines.append("- High severity and strong evidence")
    lines.append("- Items reported across multiple bureaus")
    lines.append("- Letter-ready items with high confidence")
    lines.append("")
    lines.append("Focusing on fewer, high-impact disputes per round increases the likelihood of successful resolution.")
    return "\n".join(lines)


def _build_deterministic_per_claim(selected: List[ScoredClaim]) -> Dict[str, str]:
    rationale = {}
    for sc in selected:
        rc = sc.review_claim
        reasons = []

        if rc.impact_assessment.credit_impact == CreditImpact.NEGATIVE:
            reasons.append("Negative credit impact")
        if rc.impact_assessment.severity in (Severity.HIGH, Severity.MODERATE):
            reasons.append(f"{rc.impact_assessment.severity.value.title()} severity")
        if rc.evidence_summary.cross_bureau_status == CrossBureauStatus.MULTI_BUREAU:
            reasons.append("Reported across multiple bureaus")
        conf = rc.evidence_summary.claim_confidence_summary
        if conf and conf.high > 0:
            reasons.append("High-confidence evidence")
        if rc.letter_eligibility and rc.letter_eligibility.letter_ready:
            reasons.append("Letter-ready")

        legal_ctx = build_per_claim_legal_context(rc.review_type.value)
        if legal_ctx["applicable_statutes"]:
            top_statute = legal_ctx["applicable_statutes"][0]
            reasons.append(f"Supported by {top_statute['section']}")
        if legal_ctx["applicable_cases"]:
            top_case = legal_ctx["applicable_cases"][0]
            reasons.append(f"See {top_case['case']}")

        if not reasons:
            reasons.append("Eligible for dispute")

        rationale[rc.review_claim_id] = "; ".join(reasons) + f" (score: {sc.impact_score:.1f})"

    return rationale


def build_deterministic_strategy(
    review_claims: List[ReviewClaim],
    round_size: int = DEFAULT_ROUND_SIZE,
    excluded_ids: Optional[List[str]] = None,
) -> StrategyRecommendation:
    scored = rank_claims(review_claims, excluded_ids)
    selected = select_round(scored, round_size)

    return StrategyRecommendation(
        selected_claims=selected,
        rationale=_build_deterministic_rationale(selected, len(scored)),
        round_summary=f"{len(selected)} high-impact items selected for dispute",
        source="deterministic",
        per_claim_rationale=_build_deterministic_per_claim(selected),
    )


def _build_llm_payload(scored_claims: List[ScoredClaim], round_size: int) -> List[Dict[str, Any]]:
    payload = []
    for sc in scored_claims[:20]:
        rc = sc.review_claim
        conf = rc.evidence_summary.claim_confidence_summary

        legal_ctx = build_per_claim_legal_context(rc.review_type.value)

        item = {
            "id": rc.review_claim_id,
            "type": rc.review_type.value,
            "summary": rc.summary,
            "account": rc.entities.get("account_name", "Unknown"),
            "bureau": rc.entities.get("bureau", "Unknown"),
            "severity": rc.impact_assessment.severity.value,
            "credit_impact": rc.impact_assessment.credit_impact.value,
            "cross_bureau": rc.evidence_summary.cross_bureau_status.value,
            "evidence_count": len(rc.supporting_claim_ids),
            "confidence_high": conf.high if conf else 0,
            "confidence_med": conf.medium if conf else 0,
            "confidence_low": conf.low if conf else 0,
            "letter_ready": rc.letter_eligibility.letter_ready if rc.letter_eligibility else False,
            "impact_score": round(sc.impact_score, 1),
            "observations": rc.evidence_summary.system_observations[:3],
            "legal_authorities": {
                "statutes": [
                    {"section": s["section"], "title": s["title"]}
                    for s in legal_ctx["applicable_statutes"]
                ],
                "cases": [
                    {"case": c["case"], "citation": c["citation"]}
                    for c in legal_ctx["applicable_cases"]
                ],
                "strategy_note": legal_ctx["strategy_note"],
            },
        }
        payload.append(item)
    return payload


STRATEGY_SYSTEM_PROMPT = """You are a credit report analysis assistant for 850 Lab. Your role is to help consumers understand their credit reports and select the most impactful items to dispute in each round.

You have access to a legal knowledge base. Each item includes applicable federal statutes (FCRA, TILA, Dodd-Frank) and relevant court precedents. Use this legal context to inform your prioritization and explain WHY certain items have stronger dispute potential.

STRICT RULES:
1. You provide FACTUAL analysis only. Never provide legal advice.
2. Never threaten litigation or guarantee outcomes.
3. Never recommend disputing accurate information.
4. Use plain, empowering language a consumer can understand.
5. Focus on which items to prioritize and why, based on potential credit impact AND legal strength.
6. Reference specific statutes and case precedents from the provided legal_authorities when explaining your selections.
7. Keep rationale concise - 2-3 sentences per item max, citing the most relevant statute or case.
8. When multiple legal authorities apply, mention the strongest one for the specific situation.

LEGAL CONTEXT USAGE:
- Each item includes a "legal_authorities" field with applicable statutes, cases, and strategy notes.
- Use statute sections (e.g., "15 U.S.C. § 1681i(a)") when explaining why an item is disputable.
- Reference case precedents (e.g., "Cushman v. Trans Union") when they strengthen the dispute rationale.
- TILA provisions apply when billing disputes or creditor reporting obligations are involved.
- Dodd-Frank UDAAP applies when reporting practices are deceptive or unfair.

You will receive a list of dispute-eligible items with scores, evidence, and legal authorities. Select the top items for this round and explain why each was chosen, incorporating legal backing.

Respond in valid JSON with this structure:
{
  "selected_ids": ["id1", "id2", ...],
  "round_summary": "Brief 1-2 sentence summary of the strategy",
  "per_item_rationale": {
    "id1": "Why this item was selected, citing applicable law (2-3 sentences)",
    "id2": "Why this item was selected, citing applicable law (2-3 sentences)"
  },
  "overall_rationale": "3-5 sentence explanation of the overall strategy for this round, referencing the legal framework"
}"""


def _parse_llm_response(
    response_text: str,
    scored_claims: List[ScoredClaim],
    round_size: int = DEFAULT_ROUND_SIZE,
) -> Optional[StrategyRecommendation]:
    try:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        data = json.loads(cleaned)
        selected_ids = set(data.get("selected_ids", []))

        selected = [sc for sc in scored_claims if sc.review_claim.review_claim_id in selected_ids]

        if not selected:
            return None

        deduped = select_round(selected, round_size)

        return StrategyRecommendation(
            selected_claims=deduped,
            rationale=data.get("overall_rationale", ""),
            round_summary=data.get("round_summary", f"{len(deduped)} items selected"),
            source="ai",
            per_claim_rationale=data.get("per_item_rationale", {}),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"Failed to parse LLM response: {e}")
        return None


def build_ai_strategy(
    review_claims: List[ReviewClaim],
    round_size: int = DEFAULT_ROUND_SIZE,
    excluded_ids: Optional[List[str]] = None,
) -> StrategyRecommendation:
    scored = rank_claims(review_claims, excluded_ids)

    if not scored:
        return StrategyRecommendation(
            selected_claims=[],
            rationale="No eligible items found for dispute.",
            round_summary="No items to dispute",
            source="deterministic",
        )

    payload = _build_llm_payload(scored, round_size)

    user_prompt = (
        f"Analyze these {len(payload)} dispute-eligible credit report items and select "
        f"the top {round_size} for this dispute round. Prioritize items with the highest "
        f"potential credit impact.\n\n"
        f"Items:\n{json.dumps(payload, indent=2)}"
    )

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL"),
            api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY"),
        )

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": STRATEGY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=2000,
        )

        response_text = response.choices[0].message.content or ""
        result = _parse_llm_response(response_text, scored, round_size)

        if result:
            return result

        logger.warning("LLM response parsing failed, falling back to deterministic")

    except Exception as e:
        logger.warning(f"LLM strategy call failed: {e}, falling back to deterministic")

    return build_deterministic_strategy(review_claims, round_size, excluded_ids)
