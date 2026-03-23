"""
Dispute orchestration (Streamlit-free).

Extracted from app_real.py GENERATING flow and related dispute helpers: canonical
claims, readiness, letter grouping/capacity, bureau aggregation, round-1 vs
round-N letter generation, forbidden-assertion scans, and optional AI strategy
plus 72-hour plan builders (credit_command_plan / war_room_plan).

app_real.py is not wired to this module yet (Phase 1 extraction only).
"""

from __future__ import annotations

import traceback
from typing import Any, Dict, List, Optional, Tuple

import database as db
import auth

from approval import create_approval
from claims import ClaimState
from constants import BLOCKER_MAPPING, CAPACITY_LIMIT_V1
from credit_command_plan import build_credit_command_plan
from dispute_strategy import build_ai_strategy, build_deterministic_strategy
from evidence_chain import build_evidence_chain, validate_evidence_chain
from letter_generator import generate_letter_from_claims, generate_round1_letter
from readiness import Decision, apply_capacity, evaluate_claim_readiness, group_into_letters
from services.review_helpers import review_claim_to_canonical
from truth_posture import forbidden_assertions_scan
from war_room_plan import build_war_room_plan


def _group_disputes_by_review_type(items: List[Any]) -> Dict[Any, List[Any]]:
    grouped: Dict[Any, List[Any]] = {}
    for rc in items:
        rt = rc.review_type
        if rt not in grouped:
            grouped[rt] = []
        grouped[rt].append(rc)
    return grouped


def _selected_bureaus_lower(selected_claims: List[Any]) -> set:
    bureaus = set()
    for rc in selected_claims:
        b = (rc.entities.get("bureau") or "unknown").lower()
        bureaus.add(b)
    return bureaus


def _compute_strategy_result(
    review_claims_list: List[Any],
    eligible_count: int,
    excluded_ids: List[str],
) -> Dict[str, Any]:
    try:
        strategy = build_ai_strategy(
            review_claims_list,
            round_size=min(eligible_count, 10),
            excluded_ids=excluded_ids,
        )
    except Exception as e:
        print(f"[AI_STRATEGY_ERROR] {type(e).__name__}: {e}")
        strategy = build_deterministic_strategy(
            review_claims_list,
            round_size=min(eligible_count, 10),
            excluded_ids=excluded_ids,
        )

    ai_per_claim: Dict[str, Any] = {}
    for sc in strategy.selected_claims:
        rc_id = sc.review_claim.review_claim_id
        per_rationale = strategy.per_claim_rationale.get(rc_id, "")
        ai_per_claim[rc_id] = {
            "rationale": per_rationale,
            "score": round(sc.impact_score, 1),
            "rank": sc.rank,
        }
    return {
        "source": strategy.source,
        "rationale": strategy.rationale,
        "round_summary": strategy.round_summary,
        "per_claim": ai_per_claim,
        "selected_ids": [sc.review_claim.review_claim_id for sc in strategy.selected_claims],
        "_strategy_object": strategy,
    }


def _apply_ai_entitlement_spend(
    strategy_source: str,
    user_id: Any,
    is_admin_user: bool,
    ai_balance: int,
) -> Tuple[int, bool]:
    """Returns (new_ai_balance, spend_failed). Mirrors app_real DISPUTES AI block."""
    if strategy_source == "ai" and not is_admin_user:
        if auth.spend_entitlement(user_id, "ai_rounds", 1):
            return max(0, ai_balance - 1), False
        return ai_balance, True
    return ai_balance, False


