"""
statutes.py | 850 Lab Parser Machine
Statute definitions and citation text for dispute letters.
Covers FCRA, Dodd-Frank, TILA, and furnisher obligations.
"""

from legal_kb import (
    get_legal_context_for_review_type,
    get_all_statutes,
    FCRA_STATUTES_KB,
    DODD_FRANK_KB,
    TILA_KB,
)

FCRA_STATUTES = {
    "1681e_b": {
        "section": "15 U.S.C. § 1681e(b)",
        "title": "Accuracy of Report",
        "text": "Whenever a consumer reporting agency prepares a consumer report it shall follow reasonable procedures to assure maximum possible accuracy of the information concerning the individual about whom the report relates.",
        "short_citation": "FCRA § 607(b)",
        "dispute_basis": "The information reported does not accurately reflect my records.",
        "applicable_to": ["inaccurate_balance", "duplicate_account", "incorrect_personal_info"]
    },
    "1681i_a": {
        "section": "15 U.S.C. § 1681i(a)",
        "title": "Reinvestigation of Disputed Information",
        "text": "If the completeness or accuracy of any item of information contained in a consumer's file at a consumer reporting agency is disputed by the consumer and the consumer notifies the agency directly, or indirectly through a reseller, of such dispute, the agency shall, free of charge, conduct a reasonable reinvestigation to determine whether the disputed information is inaccurate.",
        "short_citation": "FCRA § 611(a)",
        "dispute_basis": "I am disputing this information and request a reinvestigation.",
        "applicable_to": ["unknown_account", "inaccurate_balance", "duplicate_account", "incorrect_personal_info"]
    },
    "1681i_a_5": {
        "section": "15 U.S.C. § 1681i(a)(5)",
        "title": "Deletion of Unverifiable Information",
        "text": "If, after any reinvestigation under paragraph (1) of any information disputed by a consumer, an item of the information is found to be inaccurate or incomplete or cannot be verified, the consumer reporting agency shall promptly delete that item of information from the file of the consumer, or modify that item of information, as appropriate.",
        "short_citation": "FCRA § 611(a)(5)",
        "dispute_basis": "This information cannot be verified and must be deleted from my file.",
        "applicable_to": ["unverifiable_account", "unknown_account"]
    },
    "1681c_a": {
        "section": "15 U.S.C. § 1681c(a)",
        "title": "Information Excluded from Consumer Reports",
        "text": "Except as authorized under subsection (b), no consumer reporting agency may make any consumer report containing any of the following items of information: (1) Cases under title 11 or under the Bankruptcy Act that, from the date of entry of the order for relief or the date of adjudication, as the case may be, antedate the report by more than 10 years. (2) Civil suits, civil judgments, and records of arrest that, from date of entry, antedate the report by more than seven years or until the governing statute of limitations has expired, whichever is the longer period. (3) Paid tax liens which, from date of payment, antedate the report by more than seven years. (4) Accounts placed for collection or charged to profit and loss which antedate the report by more than seven years. (5) Any other adverse item of information, other than records of convictions of crimes which antedates the report by more than seven years.",
        "short_citation": "FCRA § 605(a)",
        "dispute_basis": "This adverse information has exceeded the maximum reporting period allowed by law.",
        "applicable_to": ["outdated_information"]
    },
    "1681b": {
        "section": "15 U.S.C. § 1681b",
        "title": "Permissible Purposes of Consumer Reports",
        "text": "A consumer reporting agency may furnish a consumer report under the following circumstances and no other: (a) In response to the order of a court having jurisdiction to issue such an order, a subpoena issued in connection with proceedings before a Federal grand jury, or a subpoena issued in accordance with section 5318 of title 31 or section 3486 of title 18. (b) In accordance with the written instructions of the consumer to whom it relates. (c) To a person which it has reason to believe (1) intends to use the information in connection with a credit transaction involving the consumer on whom the information is to be furnished and involving the extension of credit to, or review or collection of an account of, the consumer; or (2) intends to use the information for employment purposes; or (3) intends to use the information in connection with the underwriting of insurance involving the consumer.",
        "short_citation": "FCRA § 604",
        "dispute_basis": "I dispute that I authorized this inquiry and request verification of permissible purpose.",
        "applicable_to": ["unauthorized_inquiry"]
    },
    "1681s_2_a": {
        "section": "15 U.S.C. § 1681s-2(a)",
        "title": "Furnisher Duty to Provide Accurate Information",
        "text": "A person shall not furnish any information relating to a consumer to any consumer reporting agency if the person knows or has reasonable cause to believe that the information is inaccurate.",
        "short_citation": "FCRA § 623(a)",
        "dispute_basis": "The furnisher is reporting information that is inaccurate.",
        "applicable_to": ["inaccurate_balance", "incorrect_status", "incorrect_payment_history"]
    },
    "1681s_2_b": {
        "section": "15 U.S.C. § 1681s-2(b)",
        "title": "Furnisher Duty Upon Notice of Dispute",
        "text": "After receiving notice of a dispute from a CRA, the furnisher shall conduct an investigation, review all relevant information provided by the CRA, report results to the CRA, and if incomplete or inaccurate, report those results to all CRAs to which the information was furnished.",
        "short_citation": "FCRA § 623(b)",
        "dispute_basis": "The furnisher has an obligation to investigate this dispute and correct any inaccurate information.",
        "applicable_to": ["inaccurate_balance", "unknown_account", "incorrect_status"]
    },
    "1681g": {
        "section": "15 U.S.C. § 1681g",
        "title": "Consumer Disclosure Rights",
        "text": "Every consumer reporting agency shall, upon request and proper identification, clearly and accurately disclose to the consumer all information in the consumer's file, the sources of the information, and identification of each person that procured a consumer report.",
        "short_citation": "FCRA § 609",
        "dispute_basis": "I request disclosure of all information in my file, including sources and method of verification.",
        "applicable_to": ["verification_request", "source_disclosure"]
    },
}

