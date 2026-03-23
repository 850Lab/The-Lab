"""
letter_generator.py | 850 Lab Parser Machine
Consumer dispute letter generation from legally_actionable Claim objects.
Letters sound personal and consumer-written while citing specific FCRA provisions.
One letter per bureau with clear, factual dispute language.
"""

from __future__ import annotations
from datetime import datetime
from io import BytesIO
import textwrap
import re
import random
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from statutes import get_statute, get_bureau_address, DISPUTE_TYPES
from legal_kb import build_per_claim_legal_context

if TYPE_CHECKING:
    from claims import Claim, ClaimType


class LetterEligibilityError(Exception):
    pass


VOICE_GREETINGS = {
    'Calm & Professional': 'To Whom It May Concern:',
    'Firm & Direct': 'To Whom It May Concern:',
    'Short & Concise': 'To Whom It May Concern:',
}

VOICE_DISPUTE_PHRASES = {
    'I dispute the accuracy of…': 'I dispute the accuracy of',
    'I am challenging the accuracy of…': 'I am challenging the accuracy of',
    'This information is inaccurate and must be corrected…': 'This information is inaccurate and must be corrected regarding',
}

VOICE_REQUEST_PHRASES = {
    'Please investigate and correct or delete…': 'please reinvestigate and correct or delete',
    'I request reinvestigation and correction/removal…': 'I request reinvestigation and correction or removal of',
    'Please verify, update, or remove…': 'please verify, update, or remove',
}

VOICE_VERIFY_PHRASES = {
    'Provide the method of verification…': 'provide a description of the method used to verify the information',
    'Provide how this was verified…': 'provide how this information was verified',
    'Provide verification procedures used…': 'provide the verification procedures used',
}


def _apply_voice_to_closing(closing_text, consumer_name, voice_profile):
    if not voice_profile:
        return closing_text
    closing_signoff = voice_profile.get('closing', 'Sincerely,')
    if closing_signoff and closing_signoff != 'Sincerely,':
        closing_text = closing_text.replace('Sincerely,', closing_signoff)
    return closing_text


def _apply_voice_to_opening(opening_text, voice_profile):
    if not voice_profile:
        return opening_text

    phrases = voice_profile.get('preferred_phrases', {})
    dispute_phrase = phrases.get('dispute', '')
    request_phrase = phrases.get('request', '')

    if dispute_phrase and dispute_phrase != 'I dispute the accuracy of…':
        mapped = VOICE_DISPUTE_PHRASES.get(dispute_phrase, '')
        if mapped:
            opening_text = opening_text.replace('I am disputing specific information', mapped.rstrip(' of'))
            opening_text = opening_text.replace('I am disputing', mapped.rstrip(' of').replace('the accuracy of', '').strip() or 'I am disputing')

    if request_phrase and request_phrase != 'Please investigate and correct or delete…':
        mapped = VOICE_REQUEST_PHRASES.get(request_phrase, '')
        if mapped:
            opening_text = opening_text.replace('reinvestigate and correct or delete', mapped.replace('please ', '').replace('I request ', ''))

    return opening_text


def _apply_voice_to_verify(letter_text, voice_profile):
    if not voice_profile:
        return letter_text

    phrases = voice_profile.get('preferred_phrases', {})
    verify_phrase = phrases.get('verify', '')

    if verify_phrase and verify_phrase != 'Provide the method of verification…':
        mapped = VOICE_VERIFY_PHRASES.get(verify_phrase, '')
        if mapped:
            letter_text = letter_text.replace(
                'provide a description of the method used to verify the information',
                mapped,
            )
            letter_text = letter_text.replace(
                'description of the method used to verify',
                mapped.replace('provide ', ''),
            )

    return letter_text


def _apply_voice_detail_level(closing_text, voice_profile):
    if not voice_profile:
        return closing_text
    detail = voice_profile.get('detail_level', 'Standard')
    if detail == 'Minimal':
        closing_text = re.sub(
            r'Be advised that under.*?§ 1681n, and attorney\'s fees\.\s*',
            '',
            closing_text,
            flags=re.DOTALL,
        )
        closing_text = re.sub(
            r'I am also aware that under.*?§ 1681n, and attorney\'s fees\.\s*',
            '',
            closing_text,
            flags=re.DOTALL,
        )
    return closing_text


def apply_voice_profile(letter_text, consumer_name, voice_profile):
    if not voice_profile:
        return letter_text
    letter_text = _apply_voice_to_verify(letter_text, voice_profile)
    letter_text = _apply_voice_to_closing(letter_text, consumer_name, voice_profile)
    letter_text = _apply_voice_detail_level(letter_text, voice_profile)
    return letter_text


def filter_letter_eligible_claims(claims: List['Claim']) -> List['Claim']:
    eligible = []
    for claim in claims:
        if claim.fields.get('letter_eligible', False):
            eligible.append(claim)
    return eligible


def check_letter_readiness(claims: List['Claim']) -> Dict[str, Any]:
    if not claims:
        return {
            "letter_ready": False,
            "letter_block_reason": "No claims available for letter generation."
        }

    high_count = sum(1 for c in claims if c.fields.get('claim_confidence') == 'high')
    medium_count = sum(1 for c in claims if c.fields.get('claim_confidence') == 'medium')
    low_count = sum(1 for c in claims if c.fields.get('claim_confidence') == 'low')
    eligible_count = sum(1 for c in claims if c.fields.get('letter_eligible', False))

    if eligible_count > 0:
        return {
            "letter_ready": True,
            "letter_block_reason": None,
            "eligible_count": eligible_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count
        }

    if high_count == 0 and medium_count > 0:
        return {
            "letter_ready": False,
            "letter_block_reason": f"No high-confidence disputes detected. Review {medium_count} medium-confidence item(s) to enable letter generation.",
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count
        }

    if high_count == 0 and medium_count == 0:
        return {
            "letter_ready": False,
            "letter_block_reason": "Only low-confidence claims detected. These items require review before disputing.",
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count
        }

    return {
        "letter_ready": False,
        "letter_block_reason": "No eligible claims for letter generation.",
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count
    }


CLAIM_TYPE_TO_REVIEW_TYPE = {
    "account_present": "account_ownership",
    "balance_reported": "accuracy_verification",
    "status_reported": "accuracy_verification",
    "late_payment_reported": "negative_impact",
    "inquiry_present": "accuracy_verification",
    "personal_info_present": "identity_verification",
    "address_listed": "identity_verification",
    "duplicate_detected": "duplicate_account",
    "date_reported": "accuracy_verification",
}

CLAIM_TYPE_TO_DISPUTE_TYPE = {
    "account_present": "account_present",
    "balance_reported": "balance_reported",
    "status_reported": "status_reported",
    "late_payment_reported": "late_payment_reported",
    "inquiry_present": "inquiry_present",
    "personal_info_present": "personal_info_present",
    "address_listed": "personal_info_present",
    "duplicate_detected": "duplicate_detected",
    "date_reported": "date_reported",
}


def _safe_str(val) -> str:
    if val is None:
        return ''
    return str(val).strip()


def _is_valid(val, min_len=1) -> bool:
    s = _safe_str(val)
    if not s or len(s) < min_len:
        return False
    return s.lower() not in ('', 'unknown', 'n/a', 'none', 'not_found', 'not provided')


def _format_ssn_last_four(ssn_raw: str) -> str:
    if not ssn_raw:
        return ''
    digits = re.sub(r'[^\d]', '', ssn_raw)
    if len(digits) >= 4:
        return digits[-4:]
    return ''


def _format_balance(balance) -> str:
    bal_str = _safe_str(balance)
    if not bal_str or bal_str.lower() in ('0', '$0', '$0.00', 'unknown', 'n/a', ''):
        return ''
    if not bal_str.startswith('$'):
        try:
            bal_num = float(bal_str.replace(',', ''))
            bal_str = f"${bal_num:,.2f}"
        except (ValueError, TypeError):
            bal_str = f"${bal_str}"
    return bal_str