def process_dispute_pipeline(
    selected_claims: List[Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run dispute letter orchestration (and optional strategy / 72-hour plans).

    Parameters
    ----------
    selected_claims:
        ReviewClaim instances the user selected for generation (same as
        ``_gen_selected_items`` in app_real).
    context:
        Required keys:
        - ``uploaded_reports``: dict snapshot_key -> report dict (``report_pipeline`` shape)
        - ``extracted_claims``: dict snapshot_key -> list of Claim
        - ``identity_confirmed``: dict bureau_lower -> bool
        - ``review_claim_responses``: dict review_claim_id -> response str
        - ``review_claims_list``: full list of ReviewClaim (for canonical build)
        - ``round_number``: int (1 = round 1 letters)

        Optional:
        - ``user_id``: for ``db.save_letter`` and billing logs
        - ``is_admin_user``: bool (default False)
        - ``run_dispute_strategy``: if True, run AI/deterministic strategy first
        - ``strategy_excluded_ids``: claim ids excluded from strategy round
        - ``strategy_eligible_count``: int for strategy round_size cap (default len(selected_claims))
        - ``apply_ai_spend``: if True with ``run_dispute_strategy``, spend one ai_round (default False)
        - ``ai_balance``: int entitlement balance for spend math (default 0)
        - ``persist_letters``: call ``db.save_letter`` when True (default True)
        - ``strike_metrics``, ``violations``, ``tradelines``, ``mission_goal``,
          ``mission_timeline``, ``has_mailed``, ``days_elapsed`` — forwarded to
          ``build_war_room_plan`` when ``strike_metrics`` is present
        - ``apply_letter_billing``: spend free round / free letters / letter
          entitlements like app_real (default True; requires user_id)

    Returns
    -------
    dict with keys:
        ``letters``, ``grouped_disputes``, ``strategy``, ``72_hour_plan``,
        ``readiness``, ``truth_posture``,
    plus when applicable:
        ``error``, ``billing``, ``_ai_spend_failed``, ``dispute_round_record``.
    """
    uploaded_reports: Dict[str, Any] = context["uploaded_reports"]
    extracted_claims: Dict[str, Any] = context["extracted_claims"]
    identity_confirmed: Dict[str, bool] = context["identity_confirmed"]
    review_claims_list: List[Any] = context["review_claims_list"]
    round_number: int = context["round_number"]

    user_id = context.get("user_id")
    is_admin_user = bool(context.get("is_admin_user", False))
    persist_letters = context.get("persist_letters", True)
    apply_letter_billing = context.get("apply_letter_billing", True)

    grouped_disputes = _group_disputes_by_review_type(selected_claims)
    bureaus_set = _selected_bureaus_lower(selected_claims)

    strategy: Optional[Dict[str, Any]] = None
    _ai_spend_failed = False
    new_ai_balance = int(context.get("ai_balance", 0))

    if context.get("run_dispute_strategy"):
        excluded = list(context.get("strategy_excluded_ids") or [])
        elig_n = int(context.get("strategy_eligible_count", len(selected_claims) or 0))
        strategy = _compute_strategy_result(review_claims_list, max(elig_n, 1), excluded)
        strat_obj = strategy.pop("_strategy_object", None)
        if context.get("apply_ai_spend") and user_id is not None and strat_obj is not None:
            new_ai_balance, _ai_spend_failed = _apply_ai_entitlement_spend(
                strat_obj.source, user_id, is_admin_user, new_ai_balance
            )

    credit_plan = build_credit_command_plan(
        items_by_type=grouped_disputes,
        selected_count=len(selected_claims),
        bureaus=bureaus_set,
        parsed_reports=uploaded_reports,
    )

    truth_posture: Dict[str, Any] = {
        "forbidden_scan_by_bureau": {},
        "bureaus_skipped_by_scan": [],
    }
    readiness: Dict[str, Any] = {
        "decisions": [],
        "include_decisions": [],
        "blocked_decisions": [],
        "letter_candidates": [],
        "final_selected": [],
        "capacity_result": None,
        "approval_obj": None,
    }
    letters: Dict[str, Any] = {}
    war_room_dict: Optional[Dict[str, Any]] = None

    billing = {
        "letter_deduct_count": 0,
        "used_free_round": False,
        "spent_free_letters": False,
        "spent_entitlement_letters": False,
        "letter_spend_failed": False,
        "new_letters_balance": None,
    }

    if not selected_claims:
        hour72 = {"credit_command": credit_plan, "war_room": war_room_dict}
        return {
            "letters": letters,
            "grouped_disputes": grouped_disputes,
            "strategy": strategy,
            "72_hour_plan": hour72,
            "readiness": readiness,
            "truth_posture": truth_posture,
            "error": "no_selected_claims",
            "billing": billing,
            "_ai_spend_failed": _ai_spend_failed,
            "_ai_balance_after": new_ai_balance,
        }

    responses = dict(context.get("review_claim_responses") or {})
    included_rc_ids = [rc.review_claim_id for rc in selected_claims]
    for rc_id in included_rc_ids:
        responses[rc_id] = "inaccurate"

    canonical_claims: List[Dict[str, Any]] = []
    for snapshot_key_c, report_c in uploaded_reports.items():
        bureau_key_c = report_c.get("bureau", "unknown").lower()
        identity_ok_c = identity_confirmed.get(bureau_key_c, False)
        bureau_rcs_c = [
            rc
            for rc in review_claims_list
            if (rc.entities.get("bureau") or "").lower() == bureau_key_c
        ]
        for rc in bureau_rcs_c:
            response_c = responses.get(rc.review_claim_id, "awaiting")
            canonical_c = review_claim_to_canonical(rc, response_c, bureau_key_c, identity_ok_c)
            canonical_claims.append(canonical_c)

    canonical_inputs: Dict[str, Any] = {
        "identity_confirmed": any(identity_confirmed.values()),
    }

    decisions: List[Decision] = []
    for cc in canonical_claims:
        bureau_code = cc.get("bureau", "")
        bureau_lower_map = {"EQ": "equifax", "EX": "experian", "TU": "transunion"}
        bureau_lower = bureau_lower_map.get(bureau_code, bureau_code.lower())
        per_claim_inputs = dict(canonical_inputs)
        per_claim_inputs["identity_confirmed"] = identity_confirmed.get(bureau_lower, False)
        decision = evaluate_claim_readiness(cc, per_claim_inputs)
        decisions.append(decision)

    for i, decision in enumerate(decisions):
        if decision.include_reason_code:
            cc = canonical_claims[i]
            if decision.include_reason_code == "USER_CONFIRMED_FACT" and cc.get("user_assertion_flags"):
                continue
            chain = build_evidence_chain(cc, canonical_inputs)
            tier = decision.letter_language_tier
            if tier and not validate_evidence_chain(chain, tier):
                mapping = BLOCKER_MAPPING["MISSING_REQUIRED_FIELDS"]
                decisions[i] = Decision(
                    claim_id=decision.claim_id,
                    blocker_reason_code="MISSING_REQUIRED_FIELDS",
                    ui_label=mapping["ui_label"],
                    user_action=mapping["user_action"],
                    posture="NONE",
                )

    readiness["decisions"] = decisions
    include_decisions = [d for d in decisions if d.include_reason_code]
    blocked_decisions = [d for d in decisions if d.blocker_reason_code]
    readiness["include_decisions"] = include_decisions
    readiness["blocked_decisions"] = blocked_decisions

    if not include_decisions:
        hour72 = {"credit_command": credit_plan, "war_room": war_room_dict}
        return {
            "letters": letters,
            "grouped_disputes": grouped_disputes,
            "strategy": strategy,
            "72_hour_plan": hour72,
            "readiness": readiness,
            "truth_posture": truth_posture,
            "error": "blocked",
            "billing": billing,
            "_ai_spend_failed": _ai_spend_failed,
            "_ai_balance_after": new_ai_balance,
        }

    letter_candidates = group_into_letters(include_decisions, canonical_claims)
    capacity_result = apply_capacity(letter_candidates, CAPACITY_LIMIT_V1)
    final_selected = capacity_result["selected"]

    readiness["letter_candidates"] = letter_candidates
    readiness["final_selected"] = final_selected
    readiness["capacity_result"] = capacity_result

    approved_letter_keys = [c.letter_key for c in final_selected]
    approved_claim_ids: List[str] = []
    approved_postures = set()
    approved_targets = set()
    for c in final_selected:
        approved_claim_ids.extend(c.claims)
        approved_targets.add(c.letter_key[0])
    for d in include_decisions:
        if d.claim_id in approved_claim_ids:
            approved_postures.add(d.posture)

    approval_obj = create_approval(
        user_id="session_user",
        capacity_limit=CAPACITY_LIMIT_V1,
        approved_letters=approved_letter_keys,
        approved_items=approved_claim_ids,
        approved_postures=list(approved_postures),
        approved_targets=list(approved_targets),
    )
    readiness["approval_obj"] = approval_obj

    rc_map = {rc.review_claim_id: rc for rc in review_claims_list}

    letters_generated: Dict[str, Any] = {}
    bureau_aggregated_claims: Dict[str, List[Any]] = {}
    bureau_consumer_info: Dict[str, Any] = {}
    bureau_report_data: Dict[str, Any] = {}
    bureau_rc_details: Dict[str, List[Dict[str, Any]]] = {}

    try:
        for candidate in final_selected:
            target_type, creditor_norm, bureau_code = candidate.letter_key
            bureau_lower_map = {"EQ": "equifax", "EX": "experian", "TU": "transunion"}
            bureau_lower = bureau_lower_map.get(bureau_code, bureau_code.lower())

            matching_snapshot = next(
                (
                    (k, r)
                    for k, r in uploaded_reports.items()
                    if r.get("bureau", "").lower() == bureau_lower
                ),
                (None, None),
            )
            snapshot_key_l, report_data = matching_snapshot
            if not snapshot_key_l:
                continue

            bureau_claims_raw = extracted_claims.get(snapshot_key_l, [])

            rc_claim_ids_in_letter = set()
            for claim_id in candidate.claims:
                rc_l = rc_map.get(claim_id)
                if rc_l:
                    rc_claim_ids_in_letter.update(rc_l.supporting_claim_ids)
                    if bureau_lower not in bureau_rc_details:
                        bureau_rc_details[bureau_lower] = []
                    creditor_display = (
                        rc_l.entities.get("creditor")
                        or rc_l.entities.get("account_name")
                        or rc_l.entities.get("_extracted_creditor")
                        or rc_l.entities.get("furnisher")
                        or rc_l.entities.get("inquirer")
                        or "Unknown Account"
                    )
                    review_type_display = (
                        rc_l.review_type.value.replace("_", " ").title()
                        if hasattr(rc_l.review_type, "value")
                        else str(rc_l.review_type)
                    )
                    if not any(d["rc_id"] == claim_id for d in bureau_rc_details[bureau_lower]):
                        bureau_rc_details[bureau_lower].append(
                            {
                                "rc_id": claim_id,
                                "creditor": creditor_display,
                                "review_type": review_type_display,
                            }
                        )

            seen_ids = {c.claim_id for c in bureau_aggregated_claims.get(bureau_lower, [])}
            for claim in bureau_claims_raw:
                if claim.claim_id in rc_claim_ids_in_letter and claim.claim_id not in seen_ids:
                    if claim.state == ClaimState.AWAITING_CONSUMER_REVIEW:
                        response_l = responses.get(
                            next(
                                (
                                    rc_id
                                    for rc_id, rc_v in rc_map.items()
                                    if claim.claim_id in rc_v.supporting_claim_ids
                                ),
                                "",
                            ),
                            "awaiting",
                        )
                        if response_l == "inaccurate":
                            claim.consumer_marks_inaccurate()
                        elif response_l == "unsure":
                            claim.consumer_marks_unverifiable()
                    if claim.state in [
                        ClaimState.CONSUMER_MARKED_INACCURATE,
                        ClaimState.CONSUMER_MARKED_UNVERIFIABLE,
                    ]:
                        claim.promote_to_legally_actionable()
                    if claim.state == ClaimState.LEGALLY_ACTIONABLE:
                        claim.fields["letter_eligible"] = True
                        if bureau_lower not in bureau_aggregated_claims:
                            bureau_aggregated_claims[bureau_lower] = []
                        bureau_aggregated_claims[bureau_lower].append(claim)

            if bureau_lower not in bureau_consumer_info:
                bureau_consumer_info[bureau_lower] = (report_data or {}).get("parsed_data", {}).get(
                    "personal_info", {}
                )
            if bureau_lower not in bureau_report_data:
                bureau_report_data[bureau_lower] = report_data

        if round_number == 1:
            bureau_round1_items: Dict[str, List[Dict[str, Any]]] = {}
            for candidate in final_selected:
                target_type, creditor_norm, bureau_code = candidate.letter_key
                bureau_lower_r1 = {"EQ": "equifax", "EX": "experian", "TU": "transunion"}.get(
                    bureau_code, bureau_code.lower()
                )
                for claim_id in candidate.claims:
                    rc_r1 = rc_map.get(claim_id)
                    if rc_r1:
                        if bureau_lower_r1 not in bureau_round1_items:
                            bureau_round1_items[bureau_lower_r1] = []
                        rt_val = (
                            rc_r1.review_type.value
                            if hasattr(rc_r1.review_type, "value")
                            else str(rc_r1.review_type)
                        )
                        ct_val = ""
                        merged_fields: Dict[str, Any] = {}
                        if rc_r1.supporting_claim_ids:
                            snapshot_key_ct = next(
                                (
                                    k
                                    for k, r in uploaded_reports.items()
                                    if r.get("bureau", "").lower() == bureau_lower_r1
                                ),
                                None,
                            )
                            if snapshot_key_ct:
                                raw_claims_ct = extracted_claims.get(snapshot_key_ct, [])
                                for rc_claim in raw_claims_ct:
                                    if rc_claim.claim_id in rc_r1.supporting_claim_ids:
                                        if not ct_val:
                                            ct_val = (
                                                rc_claim.claim_type.value
                                                if hasattr(rc_claim.claim_type, "value")
                                                else str(rc_claim.claim_type)
                                            )
                                        if hasattr(rc_claim, "fields") and rc_claim.fields:
                                            for fk, fv in rc_claim.fields.items():
                                                if fv and fk not in merged_fields:
                                                    merged_fields[fk] = fv
                        bureau_round1_items[bureau_lower_r1].append(
                            {
                                "entities": dict(rc_r1.entities) if rc_r1.entities else {},
                                "fields": merged_fields,
                                "claim_type": ct_val,
                                "review_type": rt_val,
                                "rc_id": claim_id,
                            }
                        )

            for bureau_lower_r1, items_r1 in bureau_round1_items.items():
                if not items_r1:
                    continue
                consumer_info = bureau_consumer_info.get(bureau_lower_r1, {})
                try:
                    letter_data = generate_round1_letter(bureau_lower_r1, consumer_info, items_r1)
                except ValueError as ve:
                    print(f"[ROUND1_LETTER_ERROR] {ve}")
                    continue

                letter_text = letter_data.get("letter_text", "")
                passed = forbidden_assertions_scan(letter_text)
                truth_posture["forbidden_scan_by_bureau"][bureau_lower_r1] = passed
                if not passed:
                    truth_posture["bureaus_skipped_by_scan"].append(bureau_lower_r1)
                    continue

                letter_data["rc_details"] = bureau_rc_details.get(bureau_lower_r1, [])
                letters_generated[bureau_lower_r1] = letter_data

                report_data = bureau_report_data.get(bureau_lower_r1)
                report_id_val = (report_data or {}).get("report_id")
                if persist_letters and report_id_val and user_id is not None:
                    try:
                        uid = user_id
                        db.save_letter(
                            report_id_val,
                            letter_data["letter_text"],
                            bureau_lower_r1,
                            letter_data.get("claim_count", 0),
                            letter_data.get("categories", []),
                            user_id=uid,
                        )
                    except Exception:
                        pass
        else:
            for bureau_lower, actionable_claims in bureau_aggregated_claims.items():
                if not actionable_claims:
                    continue

                consumer_info = bureau_consumer_info.get(bureau_lower, {})

                letter_data = generate_letter_from_claims(
                    actionable_claims,
                    consumer_info,
                    bureau_lower,
                )

                letter_text = letter_data.get("letter_text", "")
                passed = forbidden_assertions_scan(letter_text)
                truth_posture["forbidden_scan_by_bureau"][bureau_lower] = passed
                if not passed:
                    truth_posture["bureaus_skipped_by_scan"].append(bureau_lower)
                    continue

                letter_data["rc_details"] = bureau_rc_details.get(bureau_lower, [])
                letters_generated[bureau_lower] = letter_data

                report_data = bureau_report_data.get(bureau_lower)
                report_id_val = (report_data or {}).get("report_id")
                if persist_letters and report_id_val and user_id is not None:
                    try:
                        uid = user_id
                        db.save_letter(
                            report_id_val,
                            letter_data["letter_text"],
                            bureau_lower,
                            letter_data.get("claim_count", 0),
                            letter_data.get("categories", []),
                            user_id=uid,
                        )
                    except Exception:
                        pass

    except Exception as e:
        print(f"[LETTER_GEN_ERROR] {type(e).__name__}: {str(e)}")
        print(f"[LETTER_GEN_TRACE] {traceback.format_exc()}")
        hour72 = {"credit_command": credit_plan, "war_room": war_room_dict}
        return {
            "letters": letters_generated,
            "grouped_disputes": grouped_disputes,
            "strategy": strategy,
            "72_hour_plan": hour72,
            "readiness": readiness,
            "truth_posture": truth_posture,
            "error": "exception",
            "billing": billing,
            "_ai_spend_failed": _ai_spend_failed,
            "_ai_balance_after": new_ai_balance,
        }

    letters = letters_generated

    if context.get("strike_metrics") is not None:
        wr = build_war_room_plan(
            strike_metrics=context["strike_metrics"],
            violations=context.get("violations"),
            tradelines=context.get("tradelines"),
            mission_goal=context.get("mission_goal", "General Rebuild"),
            mission_timeline=context.get("mission_timeline", "ASAP (7 days)"),
            has_letters=bool(letters_generated),
            has_mailed=bool(context.get("has_mailed", False)),
            days_elapsed=int(context.get("days_elapsed", 0)) if context.get("has_mailed") else 0,
        )
        war_room_dict = wr.as_dict()

    hour72 = {"credit_command": credit_plan, "war_room": war_room_dict}

    if not letters_generated:
        return {
            "letters": letters,
            "grouped_disputes": grouped_disputes,
            "strategy": strategy,
            "72_hour_plan": hour72,
            "readiness": readiness,
            "truth_posture": truth_posture,
            "error": "no_letters",
            "billing": billing,
            "_ai_spend_failed": _ai_spend_failed,
            "_ai_balance_after": new_ai_balance,
        }

    letter_deduct_count = min(
        int(context.get("letter_count_to_deduct", len(letters_generated))),
        len(letters_generated),
    )
    billing["letter_deduct_count"] = letter_deduct_count

    is_free_gen = bool(context.get("is_free_generation", False))
    free_item_count = int(context.get("free_item_count", 0)) if is_free_gen else 0
    free_max_cap = int(context.get("free_max_capacity", 0)) if is_free_gen else 0
    current_letters_bal = int(context.get("current_letters_balance", 0))

    is_sprint_free_r3 = bool(
        round_number >= 3
        and user_id is not None
        and db.check_free_round_eligible(user_id)
    )

    if apply_letter_billing and user_id is not None:
        if is_sprint_free_r3 and not is_admin_user:
            db.use_free_round(user_id)
            db.log_activity(user_id, "free_round3", "Sprint guarantee Round 3 used", "GENERATING")
            billing["used_free_round"] = True
        elif is_free_gen and not is_admin_user:
            cap = free_max_cap if free_max_cap > 0 else None
            if not auth.spend_free_letters(user_id, free_item_count, max_capacity=cap):
                billing["letter_spend_failed"] = True
            else:
                billing["spent_free_letters"] = True
        elif not is_admin_user and letter_deduct_count > 0:
            if auth.spend_entitlement(user_id, "letters", letter_deduct_count):
                billing["spent_entitlement_letters"] = True
                billing["new_letters_balance"] = max(0, current_letters_bal - letter_deduct_count)
            else:
                billing["letter_spend_failed"] = True

    dispute_round_record = {
        "round_number": round_number,
        "claim_ids": included_rc_ids,
        "letters": list(letters_generated.keys()),
        "source": "battle_plan",
    }

    try:
        if user_id is not None:
            db.log_activity(
                user_id,
                "generate_letters",
                f"{len(letters_generated)} letter(s) for {', '.join(b.title() for b in letters_generated.keys())}",
                "GENERATING",
            )
    except Exception:
        pass

    return {
        "letters": letters,
        "grouped_disputes": grouped_disputes,
        "strategy": strategy,
        "72_hour_plan": hour72,
        "readiness": readiness,
        "truth_posture": truth_posture,
        "error": None,
        "billing": billing,
        "dispute_round_record": dispute_round_record,
        "_ai_spend_failed": _ai_spend_failed,
        "_ai_balance_after": new_ai_balance,
    }
