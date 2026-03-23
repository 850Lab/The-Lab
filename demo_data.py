import streamlit as st
from datetime import datetime
from review_claims import (
    ReviewClaim, ReviewType, EvidenceSummary, ConsumerResponse,
    ImpactAssessment, Audit, CrossBureauStatus, CreditImpact,
    Severity, ClaimConfidenceSummary, ConsumerResponseStatus,
    LetterEligibility,
)


DEMO_SAMPLE_LETTER_HTML = """
<div class="demo-letter-preview" style="font-family: 'Times New Roman', serif; max-width: 680px; margin: 0 auto;
            padding: 40px; background: #fff !important; color: #111 !important; line-height: 1.6; border: 1px solid #ccc;">
  <p>Alex Johnson<br>4521 Maple Creek Dr<br>Charlotte, NC 28205</p>
  <p style="margin-top:24px;">{date}</p>
  <p style="margin-top:24px;">
    TransUnion Consumer Solutions<br>
    P.O. Box 2000<br>
    Chester, PA 19016
  </p>
  <p style="margin-top:24px;"><strong>Re: Dispute of Inaccurate Information — Request for Investigation</strong></p>
  <p>Dear TransUnion Disputes Department,</p>
  <p>
    I am writing pursuant to my rights under the Fair Credit Reporting Act,
    15 U.S.C. &sect; 1681 <em>et seq.</em>, to dispute the following inaccurate
    information appearing on my credit report.
  </p>
  <p><strong>DISPUTED ITEM #1: Capital One Quicksilver (****4417)</strong><br>
     Issue: Late payment reported for March 2024 — 30 days past due.<br>
     My records confirm this payment was made on time via automatic bank draft on 03/02/2024.
     This information is inaccurate and must be corrected or removed.</p>
  <p><strong>DISPUTED ITEM #2: Midland Credit Management (****9182)</strong><br>
     Issue: Collection account for $2,847 — I do not recognize this account and have no
     record of any obligation to the original creditor. This account cannot be verified
     and must be removed per FCRA &sect; 611.</p>
  <p><strong>DISPUTED ITEM #3: Chase Sapphire (****7823)</strong><br>
     Issue: Balance reported as $6,340 but my most recent statement shows $3,170.
     This information is inaccurate and must be corrected.</p>
  <p>
    I request that you investigate these items and provide me with the results
    within 30 days as required by FCRA &sect; 611(a)(1). If you cannot verify
    the accuracy of these items, they must be promptly deleted from my credit file.
  </p>
  <p>Please send your response to the address listed above.</p>
  <p style="margin-top:32px;">Sincerely,<br><br>Alex Johnson</p>
</div>
""".format(date=datetime.now().strftime("%B %d, %Y"))