def _mask_account(account: str) -> str:
    if not account or len(account.strip()) < 1:
        return ''
    mask = account.strip()
    if len(mask) > 4:
        mask = "xxxx" + mask[-4:]
    return mask


def _format_account_reference(account_raw: str) -> str:
    if not account_raw or len(account_raw.strip()) < 1:
        return ''
    acct = account_raw.strip()
    has_x_prefix = bool(re.match(r'^[Xx*#\.]+\d', acct))
    has_x_suffix = bool(re.search(r'\d[Xx*#\.]+$', acct))
    has_mixed_mask = bool(re.search(r'[Xx*#\.]{2,}', acct))
    digits_only = re.sub(r'[^0-9]', '', acct)
    if has_x_prefix or has_x_suffix or has_mixed_mask:
        return acct
    if len(digits_only) <= 4:
        return acct
    return acct


def _build_account_label(account_ref: str, account_number: str = '') -> str:
    raw = account_ref or account_number
    if not raw or not raw.strip():
        return ''
    raw = raw.strip()
    formatted = _format_account_reference(raw)
    digits_only = re.sub(r'[^0-9]', '', raw)
    has_mask_chars = bool(re.search(r'[Xx*#\.]{2,}', raw))
    if has_mask_chars:
        return f"Account #{formatted}"
    if len(digits_only) <= 4:
        return f"Account #{formatted}"
    if len(digits_only) > 8:
        return f"Account #{formatted}"
    return f"Account #{formatted}"