SUPPLEMENTAL_STATUTES = {
    "tila_1666": {
        "section": "15 U.S.C. § 1666",
        "title": "Billing Error Resolution (TILA)",
        "text": "After receipt of a billing error notice, the creditor shall not report or threaten to report the consumer as delinquent to any third party, including a consumer reporting agency, until the billing error allegations are resolved.",
        "short_citation": "TILA § 161",
        "dispute_basis": "The creditor reported this amount as delinquent while a billing dispute was pending, in violation of TILA.",
        "applicable_to": ["disputed_billing", "incorrect_payment_history"],
        "law": "TILA",
    },
    "tila_1666a": {
        "section": "15 U.S.C. § 1666a",
        "title": "Regulation of Credit Reports During Dispute (TILA)",
        "text": "If a creditor receives a billing error notice and reports to a consumer reporting agency information regarding that delinquency, the creditor shall report that the amount or item is in dispute.",
        "short_citation": "TILA § 162",
        "dispute_basis": "The creditor failed to report that this amount is in dispute, as required by law.",
        "applicable_to": ["disputed_billing", "missing_dispute_notation"],
        "law": "TILA",
    },
    "df_udaap": {
        "section": "12 U.S.C. § 5536",
        "title": "Prohibition on Unfair, Deceptive, or Abusive Acts (Dodd-Frank)",
        "text": "It shall be unlawful for any covered person or service provider to engage in any unfair, deceptive, or abusive act or practice.",
        "short_citation": "Dodd-Frank § 1036",
        "dispute_basis": "The reporting practices in this case may constitute unfair or deceptive acts under consumer protection law.",
        "applicable_to": ["duplicate_account", "systematic_inaccuracy"],
        "law": "Dodd-Frank",
    },
}

