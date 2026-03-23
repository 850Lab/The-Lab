"""
constants.py | 850 Lab Parser Machine
Immutable Contracts - Node 1: Reason Codes Contract (CLOSED)

All closed lists, mapping tables, and constants for the V1 contract system.
No additions, modifications, or free-text substitutes allowed.
"""

BLOCKER_REASON_CODES = {
    "NO_ACTIONABLE_BASIS",
    "NEEDS_USER_CONFIRMATION",
    "IDENTITY_NOT_CONFIRMED",
    "WAITING_FOR_RESPONSE",
    "POSITIONED_TIMING",
    "LOW_CONFIDENCE_NO_VERIFY_PATH",
    "MISSING_REQUIRED_FIELDS",
    "CONFLICTING_DATA_REQUIRES_REVIEW",
    "DUPLICATE_OR_SUPERSEDED",
    "OUT_OF_SCOPE_V1",
}

INCLUDE_REASON_CODES = {
    "HIGH_CONFIDENCE_ACCURACY",
    "INCONSISTENCY_VERIFICATION",
    "USER_CONFIRMED_FACT",
    "POST_VERIFICATION_ESCALATION",
    "UNVERIFIABLE_RECORD_REQUEST",
    "IDENTITY_CORRECTION_REQUEST",
}

INCLUDE_PRIORITY_ORDER = [
    "POST_VERIFICATION_ESCALATION",
    "HIGH_CONFIDENCE_ACCURACY",
    "USER_CONFIRMED_FACT",
    "INCONSISTENCY_VERIFICATION",
    "UNVERIFIABLE_RECORD_REQUEST",
    "IDENTITY_CORRECTION_REQUEST",
]

LETTER_LANGUAGE_TIERS = {
    "TIER_VERIFY",
    "TIER_ACCURACY",
    "TIER_IDENTITY",
    "TIER_ESCALATION",
}

EVIDENCE_TIERS = {
    "TIER_A",
    "TIER_B",
    "TIER_C",
    "TIER_D",
}

CAPACITY_LIMIT_V1 = 100

SYSTEM_ERROR_UI_STATE = "SYSTEM_ERROR"

CLAIM_TYPES = {
    "account",
    "inquiry",
    "public_record",
    "identity",
    "negative_item",
}

BUREAUS = {"EQ", "EX", "TU"}

USER_ASSERTION_FLAGS = {
    "NOT_MINE",
    "INCORRECT_BALANCE",
    "INCORRECT_STATUS",
    "INCORRECT_DATE",
    "INCORRECT_IDENTITY",
}

ACTION_TYPES = {"NONE", "VERIFY", "DIRECT", "ESCALATE"}
ACTION_TARGETS = {"BUREAU", "FURNISHER"}

STATUS_VALUES = {"OPEN", "CLOSED", "CHARGED_OFF", "COLLECTION", "PAID", "UNKNOWN"}
PAYMENT_STATUS_VALUES = {"CURRENT", "LATE_30", "LATE_60", "LATE_90_PLUS", "UNKNOWN"}

POSTURES = {"VERIFY", "DIRECT", "ESCALATE", "IDENTITY", "NONE"}

INCLUDE_MAPPING = {
    "HIGH_CONFIDENCE_ACCURACY": {
        "ui_label": "Ready to dispute now",
        "user_action": "Authorize sending",
        "letter_language_tier": "TIER_ACCURACY",
    },
    "INCONSISTENCY_VERIFICATION": {
        "ui_label": "Ready (verification approach)",
        "user_action": "Authorize sending",
        "letter_language_tier": "TIER_VERIFY",
    },
    "USER_CONFIRMED_FACT": {
        "ui_label": "Unlocked by your confirmation",
        "user_action": "Authorize sending",
        "letter_language_tier": "TIER_ACCURACY",
    },
    "POST_VERIFICATION_ESCALATION": {
        "ui_label": "Escalation ready (after prior attempt)",
        "user_action": "Authorize sending",
        "letter_language_tier": "TIER_ESCALATION",
    },
    "UNVERIFIABLE_RECORD_REQUEST": {
        "ui_label": "Requesting verification of record",
        "user_action": "Authorize sending",
        "letter_language_tier": "TIER_VERIFY",
    },
    "IDENTITY_CORRECTION_REQUEST": {
        "ui_label": "Identity correction ready",
        "user_action": "Authorize sending",
        "letter_language_tier": "TIER_IDENTITY",
    },
}

BLOCKER_MAPPING = {
    "NO_ACTIONABLE_BASIS": {
        "ui_label": "No action recommended right now",
        "user_action": "None \u2014 we'll monitor",
    },
    "NEEDS_USER_CONFIRMATION": {
        "ui_label": "Needs your confirmation",
        "user_action": "Confirm / Not mine / Skip in Review",
    },
    "IDENTITY_NOT_CONFIRMED": {
        "ui_label": "Identity confirmation required",
        "user_action": "Complete identity step",
    },
    "WAITING_FOR_RESPONSE": {
        "ui_label": "Waiting on a response window",
        "user_action": "No action \u2014 check back after deadline",
    },
    "POSITIONED_TIMING": {
        "ui_label": "Better handled next round",
        "user_action": "No action \u2014 staged with a reminder",
    },
    "LOW_CONFIDENCE_NO_VERIFY_PATH": {
        "ui_label": "Not strong enough to send safely",
        "user_action": "Provide more info or wait for stronger signal",
    },
    "MISSING_REQUIRED_FIELDS": {
        "ui_label": "Missing required details from the report",
        "user_action": "Upload a clearer report / different bureau file",
    },
    "CONFLICTING_DATA_REQUIRES_REVIEW": {
        "ui_label": "Conflicting information detected",
        "user_action": "Review the conflicting fields",
    },
    "DUPLICATE_OR_SUPERSEDED": {
        "ui_label": "Already covered elsewhere",
        "user_action": "No action \u2014 included in another letter/item",
    },
    "OUT_OF_SCOPE_V1": {
        "ui_label": "Not supported in this version",
        "user_action": "No action \u2014 tracked for future support",
    },
}

EVIDENCE_TIER_REQUIREMENTS = {
    "TIER_VERIFY": {"any_of": ["TIER_A", "TIER_C", "TIER_D"]},
    "TIER_ACCURACY": {"all_of": ["TIER_A", "TIER_B"]},
    "TIER_IDENTITY": {"all_of": ["TIER_B"]},
    "TIER_ESCALATION": {"any_of": ["TIER_C", "TIER_D"], "requires_prior_action": True},
}

FORBIDDEN_ASSERTIONS = [
    "This violates the FCRA",
    "You are required by law to delete",
    "This is fraudulent",
    "This account is illegal",
    "You failed to comply with",
]

NORMALIZED_KEYS = [
    "normalized_creditor_name",
    "normalized_account_identifier",
    "normalized_open_date",
    "normalized_status",
    "normalized_balance",
    "normalized_payment_status",
    "normalized_last_reported_date",
]