def generate_letter_from_claims(
    claims: List['Claim'],
    consumer_info: Dict[str, Any],
    bureau: str,
    strategy_context: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    from claims import ClaimState, ClaimType, IllegalStateAccessError

    for claim in claims:
        if claim.state != ClaimState.LEGALLY_ACTIONABLE:
            raise IllegalStateAccessError(
                f"Cannot generate letter: claim {claim.claim_id} is in {claim.state.value}, "
                f"not legally_actionable. Consumer must mark claim first."
            )

        if not claim.fields.get('letter_eligible', False):
            raise LetterEligibilityError(
                f"Cannot generate letter: claim {claim.claim_id} has letter_eligible=False. "
                f"Only high-confidence claims or user-confirmed medium-confidence claims are eligible."
            )

    bureau_info = get_bureau_address(bureau)

    consumer_name = _safe_str(consumer_info.get('name', ''))
    if not consumer_name or len(consumer_name) < 2:
        consumer_name = '[Your Full Name]'

    consumer_address = _safe_str(consumer_info.get('address', ''))
    addr_invalid_patterns = ['id address', 'not provided', 'n/a', 'unknown']
    if (not consumer_address or len(consumer_address) < 5
            or any(p in consumer_address.lower() for p in addr_invalid_patterns)):
        consumer_address = '[Your Address]'

    ssn_raw = consumer_info.get('ssn', '') or consumer_info.get('ssn_last_four', '') or consumer_info.get('ssn_last4', '')
    ssn_last_four = _format_ssn_last_four(_safe_str(ssn_raw))

    dob_raw = consumer_info.get('dob', '') or consumer_info.get('date_of_birth', '')
    dob_str = _safe_str(dob_raw)
    if dob_str and dob_str.lower() in ('unknown', 'n/a', 'not_found', 'none'):
        dob_str = ''

    confirmation_number = _safe_str(consumer_info.get('confirmation_number', '')
                                     or consumer_info.get('report_number', '')
                                     or consumer_info.get('file_number', ''))
    if confirmation_number and confirmation_number.lower() in ('unknown', 'n/a', 'none'):
        confirmation_number = ''

    date_str = datetime.now().strftime("%B %d, %Y")
    grouped = _group_claims_by_type(claims)
    categories_used = []
    for claim_type in grouped:
        categories_used.append(claim_type.value if hasattr(claim_type, 'value') else str(claim_type))

    item_count = len(claims)
    item_word = "item" if item_count == 1 else "items"

    letter = f"""{consumer_name}
{consumer_address}

{date_str}

{bureau_info['name']}
{bureau_info['address']}
{bureau_info['city_state_zip']}

Re: Formal Dispute — Demand for Reinvestigation and Verification

To Whom It May Concern:

I am disputing {item_count} {item_word} on my credit report under the Fair Credit Reporting Act, 15 U.S.C. § 1681 et seq. Your agency is required to follow reasonable procedures to assure maximum possible accuracy (15 U.S.C. § 1681e(b)), and I am demanding that you conduct a genuine reinvestigation of each item listed below — not a cursory review or automated parroting of the furnisher's original data.

"""

    id_lines = []
    if ssn_last_four:
        id_lines.append(f"SSN (last four): XXX-XX-{ssn_last_four}")
    if dob_str:
        id_lines.append(f"Date of Birth: {dob_str}")
    if confirmation_number:
        id_lines.append(f"Report/File Number: {confirmation_number}")

    if id_lines:
        letter += "For identification purposes:\n"
        for id_line in id_lines:
            letter += f"  {id_line}\n"
        letter += "\n"

    letter += f"""I am exercising my rights under 15 U.S.C. § 1681i(a) to a free reinvestigation. For each item below, I demand that you contact the furnisher directly, obtain actual verification — not simply a confirmation that the data matches what was previously reported — and provide me with the method of verification used as required by 15 U.S.C. § 1681i(a)(7). Any item that cannot be independently verified is subject to immediate deletion under 15 U.S.C. § 1681i(a)(5)(A).

"""


    item_num = 1
    for claim_type, type_claims in grouped.items():
        for claim in type_claims:
            claim_strategy_note = None
            if strategy_context:
                claim_strategy_note = strategy_context.get(claim.claim_id)
            letter += _generate_claim_section(claim, item_num, claim_strategy_note)
            item_num += 1

    account_dispute_types = {'account_present', 'balance_reported', 'status_reported',
                              'late_payment_reported', 'duplicate_detected', 'date_reported'}
    has_account_disputes = any(
        (ct.value if hasattr(ct, 'value') else str(ct)) in account_dispute_types
        for ct in grouped.keys()
    )
    letter += _build_closing(consumer_name, item_count, has_account_disputes)

    return {
        'bureau': bureau,
        'letter_text': letter,
        'claim_count': len(claims),
        'categories': categories_used
    }


def _group_claims_by_type(claims: List['Claim']) -> Dict['ClaimType', List['Claim']]:
    grouped = {}
    for claim in claims:
        if claim.claim_type not in grouped:
            grouped[claim.claim_type] = []
        grouped[claim.claim_type].append(claim)
    return grouped


def _get_case_precedents_for_claim(claim: 'Claim') -> List[Dict[str, str]]:
    claim_type_val = claim.claim_type.value if hasattr(claim.claim_type, 'value') else str(claim.claim_type)
    review_type = CLAIM_TYPE_TO_REVIEW_TYPE.get(claim_type_val, "")
    if not review_type:
        return []
    legal_ctx = build_per_claim_legal_context(review_type)
    cases = legal_ctx.get("applicable_cases", [])
    return cases[:1]


def _generate_claim_section(claim: 'Claim', item_num: int, strategy_note: Optional[str] = None) -> str:
    from claims import ClaimType

    creditor = _safe_str(
        claim.fields.get('creditor', '') or claim.fields.get('account_name', '')
        or claim.fields.get('furnisher', '')
    )
    account = _safe_str(
        claim.fields.get('account', '') or claim.fields.get('account_number', '')
        or claim.fields.get('account_mask', '')
    )

    section = f"DISPUTED ITEM #{item_num}\n"

    creditor_display = ''
    if _is_valid(creditor, 2):
        creditor_display = creditor
        section += f"Creditor/Furnisher: {creditor}\n"

    account_display = ''
    if _is_valid(account):
        account_display = _format_account_reference(account)
        section += f"Account Number: {account_display}\n"

    balance_display = _format_balance(claim.fields.get('balance', ''))
    if balance_display:
        section += f"Balance Reported: {balance_display}\n"

    status_display = _safe_str(claim.fields.get('status', ''))
    if _is_valid(status_display):
        section += f"Status Reported: {status_display}\n"

    date_opened_val = _safe_str(claim.fields.get('date_opened', '') or claim.fields.get('date', '') or claim.fields.get('opened_date', ''))
    date_reported_val = _safe_str(claim.fields.get('date_reported', '') or claim.fields.get('date_updated', ''))
    date_closed_val = _safe_str(claim.fields.get('date_closed', ''))
    if _is_valid(date_opened_val):
        section += f"Date Opened: {date_opened_val}\n"
    if _is_valid(date_reported_val):
        section += f"Date Reported: {date_reported_val}\n"
    if _is_valid(date_closed_val):
        section += f"Date Closed: {date_closed_val}\n"

    date_first_delinq = _safe_str(
        claim.fields.get('date_first_delinquency', '')
        or claim.fields.get('first_delinquency', '')
        or claim.fields.get('date_of_first_delinquency', '')
    )
    if _is_valid(date_first_delinq):
        section += f"Date of First Delinquency: {date_first_delinq}\n"

    dispute_text = _get_claim_dispute_text(
        claim,
        creditor_name=creditor_display,
        balance_str=balance_display,
        status_str=status_display,
        date_str=date_opened_val if _is_valid(date_opened_val) else '',
        date_first_delinq=date_first_delinq if _is_valid(date_first_delinq) else '',
        strategy_note=strategy_note,
    )
    section += f"Dispute: {dispute_text}\n"

    fcra_sections = _get_fcra_sections_for_claim(claim)
    law_refs = []
    for fcra_section in fcra_sections:
        statute = get_statute(fcra_section)
        if statute:
            law_label = statute.get('law', '')
            if law_label and law_label not in ('FCRA',):
                law_refs.append(f"{statute['section']} ({statute['title']}) [{law_label}]")
            else:
                law_refs.append(f"{statute['section']} ({statute['title']})")

    if law_refs:
        section += "Applicable law: " + "; ".join(law_refs) + "\n"

    case_refs = _get_case_precedents_for_claim(claim)
    if case_refs:
        case = case_refs[0]
        section += f"See also: {case['case']}, {case['citation']}\n"

    section += f"I demand: {_get_requested_action_for_claim(claim, creditor_display, balance_display)}\n\n"

    return section


def _get_claim_dispute_text(
    claim: 'Claim',
    creditor_name: str = '',
    balance_str: str = '',
    status_str: str = '',
    date_str: str = '',
    date_first_delinq: str = '',
    strategy_note: Optional[str] = None,
) -> str:
    from claims import ClaimType

    cred_ref = f" with {creditor_name}" if creditor_name else ""
    cred_ref_the = f" the {creditor_name} account" if creditor_name else " this account"

    parts = []

    if claim.claim_type == ClaimType.ACCOUNT_PRESENT:
        parts.append(f"I dispute{cred_ref_the}. I have no record of opening, authorizing, or benefiting from this account. Provide the original signed application or agreement bearing my signature, the complete payment history from the furnisher, and proof that this account was reported in full compliance with Metro 2 format requirements. If you cannot produce these documents, delete this account from my file under 15 U.S.C. § 1681i(a)(5)(A).")

    elif claim.claim_type == ClaimType.BALANCE_REPORTED:
        if balance_str:
            parts.append(f"The balance of {balance_str} reported for{cred_ref_the} is disputed. I demand that the furnisher provide a complete, certified payment ledger and account statement verifying this exact amount. An automated e-OSCAR confirmation is not a reasonable investigation under Cushman v. Trans Union Corp. If the furnisher cannot produce original documentation substantiating this balance, correct or delete it.")
        else:
            parts.append(f"The balance reported for{cred_ref_the} is disputed. I demand the furnisher produce a certified account ledger verifying this amount. If the balance cannot be substantiated with original documentation, correct or delete it under 15 U.S.C. § 1681i(a)(5)(A).")

    elif claim.claim_type == ClaimType.STATUS_REPORTED:
        if status_str:
            parts.append(f"The status of \"{status_str}\" reported for{cred_ref_the} is disputed. I demand that the furnisher provide documentation proving this status is accurate, including the complete account history and any notices sent to me prior to reporting this status. Under 15 U.S.C. § 1681s-2(b), the furnisher must conduct a reasonable investigation — not simply re-confirm what was already reported.")
        else:
            parts.append(f"The account status reported for{cred_ref_the} is disputed. I demand that the furnisher produce documentation proving this status is accurate. Under 15 U.S.C. § 1681s-2(b), the furnisher must conduct a reasonable investigation and provide supporting records.")

    elif claim.claim_type == ClaimType.LATE_PAYMENT_REPORTED:
        if date_str:
            parts.append(f"A late payment is reported for{cred_ref_the} around {date_str}. I dispute this notation. I demand the furnisher produce the original payment records, including the due date, date payment was received, and any grace period terms. Note that reporting a delinquency during a pending billing dispute may implicate 15 U.S.C. § 1666(a). Produce the records or delete this notation.")
        else:
            parts.append(f"A late payment is reported for{cred_ref_the}. I dispute this notation. I demand the furnisher produce the original payment records showing the due date, date received, and grace period terms. Produce the records or delete.")

    elif claim.claim_type == ClaimType.INQUIRY_PRESENT:
        parts.append(f"I did not authorize this inquiry{cred_ref} and no permissible purpose existed under 15 U.S.C. § 1681b(a). Provide written proof of the permissible purpose and my authorization. If you cannot produce both, remove this inquiry immediately.")

    elif claim.claim_type == ClaimType.PERSONAL_INFO_PRESENT:
        info_val = _safe_str(claim.fields.get('value', ''))
        if info_val and _is_valid(info_val):
            parts.append(f"The personal information \"{info_val}\" is inaccurate and does not identify me. Provide the source of this data and correct or remove it.")
        else:
            parts.append("This personal information is inaccurate. Provide the source and correct or remove it.")

    elif claim.claim_type == ClaimType.ADDRESS_LISTED:
        addr_val = _safe_str(claim.fields.get('value', '') or claim.fields.get('address', ''))
        if addr_val and _is_valid(addr_val, 3):
            parts.append(f"The address \"{addr_val}\" is not mine and should not appear on my file. Disclose the source of this information under 15 U.S.C. § 1681g and remove it.")
        else:
            parts.append("This address is not mine. Disclose the source under 15 U.S.C. § 1681g and remove it.")

    elif claim.claim_type == ClaimType.DUPLICATE_DETECTED:
        parts.append(f"This account{cred_ref} is reported more than once, inflating my reported obligations. Compare your records and delete the duplicate entry. Reporting the same debt more than once raises accuracy concerns under 15 U.S.C. § 1681e(b).")

    elif claim.claim_type == ClaimType.DATE_REPORTED:
        if date_first_delinq:
            parts.append(f"The date of first delinquency is reported as {date_first_delinq} for{cred_ref_the}. I dispute this date. Provide the furnisher's original records establishing the date of first delinquency. If this date is incorrect, the account may have exceeded the seven-year reporting period under 15 U.S.C. § 1681c(a) and should be removed.")
        elif date_str:
            parts.append(f"The date reported ({date_str}) for{cred_ref_the} is disputed. Provide the furnisher's original documentation verifying this date. If it cannot be verified, correct or delete it.")
        else:
            parts.append(f"The date reported for{cred_ref_the} is disputed. Provide original documentation verifying this date or delete it.")

    else:
        parts.append(f"The information reported for{cred_ref_the} is disputed. I demand that you obtain actual verification from the furnisher — not an automated confirmation — and provide me with the method of verification used. If it cannot be verified, delete it under 15 U.S.C. § 1681i(a)(5)(A).")

    if strategy_note:
        cleaned_note = strategy_note.strip()
        if cleaned_note and not cleaned_note.endswith('.'):
            cleaned_note += '.'
        if cleaned_note:
            parts.append(cleaned_note)

    return " ".join(parts)


def _get_fcra_sections_for_claim(claim: 'Claim') -> List[str]:
    from claims import ClaimType

    claim_type_val = claim.claim_type.value if hasattr(claim.claim_type, 'value') else str(claim.claim_type)
    dispute_type_key = CLAIM_TYPE_TO_DISPUTE_TYPE.get(claim_type_val, "")

    if dispute_type_key:
        dtype = DISPUTE_TYPES.get(dispute_type_key)
        if dtype:
            sections = list(dtype.get("fcra_sections", []))
            for supp_key in dtype.get("supplemental_law", []):
                sections.append(supp_key)
            return sections

    fcra_map = {
        ClaimType.ACCOUNT_PRESENT: ["1681i_a", "1681i_a_5", "1681s_2_b"],
        ClaimType.BALANCE_REPORTED: ["1681e_b", "1681i_a", "1681s_2_a", "tila_1666"],
        ClaimType.STATUS_REPORTED: ["1681e_b", "1681i_a", "1681s_2_a"],
        ClaimType.LATE_PAYMENT_REPORTED: ["1681e_b", "1681i_a", "1681s_2_a", "tila_1666", "tila_1666a"],
        ClaimType.INQUIRY_PRESENT: ["1681b"],
        ClaimType.PERSONAL_INFO_PRESENT: ["1681e_b", "1681i_a", "1681g"],
        ClaimType.ADDRESS_LISTED: ["1681e_b", "1681i_a", "1681g"],
        ClaimType.DUPLICATE_DETECTED: ["1681e_b", "1681i_a"],
        ClaimType.DATE_REPORTED: ["1681c_a"],
    }

    return fcra_map.get(claim.claim_type, ["1681i_a"])


def _get_requested_action_for_claim(claim: 'Claim', creditor_name: str = '', balance_str: str = '') -> str:
    from claims import ClaimType

    cred_ref = f" ({creditor_name})" if creditor_name else ""

    actions = {
        ClaimType.ACCOUNT_PRESENT: f"Provide: (1) the original signed contract or application for this account{cred_ref}, (2) complete payment history from account opening to present, (3) the business name, address, and telephone number of the furnisher contacted during your investigation per 15 U.S.C. § 1681i(a)(6)(B)(iii), and (4) a description of the procedure used to verify this account per 15 U.S.C. § 1681i(a)(7). If any of these cannot be produced, delete this account from my file under 15 U.S.C. § 1681i(a)(5)(A).",
        ClaimType.BALANCE_REPORTED: f"Provide: (1) a certified account ledger from the furnisher showing how the balance{' of ' + balance_str if balance_str else ''} was calculated for this account{cred_ref}, (2) the last billing statement sent to me, (3) the business name, address, and telephone number of the furnisher contacted per 15 U.S.C. § 1681i(a)(6)(B)(iii), and (4) proof this data was reported in Metro 2 compliance. If the furnisher cannot produce these records, correct or delete this balance.",
        ClaimType.STATUS_REPORTED: f"Provide: (1) the furnisher's complete account records substantiating this status for this account{cred_ref}, (2) copies of any required notices sent to me before this status was reported, (3) the method of verification used, and (4) proof the furnisher conducted a genuine investigation under 15 U.S.C. § 1681s-2(b) — not an automated re-confirmation. If these cannot be produced, correct or delete this status.",
        ClaimType.LATE_PAYMENT_REPORTED: f"Provide: (1) the original payment records showing the due date, date my payment was received, and applicable grace period for this account{cred_ref}, (2) proof that any required notice was sent before reporting this delinquency, and (3) the method of verification used. Note that reporting a delinquency during a pending billing dispute may implicate 15 U.S.C. § 1666(a). Produce records or delete this notation.",
        ClaimType.INQUIRY_PRESENT: f"Provide: (1) written documentation of the permissible purpose under 15 U.S.C. § 1681b(a) for this inquiry{cred_ref}, and (2) proof of my written authorization or consent. If neither can be produced, remove this inquiry from my report immediately.",
        ClaimType.PERSONAL_INFO_PRESENT: "Provide the source of this personal information and correct or remove it so my file accurately identifies me per 15 U.S.C. § 1681e(b).",
        ClaimType.ADDRESS_LISTED: "Disclose the source of this address under 15 U.S.C. § 1681g and remove it from my file. This address is not associated with me.",
        ClaimType.DUPLICATE_DETECTED: f"Compare your records for this account{cred_ref} and delete the duplicate entry. Reporting the same obligation twice inflates my reported debt and raises accuracy concerns under 15 U.S.C. § 1681e(b).",
        ClaimType.DATE_REPORTED: f"Provide: (1) the furnisher's original records establishing the date of first delinquency for this account{cred_ref}, and (2) proof this date has not been re-aged, as re-aging is prohibited under 15 U.S.C. § 1681c(a). If this adverse information has exceeded the seven-year reporting period, delete it.",
    }

    return actions.get(claim.claim_type, "Provide the method of verification used and original documentation from the furnisher. If this item cannot be independently verified, delete it under 15 U.S.C. § 1681i(a)(5)(A).")


def _build_closing(consumer_name: str, item_count: int, has_account_disputes: bool = False) -> str:
    item_word = "item" if item_count == 1 else "items"

    enclosures = ["Copy of government-issued photo identification"]
    if has_account_disputes:
        enclosures.append("Copy of credit report page(s) with disputed items marked")
    enclosures.append("Proof of current address (utility bill or bank statement)")

    enclosure_lines = "\n".join(f"  - {e}" for e in enclosures)

    return f"""You have 30 days from receipt of this letter to complete your reinvestigation as required by 15 U.S.C. § 1681i(a)(1)(A). Upon completion, provide me with:
1. Written notice of the results of your reinvestigation for each disputed {item_word}
2. The specific method of verification used for each item, including the business name, address, and telephone number of any furnisher contacted, as required by 15 U.S.C. § 1681i(a)(6)(B)(iii) and § 1681i(a)(7)
3. A revised copy of my credit report reflecting any corrections
4. A description of the procedure used to determine accuracy and completeness

I also demand, under 15 U.S.C. § 1681g, disclosure of all information in my consumer file related to the disputed {item_word}, including the sources of that information. Be advised that under 15 U.S.C. § 1681i(a)(5)(A), any information that cannot be verified through a reasonable reinvestigation is subject to prompt deletion or modification. A reasonable reinvestigation requires more than matching the disputed data against the furnisher's own records — it requires independent verification (see Cushman v. Trans Union Corp., 115 F.3d 220 (3d Cir. 1997)).

I am also aware that under Regulation V (12 CFR § 1022.42), furnishers have a duty to conduct a reasonable investigation and report only information they have determined to be accurate. Failure to comply with the FCRA may result in liability for actual damages, statutory damages of $100 to $1,000 per violation under 15 U.S.C. § 1681n, and attorney's fees.

I am preserving all of my rights under federal and state law.

Sincerely,

_______________________________
{consumer_name}

Enclosures:
{enclosure_lines}
"""


def format_letter_filename(bureau: str) -> str:
    date_str = datetime.now().strftime("%Y%m%d")
    return f"dispute_letter_{bureau}_{date_str}"


def generate_letter_pdf(letter_text: str, signature_image: bytes = None, proof_documents: list = None) -> bytes:
    from reportlab.lib.pagesizes import letter as letter_size
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader

    sig_reader = None
    if signature_image:
        try:
            sig_reader = ImageReader(BytesIO(signature_image))
        except Exception:
            sig_reader = None

    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter_size)
    page_width, page_height = letter_size
    left_margin = 1.0 * inch
    right_margin = 1.0 * inch
    top_margin = 1.0 * inch
    bottom_margin = 1.0 * inch
    usable_width = page_width - left_margin - right_margin

    font_name = "Times-Roman"
    bold_font = "Times-Bold"
    font_size = 11
    line_height = 16
    header_font_size = 12
    header_line_height = 18
    max_chars = int(usable_width / 6.0)

    y = page_height - top_margin

    def new_page():
        nonlocal y
        c.showPage()
        y = page_height - top_margin

    def draw_line(text, bold=False, font_sz=font_size, leading=line_height):
        nonlocal y
        if y < bottom_margin + leading:
            new_page()
        fn = bold_font if bold else font_name
        c.setFont(fn, font_sz)
        c.drawString(left_margin, y, text)
        y -= leading

    lines = letter_text.split('\n')

    bold_patterns = [
        'DISPUTED ITEM #',
        'Re: Formal Dispute',
        'Subject: Reinvestigation',
        'Dispute:',
        'I demand:',
        'Applicable law:',
        'See also:',
        'For identification purposes:',
        'Enclosures:',
        'Provide:',
        'Concern:',
        'Request:',
    ]

    for line in lines:
        stripped = line.strip()

        if not stripped:
            y -= line_height * 0.3
            if y < bottom_margin:
                new_page()
            continue

        is_disputed_item = stripped.startswith('DISPUTED ITEM #') or re.match(r'^#\d+\)', stripped)
        is_bold_label = any(stripped.startswith(p) for p in bold_patterns)

        if is_disputed_item:
            if y < bottom_margin + header_line_height * 2:
                new_page()
            is_round2_header = stripped.startswith('DISPUTED ITEM #')
            if is_round2_header:
                y -= 6
                c.setStrokeColorRGB(0.7, 0.7, 0.7)
                c.line(left_margin, y + header_line_height - 2, page_width - right_margin, y + header_line_height - 2)
                y -= 2
            else:
                y -= 3
            draw_line(stripped, bold=True, font_sz=header_font_size, leading=header_line_height)
            continue

        if is_bold_label:
            colon_pos = stripped.find(':')
            if colon_pos > 0 and colon_pos < len(stripped) - 1:
                label_part = stripped[:colon_pos + 1]
                rest_part = stripped[colon_pos + 1:].strip()

                if len(stripped) > max_chars:
                    draw_line(label_part, bold=True)
                    wrapped = textwrap.wrap(rest_part, width=max_chars - 4)
                    for wline in wrapped:
                        draw_line("    " + wline)
                else:
                    if y < bottom_margin + line_height:
                        new_page()
                    c.setFont(bold_font, font_size)
                    label_width = c.stringWidth(label_part, bold_font, font_size)
                    c.drawString(left_margin, y, label_part)
                    c.setFont(font_name, font_size)
                    c.drawString(left_margin + label_width + 3, y, " " + rest_part)
                    y -= line_height
                continue
            elif stripped.endswith(':'):
                draw_line(stripped, bold=True)
                continue

        if sig_reader and re.match(r'^_{10,}$', stripped):
            sig_w = 2.0 * inch
            sig_h = 0.6 * inch
            if y < bottom_margin + sig_h + line_height:
                new_page()
            y -= sig_h
            c.drawImage(sig_reader, left_margin, y, width=sig_w, height=sig_h, preserveAspectRatio=True, mask='auto')
            y -= 4
            continue

        if re.match(r'^\d+\.', stripped):
            if len(stripped) > max_chars:
                wrapped = textwrap.wrap(stripped, width=max_chars - 4)
                for i, wline in enumerate(wrapped):
                    prefix = "    " if i > 0 else ""
                    draw_line(prefix + wline)
            else:
                draw_line("  " + stripped)
            continue

        if stripped.startswith('- ') or stripped.startswith('  -'):
            clean = stripped.lstrip(' -').strip()
            draw_line("    - " + clean)
            continue

        if len(stripped) > max_chars:
            wrapped = textwrap.wrap(stripped, width=max_chars)
            for i, wline in enumerate(wrapped):
                draw_line(wline)
        else:
            draw_line(stripped)

    if proof_documents:
        def _draw_proof_page(img_bytes, label_text):
            try:
                doc_reader = ImageReader(BytesIO(img_bytes))
                c.showPage()
                c.setFont("Helvetica-Bold", 14)
                c.drawString(left_margin, page_height - top_margin, f"Enclosure: {label_text}")
                c.setFont("Helvetica", 10)
                c.drawString(left_margin, page_height - top_margin - 18, "Attached as supporting documentation for this dispute letter.")
                iw, ih = doc_reader.getSize()
                max_w = page_width - left_margin - right_margin
                max_h = page_height - top_margin - bottom_margin - 50
                scale = min(max_w / iw, max_h / ih, 1.0)
                draw_w = iw * scale
                draw_h = ih * scale
                x = left_margin + (max_w - draw_w) / 2
                y = page_height - top_margin - 50 - draw_h
                c.drawImage(doc_reader, x, y, width=draw_w, height=draw_h, preserveAspectRatio=True, mask='auto')
            except Exception:
                pass

        for doc in proof_documents:
            raw = doc.get('data')
            if not raw:
                continue
            label = doc.get('label', 'Enclosure')
            if raw[:5] == b'%PDF-':
                try:
                    from pdf2image import convert_from_bytes
                    pages = convert_from_bytes(raw, dpi=200, fmt='png')
                    for pi, page_img in enumerate(pages):
                        img_buf = BytesIO()
                        page_img.save(img_buf, format='PNG')
                        pg_label = f"{label} (page {pi + 1})" if len(pages) > 1 else label
                        _draw_proof_page(img_buf.getvalue(), pg_label)
                except Exception:
                    pass
            else:
                _draw_proof_page(raw, label)

    c.save()
    return pdf_buffer.getvalue()