DISPUTE_TYPES = {
    "account_present": {
        "name": "Account Dispute",
        "description": "Consumer disputes account presence or ownership",
        "fcra_sections": ["1681i_a", "1681i_a_5", "1681s_2_b"],
        "primary_section": "1681i_a",
        "supplemental_law": [],
    },
    "balance_reported": {
        "name": "Balance Dispute",
        "description": "Consumer disputes reported balance",
        "fcra_sections": ["1681e_b", "1681i_a", "1681s_2_a"],
        "primary_section": "1681e_b",
        "supplemental_law": ["tila_1666"],
    },
    "status_reported": {
        "name": "Status Dispute",
        "description": "Consumer disputes account status",
        "fcra_sections": ["1681e_b", "1681i_a", "1681s_2_a"],
        "primary_section": "1681e_b",
        "supplemental_law": [],
    },
    "late_payment_reported": {
        "name": "Late Payment Dispute",
        "description": "Consumer disputes late payment notation",
        "fcra_sections": ["1681e_b", "1681i_a", "1681s_2_a"],
        "primary_section": "1681e_b",
        "supplemental_law": ["tila_1666", "tila_1666a"],
    },
    "duplicate_detected": {
        "name": "Duplicate Entry Dispute",
        "description": "Same account reported multiple times",
        "fcra_sections": ["1681e_b", "1681i_a"],
        "primary_section": "1681e_b",
        "supplemental_law": ["df_udaap"],
    },
    "date_reported": {
        "name": "Date Dispute",
        "description": "Consumer disputes reported date or timing",
        "fcra_sections": ["1681c_a"],
        "primary_section": "1681c_a",
        "supplemental_law": [],
    },
    "personal_info_present": {
        "name": "Personal Info Dispute",
        "description": "Name, address, SSN, or other personal data is incorrect",
        "fcra_sections": ["1681e_b", "1681i_a", "1681g"],
        "primary_section": "1681e_b",
        "supplemental_law": [],
    },
    "inquiry_present": {
        "name": "Inquiry Dispute",
        "description": "Consumer disputes authorization and requests verification of permissible purpose",
        "fcra_sections": ["1681b"],
        "primary_section": "1681b",
        "supplemental_law": [],
    },
    "unverifiable_info": {
        "name": "Unverifiable Information Dispute",
        "description": "Information cannot be verified by the CRA or furnisher",
        "fcra_sections": ["1681i_a_5", "1681i_a", "1681g"],
        "primary_section": "1681i_a_5",
        "supplemental_law": [],
    },
}

VIOLATION_TYPES = DISPUTE_TYPES

BUREAU_ADDRESSES = {
    "equifax": {
        "name": "Equifax Information Services LLC",
        "address": "P.O. Box 740256",
        "city_state_zip": "Atlanta, GA 30374-0256"
    },
    "experian": {
        "name": "Experian",
        "address": "P.O. Box 4500",
        "city_state_zip": "Allen, TX 75013"
    },
    "transunion": {
        "name": "TransUnion LLC",
        "address": "P.O. Box 2000",
        "city_state_zip": "Chester, PA 19016"
    },
    "unknown": {
        "name": "[Credit Bureau Name]",
        "address": "[Bureau Address]",
        "city_state_zip": "[City, State ZIP]"
    }
}

def get_statute(section_key):
    result = FCRA_STATUTES.get(section_key)
    if result:
        return result
    return SUPPLEMENTAL_STATUTES.get(section_key)

def get_violation_type(type_key):
    return VIOLATION_TYPES.get(type_key)

def get_primary_statute_for_violation(violation_type):
    vtype = VIOLATION_TYPES.get(violation_type)
    if vtype:
        return FCRA_STATUTES.get(vtype["primary_section"])
    return None

def get_supplemental_statutes_for_violation(violation_type):
    vtype = VIOLATION_TYPES.get(violation_type)
    if not vtype:
        return []
    supp_keys = vtype.get("supplemental_law", [])
    return [SUPPLEMENTAL_STATUTES[k] for k in supp_keys if k in SUPPLEMENTAL_STATUTES]

def get_all_applicable_statutes(violation_type):
    vtype = VIOLATION_TYPES.get(violation_type)
    if not vtype:
        return []
    statutes = []
    for key in vtype.get("fcra_sections", []):
        s = FCRA_STATUTES.get(key)
        if s:
            statutes.append(s)
    for key in vtype.get("supplemental_law", []):
        s = SUPPLEMENTAL_STATUTES.get(key)
        if s:
            statutes.append(s)
    return statutes

def get_bureau_address(bureau):
    return BUREAU_ADDRESSES.get(bureau.lower(), BUREAU_ADDRESSES["unknown"])
