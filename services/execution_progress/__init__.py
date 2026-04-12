"""
Execution outcome intake and block progression (Capability 6).
"""

from __future__ import annotations

from .engine import apply_outcome_submission, compute_execution_partition, create_initial_state
from .models import (
    PROGRESS_SCHEMA_VERSION,
    ExecutionProgressState,
    OutcomeRecord,
    OutcomeSource,
    OutcomeSubmission,
    ProgressionResult,
    mail_receipt_flag,
)

__all__ = [
    "PROGRESS_SCHEMA_VERSION",
    "ExecutionProgressState",
    "OutcomeRecord",
    "OutcomeSource",
    "OutcomeSubmission",
    "ProgressionResult",
    "apply_outcome_submission",
    "compute_execution_partition",
    "create_initial_state",
    "mail_receipt_flag",
]
