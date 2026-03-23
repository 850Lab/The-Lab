"""
legal_kb.py | 850 Lab Parser Machine
Structured Legal Knowledge Base for AI-Powered Dispute Strategy

Contains:
1. FCRA statutes (expanded with subsections and enforcement provisions)
2. Dodd-Frank consumer protection provisions (CFPB authority)
3. TILA sections relevant to credit reporting disputes
4. Key court case precedents with holdings
5. Mapping system: ReviewType → applicable legal authorities
6. Context builder for LLM strategy prompts

GUARDRAILS:
- This module provides REFERENCE DATA only
- It does NOT constitute legal advice
- Citations are used to inform factual disputes, not litigation
- Consumer-sourced disputes only
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class StatuteEntry:
    statute_id: str
    law: str
    section: str
    title: str
    full_citation: str
    summary: str
    key_text: str
    dispute_relevance: str
    applicable_dispute_types: List[str]
    enforcement: str = ""


@dataclass
class CasePrecedent:
    case_id: str
    case_name: str
    citation: str
    year: int
    court: str
    holding: str
    dispute_relevance: str
    applicable_dispute_types: List[str]
    key_quote: str = ""


@dataclass
class LegalContext:
    statutes: List[StatuteEntry]
    cases: List[CasePrecedent]
    summary: str


FCRA_STATUTES_KB = {
    "fcra_1681e_b": StatuteEntry(
        statute_id="fcra_1681e_b",
        law="FCRA",
        section="15 U.S.C. § 1681e(b)",
        title="Accuracy of Report",
        full_citation="Fair Credit Reporting Act § 607(b), 15 U.S.C. § 1681e(b)",
        summary="Requires CRAs to follow reasonable procedures to assure maximum possible accuracy.",
        key_text="Whenever a consumer reporting agency prepares a consumer report it shall follow reasonable procedures to assure maximum possible accuracy of the information concerning the individual about whom the report relates.",
        dispute_relevance="Applicable when reported information does not accurately reflect consumer's actual account status, balance, payment history, or personal information.",
        applicable_dispute_types=["accuracy_verification", "negative_impact", "identity_verification"],
    ),
    "fcra_1681i_a": StatuteEntry(
        statute_id="fcra_1681i_a",
        law="FCRA",
        section="15 U.S.C. § 1681i(a)",
        title="Reinvestigation of Disputed Information",
        full_citation="Fair Credit Reporting Act § 611(a), 15 U.S.C. § 1681i(a)",
        summary="Requires CRAs to conduct a reasonable reinvestigation when a consumer disputes information.",
        key_text="If the completeness or accuracy of any item of information contained in a consumer's file is disputed by the consumer, the agency shall conduct a reasonable reinvestigation to determine whether the disputed information is inaccurate and record the current status of the disputed information, or delete the item from the file.",
        dispute_relevance="Foundation for all consumer disputes. CRA must investigate within 30 days (extendable to 45 if consumer provides additional info). If not verified, must be deleted.",
        applicable_dispute_types=["accuracy_verification", "negative_impact", "account_ownership", "duplicate_account", "unverifiable_information"],
        enforcement="CRA must complete reinvestigation within 30 days (45 if additional info provided). Must notify furnisher within 5 business days.",
    ),
    "fcra_1681i_a_5": StatuteEntry(
        statute_id="fcra_1681i_a_5",
        law="FCRA",
        section="15 U.S.C. § 1681i(a)(5)",
        title="Deletion of Unverifiable Information",
        full_citation="Fair Credit Reporting Act § 611(a)(5), 15 U.S.C. § 1681i(a)(5)",
        summary="Requires deletion of information that cannot be verified after reinvestigation.",
        key_text="If, after any reinvestigation under paragraph (1) of any information disputed by a consumer, an item of the information is found to be inaccurate or incomplete or cannot be verified, the consumer reporting agency shall promptly delete that item of information from the file of the consumer, or modify that item of information, as appropriate.",
        dispute_relevance="Key provision for unverifiable information disputes. If the CRA or furnisher cannot verify the disputed item, it must be deleted entirely.",
        applicable_dispute_types=["unverifiable_information", "accuracy_verification", "account_ownership"],
    ),
    "fcra_1681c_a": StatuteEntry(
        statute_id="fcra_1681c_a",
        law="FCRA",
        section="15 U.S.C. § 1681c(a)",
        title="Obsolete Information / Reporting Time Limits",
        full_citation="Fair Credit Reporting Act § 605(a), 15 U.S.C. § 1681c(a)",
        summary="Prohibits reporting adverse information beyond statutory time limits.",
        key_text="No consumer reporting agency may report: bankruptcies older than 10 years; civil suits, judgments, arrest records older than 7 years; paid tax liens older than 7 years; accounts placed for collection or charged off older than 7 years; any other adverse information older than 7 years.",
        dispute_relevance="Applicable when adverse information has exceeded the maximum allowable reporting period. The 7-year period runs from the date of first delinquency.",
        applicable_dispute_types=["negative_impact", "accuracy_verification"],
    ),
    "fcra_1681b": StatuteEntry(
        statute_id="fcra_1681b",
        law="FCRA",
        section="15 U.S.C. § 1681b",
        title="Permissible Purposes of Consumer Reports",
        full_citation="Fair Credit Reporting Act § 604, 15 U.S.C. § 1681b",
        summary="Limits the circumstances under which a consumer report may be furnished.",
        key_text="A consumer reporting agency may furnish a consumer report only under specified permissible purposes including: court order, consumer instruction, credit transaction, employment, insurance underwriting, legitimate business need, or account review.",
        dispute_relevance="Applicable when an inquiry appears without consumer authorization. Consumer may request verification of the permissible purpose for any hard inquiry.",
        applicable_dispute_types=["accuracy_verification"],
        enforcement="Unauthorized access to consumer report may result in actual or statutory damages.",
    ),
    "fcra_1681s_2_a": StatuteEntry(
        statute_id="fcra_1681s_2_a",
        law="FCRA",
        section="15 U.S.C. § 1681s-2(a)",
        title="Furnisher Duty to Provide Accurate Information",
        full_citation="Fair Credit Reporting Act § 623(a), 15 U.S.C. § 1681s-2(a)",
        summary="Requires data furnishers to report accurate information and prohibits furnishing information known to be inaccurate.",
        key_text="A person shall not furnish any information relating to a consumer to any consumer reporting agency if the person knows or has reasonable cause to believe that the information is inaccurate. A person shall not furnish information that the person has been notified is inaccurate by the consumer, unless the information is accurate.",
        dispute_relevance="Strengthens disputes where the furnisher (creditor) is reporting information the consumer has identified as inaccurate. Creates obligation on the furnisher, not just the CRA.",
        applicable_dispute_types=["accuracy_verification", "negative_impact", "account_ownership"],
    ),
    "fcra_1681s_2_b": StatuteEntry(
        statute_id="fcra_1681s_2_b",
        law="FCRA",
        section="15 U.S.C. § 1681s-2(b)",
        title="Furnisher Duty Upon Notice of Dispute",
        full_citation="Fair Credit Reporting Act § 623(b), 15 U.S.C. § 1681s-2(b)",
        summary="Requires furnishers to investigate disputes forwarded by CRAs and correct or delete inaccurate information.",
        key_text="After receiving notice of a dispute from a CRA, the furnisher shall conduct an investigation, review all relevant information provided by the CRA, report results to the CRA, and if incomplete or inaccurate, report those results to all CRAs to which the information was furnished.",
        dispute_relevance="Critical for follow-up disputes. If a CRA forwards the dispute and the furnisher fails to properly investigate, this creates an independent violation.",
        applicable_dispute_types=["accuracy_verification", "negative_impact", "unverifiable_information"],
        enforcement="Private right of action exists under § 1681s-2(b) for furnisher violations after CRA notification.",
    ),
    "fcra_1681g": StatuteEntry(
        statute_id="fcra_1681g",
        law="FCRA",
        section="15 U.S.C. § 1681g",
        title="Consumer Disclosure Rights",
        full_citation="Fair Credit Reporting Act § 609, 15 U.S.C. § 1681g",
        summary="Entitles consumers to disclosure of all information in their file, sources of information, and recipients of reports.",
        key_text="Every consumer reporting agency shall, upon request and proper identification, clearly and accurately disclose to the consumer all information in the consumer's file, the sources of the information, and identification of each person that procured a consumer report.",
        dispute_relevance="Supports requests for method of verification and source documentation. Consumer has right to know what is in their file and where it came from.",
        applicable_dispute_types=["accuracy_verification", "identity_verification", "unverifiable_information"],
    ),
}


DODD_FRANK_KB = {
    "df_1034": StatuteEntry(
        statute_id="df_1034",
        law="Dodd-Frank",
        section="12 U.S.C. § 5534",
        title="Consumer Complaint Response (Section 1034)",
        full_citation="Dodd-Frank Wall Street Reform and Consumer Protection Act § 1034, 12 U.S.C. § 5534",
        summary="Requires supervised entities to provide timely responses to consumer complaints and inquiries forwarded by the CFPB.",
        key_text="The Bureau may establish reasonable procedures to route consumer complaints and inquiries to supervised entities for response, and entities must provide a timely response.",
        dispute_relevance="Supports escalation path through CFPB when CRAs or furnishers fail to adequately respond to consumer disputes.",
        applicable_dispute_types=["accuracy_verification", "negative_impact", "unverifiable_information"],
    ),
    "df_1036": StatuteEntry(
        statute_id="df_1036",
        law="Dodd-Frank",
        section="12 U.S.C. § 5536",
        title="Prohibition on Unfair, Deceptive, or Abusive Acts (UDAAP)",
        full_citation="Dodd-Frank Wall Street Reform and Consumer Protection Act § 1036, 12 U.S.C. § 5536",
        summary="Prohibits covered persons from engaging in unfair, deceptive, or abusive acts or practices.",
        key_text="It shall be unlawful for any covered person or service provider to engage in any unfair, deceptive, or abusive act or practice.",
        dispute_relevance="Applicable when a furnisher or CRA engages in deceptive reporting practices, such as re-aging accounts, reporting disputed debts without notation, or systematically failing to investigate disputes.",
        applicable_dispute_types=["accuracy_verification", "negative_impact", "duplicate_account"],
    ),
    "df_1024_cfpb": StatuteEntry(
        statute_id="df_1024_cfpb",
        law="Dodd-Frank",
        section="12 U.S.C. § 5514",
        title="CFPB Supervisory Authority Over CRAs",
        full_citation="Dodd-Frank Wall Street Reform and Consumer Protection Act § 1024, 12 U.S.C. § 5514",
        summary="Grants CFPB supervisory authority over consumer reporting agencies and large participants in consumer financial markets.",
        key_text="The Bureau shall have exclusive authority to require reports and conduct examinations of persons described in subsection (a)(1) for purposes of assessing compliance with Federal consumer financial laws and obtaining information about activities subject to those laws.",
        dispute_relevance="Establishes CFPB oversight of CRAs, providing regulatory backing for consumer complaints and disputes when CRAs fail to comply with FCRA obligations.",
        applicable_dispute_types=["accuracy_verification", "negative_impact", "unverifiable_information"],
    ),
}


TILA_KB = {
    "tila_1637": StatuteEntry(
        statute_id="tila_1637",
        law="TILA",
        section="15 U.S.C. § 1637",
        title="Open-End Credit Account Disclosures",
        full_citation="Truth in Lending Act § 127, 15 U.S.C. § 1637",
        summary="Requires creditors to provide accurate periodic statements with current balance, payment due date, finance charges, and APR for open-end credit accounts.",
        key_text="The creditor of any account under an open end consumer credit plan shall transmit a statement setting forth each extension of credit during the period, the applicable finance charges, and the annual percentage rate.",
        dispute_relevance="When a credit report shows balance or payment information that conflicts with the creditor's own periodic statements, this creates a basis for disputing the reported information as inaccurate.",
        applicable_dispute_types=["accuracy_verification", "negative_impact"],
    ),
    "tila_1666": StatuteEntry(
        statute_id="tila_1666",
        law="TILA",
        section="15 U.S.C. § 1666",
        title="Billing Error Resolution",
        full_citation="Truth in Lending Act § 161, 15 U.S.C. § 1666",
        summary="Prohibits creditors from reporting amounts in dispute as delinquent during the billing error resolution process.",
        key_text="After receipt of a billing error notice, the creditor shall not report or threaten to report the consumer as delinquent to any third party, including a consumer reporting agency, until the billing error allegations are resolved.",
        dispute_relevance="Directly applicable when a creditor reports a disputed amount as delinquent to CRAs while the billing dispute is still pending. Creates independent basis for removing negative marks.",
        applicable_dispute_types=["accuracy_verification", "negative_impact"],
    ),
    "tila_1666a": StatuteEntry(
        statute_id="tila_1666a",
        law="TILA",
        section="15 U.S.C. § 1666a",
        title="Regulation of Credit Reports During Dispute",
        full_citation="Truth in Lending Act § 162, 15 U.S.C. § 1666a",
        summary="Requires creditors reporting a disputed balance to also report that the amount is in dispute.",
        key_text="If a creditor receives a billing error notice and reports to a consumer reporting agency information regarding that delinquency, the creditor shall report that the amount or item is in dispute.",
        dispute_relevance="If a creditor reported negative information without noting it was disputed, this is an independent violation that supports the dispute.",
        applicable_dispute_types=["accuracy_verification", "negative_impact"],
    ),
}


CASE_PRECEDENTS = {
    "cushman_v_transunion": CasePrecedent(
        case_id="cushman_v_transunion",
        case_name="Cushman v. Trans Union Corp.",
        citation="115 F.3d 220 (3d Cir. 1997)",
        year=1997,
        court="Third Circuit",
        holding="A CRA's reinvestigation that merely parrots the furnisher's response without independent verification may not constitute a 'reasonable reinvestigation' under FCRA § 611.",
        dispute_relevance="Strengthens disputes where the CRA's prior reinvestigation was perfunctory — simply confirming with the furnisher without verifying underlying documentation.",
        applicable_dispute_types=["accuracy_verification", "negative_impact", "unverifiable_information"],
        key_quote="A reasonable reinvestigation requires more than merely shifting the burden back to the consumer.",
    ),
    "stevenson_v_trs": CasePrecedent(
        case_id="stevenson_v_trs",
        case_name="Stevenson v. TRW Inc.",
        citation="987 F.2d 288 (5th Cir. 1993)",
        year=1993,
        court="Fifth Circuit",
        holding="A CRA that fails to verify disputed information through reasonable procedures violates § 1681e(b), even if the furnisher confirms the data.",
        dispute_relevance="Supports disputes where the bureau relied solely on automated verification (e-OSCAR) without examining underlying records.",
        applicable_dispute_types=["accuracy_verification", "negative_impact"],
    ),
    "dennis_v_bf_goodrich": CasePrecedent(
        case_id="dennis_v_bf_goodrich",
        case_name="Dennis v. BEH-1, LLC",
        citation="520 F.3d 1066 (9th Cir. 2008)",
        year=2008,
        court="Ninth Circuit",
        holding="A furnisher who receives notice of a dispute from a CRA must conduct a reasonable investigation, not merely verify that the account exists in their system.",
        dispute_relevance="Applicable when a furnisher's investigation consists only of confirming the existence of an account or balance in their database without reviewing the consumer's specific dispute.",
        applicable_dispute_types=["accuracy_verification", "negative_impact", "account_ownership"],
    ),
    "saunders_v_branch_banking": CasePrecedent(
        case_id="saunders_v_branch_banking",
        case_name="Saunders v. Branch Banking & Trust Co.",
        citation="526 F.3d 142 (4th Cir. 2008)",
        year=2008,
        court="Fourth Circuit",
        holding="A furnisher's investigation must be reasonable in light of the specific information provided by the consumer, and mechanical verification is insufficient.",
        dispute_relevance="Strengthens disputes where detailed consumer evidence was provided but the furnisher performed only a superficial check.",
        applicable_dispute_types=["accuracy_verification", "negative_impact"],
    ),
    "nelson_v_chase": CasePrecedent(
        case_id="nelson_v_chase",
        case_name="Nelson v. Chase Manhattan Mortgage Corp.",
        citation="282 F.3d 1057 (9th Cir. 2002)",
        year=2002,
        court="Ninth Circuit",
        holding="CRAs cannot satisfy their duty under § 1681e(b) by mechanically relying on information from furnishers without examining whether the procedures used are reasonable.",
        dispute_relevance="Supports arguments that a CRA's reliance on automated furnisher responses (e-OSCAR) is not a 'reasonable procedure' when the consumer has presented specific evidence of inaccuracy.",
        applicable_dispute_types=["accuracy_verification", "unverifiable_information"],
    ),
    "gorman_v_wolpoff": CasePrecedent(
        case_id="gorman_v_wolpoff",
        case_name="Gorman v. Wolpoff & Abramson, LLP",
        citation="584 F.3d 1147 (9th Cir. 2009)",
        year=2009,
        court="Ninth Circuit",
        holding="Under § 1681s-2(b), a furnisher's investigation must consider all relevant information forwarded by the CRA, including documents submitted by the consumer.",
        dispute_relevance="Critical for disputes where the consumer provided supporting documentation. Furnishers cannot ignore consumer-submitted evidence during investigation.",
        applicable_dispute_types=["accuracy_verification", "negative_impact", "account_ownership"],
    ),
    "jones_v_experian": CasePrecedent(
        case_id="jones_v_experian",
        case_name="Jones v. Experian Information Solutions",
        citation="No. 17-2495 (E.D. Pa. 2018)",
        year=2018,
        court="Eastern District of Pennsylvania",
        holding="Reporting a single account multiple times with different identifiers can constitute inaccurate reporting under § 1681e(b).",
        dispute_relevance="Directly supports duplicate account disputes where the same underlying account appears under different names, numbers, or statuses.",
        applicable_dispute_types=["duplicate_account", "accuracy_verification"],
    ),
    "spence_v_trs": CasePrecedent(
        case_id="spence_v_trs",
        case_name="Spence v. TRW, Inc.",
        citation="92 F.3d 380 (6th Cir. 1996)",
        year=1996,
        court="Sixth Circuit",
        holding="Inclusion of inaccurate information in a consumer report is sufficient injury under the FCRA; actual denial of credit need not be shown.",
        dispute_relevance="Establishes that the mere presence of inaccurate information on a credit report is harmful — the consumer need not prove they were denied credit as a result.",
        applicable_dispute_types=["accuracy_verification", "negative_impact", "identity_verification"],
    ),
    "bach_v_first_union": CasePrecedent(
        case_id="bach_v_first_union",
        case_name="Bach v. First Union National Bank",
        citation="149 F. App'x 354 (6th Cir. 2005)",
        year=2005,
        court="Sixth Circuit",
        holding="A furnisher's duty to investigate under § 1681s-2(b) is triggered upon receipt of notice from a CRA, and the investigation must be meaningful and address the consumer's specific claims.",
        dispute_relevance="Supports follow-up disputes where initial investigation was inadequate. Furnisher must address the specific nature of the consumer's dispute, not just verify the account exists.",
        applicable_dispute_types=["accuracy_verification", "negative_impact", "unverifiable_information"],
    ),
}


REVIEW_TYPE_TO_LEGAL_MAP = {
    "identity_verification": {
        "statutes": ["fcra_1681e_b", "fcra_1681g"],
        "cases": ["spence_v_trs"],
        "strategy_note": "Personal information inaccuracies are foundational — incorrect identity data can link accounts to the wrong consumer. Dispute under § 1681e(b) (maximum accuracy) and request full file disclosure under § 1681g.",
    },
    "account_ownership": {
        "statutes": ["fcra_1681i_a", "fcra_1681i_a_5", "fcra_1681s_2_b"],
        "cases": ["dennis_v_bf_goodrich", "gorman_v_wolpoff", "bach_v_first_union"],
        "strategy_note": "Account ownership disputes carry high impact. Under § 1681i, the CRA must reinvestigate; under § 1681s-2(b), the furnisher must conduct a meaningful investigation upon CRA notification. If the account cannot be verified as belonging to the consumer, it must be deleted under § 1681i(a)(5).",
    },
    "duplicate_account": {
        "statutes": ["fcra_1681e_b", "fcra_1681i_a", "df_1036"],
        "cases": ["jones_v_experian", "nelson_v_chase"],
        "strategy_note": "Duplicate reporting inflates liabilities and lowers credit scores. Each duplicate represents a separate accuracy violation under § 1681e(b). UDAAP provisions may apply if duplicates result from systematic reporting failures.",
    },
    "negative_impact": {
        "statutes": ["fcra_1681e_b", "fcra_1681s_2_a", "fcra_1681s_2_b", "fcra_1681c_a", "tila_1666", "tila_1666a"],
        "cases": ["cushman_v_transunion", "stevenson_v_trs", "saunders_v_branch_banking", "gorman_v_wolpoff"],
        "strategy_note": "Negative impact items (late payments, collections, charge-offs) have the greatest effect on credit scores. Multiple legal authorities apply: FCRA accuracy requirements, furnisher duties, and TILA protections if the amount was in billing dispute. Prioritize items with strongest evidence of inaccuracy.",
    },
    "accuracy_verification": {
        "statutes": ["fcra_1681e_b", "fcra_1681i_a", "fcra_1681s_2_a", "tila_1637"],
        "cases": ["stevenson_v_trs", "nelson_v_chase", "saunders_v_branch_banking", "bach_v_first_union"],
        "strategy_note": "Accuracy disputes are the broadest category. The CRA's duty under § 1681e(b) requires reasonable procedures for maximum accuracy. TILA § 127 requires creditors to provide accurate periodic statements — discrepancies between statements and reported data strengthen accuracy disputes.",
    },
    "unverifiable_information": {
        "statutes": ["fcra_1681i_a_5", "fcra_1681i_a", "fcra_1681g", "df_1034"],
        "cases": ["cushman_v_transunion", "nelson_v_chase", "bach_v_first_union"],
        "strategy_note": "Unverifiable information must be deleted under § 1681i(a)(5). This is one of the strongest consumer provisions — if the CRA or furnisher cannot produce documentation to verify the disputed item, deletion is mandatory. Request method of verification under § 1681g.",
    },
}


def get_legal_context_for_review_type(review_type_value: str) -> LegalContext:
    mapping = REVIEW_TYPE_TO_LEGAL_MAP.get(review_type_value)
    if not mapping:
        return LegalContext(statutes=[], cases=[], summary="No specific legal context mapped for this dispute type.")

    statutes = []
    for sid in mapping["statutes"]:
        entry = FCRA_STATUTES_KB.get(sid) or DODD_FRANK_KB.get(sid) or TILA_KB.get(sid)
        if entry:
            statutes.append(entry)

    cases = []
    for cid in mapping["cases"]:
        case = CASE_PRECEDENTS.get(cid)
        if case:
            cases.append(case)

    return LegalContext(
        statutes=statutes,
        cases=cases,
        summary=mapping["strategy_note"],
    )


def get_all_statutes() -> Dict[str, StatuteEntry]:
    combined = {}
    combined.update(FCRA_STATUTES_KB)
    combined.update(DODD_FRANK_KB)
    combined.update(TILA_KB)
    return combined


def get_all_cases() -> Dict[str, CasePrecedent]:
    return dict(CASE_PRECEDENTS)


def build_legal_context_for_claims(review_types: List[str]) -> Dict[str, Any]:
    unique_types = list(set(review_types))
    all_statutes = {}
    all_cases = {}
    type_summaries = {}

    for rt in unique_types:
        ctx = get_legal_context_for_review_type(rt)
        type_summaries[rt] = ctx.summary
        for s in ctx.statutes:
            all_statutes[s.statute_id] = s
        for c in ctx.cases:
            all_cases[c.case_id] = c

    return {
        "statutes": {
            sid: {
                "law": s.law,
                "section": s.section,
                "title": s.title,
                "summary": s.summary,
                "dispute_relevance": s.dispute_relevance,
            }
            for sid, s in all_statutes.items()
        },
        "cases": {
            cid: {
                "case_name": c.case_name,
                "citation": c.citation,
                "holding": c.holding,
                "dispute_relevance": c.dispute_relevance,
            }
            for cid, c in all_cases.items()
        },
        "type_strategy_notes": type_summaries,
    }


def build_per_claim_legal_context(review_type_value: str) -> Dict[str, Any]:
    ctx = get_legal_context_for_review_type(review_type_value)

    statute_refs = []
    for s in ctx.statutes:
        statute_refs.append({
            "section": s.section,
            "title": s.title,
            "relevance": s.dispute_relevance,
        })

    case_refs = []
    for c in ctx.cases:
        case_refs.append({
            "case": c.case_name,
            "citation": c.citation,
            "holding": c.holding,
        })

    return {
        "applicable_statutes": statute_refs,
        "applicable_cases": case_refs,
        "strategy_note": ctx.summary,
    }