ROUND1_BANNED_TERMS = [
    "e-OSCAR", "e-oscar", "eOSCAR",
    "Metro 2", "metro 2", "Metro-2",
    "signed agreement", "signed application", "signed contract",
    "original application", "original signed",
    "statutory damages",
    "$100", "$1,000", "$1000",
    "names of each person who verified",
    "name, address, and telephone number of any person",
    "name, address, and phone number",
    "failure to respond in 30 days",
    "Cushman v. Trans Union",
    "Regulation V",
    "12 CFR",
    "attorney's fees",
    "litigation",
    "lawsuit",
]

ROUND1_BANNED_WORD_REGEX = [
    re.compile(r'\bsue\b', re.IGNORECASE),
    re.compile(r'\bcourt\b', re.IGNORECASE),
]

ROUND1_BANNED_REGEX = [
    re.compile(r'statutory\s+damages', re.IGNORECASE),
    re.compile(r'\$1[,.]?000', re.IGNORECASE),
    re.compile(r'\$100\b', re.IGNORECASE),
    re.compile(r'failure\s+to\s+respond\s+in\s+30\s+days', re.IGNORECASE),
    re.compile(r'verifier.{0,10}(name|phone|address)', re.IGNORECASE),
    re.compile(r'person\s+who\s+verified', re.IGNORECASE),
]