def _build_demo_review_claims():
    bureau = "transunion"
    bureau_display = "Transunion"
    claims = []

    claims.append(ReviewClaim(
        review_claim_id="demo_rc_neg_late",
        review_type=ReviewType.NEGATIVE_IMPACT,
        summary="Late payment reported March 2024 — 30 days past due on Capital One Quicksilver (****4417)",
        question="Is this late payment on Capital One Quicksilver accurate?",
        entities={"account_name": "Capital One Quicksilver (****4417)", "bureau": bureau_display},
        supporting_claim_ids=["demo_claim_1a", "demo_claim_1b"],
        evidence_summary=EvidenceSummary(
            system_observations=[
                "Late payment reported for 03/2024 — 30 days past due",
                "Account with Capital One reported",
                "Balance of $1,842 reported",
                "Status: 30 Days Late",
            ],
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=ClaimConfidenceSummary(high=2, medium=0, low=0),
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=CreditImpact.NEGATIVE,
            severity=Severity.HIGH,
        ),
        audit=Audit(),
    ))

    claims.append(ReviewClaim(
        review_claim_id="demo_rc_neg_coll",
        review_type=ReviewType.NEGATIVE_IMPACT,
        summary="Collection account reported by Midland Credit Management for $2,847 (****9182)",
        question="Is this collection account from Midland Credit Management accurate?",
        entities={"account_name": "Midland Credit Management (****9182)", "bureau": bureau_display},
        supporting_claim_ids=["demo_claim_2a", "demo_claim_2b"],
        evidence_summary=EvidenceSummary(
            system_observations=[
                "Collection account reported — $2,847 balance",
                "Account with Midland Credit Management reported",
                "Status: Collection",
                "Date opened: 08/2023",
            ],
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=ClaimConfidenceSummary(high=2, medium=0, low=0),
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=CreditImpact.NEGATIVE,
            severity=Severity.HIGH,
        ),
        audit=Audit(),
    ))

    claims.append(ReviewClaim(
        review_claim_id="demo_rc_dup",
        review_type=ReviewType.DUPLICATE_ACCOUNT,
        summary="Possible duplicate: Wells Fargo Auto Loan appears twice with different account numbers (****3301 and ****3302)",
        question="Is this the same Wells Fargo Auto Loan account reported multiple times?",
        entities={"account_name": "Wells Fargo Auto Loan", "bureau": bureau_display},
        supporting_claim_ids=["demo_claim_3a", "demo_claim_3b"],
        evidence_summary=EvidenceSummary(
            system_observations=[
                "Possible duplicate entry detected",
                "Account ****3301 — balance $12,450, opened 01/2022",
                "Account ****3302 — balance $12,450, opened 01/2022",
                "Same creditor, same balance, same open date",
            ],
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=ClaimConfidenceSummary(high=1, medium=1, low=0),
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=CreditImpact.NEGATIVE,
            severity=Severity.MODERATE,
        ),
        audit=Audit(),
    ))

    claims.append(ReviewClaim(
        review_claim_id="demo_rc_acc_bal",
        review_type=ReviewType.ACCURACY_VERIFICATION,
        summary="Chase Sapphire (****7823) reports balance of $6,340 — may be incorrect",
        question="Is the reported balance of $6,340 on Chase Sapphire accurate?",
        entities={"account_name": "Chase Sapphire (****7823)", "bureau": bureau_display},
        supporting_claim_ids=["demo_claim_4a", "demo_claim_4b"],
        evidence_summary=EvidenceSummary(
            system_observations=[
                "Balance of $6,340 reported",
                "Account with Chase reported",
                "Status: Open / Current",
                "Credit limit: $15,000",
            ],
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=ClaimConfidenceSummary(high=2, medium=0, low=0),
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=CreditImpact.NEUTRAL,
            severity=Severity.MODERATE,
        ),
        audit=Audit(),
    ))

    claims.append(ReviewClaim(
        review_claim_id="demo_rc_acc_status",
        review_type=ReviewType.ACCURACY_VERIFICATION,
        summary="Discover It (****5590) shows status 'Open' but account was closed June 2023",
        question="Is the reported status of 'Open' on Discover It accurate?",
        entities={"account_name": "Discover It (****5590)", "bureau": bureau_display},
        supporting_claim_ids=["demo_claim_5a"],
        evidence_summary=EvidenceSummary(
            system_observations=[
                "Account status shows 'Open'",
                "Account with Discover reported",
                "Balance: $0",
                "Last payment date: 06/2023",
            ],
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=ClaimConfidenceSummary(high=1, medium=0, low=0),
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=CreditImpact.NEUTRAL,
            severity=Severity.LOW,
        ),
        audit=Audit(),
    ))

    claims.append(ReviewClaim(
        review_claim_id="demo_rc_unverify",
        review_type=ReviewType.UNVERIFIABLE_INFORMATION,
        summary="Synchrony Bank (****6104) — account details cannot be verified from available records",
        question="Can you verify this Synchrony Bank account information from your records?",
        entities={"account_name": "Synchrony Bank (****6104)", "bureau": bureau_display},
        supporting_claim_ids=["demo_claim_6a", "demo_claim_6b"],
        evidence_summary=EvidenceSummary(
            system_observations=[
                "Account with Synchrony Bank reported",
                "Balance of $430 reported",
                "Status: Open / Current",
                "Limited verifiable data available",
            ],
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=ClaimConfidenceSummary(high=0, medium=2, low=0),
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=CreditImpact.NEUTRAL,
            severity=Severity.LOW,
        ),
        audit=Audit(),
    ))

    claims.append(ReviewClaim(
        review_claim_id="demo_rc_own_amex",
        review_type=ReviewType.ACCOUNT_OWNERSHIP,
        summary="Amex Blue Cash Preferred (****2209) reported by Transunion",
        question="Do you recognize this Amex Blue Cash Preferred account as yours?",
        entities={"account_name": "Amex Blue Cash Preferred (****2209)", "bureau": bureau_display},
        supporting_claim_ids=["demo_claim_7a"],
        evidence_summary=EvidenceSummary(
            system_observations=[
                "Account with American Express reported",
                "Balance of $2,100 reported",
                "Status: Open / Current",
                "Date opened: 03/2021",
            ],
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=ClaimConfidenceSummary(high=1, medium=0, low=0),
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=CreditImpact.NEUTRAL,
            severity=Severity.LOW,
        ),
        audit=Audit(),
    ))

    claims.append(ReviewClaim(
        review_claim_id="demo_rc_own_bofa",
        review_type=ReviewType.ACCOUNT_OWNERSHIP,
        summary="Bank of America Customized Cash (****8871) reported by Transunion",
        question="Do you recognize this Bank of America account as yours?",
        entities={"account_name": "Bank of America Customized Cash (****8871)", "bureau": bureau_display},
        supporting_claim_ids=["demo_claim_8a"],
        evidence_summary=EvidenceSummary(
            system_observations=[
                "Account with Bank of America reported",
                "Balance of $750 reported",
                "Status: Open / Current",
                "Date opened: 11/2019",
            ],
            cross_bureau_status=CrossBureauStatus.SINGLE_BUREAU,
            claim_confidence_summary=ClaimConfidenceSummary(high=1, medium=0, low=0),
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(
            credit_impact=CreditImpact.NEUTRAL,
            severity=Severity.LOW,
        ),
        audit=Audit(),
    ))

    return claims


def _build_demo_uploaded_reports():
    return {
        "demo_transunion": {
            "bureau": "transunion",
            "report_id": "demo_tu_001",
            "parsed_data": {
                "personal_info": {
                    "name": "Alex Johnson",
                    "address": "4521 Maple Creek Dr, Charlotte, NC 28205",
                    "ssn": "***-**-7890",
                    "dob": "05/12/1988",
                },
                "accounts": [
                    {
                        "creditor": "Capital One",
                        "account_name": "Capital One Quicksilver",
                        "account_number": "****4417",
                        "balance": "$1,842",
                        "status": "30 Days Late",
                        "date_opened": "06/2020",
                        "type": "Credit Card",
                        "responsibility": "Individual",
                    },
                    {
                        "creditor": "Midland Credit Management",
                        "account_name": "Midland Credit Management",
                        "account_number": "****9182",
                        "balance": "$2,847",
                        "status": "Collection",
                        "date_opened": "08/2023",
                        "type": "Collection",
                        "responsibility": "Individual",
                    },
                    {
                        "creditor": "Wells Fargo",
                        "account_name": "Wells Fargo Auto Loan",
                        "account_number": "****3301",
                        "balance": "$12,450",
                        "status": "Open",
                        "date_opened": "01/2022",
                        "type": "Auto Loan",
                        "responsibility": "Individual",
                    },
                    {
                        "creditor": "Wells Fargo",
                        "account_name": "Wells Fargo Auto Loan",
                        "account_number": "****3302",
                        "balance": "$12,450",
                        "status": "Open",
                        "date_opened": "01/2022",
                        "type": "Auto Loan",
                        "responsibility": "Individual",
                    },
                    {
                        "creditor": "Chase",
                        "account_name": "Chase Sapphire",
                        "account_number": "****7823",
                        "balance": "$6,340",
                        "status": "Open",
                        "date_opened": "09/2019",
                        "type": "Credit Card",
                        "credit_limit": "$15,000",
                        "responsibility": "Individual",
                    },
                    {
                        "creditor": "Discover",
                        "account_name": "Discover It",
                        "account_number": "****5590",
                        "balance": "$0",
                        "status": "Open",
                        "date_opened": "04/2018",
                        "type": "Credit Card",
                        "responsibility": "Individual",
                    },
                    {
                        "creditor": "Synchrony Bank",
                        "account_name": "Synchrony Bank",
                        "account_number": "****6104",
                        "balance": "$430",
                        "status": "Open",
                        "date_opened": "02/2021",
                        "type": "Credit Card",
                        "responsibility": "Individual",
                    },
                    {
                        "creditor": "American Express",
                        "account_name": "Amex Blue Cash Preferred",
                        "account_number": "****2209",
                        "balance": "$2,100",
                        "status": "Open",
                        "date_opened": "03/2021",
                        "type": "Credit Card",
                        "responsibility": "Individual",
                    },
                    {
                        "creditor": "Bank of America",
                        "account_name": "Bank of America Customized Cash",
                        "account_number": "****8871",
                        "balance": "$750",
                        "status": "Open",
                        "date_opened": "11/2019",
                        "type": "Credit Card",
                        "responsibility": "Individual",
                    },
                ],
            },
        }
    }


def load_demo_session():
    _stale_keys = (
        'generated_letters', 'panel', 'report_id', 'current_report',
        '_cached_entitlements', '_email_verified_cached', '_activity_session_logged',
        'unified_summary', 'parsed_totals', 'report_totals',
        'readiness_decisions', 'letter_candidates', 'current_approval',
        'capacity_selection', 'ai_strategy_result', 'battle_plan_items',
        '_credit_command_plan', '_demo_show_sample_letter',
        'claim_responses', 'review_claim_responses',
    )
    for _k in _stale_keys:
        st.session_state.pop(_k, None)
    st.session_state._demo_mode = True
    st.session_state.ui_card = "SUMMARY"
    st.session_state.identity_confirmed = {}
    st.session_state.dispute_rounds = []
    st.session_state.generated_letters = {}
    st.session_state.uploaded_reports = _build_demo_uploaded_reports()
    st.session_state.review_claims = _build_demo_review_claims()
    st.session_state.auth_page = "demo"