ROUND1_OPENINGS = [
    "I am disputing specific information on my {bureau} credit file. The items below appear inaccurate, incomplete, or cannot be verified as accurate and complete. Please reinvestigate and correct or delete any information that cannot be verified as accurate and complete.",
    "This letter is a request for reinvestigation of the items listed below on my {bureau} report. The reporting appears inaccurate and/or incomplete. Please conduct a reinvestigation and update or delete any item that cannot be verified as accurate and complete.",
    "I am requesting a reinvestigation of the accounts listed below. I am disputing the accuracy and completeness of the reporting. If the information cannot be verified as accurate and complete, please delete it.",
]


def round1_banned_terms_check(letter_text: str) -> bool:
    for term in ROUND1_BANNED_TERMS:
        if term in letter_text:
            return False
    for pattern in ROUND1_BANNED_REGEX:
        if pattern.search(letter_text):
            return False
    for pattern in ROUND1_BANNED_WORD_REGEX:
        if pattern.search(letter_text):
            return False
    return True


def build_round1_concerns(item: Dict[str, Any]) -> List[str]:
    concerns = []
    fields = item.get('fields', {})
    entities = item.get('entities', {})
    claim_type = item.get('claim_type', '')
    review_type = item.get('review_type', '')

    merged = {}
    merged.update(fields)
    merged.update(entities)

    balance = _safe_str(merged.get('balance', ''))
    status = _safe_str(merged.get('status', ''))
    opened_date = _safe_str(merged.get('opened_date', '') or merged.get('date_opened', '') or merged.get('date', ''))
    date_reported = _safe_str(merged.get('date_reported', '') or merged.get('date_updated', ''))
    date_closed = _safe_str(merged.get('date_closed', ''))
    dofd = _safe_str(
        merged.get('date_first_delinquency', '')
        or merged.get('first_delinquency', '')
        or merged.get('date_of_first_delinquency', '')
    )
    payment_history = _safe_str(merged.get('payment_history', '') or merged.get('payment_pattern', ''))
    creditor = _safe_str(merged.get('creditor', '') or merged.get('account_name', '') or merged.get('furnisher', ''))
    account_ref = _safe_str(merged.get('account_mask', '') or merged.get('account', '') or merged.get('account_reference', '') or merged.get('last4', ''))

    has_structured = bool(balance or status or opened_date or dofd or payment_history or date_reported or date_closed)

    def _parse_date(d):
        from datetime import datetime as _dt
        for fmt in ('%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d', '%m-%d-%Y', '%b %d, %Y'):
            try:
                return _dt.strptime(d.strip(), fmt)
            except (ValueError, AttributeError):
                continue
        return None

    if has_structured:
        if not _is_valid(dofd) and claim_type in ('date_reported', 'account_present', 'negative_impact', ''):
            concerns.append("Key delinquency/date fields appear incomplete or not shown, making accuracy difficult to confirm.")

        if _is_valid(dofd):
            dofd_dt = _parse_date(dofd)
            if dofd_dt:
                from datetime import datetime as _dt
                age_days = (_dt.now() - dofd_dt).days
                if age_days > (7 * 365):
                    concerns.append(f"The date of first delinquency ({dofd}) exceeds the 7-year reporting window; this item may be obsolete under 15 U.S.C. § 1681c(a).")
                elif age_days > (6 * 365):
                    concerns.append(f"The date of first delinquency ({dofd}) is nearing the 7-year reporting limit; its continued inclusion should be verified for timeliness.")

        if _is_valid(date_closed) and _is_valid(date_reported):
            closed_dt = _parse_date(date_closed)
            reported_dt = _parse_date(date_reported)
            if closed_dt and reported_dt and reported_dt > closed_dt:
                diff_days = (reported_dt - closed_dt).days
                if diff_days > 90:
                    concerns.append("The account was closed but continues to show reporting activity well after the closure date, raising accuracy questions.")

        if _is_valid(balance) and _is_valid(status):
            status_lower = status.lower()
            closed_indicators = ['closed', 'paid', 'transferred', 'sold']
            if any(ci in status_lower for ci in closed_indicators):
                bal_clean = balance.replace('$', '').replace(',', '').strip()
                try:
                    if float(bal_clean) > 0:
                        concerns.append("The balance/amounts being reported appear inconsistent with the account status shown.")
                except (ValueError, TypeError):
                    pass

        if _is_valid(status):
            status_lower = status.lower()
            if any(ci in status_lower for ci in ['closed', 'paid']):
                if _is_valid(opened_date) and _is_valid(date_reported):
                    concerns.append("The account appears closed, yet reporting updates suggest ongoing activity; the accuracy/completeness is unclear.")

        if not _is_valid(payment_history) and claim_type in ('late_payment_reported', 'negative_impact', ''):
            concerns.append("The payment history appears incomplete/unclear for the reported timeframe.")

        if review_type == 'duplicate_account' or claim_type == 'duplicate_detected':
            concerns.append("This item appears duplicated or overlapping with similar reporting, creating potential inaccuracy.")

        if review_type == 'identity_verification' or claim_type in ('personal_info_present', 'address_listed'):
            concerns.append("The association of this account to my file is unclear based on the identifying information shown.")

        if review_type == 'account_ownership' or claim_type == 'account_present':
            if not concerns:
                concerns.append("The account details shown appear incomplete, and I am disputing the accuracy and completeness of the reporting.")

        if _is_valid(balance) and not concerns:
            concerns.append("The balance/amounts being reported cannot be confirmed as accurate and complete based on the information shown.")

        if _is_valid(status) and not concerns:
            concerns.append("The status and amounts being reported are unclear from the report presentation, and I cannot confirm they are accurate and complete.")

    if not concerns:
        generic_concerns = [
            "The reporting lacks sufficient detail to confirm accuracy and completeness (e.g., key dates/amounts/status fields are unclear).",
            "The status and amounts being reported are unclear from the report presentation, and I cannot confirm they are accurate and complete.",
            "The account details shown appear incomplete, and I am disputing the accuracy and completeness of the reporting.",
        ]
        if review_type == 'identity_verification' or claim_type in ('personal_info_present', 'address_listed'):
            concerns.append("The association of this information to my file is unclear based on the identifying information shown.")
        elif review_type == 'account_ownership':
            concerns.append(generic_concerns[2])
        else:
            concerns.append(generic_concerns[0])
            if claim_type in ('balance_reported', 'status_reported', 'late_payment_reported'):
                concerns.append(generic_concerns[1])

    return concerns[:3]


def generate_round1_letter(
    bureau: str,
    user_profile: Dict[str, Any],
    selected_items: List[Dict[str, Any]],
    voice_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    bureau_info = get_bureau_address(bureau)

    consumer_name = _safe_str(user_profile.get('name', ''))
    if not consumer_name or len(consumer_name) < 2:
        consumer_name = '[Your Full Name]'

    consumer_address = _safe_str(user_profile.get('address', ''))
    addr_invalid_patterns = ['id address', 'not provided', 'n/a', 'unknown']
    if (not consumer_address or len(consumer_address) < 5
            or any(p in consumer_address.lower() for p in addr_invalid_patterns)):
        consumer_address = '[Your Address]'

    ssn_raw = user_profile.get('ssn', '') or user_profile.get('ssn_last_four', '') or user_profile.get('ssn_last4', '')
    ssn_last_four = _format_ssn_last_four(_safe_str(ssn_raw))

    dob_raw = user_profile.get('dob', '') or user_profile.get('date_of_birth', '')
    dob_str = _safe_str(dob_raw)
    if dob_str and dob_str.lower() in ('unknown', 'n/a', 'not_found', 'none'):
        dob_str = ''

    confirmation_number = _safe_str(user_profile.get('confirmation_number', '')
                                     or user_profile.get('report_number', '')
                                     or user_profile.get('file_number', ''))
    if confirmation_number and confirmation_number.lower() in ('unknown', 'n/a', 'none'):
        confirmation_number = ''

    date_str = datetime.now().strftime("%B %d, %Y")
    bureau_display = bureau_info['name']

    opening = random.choice(ROUND1_OPENINGS).format(bureau=bureau_display)
    if voice_profile:
        opening = _apply_voice_to_opening(opening, voice_profile)

    letter = f"""{consumer_name}
{consumer_address}

{date_str}

{bureau_info['name']}
{bureau_info['address']}
{bureau_info['city_state_zip']}

Subject: Reinvestigation Request (FCRA §611)

To Whom It May Concern:

"""

    id_lines = []
    if ssn_last_four:
        id_lines.append(f"SSN (last four): XXX-XX-{ssn_last_four}")
    if dob_str:
        id_lines.append(f"Date of Birth: {dob_str}")
    if confirmation_number:
        id_lines.append(f"Report/File Number: {confirmation_number}")

    if id_lines:
        letter += "For identification purposes:\n"
        for id_line in id_lines:
            letter += f"  {id_line}\n"
        letter += "\n"

    letter += f"{opening}\n\n"

    for idx, item in enumerate(selected_items, 1):
        letter += _build_round1_item_block(idx, item)
    letter += "\n"

    letter += _build_round1_closing(consumer_name)

    if not round1_banned_terms_check(letter):
        raise ValueError("Round 1 letter contains banned terms — generation blocked.")

    has_concern = "Concern:" in letter
    has_reinvestigate = "reinvestigate" in letter.lower()
    has_accurate_complete = "accurate and complete" in letter.lower()
    has_method = "method used to verify" in letter.lower() or "method of verification" in letter.lower() or "verification procedures" in letter.lower() or "how this was verified" in letter.lower()
    if not (has_concern and has_reinvestigate and has_accurate_complete and has_method):
        missing = []
        if not has_concern:
            missing.append("Concern:")
        if not has_reinvestigate:
            missing.append("reinvestigate")
        if not has_accurate_complete:
            missing.append("accurate and complete")
        if not has_method:
            missing.append("method used to verify")
        raise ValueError(f"Round 1 letter missing required elements: {', '.join(missing)}")

    if voice_profile:
        letter = apply_voice_profile(letter, consumer_name, voice_profile)

    return {
        'bureau': bureau,
        'letter_text': letter,
        'claim_count': len(selected_items),
        'categories': list(set(item.get('claim_type', 'unknown') for item in selected_items)),
        'round': 1,
        'voice_profile_snapshot': voice_profile,
    }


def _build_round1_item_block(idx: int, item: Dict[str, Any]) -> str:
    entities = item.get('entities', {})
    fields = item.get('fields', {})
    merged = {}
    merged.update(fields)
    merged.update(entities)

    furnisher = _safe_str(
        merged.get('creditor', '') or merged.get('account_name', '')
        or merged.get('furnisher', '') or merged.get('inquirer', '')
    )
    if not furnisher or not _is_valid(furnisher, 2):
        furnisher = "Unknown Furnisher"

    account_ref = _safe_str(
        merged.get('account_mask', '') or merged.get('account', '')
        or merged.get('account_reference', '') or merged.get('last4', '')
        or merged.get('account_number', '')
    )
    account_label = _build_account_label(account_ref)

    header = f"#{idx}) {furnisher}"
    if account_label:
        header += f" — {account_label}"

    block = f"{header}\n"

    date_opened = _safe_str(merged.get('date_opened', '') or merged.get('opened_date', ''))
    date_reported = _safe_str(merged.get('date_reported', '') or merged.get('date_updated', ''))
    date_closed = _safe_str(merged.get('date_closed', ''))
    dofd = _safe_str(
        merged.get('date_first_delinquency', '') or merged.get('first_delinquency', '')
        or merged.get('date_of_first_delinquency', '')
    )

    date_parts = []
    if _is_valid(date_opened):
        date_parts.append(f"Date Opened: {date_opened}")
    if _is_valid(date_reported):
        date_parts.append(f"Date Reported: {date_reported}")
    if _is_valid(date_closed):
        date_parts.append(f"Date Closed: {date_closed}")
    if _is_valid(dofd):
        date_parts.append(f"Date of First Delinquency: {dofd}")
    if date_parts:
        block += f"  {' | '.join(date_parts)}\n"

    concerns = build_round1_concerns(item)
    for concern in concerns:
        block += f"  - Concern: {concern}\n"

    return block


def _build_round1_closing(consumer_name: str) -> str:
    return f"""
For each item listed above, please reinvestigate the reporting and confirm that it is accurate and complete. If any item cannot be verified as accurate and complete, please delete it from my file. For each item you verify, please provide a description of the method used to verify the information.

Please send me an updated copy of my credit report upon completion of the reinvestigation. Thank you.

Sincerely,

_______________________________
{consumer_name}

Enclosures:
  - Copy of government-issued photo identification
  - Proof of current address (utility bill or bank statement)
"""


ROUND2_OPENINGS = [
    "I previously submitted a dispute regarding my {bureau} credit file. The items below were either not corrected, not adequately investigated, or remain inaccurate after your reinvestigation. Under 15 U.S.C. § 1681i(a), I am demanding a new reinvestigation — and this time, I am requiring that you provide the specific method of verification used for each item, including the business name, address, and telephone number of any person contacted, as required by 15 U.S.C. § 1681i(a)(6)(B)(iii) and § 1681i(a)(7).",
    "This is a follow-up dispute regarding items on my {bureau} report that were previously disputed but remain unresolved. Your prior reinvestigation did not result in the correction or deletion of the inaccurate information listed below. I am now exercising my rights under 15 U.S.C. § 1681i(a) to demand a genuine reinvestigation — not a cursory review or automated re-confirmation of the furnisher's original data. For each item, I require the method of verification used, per 15 U.S.C. § 1681i(a)(7).",
    "I am writing again regarding disputed items on my {bureau} credit report. My previous dispute did not result in the corrections required by law. Under 15 U.S.C. § 1681i(a), you must conduct a reasonable reinvestigation — which means contacting the furnisher directly and obtaining original documentation, not simply re-confirming what was already reported via e-OSCAR. I demand the method of verification for each item below as required by 15 U.S.C. § 1681i(a)(7).",
]


def build_round2_demands(item: Dict[str, Any]) -> List[str]:
    demands = []
    fields = item.get('fields', {})
    entities = item.get('entities', {})
    claim_type = item.get('claim_type', '')
    review_type = item.get('review_type', '')

    merged = {}
    merged.update(fields)
    merged.update(entities)

    creditor = _safe_str(merged.get('creditor', '') or merged.get('account_name', '') or merged.get('furnisher', ''))
    balance = _safe_str(merged.get('balance', ''))
    status = _safe_str(merged.get('status', ''))

    if claim_type in ('account_present',) or review_type == 'account_ownership':
        demands.append("Provide the original signed contract or credit application bearing my signature, or delete this account.")
        demands.append("Identify the furnisher contacted and the method of verification used per 15 U.S.C. § 1681i(a)(7).")

    elif claim_type in ('balance_reported',):
        demands.append("Provide a certified account ledger from the original creditor showing how this balance was calculated.")
        if balance:
            demands.append(f"The balance of {balance} has not been verified with original documentation — an e-OSCAR confirmation is not sufficient under Cushman v. Trans Union Corp.")

    elif claim_type in ('status_reported',):
        demands.append("Provide the furnisher's complete account records substantiating this status, not an automated re-confirmation.")
        if status:
            demands.append(f"The status \"{status}\" was not corrected after my prior dispute. Demand the furnisher conduct a genuine investigation under 15 U.S.C. § 1681s-2(b).")

    elif claim_type in ('late_payment_reported',):
        demands.append("Provide original payment records showing the exact due date, date payment was received, and grace period terms.")
        demands.append("If the furnisher cannot produce these records, this late-payment notation must be deleted under 15 U.S.C. § 1681i(a)(5)(A).")

    elif claim_type in ('inquiry_present',):
        demands.append("Provide written proof of the permissible purpose under 15 U.S.C. § 1681b(a) and my authorization for this inquiry.")
        demands.append("An inquiry without permissible purpose violates the FCRA and must be removed immediately.")

    elif claim_type in ('duplicate_detected',) or review_type == 'duplicate_account':
        demands.append("This item appears to be a duplicate of another entry. Compare your records and delete the redundant reporting.")
        demands.append("Duplicate reporting inflates my obligations and violates the accuracy requirements of 15 U.S.C. § 1681e(b).")

    elif claim_type in ('date_reported',):
        demands.append("Provide the furnisher's original records establishing the date of first delinquency.")
        demands.append("If this date has been re-aged or is incorrect, the account may have exceeded the 7-year reporting period under 15 U.S.C. § 1681c(a) and must be removed.")

    elif claim_type in ('personal_info_present', 'address_listed') or review_type == 'identity_verification':
        demands.append("Disclose the source of this information under 15 U.S.C. § 1681g and correct or remove it.")

    if not demands:
        demands.append("This item was previously disputed and not corrected. Provide the method of verification used and original documentation from the furnisher.")
        demands.append("If the furnisher cannot produce original records verifying this information, delete it under 15 U.S.C. § 1681i(a)(5)(A).")

    return demands[:3]


def _build_round2_item_block(idx: int, item: Dict[str, Any]) -> str:
    entities = item.get('entities', {})
    fields = item.get('fields', {})
    merged = {}
    merged.update(fields)
    merged.update(entities)

    furnisher = _safe_str(
        merged.get('creditor', '') or merged.get('account_name', '')
        or merged.get('furnisher', '') or merged.get('inquirer', '')
    )
    if not furnisher or not _is_valid(furnisher, 2):
        furnisher = "Unknown Furnisher"

    account_ref = _safe_str(
        merged.get('account_mask', '') or merged.get('account', '')
        or merged.get('account_reference', '') or merged.get('last4', '')
        or merged.get('account_number', '')
    )
    account_label = _build_account_label(account_ref)

    header = f"DISPUTED ITEM #{idx}: {furnisher}"
    if account_label:
        header += f" — {account_label}"

    block = f"{header}\n"

    balance = _safe_str(merged.get('balance', ''))
    status = _safe_str(merged.get('status', ''))
    if balance and _is_valid(balance):
        block += f"  Balance Reported: {balance}\n"
    if status and _is_valid(status):
        block += f"  Status Reported: {status}\n"

    date_opened = _safe_str(merged.get('date_opened', '') or merged.get('opened_date', ''))
    date_reported = _safe_str(merged.get('date_reported', '') or merged.get('date_updated', ''))
    date_closed = _safe_str(merged.get('date_closed', ''))
    dofd = _safe_str(
        merged.get('date_first_delinquency', '') or merged.get('first_delinquency', '')
        or merged.get('date_of_first_delinquency', '')
    )

    date_parts = []
    if _is_valid(date_opened):
        date_parts.append(f"Date Opened: {date_opened}")
    if _is_valid(date_reported):
        date_parts.append(f"Date Reported: {date_reported}")
    if _is_valid(date_closed):
        date_parts.append(f"Date Closed: {date_closed}")
    if _is_valid(dofd):
        date_parts.append(f"Date of First Delinquency: {dofd}")
    if date_parts:
        block += f"  {' | '.join(date_parts)}\n"

    demands = build_round2_demands(item)
    for demand in demands:
        block += f"  - Demand: {demand}\n"

    block += f"  - Required: Provide the business name, address, and telephone number of the furnisher contacted, and a description of the method used to verify this information per 15 U.S.C. § 1681i(a)(6)(B)(iii) and § 1681i(a)(7).\n"

    block += "\n"
    return block


def _build_round2_closing(consumer_name: str, item_count: int) -> str:
    item_word = "item" if item_count == 1 else "items"

    return f"""
You have 30 days from receipt of this letter to complete your reinvestigation as required by 15 U.S.C. § 1681i(a)(1)(A). Be advised that a "reinvestigation" requires more than matching disputed data against the furnisher's own previously reported records — it requires independent verification from original source documents (see Cushman v. Trans Union Corp., 115 F.3d 220 (3d Cir. 1997)).

Upon completion, provide me with:
1. Written notice of the results for each disputed {item_word}
2. The specific method of verification used, including the business name, address, and telephone number of each furnisher contacted, as required by 15 U.S.C. § 1681i(a)(6)(B)(iii) and § 1681i(a)(7)
3. A revised copy of my credit report reflecting any corrections
4. Copies of any documents the furnisher provided during the reinvestigation

I am also aware that under Regulation V (12 CFR § 1022.42), furnishers have a duty to conduct a reasonable investigation and report only information they have determined to be accurate. Failure to comply with the FCRA may result in liability for actual damages, statutory damages of $100 to $1,000 per violation under 15 U.S.C. § 1681n, and attorney's fees.

This is my second request regarding these {item_word}. I am preserving all of my rights under federal and state law and will take appropriate action if this matter is not resolved.

Sincerely,

_______________________________
{consumer_name}

Enclosures:
  - Copy of government-issued photo identification
  - Proof of current address (utility bill or bank statement)
  - Copy of previous dispute letter and/or confirmation number
  - Copy of credit report page(s) with disputed items marked
"""


def generate_round2_letter(
    bureau: str,
    user_profile: Dict[str, Any],
    selected_items: List[Dict[str, Any]],
    round_number: int = 2,
    voice_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    bureau_info = get_bureau_address(bureau)

    consumer_name = _safe_str(user_profile.get('name', ''))
    if not consumer_name or len(consumer_name) < 2:
        consumer_name = '[Your Full Name]'

    consumer_address = _safe_str(user_profile.get('address', ''))
    addr_invalid_patterns = ['id address', 'not provided', 'n/a', 'unknown']
    if (not consumer_address or len(consumer_address) < 5
            or any(p in consumer_address.lower() for p in addr_invalid_patterns)):
        consumer_address = '[Your Address]'

    ssn_raw = user_profile.get('ssn', '') or user_profile.get('ssn_last_four', '') or user_profile.get('ssn_last4', '')
    ssn_last_four = _format_ssn_last_four(_safe_str(ssn_raw))

    dob_raw = user_profile.get('dob', '') or user_profile.get('date_of_birth', '')
    dob_str = _safe_str(dob_raw)
    if dob_str and dob_str.lower() in ('unknown', 'n/a', 'not_found', 'none'):
        dob_str = ''

    confirmation_number = _safe_str(user_profile.get('confirmation_number', '')
                                     or user_profile.get('report_number', '')
                                     or user_profile.get('file_number', ''))
    if confirmation_number and confirmation_number.lower() in ('unknown', 'n/a', 'none'):
        confirmation_number = ''

    date_str = datetime.now().strftime("%B %d, %Y")
    bureau_display = bureau_info['name']

    opening = random.choice(ROUND2_OPENINGS).format(bureau=bureau_display)

    round_label = f"Round {round_number} " if round_number > 2 else ""

    letter = f"""{consumer_name}
{consumer_address}

{date_str}

{bureau_info['name']}
{bureau_info['address']}
{bureau_info['city_state_zip']}

Subject: {round_label}Follow-Up Dispute — Demand for Verification and Method of Investigation (FCRA §611)

To Whom It May Concern:

"""

    id_lines = []
    if ssn_last_four:
        id_lines.append(f"SSN (last four): XXX-XX-{ssn_last_four}")
    if dob_str:
        id_lines.append(f"Date of Birth: {dob_str}")
    if confirmation_number:
        id_lines.append(f"Report/File Number: {confirmation_number}")

    if id_lines:
        letter += "For identification purposes:\n"
        for id_line in id_lines:
            letter += f"  {id_line}\n"
        letter += "\n"

    letter += f"{opening}\n\n"

    for idx, item in enumerate(selected_items, 1):
        letter += _build_round2_item_block(idx, item)

    letter += _build_round2_closing(consumer_name, len(selected_items))

    if voice_profile:
        letter = apply_voice_profile(letter, consumer_name, voice_profile)

    return {
        'bureau': bureau,
        'letter_text': letter,
        'claim_count': len(selected_items),
        'categories': list(set(item.get('claim_type', 'unknown') for item in selected_items)),
        'round': round_number,
        'voice_profile_snapshot': voice_profile,
    }
